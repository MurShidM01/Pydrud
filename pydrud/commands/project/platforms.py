"""
``pydrud init <platform>`` — add a native platform to an existing project.

A project created with ``pydrud create`` is pure Python (the Pydash live
preview needs no native toolchain). Platforms are added afterwards, inside
the project directory::

    cd my_app
    pydrud init android   # standalone APK with embedded Python

``android`` is the only platform in 2.1.2. It embeds CPython with Chaquopy
so the APK runs the app fully offline; ``pydrud dev`` remains the desktop
development loop. iOS, Linux, Windows, web and macOS are reserved names for
future platforms.
"""

from __future__ import annotations

import os

from pydrud.commands.project_config import load_project_config, set_scalar
from pydrud.runtime.runtime import Runtime, persist_runtime
from pydrud.utils import tui
from pydrud.utils.colors import fail, info
from pydrud.commands.project.bundle import (
    _bundle_pydrud_source, _copy_icon_resources,
)
from pydrud.commands.project.config import (
    ProjectConfigError, _toml_section, _validate_package,
)
from pydrud.commands.project.paths import (
    _camel, _detect_sdk, _ensure_dir, _slugify, _version, _write_template,
)
from pydrud.commands.project.python_runtime import _detect_build_python
from pydrud.commands.project.sync import (
    _discover_project, _remove_generated_java, _stamp_version,
    _sync_context, _sync_generated_metadata, _sync_toml_identity,
)
from pydrud.commands.project.templates import _render_managed_android


#: Platforms ``pydrud init`` can generate today.
SUPPORTED_PLATFORMS = ("android",)

#: Reserved for future releases; ``pydrud init`` names them explicitly.
FUTURE_PLATFORMS = ("ios", "linux", "windows", "window", "web", "macos")


def android_platform_present(project_dir: str) -> bool:
    """Whether *project_dir* already contains a generated Android target."""
    return os.path.isfile(os.path.join(
        project_dir, "android", "app", "build.gradle.kts"))


def android_is_standalone(project_dir: str) -> bool:
    """Whether the generated Android target carries a Pydrud runtime backend.

    Pydrud always generates a standalone target — either an embedded
    interpreter (Chaquopy) or, with the ``host``/``none`` backends, a native
    renderer driven by ``PythonRuntime``. A project created by an older
    release may still be a Chaquopy-free preview shell, so this reports the
    on-disk shape and lets ``pydrud init android`` / ``pydrud sync`` upgrade
    it in place. A missing Android target resolves to the legacy standalone
    default so existing APK projects keep their embedded runtime.
    """
    gradle = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(gradle, encoding="utf-8") as handle:
            if "com.chaquo.python" in handle.read():
                return True
    except OSError:
        return True
    # No Chaquopy plugin — a host/none target is still standalone as long as
    # it generated the runtime factory; a legacy preview shell has neither.
    return _has_runtime_factory(project_dir)


def _has_runtime_factory(project_dir: str) -> bool:
    """Whether the generated Java layer contains ``PydrudRuntimeFactory``."""
    java_root = os.path.join(
        project_dir, "android", "app", "src", "main", "java")
    for _root, _dirs, files in os.walk(java_root):
        if "PydrudRuntimeFactory.java" in files:
            return True
    return False


def android_python_entry(project_dir: str) -> str:
    """The Python module the standalone shell boots.

    Legacy projects created with ``--runtime chaquopy`` boot ``app.main``
    (their entry point defines ``start_app``). Platforms added later keep the
    user's ``app/main.py`` untouched and boot the managed
    ``app.android_main`` adapter instead.
    """
    if os.path.isfile(os.path.join(project_dir, "src", "app", "android_main.py")):
        return "app.android_main"
    return "app.main"


def init_platform(project_dir: str, platform: str,
                  backend: str = "chaquopy") -> bool:
    """Generate the native *platform* inside an existing Pydrud project.

    *backend* selects which ``PythonRuntime`` the generated Android target
    compiles in: ``chaquopy`` (embedded CPython, the default), ``host``
    (Python runs on the developer's machine) or ``none`` (renderer only).
    """
    project_dir = os.path.abspath(project_dir)
    platform = str(platform or "").strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        if platform in FUTURE_PLATFORMS:
            print(fail(
                f"Platform '{platform}' is planned but not available in "
                f"Pydrud {_version()} — only 'android' is supported."))
        else:
            print(fail(f"Unknown platform '{platform}'."))
            print(info("Supported: android. Planned: ios, linux, windows, "
                       "web, macos."))
        return False
    return _init_android(project_dir, backend=backend)


def _init_android(project_dir: str, backend: str = "chaquopy") -> bool:
    """Create (or upgrade) ``android/`` from the project's YAML/TOML identity."""
    if not os.path.isfile(os.path.join(project_dir, "pydrud.yaml")):
        print(fail("Not inside a Pydrud project."))
        print(info("Run this from a directory containing pydrud.yaml "
                   "(see 'pydrud create <name>')."))
        return False

    try:
        config = load_project_config(project_dir)
        package = _validate_package(
            str(config.get("package") or "").strip()
            or _toml_section(project_dir, "app").get("package", "")
            or _fallback_package(project_dir))
    except ProjectConfigError as exc:
        print(fail(f"Invalid pydrud.yaml: {exc}"))
        return False

    if android_platform_present(project_dir) and android_is_standalone(project_dir):
        print(tui.warn_badge(
            "Android platform already exists. "
            "Run 'pydrud sync' to refresh it from pydrud.yaml."))
        return True
    if android_platform_present(project_dir):
        print(info("Upgrading the Android target to the standalone "
                   "(embedded Python) shape."))

    display_name = (str(config.get("app_name") or "").strip()
                    or _toml_section(project_dir, "app").get("name", "")
                    or os.path.basename(project_dir))
    found = _discover_project(project_dir) or {
        "package": package,
        "package_path": package.replace(".", "/"),
        "app_name": _camel(display_name or "MyApp"),
        "firebase": False,
    }
    try:
        ctx = _sync_context(project_dir, found)
    except (ProjectConfigError, ValueError) as exc:
        print(fail(f"Invalid pydrud.yaml: {exc}"))
        return False
    ctx["standalone"] = True
    # The backend id drives which PythonRuntime the Gradle/Java layer compiles
    # in; chaquopy embeds CPython, host/none do not.
    ctx["runtime_backend"] = backend
    ctx["python_entry"] = "app.android_main"
    if backend == "chaquopy":
        # A fresh embedded target has no Gradle history to preserve, so probe
        # the build interpreter now. Host/none targets embed no interpreter.
        ctx["python_executable"] = _detect_build_python(
            ctx.get("python_version") or "3.11")

    _BACKEND_LABELS = {
        "chaquopy": "Standalone APK shell with embedded Python (Chaquopy)",
        "host": "Native APK shell — Python runs on your machine (host)",
        "none": "Native APK shell with no embedded runtime (renderer only)",
    }
    print(tui.render_command_header(
        "init android",
        f"Adding Android to {ctx['project_name']}",
        subtitle=_BACKEND_LABELS.get(backend, _BACKEND_LABELS["chaquopy"]),
        details=(("Package", ctx["package"]),
                 ("Mode", "standalone"),
                 ("Backend", backend),
                 ("Pydrud", _version())),
    ))

    discovered = _discover_project(project_dir)
    if discovered:
        _remove_generated_java(project_dir, discovered)
    _ensure_dir(os.path.join(project_dir, "android"))
    _render_managed_android(project_dir, ctx)

    # local.properties is written once and never synced, so a hand-fixed SDK
    # path survives every later command.
    local_properties = os.path.join(project_dir, "android", "local.properties")
    if not os.path.isfile(local_properties):
        sdk_dir = _detect_sdk().replace("\\", "/")
        _write_template("android/local.properties.j2", local_properties,
                        {**ctx, "sdk_dir": sdk_dir})
    _copy_icon_resources(project_dir, overwrite=False)

    _sync_generated_metadata(project_dir, ctx)
    jobs_path = os.path.join(project_dir, "src", "app", "jobs.py")
    if not os.path.isfile(jobs_path):
        _write_template("python/app/jobs.py.j2", jobs_path, ctx)
    _write_template(
        "python/app/android_main.py.j2",
        os.path.join(project_dir, "src", "app", "android_main.py"), ctx)
    if backend == "chaquopy":
        # Only an embedded interpreter imports the framework on device; a
        # host/none build ships no Python source at all.
        _bundle_pydrud_source(project_dir)
    _sync_toml_identity(project_dir, ctx)
    persist_runtime(project_dir, Runtime(backend))
    # Record the camera choice so `camera:` is discoverable in pydrud.yaml
    # instead of being an undocumented default.
    set_scalar(project_dir, "camera", bool(ctx.get("camera", False)))
    _stamp_version(project_dir)

    runtime_summary = {
        "chaquopy": "embedded (Chaquopy)",
        "host": "host (Python on your machine)",
        "none": "none (renderer only)",
    }.get(backend, "embedded (Chaquopy)")
    print(tui.render_summary(
        "Standalone Android platform added",
        (("Runtime", runtime_summary),
         ("Package", ctx["package"])),
    ))
    print(tui.render_next_steps(
        (("pydrud run", "build, install and hot-reload"),
         ("pydrud build --release", "signed release APK"))))
    return True


def _fallback_package(project_dir: str) -> str:
    """Last-resort package when YAML and TOML carry no identity."""
    from pydrud.commands.project.paths import _sanitize_package

    return _sanitize_package("com.example", _slugify(
        os.path.basename(os.path.abspath(project_dir))))
