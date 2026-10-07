"""
``pydrud create`` — scaffold a new Pydrud project.

By default creates a pydash project (no Android toolchain needed).
Pass ``runtime="chaquopy"`` to generate a full standalone Android project
with embedded Python; alternatively create a pydash project and add the
Android platform later with ``pydrud init android``.
"""

from __future__ import annotations

import os
import sys

from pydrud.compatibility import COMPATIBILITY
from pydrud.runtime.runtime import Runtime
from pydrud.utils import tui
from pydrud.utils.colors import fail
from pydrud.commands.project.bundle import _bundle_pydrud_source, _copy_icon_resources
from pydrud.commands.project.paths import (
    _camel, _detect_ndk, _detect_sdk, _ensure_dir, _normalise_color,
    _sanitize_package, _slugify, _version, _write_template,
)
from pydrud.commands.project.python_runtime import _detect_build_python
from pydrud.commands.project.templates import _render_app_package, _render_native_layer


def create_project(
    name: str,
    org: str = "com.example",
    *,
    min_sdk: int = 24,
    target_sdk: int = COMPATIBILITY.target_sdk,
    runtime: str = "pydash",
    pip_packages=None,
    firebase: bool = False,
    permissions=None,
    accent: str | None = None,
):
    """Scaffold a new Pydrud project in a subdirectory ``./<name>/``.

    ``accent`` is the brand colour the whole design system is generated
    from — the Python palette, the generated ``themes.xml`` and the
    starter app all start from it.

    ``runtime`` controls whether an Android project is generated::

        pydash (default) — no Android directory; use ``pydrud dev`` for
            live preview in the Pydash client. Add ``android/`` later with
            ``pydrud init android`` (preview shell) or
            ``pydrud init android --standalone`` (offline APK).
        chaquopy — full standalone Android project with embedded CPython;
            use ``pydrud run`` / ``pydrud build`` to produce an APK.
    """
    # Validate early so a typo never silently falls through to chaquopy.
    try:
        chosen = Runtime(runtime).value
    except ValueError:
        valid = ", ".join(r.value for r in Runtime)
        print(fail(
            f"Unknown runtime {runtime!r}. Valid values are: {valid}."
        ))
        sys.exit(1)

    project_dir = os.path.join(os.getcwd(), _slugify(name))
    if os.path.exists(project_dir):
        print(fail(f"Directory '{project_dir}' already exists."))
        sys.exit(1)

    pydrud_app_name = _slugify(name)
    package = _sanitize_package(org, pydrud_app_name)
    android_app_name = _camel(name)
    package_path = package.replace(".", "/")
    java_package_path = package_path  # e.g. "com/example/my_app"

    is_chaquopy = chosen == "chaquopy"

    # Chaquopy-only setup: SDK, Python interpreter, NDK detection.
    if is_chaquopy:
        sdk_dir = _detect_sdk().replace("\\", "/")
        python_exe = _detect_build_python()
        ndk_version = _detect_ndk(sdk_dir)
    else:
        sdk_dir = python_exe = ndk_version = ""

    from pydrud.widgets.theme import Colors as _Colors

    seed_color = _normalise_color(accent) or _Colors.PRIMARY
    # The focused counter starter uses no Android service APIs, so it needs
    # no runtime capabilities or permissions out of the box. Apps can opt in
    # later with the capabilities/permissions commands when they need them.
    default_capabilities: list[str] = []
    starter_permissions: list[str] = []
    ctx = {
        "project_name": name,
        "app_name": android_app_name,
        "pydrud_version": _version(),
        "seed_color": seed_color,
        "pydrud_app_name": pydrud_app_name,
        "package": package,
        "package_path": java_package_path,
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "build_tools_version": "36.0.0",  # match what we have
        "compile_sdk": max(int(target_sdk), COMPATIBILITY.compile_sdk),
        "gradle_version": COMPATIBILITY.gradle_version,
        "chaquopy_version": COMPATIBILITY.chaquopy_version,
        "python_version": COMPATIBILITY.python_version,
        "pydrud_runtime_version": COMPATIBILITY.android_runtime_version,
        "protocol_version": COMPATIBILITY.protocol_version,
        "sdk_dir": sdk_dir,
        "python_executable": python_exe,
        "ndk": ndk_version,
        # v1.3: Chaquopy pip packages, Firebase and R8 are data-driven.
        "pip_packages": list(pip_packages or []),
        "firebase": bool(firebase) or os.path.isfile(
            os.path.join(project_dir, "google-services.json")),
        "shrink": "false",
        "version_code": 1,
        "version_name": "1.0.0",
        "permissions": list(permissions or []),
        "capabilities_list": default_capabilities,
        "capabilities": {
            "foreground_service": False,
            "boot_receiver": False,
            "wake_lock": False,
            "haptics": False,
            "notifications": False,
        },
        "capability_permissions": starter_permissions,
        # ABIs shipped in the APK. 32-bit arm is still common on budget
        # devices; x86_64 keeps the emulator working.
        "abi_filters_list": ["arm64-v8a", "armeabi-v7a", "x86_64"],
        "abi_filters": ", ".join(
            f'"{abi}"' for abi in ("arm64-v8a", "armeabi-v7a", "x86_64")),
        "scheme": pydrud_app_name.replace("_", ""),
        "app_links_host": "",
        "cleartext_traffic": True,
        "assets_dir": "assets",
        "runtime": chosen,
        # Direct ``--runtime chaquopy`` projects are always the standalone
        # target: the activity boots ``app.main.start_app()`` on device.
        "standalone": True,
        "python_entry": "app.main",
    }

    subtitle = (
        "Live preview via Pydash client (no Android toolchain required)"
        if not is_chaquopy
        else "Scaffolding a native Android application powered by Python"
    )
    print(tui.render_command_header(
        "create",
        f"Creating {name}",
        subtitle=subtitle,
        details=(("Package", package), ("Directory", project_dir),
                 ("Runtime", chosen)),
    ))

    # ── 1.  Python source ────────────────────────────────────────────────
    _render_app_package(project_dir, ctx)

    # ── 1b. Bundle pydrud source into the project so Chaquopy can import
    #        it at runtime without needing pip install or network access.
    if is_chaquopy:
        _bundle_pydrud_source(project_dir)

    # ── 2.  Android / Gradle ─────────────────────────────────────────────
    if is_chaquopy:
        _render_native_layer(project_dir, java_package_path, ctx)

        # AndroidManifest.xml
        _ensure_dir(f"{project_dir}/android/app/src/main")
        _write_template("android/AndroidManifest.xml.j2",
                        f"{project_dir}/android/app/src/main/AndroidManifest.xml", ctx)

        # Build files
        _write_template("android/build.gradle.kts.j2",
                        f"{project_dir}/android/build.gradle.kts", ctx)
        _write_template("android/app/build.gradle.kts.j2",
                        f"{project_dir}/android/app/build.gradle.kts", ctx)
        _write_template("android/proguard-rules.pro.j2",
                        f"{project_dir}/android/app/proguard-rules.pro", ctx)
        _write_template("android/settings.gradle.kts.j2",
                        f"{project_dir}/android/settings.gradle.kts", ctx)
        _write_template("android/gradle.properties.j2",
                        f"{project_dir}/android/gradle.properties", ctx)
        _write_template("android/local.properties.j2",
                        f"{project_dir}/android/local.properties", ctx)

        # Launcher icons — copy from the pydrud package res/ directory.
        _copy_icon_resources(project_dir)

        # Gradle wrapper
        _ensure_dir(f"{project_dir}/android/gradle/wrapper")
        _ensure_dir(f"{project_dir}/android/gradle")
        _write_template("android/gradlew.j2",
                        f"{project_dir}/android/gradlew", ctx)
        _write_template("android/gradlew.bat.j2",
                        f"{project_dir}/android/gradlew.bat", ctx)
        _write_template("android/gradle/wrapper/gradle-wrapper.properties.j2",
                        f"{project_dir}/android/gradle/wrapper/gradle-wrapper.properties", ctx)

        # Make gradlew executable
        gradlew_path = os.path.join(project_dir, "android", "gradlew")
        os.chmod(gradlew_path, 0o755)

    # ── 3.  Assets directory ──────────────────────────────────────────────
    _ensure_dir(f"{project_dir}/assets")
    # Create a placeholder
    with open(f"{project_dir}/assets/.gitkeep", "w", encoding="utf-8") as f:
        f.write("")
    _write_template("python/pydrud_config.py.j2",
                    f"{project_dir}/src/pydrud_config.py", ctx)

    # ── 3b. Python setup for Chaquopy ─────────────────────────────────────
    if is_chaquopy:
        _write_template("python/setup.py.j2",
                        f"{project_dir}/setup.py", ctx)

    # ── 4.  Top-level config ──────────────────────────────────────────────
    _write_template("pydrud.yaml.j2", f"{project_dir}/pydrud.yaml", ctx)
    _write_template("pydrud.toml.j2", f"{project_dir}/pydrud.toml", ctx)

    # Write .gitignore
    _write_template("dot.gitignore.j2", f"{project_dir}/.gitignore", ctx)

    # Write a small Python runner script at the top-level
    _write_template("python/run.py.j2", f"{project_dir}/run.py", ctx)

    # ── 5.  Docs and tests ────────────────────────────────────────────────
    _write_template("README.md.j2", f"{project_dir}/README.md", ctx)
    _ensure_dir(f"{project_dir}/tests")
    _write_template("python/project_tests/test_app.py.j2",
                    f"{project_dir}/tests/test_app.py", ctx)
    with open(f"{project_dir}/tests/__init__.py", "w", encoding="utf-8") as f:
        f.write("")

    next_steps = (
        (f"cd {_slugify(name)}", "enter the project"),
        ("pydrud dev", "start live preview in Pydash"),
    ) if not is_chaquopy else (
        (f"cd {_slugify(name)}", "enter the project"),
        ("pydrud run", "build, install and start Hot Reload"),
    )
    print(tui.render_summary(
        f"Project '{name}' created",
        (("Package", package),
         ("Files", "Python source" if not is_chaquopy else "Android + Python scaffold")),
    ))
    print(tui.render_next_steps(next_steps))
