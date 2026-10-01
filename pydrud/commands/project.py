"""
Pydrud project scaffold — generates a complete Android + Python project tree.
"""

from __future__ import annotations
import os
import re
import shutil
import sys

from jinja2 import Environment, PackageLoader, select_autoescape

from pydrud.utils.colors import ok, fail, info, header


# Jinja2 environment — templates live under ``android/templates/``.
_env = Environment(
    loader=PackageLoader("pydrud", "android/templates"),
    autoescape=select_autoescape(["xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _write_template(template_name: str, dest: str, ctx: dict):
    """Render a Jinja2 template and write it to *dest*."""
    template = _env.get_template(template_name)
    content = template.render(**ctx)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)


def _bundle_pydrud_source(project_dir: str):
    """Copy the pydrud framework source into the generated project's ``src/``
    so Chaquopy can import it without pip or network access."""
    import shutil
    src_dir = os.path.join(project_dir, "src")
    pydrud_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "pydrud")
    pydrud_src = os.path.normpath(pydrud_src)
    dst = os.path.join(src_dir, "pydrud")
    if os.path.isdir(pydrud_src):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(
            pydrud_src,
            dst,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
        )
        print(info(f"  Bundled pydrud core ({sum(len(files) for _, _, files in os.walk(dst))} files)"))


def _copy_icon_resources(project_dir: str):
    """Copy launcher icons from pydrud's template res/ into the generated project."""
    import shutil
    # The res/ lives alongside the templates/ inside the installed package.
    src_res = os.path.join(os.path.dirname(__file__), "..", "android", "templates", "res")
    dst_res = os.path.join(project_dir, "android", "app", "src", "main", "res")
    src_res = os.path.normpath(src_res)
    if os.path.isdir(src_res):
        for item in os.listdir(src_res):
            src_item = os.path.join(src_res, item)
            dst_item = os.path.join(dst_res, item)
            if os.path.isdir(src_item):
                if os.path.isdir(dst_item):
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
            elif item.endswith(".png") or item.endswith(".xml"):
                _ensure_dir(os.path.dirname(dst_item))
                shutil.copy2(src_item, dst_item)


def _sanitize_package(org: str) -> str:
    """Ensure the package name is a valid Java package identifier."""
    parts = org.strip().lower().split(".")
    clean = []
    for p in parts:
        p = re.sub(r"[^a-z0-9_]", "", p)
        if p and p[0].isdigit():
            p = "_" + p
        if p:
            clean.append(p)
    return ".".join(clean) if clean else "com.example"


def _slugify(name: str) -> str:
    """Convert a project name to a valid Python module name."""
    s = name.strip().lower().replace("-", "_").replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "my_app"


def _detect_sdk() -> str:
    """Locate the Android SDK directory for local.properties."""
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    if sdk and os.path.isdir(sdk):
        return sdk
    if sys.platform == "win32":
        candidates = [
            os.path.expanduser("~\\AppData\\Local\\Android\\Sdk"),
            "C:\\Android\\Sdk",
            os.path.expanduser("~\\Android\\Sdk"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            os.path.expanduser("~/Library/Android/sdk"),
            os.path.expanduser("~/Android/Sdk"),
        ]
    else:
        candidates = [
            "/root/android-sdk",
            os.path.expanduser("~/Android/Sdk"),
            os.path.expanduser("~/android-sdk"),
        ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return ""


def _camel(name: str) -> str:
    """Convert ``my_app`` or ``my-app`` to ``MyApp``."""
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))


def _detect_ndk(sdk_dir: str) -> str:
    """Detect the latest installed NDK version from the SDK directory."""
    ndk_dir = os.path.join(sdk_dir, "ndk") if sdk_dir else ""
    if ndk_dir and os.path.isdir(ndk_dir):
        try:
            versions = sorted(os.listdir(ndk_dir))
            if versions:
                return versions[-1]
        except Exception:
            pass
    return "29.0.14206865"


def create_project(
    name: str,
    org: str = "com.example",
    min_sdk: int = 24,
    target_sdk: int = 35,
):
    """Scaffold a new Pydrud project in a subdirectory ``./<name>/``."""

    project_dir = os.path.join(os.getcwd(), _slugify(name))
    if os.path.exists(project_dir):
        print(fail(f"Directory '{project_dir}' already exists."))
        sys.exit(1)

    package = _sanitize_package(org)
    pydrud_app_name = _slugify(name)
    android_app_name = _camel(name)
    package_path = package.replace(".", "/")

    # Build the package path for the generated Java source.
    java_package_path = package_path  # e.g. "com/example/my_app"

    # Detect SDK for local.properties
    sdk_dir = _detect_sdk()
    # Detect Python executable for Chaquopy buildPython
    python_exe = (shutil.which("python") or shutil.which("python3") or sys.executable).replace("\\", "/")

    # Normalise paths — Windows users get backslashes, but Gradle Kotlin DSL
    # and .properties files treat ``\`` as an escape character.
    sdk_dir = sdk_dir.replace("\\", "/")

    # Detect NDK version for pydrud.yaml
    ndk_version = _detect_ndk(sdk_dir)

    ctx = {
        "project_name": name,
        "app_name": android_app_name,
        "pydrud_app_name": pydrud_app_name,
        "package": package,
        "package_path": java_package_path,
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "build_tools_version": "36.0.0",  # match what we have
        "compile_sdk": target_sdk,
        "gradle_version": "8.7",
        "chaquopy_version": "15.0.1",
        "python_version": "3.11",
        "sdk_dir": sdk_dir,
        "python_executable": python_exe,
        "ndk": ndk_version,
    }

    print(header(f"\n  Creating Pydrud project: {name}"))
    print(f"    Package:    {package}")
    print(f"    Directory:  {project_dir}\n")

    # ── 1.  Python source ────────────────────────────────────────────────
    _ensure_dir(f"{project_dir}/src/app")
    _write_template("python/main.py.j2", f"{project_dir}/src/app/main.py", ctx)
    _write_template("python/app.py.j2", f"{project_dir}/src/app/__init__.py", ctx)

    # ── 1b. Bundle pydrud source into the project so Chaquopy can import
    #        it at runtime without needing pip install or network access.
    _bundle_pydrud_source(project_dir)

    # ── 2.  Android / Gradle ─────────────────────────────────────────────
    _ensure_dir(f"{project_dir}/android/app/src/main/java/{java_package_path}")
    _write_template("android/MainActivity.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/{android_app_name}Activity.java", ctx)
    _write_template("android/BridgeService.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/BridgeService.java", ctx)
    _write_template("android/ViewFactory.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/ViewFactory.java", ctx)
    _write_template("android/EventDispatcher.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/EventDispatcher.java", ctx)
    _write_template("android/WidgetRegistry.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/WidgetRegistry.java", ctx)
    _write_template("android/ViewCreator.java.j2",
                    f"{project_dir}/android/app/src/main/java/{java_package_path}/ViewCreator.java", ctx)

    # AndroidManifest.xml
    _ensure_dir(f"{project_dir}/android/app/src/main")
    _write_template("android/AndroidManifest.xml.j2",
                    f"{project_dir}/android/app/src/main/AndroidManifest.xml", ctx)

    # Build files
    _write_template("android/build.gradle.kts.j2",
                    f"{project_dir}/android/build.gradle.kts", ctx)
    _write_template("android/app/build.gradle.kts.j2",
                    f"{project_dir}/android/app/build.gradle.kts", ctx)
    _write_template("android/settings.gradle.kts.j2",
                    f"{project_dir}/android/settings.gradle.kts", ctx)
    _write_template("android/gradle.properties.j2",
                    f"{project_dir}/android/gradle.properties", ctx)
    _write_template("android/local.properties.j2",
                    f"{project_dir}/android/local.properties", ctx)

    # Android resources (Material theme + launcher icons)
    _ensure_dir(f"{project_dir}/android/app/src/main/res/values")
    _write_template("android/themes.xml.j2",
                    f"{project_dir}/android/app/src/main/res/values/themes.xml", ctx)

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
    _write_template("python/setup.py.j2",
                    f"{project_dir}/setup.py", ctx)

    # ── 4.  Top-level config ──────────────────────────────────────────────
    _write_template("pydrud.yaml.j2", f"{project_dir}/pydrud.yaml", ctx)

    # Write .gitignore
    _write_template("dot.gitignore.j2", f"{project_dir}/.gitignore", ctx)

    # Write a small Python runner script at the top-level
    _write_template("python/run.py.j2", f"{project_dir}/run.py", ctx)

    print(ok(f"Project '{name}' created!"))
    print()
    print(f"  Next steps:")
    print(f"    $ cd {_slugify(name)}")
    print(f"    $ pydrud run")
    print()
