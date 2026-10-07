"""
``pydrud sync`` — apply ``pydrud.yaml`` to an existing generated project.
"""

from __future__ import annotations

import os
import re
import sys

from pydrud.compatibility import COMPATIBILITY, HOST_COMPATIBILITY
from pydrud.commands.project_config import load_project_config, set_scalar
from pydrud.runtime.runtime import Runtime, persist_runtime, resolve_runtime
from pydrud.utils import tui
from pydrud.utils.colors import fail, info
from pydrud.commands.project.bundle import _bundle_pydrud_source, _copy_icon_resources
from pydrud.commands.project.config import (
    ProjectConfigError, _config_bool, _config_int, _config_list, _config_string,
    _gradle_value, _manifest_permissions, _project_seed, _toml_section,
    _validate_package,
)
from pydrud.commands.project.paths import (
    _camel, _JAVA_TEMPLATES, _normalise_color, _slugify, _version, _write_template,
)
from pydrud.commands.project.templates import _render_managed_android


def _camera_already_bundled(project_dir: str) -> bool:
    """Whether an existing generated Android project already ships CameraX.

    Every project generated before the camera stack became opt-in bundled it
    unconditionally. Syncing such a project with a newer Pydrud must not
    silently break its ``CameraPreview`` widgets and ``page.camera`` calls,
    so "already there" is the default for them. New projects have no
    ``build.gradle.kts`` yet (or one without CameraX) and start lean.
    """
    gradle = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(gradle, encoding="utf-8") as handle:
            return "androidx.camera" in handle.read()
    except OSError:
        return False


def _sync_context(project_dir: str, found: dict) -> dict:
    """Resolve the complete Android template context from ``pydrud.yaml``."""
    config = load_project_config(project_dir)
    legacy_app = _toml_section(project_dir, "app")

    display_name = (_config_string(config, "app_name")
                    or legacy_app.get("name")
                    or os.path.basename(os.path.abspath(project_dir)))
    if not display_name:
        raise ProjectConfigError("'app_name' cannot be empty")
    package = _validate_package(
        _config_string(config, "package")
        or legacy_app.get("package")
        or found["package"])

    min_sdk = _config_int(config, "min_sdk", COMPATIBILITY.min_sdk, minimum=1)
    target_sdk = _config_int(config, "target_sdk", COMPATIBILITY.target_sdk,
                             minimum=1)
    compile_sdk = _config_int(
        config, "compile_sdk", max(target_sdk, COMPATIBILITY.compile_sdk),
        minimum=1)
    if min_sdk > target_sdk:
        raise ProjectConfigError("'min_sdk' cannot be greater than 'target_sdk'")
    if compile_sdk < target_sdk:
        raise ProjectConfigError("'compile_sdk' cannot be lower than 'target_sdk'")

    version_code_default = int(_gradle_value(
        project_dir, r"versionCode\s*=\s*(\d+)", "1"))
    version_name_default = _gradle_value(
        project_dir, r'versionName\s*=\s*"([^"]+)"', "1.0.0")
    version_code = _config_int(
        config, "version_code", version_code_default, minimum=1)
    version_name = _config_string(
        config, "version_name", version_name_default) or version_name_default

    pydrud_app_name = _slugify(display_name)
    android_app_name = _camel(display_name)
    scheme = (_config_string(config, "scheme")
              or legacy_app.get("scheme")
              or pydrud_app_name.replace("_", ""))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", scheme):
        raise ProjectConfigError(
            f"'scheme' must be a valid Android URI scheme, got {scheme!r}")

    permissions = _config_list(
        config, "permissions",
        _manifest_permissions(project_dir) if "permissions" not in config else ())
    from pydrud.commands.release import resolve_permission
    permissions = list(dict.fromkeys(
        resolved for name in permissions
        if (resolved := resolve_permission(name))
        not in {"INTERNET", "ACCESS_NETWORK_STATE"}
    ))

    from pydrud.commands.release import (
        CAPABILITY_PERMISSIONS, KNOWN_CAPABILITIES, resolve_capability,
    )
    try:
        capability_names = {resolve_capability(name)
                            for name in _config_list(config, "capabilities")}
    except ValueError as exc:
        raise ProjectConfigError(str(exc)) from exc
    known_capabilities = set(KNOWN_CAPABILITIES)
    generated_permissions = set().union(*(
        CAPABILITY_PERMISSIONS[name] for name in capability_names
    )) if capability_names else set()
    permissions = [name for name in permissions if name not in generated_permissions]

    # Camera stack (CameraX + ML Kit barcode scanning) is opt-in. Those
    # libraries ship ~10 MB of native code that every APK would otherwise
    # carry — and that the NDK stripper then complains about — so they are
    # only bundled when the project actually asks for a camera: either
    # explicitly with `camera: true`, or implicitly by declaring the CAMERA
    # permission (`pydrud permissions add camera`). Projects generated
    # before this knob existed already ship CameraX, and an upgrade must
    # not silently take CameraPreview away from them — hence the fallback.
    camera_permission = "CAMERA" in (
        set(permissions) | set(generated_permissions))
    camera = (_config_bool(config, "camera", _camera_already_bundled(project_dir))
              or camera_permission)
    # True when the stack is bundled for a reason the YAML does not state:
    # an older project inherited it, so nobody knows it can be dropped.
    camera_inherited = camera and "camera" not in config and not camera_permission

    abi_filters_list = _config_list(
        config, "abi_filters", ("arm64-v8a", "armeabi-v7a", "x86_64"))
    if not abi_filters_list:
        raise ProjectConfigError("'abi_filters' must contain at least one ABI")

    assets_dir = _config_string(config, "assets_dir", "assets") or "assets"
    assets_dir = assets_dir.replace("\\", "/").strip("/")
    if not assets_dir or any(part == ".." for part in assets_dir.split("/")):
        raise ProjectConfigError("'assets_dir' must stay inside the project")

    python_version = _config_string(
        config, "python_version", HOST_COMPATIBILITY.python_version)
    old_python = _gradle_value(
        project_dir,
        r'buildPython\(System\.getenv\("PYDRUD_PYTHON"\)\s*\?:\s*"([^"]+)"\)',
        sys.executable.replace("\\", "/"))
    seed = _normalise_color(_project_seed(project_dir))

    from pydrud.commands.packages import Requirements

    return {
        "project_name": display_name,
        "app_name": android_app_name,
        "pydrud_app_name": pydrud_app_name,
        "package": package,
        "package_path": package.replace(".", "/"),
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "compile_sdk": compile_sdk,
        "ndk": _config_string(config, "ndk", COMPATIBILITY.ndk_version),
        "python_version": python_version,
        "python_executable": old_python,
        "pydrud_runtime_version": _config_string(
            config, "framework_version", HOST_COMPATIBILITY.framework_version),
        "protocol_version": _config_int(
            config, "protocol_version", HOST_COMPATIBILITY.protocol_version,
            minimum=1),
        "chaquopy_version": _config_string(
            config, "chaquopy_version", COMPATIBILITY.chaquopy_version),
        "agp_version": _config_string(
            config, "agp_version", COMPATIBILITY.agp_version),
        "gradle_version": _config_string(
            config, "gradle_version", COMPATIBILITY.gradle_version),
        "assets_dir": assets_dir,
        "version_code": version_code,
        "version_name": version_name,
        "scheme": scheme,
        "app_links_host": _config_string(config, "app_links_host"),
        "cleartext_traffic": _config_bool(config, "cleartext_traffic", True),
        "abi_filters_list": abi_filters_list,
        "abi_filters": ", ".join(f'"{abi}"' for abi in abi_filters_list),
        "permissions": permissions,
        "capabilities_list": sorted(capability_names),
        "capabilities": {name: name in capability_names
                         for name in known_capabilities},
        "capability_permissions": sorted(generated_permissions),
        "firebase": _config_bool(
            config, "firebase", found.get("firebase", False)
            or os.path.isfile(os.path.join(project_dir, "google-services.json"))),
        "camera": camera,
        "camera_inherited": camera_inherited,
        "shrink": "true" if _config_bool(config, "shrink", False) else "false",
        "pip_packages": Requirements(project_dir).requirement_strings(),
        "seed_color": seed,
    }


# ── Upgrading an existing project ────────────────────────────────────────────
def _remove_generated_java(project_dir: str, found: dict) -> None:
    """Remove stale generated classes before a package/name migration.

    Only files owned by Pydrud are removed. Any hand-written Java class in the
    old package is retained, and now-empty package directories are pruned.
    """
    java_root = os.path.join(project_dir, "android", "app", "src", "main", "java")
    old_dir = os.path.join(java_root, *found["package_path"].split("/"))
    generated = {f"{name}.java" for name in _JAVA_TEMPLATES}
    generated.update({"PydrudMessagingService.java",
                      f"{found['app_name']}Activity.java"})
    for filename in generated:
        try:
            os.remove(os.path.join(old_dir, filename))
        except FileNotFoundError:
            pass
    current = old_dir
    while os.path.normpath(current) != os.path.normpath(java_root):
        try:
            os.rmdir(current)
        except OSError:
            break
        current = os.path.dirname(current)


def _sync_generated_metadata(project_dir: str, ctx: dict) -> None:
    """Refresh generated non-app metadata without touching ``src/app``.

    ``setup.py`` only exists for the standalone target (Chaquopy's pip
    install step); preview shells run Python on the host and never need it.
    """
    _write_template("python/pydrud_config.py.j2",
                    os.path.join(project_dir, "src", "pydrud_config.py"),
                    {**ctx, "runtime": "chaquopy"})
    if ctx.get("standalone", True):
        _write_template("python/setup.py.j2",
                        os.path.join(project_dir, "setup.py"), ctx)


def _sync_toml_identity(project_dir: str, ctx: dict) -> None:
    """Keep the legacy TOML identity mirror aligned with YAML.

    Dependencies, theme settings, comments and unknown TOML sections are
    preserved verbatim.
    """
    path = os.path.join(project_dir, "pydrud.toml")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return

    replacements = {
        "name": ctx["project_name"],
        "package": ctx["package"],
        "scheme": ctx["scheme"],
    }

    def assignment(key: str) -> str:
        escaped = replacements[key].replace("\\", "\\\\").replace('"', '\\"')
        return f'{key} = "{escaped}"'

    in_app = False
    app_found = False
    seen: set[str] = set()
    app_end: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_app:
                app_end = index
            in_app = stripped == "[app]"
            app_found = app_found or in_app
            continue
        if not in_app or "=" not in stripped or stripped.startswith("#"):
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in replacements:
            lines[index] = assignment(key)
            seen.add(key)
    if in_app:
        app_end = len(lines)

    if app_found and app_end is not None:
        missing = [key for key in ("name", "package", "scheme") if key not in seen]
        lines[app_end:app_end] = [assignment(key) for key in missing]
    elif not app_found:
        block = ["[app]"] + [assignment(key)
                             for key in ("name", "package", "scheme")]
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _discover_project(project_dir: str) -> dict | None:
    """Locate the currently generated package and activity.

    This identifies stale files which may need migrating; desired values are
    resolved separately from ``pydrud.yaml``.
    """
    java_root = os.path.join(project_dir, "android", "app", "src", "main", "java")
    if not os.path.isdir(java_root):
        return None

    for root, _dirs, files in os.walk(java_root):
        if "BridgeService.java" not in files:
            continue
        package_path = os.path.relpath(root, java_root).replace(os.sep, "/")
        activity = next((f for f in files if f.endswith("Activity.java")), None)
        app_name = activity[: -len("Activity.java")] if activity else _camel(
            os.path.basename(package_path))
        return {
            "package": package_path.replace("/", "."),
            "package_path": package_path,
            "app_name": app_name,
            "firebase": "PydrudMessagingService.java" in files,
        }
    return None


def sync_project(project_dir: str, *, update_runtime: bool = True) -> bool:
    """Apply ``pydrud.yaml`` to the complete generated Android project.

    Package, app name, SDK/toolchain versions, release metadata, assets,
    permissions and deep-link settings all flow from the system-level YAML
    manifest. The generated Java package is migrated when identity changes.
    Hand-written code under ``src/app/`` is never overwritten (the managed
    standalone adapter ``android_main.py`` is refreshed, and ``jobs.py`` is
    only seeded when missing).

    Pydash projects have no Android layer, so this command is an informational
    no-op for them. ``sync`` refreshes an already-generated Android project;
    to create that target inside an existing project, run
    ``pydrud init android`` (preview shell) or
    ``pydrud init android --standalone`` (offline APK with embedded Python).
    """
    # Local import: platforms.py builds on these sync helpers.
    from pydrud.commands.project.platforms import (
        android_is_standalone, android_python_entry,
    )

    # Resolve runtime first so we can short-circuit for pydash projects.
    descriptor = resolve_runtime(project_dir)
    if descriptor.runtime is Runtime.PYDASH:
        persist_runtime(project_dir, Runtime.PYDASH)
        print(tui.warn_badge(
            "This project runs in pydash mode — no Android project exists. "
            "Run 'pydrud dev' to start a live preview, or add the Android "
            "platform with 'pydrud init android'."
        ))
        return True

    found = _discover_project(project_dir)
    if not found:
        print(fail("No generated Android sources found — is this a Pydrud project?"))
        if not os.path.isdir(os.path.join(project_dir, "android")):
            print(info("Run 'pydrud init android' to generate the Android "
                       "platform for this project."))
        return False

    try:
        ctx = _sync_context(project_dir, found)
    except (ProjectConfigError, ValueError) as exc:
        print(fail(f"Invalid pydrud.yaml: {exc}"))
        return False
    standalone = android_is_standalone(project_dir)
    ctx["standalone"] = standalone
    entry = android_python_entry(project_dir)
    if (standalone and entry == "app.main"
            and not _main_defines_start_app(project_dir)):
        # A pydash entry point has no start_app for the device to call
        # (e.g. a preview shell flipped to standalone via YAML): the
        # managed adapter below boots it without touching user code.
        entry = "app.android_main"
    ctx["python_entry"] = entry

    print(tui.render_command_header(
        "sync",
        f"Syncing {ctx['project_name']}",
        subtitle="Applying pydrud.yaml to the generated Android project",
        details=(("Package", ctx["package"]), ("Pydrud", _version()),
                 ("Runtime", ctx["pydrud_runtime_version"]),
                 ("Mode", "standalone" if standalone else "preview")),
    ))

    identity_changed = (found["package"] != ctx["package"]
                        or found["app_name"] != ctx["app_name"])
    _remove_generated_java(project_dir, found)
    _render_managed_android(project_dir, ctx)
    _sync_generated_metadata(project_dir, ctx)
    _sync_toml_identity(project_dir, ctx)
    if standalone:
        # Managed standalone entry point (init-android projects only) and
        # the background-jobs adapter, created when missing. Hand-written
        # app code is never overwritten: jobs.py is only seeded, while
        # android_main.py is regenerated because it is a managed file.
        if ctx["python_entry"] == "app.android_main":
            _write_template(
                "python/app/android_main.py.j2",
                os.path.join(project_dir, "src", "app", "android_main.py"),
                ctx)
        jobs_path = os.path.join(project_dir, "src", "app", "jobs.py")
        if not os.path.isfile(jobs_path):
            _write_template("python/app/jobs.py.j2", jobs_path, ctx)
    # Fill in any launcher icon files the project is missing (never
    # overwriting icons the user generated or replaced themselves).
    _copy_icon_resources(project_dir, overwrite=False)

    count = len(_JAVA_TEMPLATES) + 1 + (1 if ctx["firebase"] else 0)
    detail = "all Android configuration"
    if identity_changed:
        detail += " + package migration"
    print(info(f"Rewrote {count} Java classes + {detail}"))

    if update_runtime and standalone:
        _bundle_pydrud_source(project_dir)

    # Persist the resolved camera choice: the YAML always shows why the
    # (heavy) CameraX + ML Kit stack is — or is not — in the APK.
    set_scalar(project_dir, "camera", bool(ctx.get("camera", False)))
    if ctx.get("camera_inherited"):
        print(info("Camera stack inherited from an older project — set "
                   "'camera: false' in pydrud.yaml and re-sync to drop "
                   "~10 MB of CameraX/ML Kit from the APK."))

    persist_runtime(project_dir, descriptor.runtime)
    _stamp_version(project_dir)
    print(tui.render_summary(
        "Project synchronized",
        (("Java classes", count), ("Package", ctx["package"]),
         ("Runtime", "updated" if update_runtime else "kept"),
         ("Camera", "bundled" if ctx.get("camera") else "not bundled")),
    ))
    print(tui.render_next_steps((("pydrud run", "rebuild and launch"),)))
    return True


def _main_defines_start_app(project_dir: str) -> bool:
    """Whether ``src/app/main.py`` defines the device entry point."""
    try:
        with open(os.path.join(project_dir, "src", "app", "main.py"),
                  encoding="utf-8") as handle:
            return "def start_app" in handle.read()
    except OSError:
        return False


def _stamp_version(project_dir: str) -> None:
    """Record which Pydrud generated the native layer, in ``pydrud.yaml``.

    ``pydrud run`` compares this with the installed version and tells the
    user to ``pydrud sync`` when they drift apart — the generated Java and
    the Python runtime are two halves of one protocol.
    """
    path = os.path.join(project_dir, "pydrud.yaml")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return
    stamp = f'pydrud_version: "{_version()}"'
    for index, line in enumerate(lines):
        if line.strip().startswith("pydrud_version:"):
            lines[index] = stamp
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, stamp)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass
