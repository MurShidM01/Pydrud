"""
Doctor — check the development environment for required tools.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from pydrud.utils.colors import fail, warn
from pydrud.utils import tui

_MIN_JAVA_VERSION = 17
_MIN_SDK_VERSION = 33


def run_doctor():
    """Run all environment checks and print a summary."""
    print(tui.render_command_header(
        "doctor",
        "Development environment",
        subtitle="Checking the tools required to build and run native Android apps",
        details=(("Python", sys.executable), ("Platform", sys.platform)),
    ))
    print(tui.render_section("Toolchain"))

    all_ok = True

    # 1. Python
    all_ok &= _check_python()
    # 2. Java / JDK
    all_ok &= _check_java()
    # 3. Android SDK
    all_ok &= _check_android_sdk()
    # 4. Android-native build pieces.
    all_ok &= _check_ndk()
    all_ok &= _check_cmake()
    # 5. Gradle / device bridge.
    all_ok &= _check_gradle()
    all_ok &= _check_adb()
    # 6. Python packages used to generate the project.
    all_ok &= _check_package("jinja2", "Jinja2")
    all_ok &= _check_package("click", "click")
    # 7. A generated project receives consistency checks as well. These catch
    # the manifest mismatch before a camera/file-picker call does at runtime.
    project = _find_project(os.getcwd())
    if project:
        print(tui.render_section("Project"))
        all_ok &= _check_chaquopy(project)
        all_ok &= _check_manifest_permissions(project)

    print(tui.render_summary(
        "Environment is ready" if all_ok else "Environment needs attention",
        (("Result", "all checks passed" if all_ok else "one or more checks failed"),),
        success=all_ok,
    ))
    if not all_ok:
        print(tui.render_next_steps((("pydrud doctor", "run again after fixing the failed tools"),)))


def _check_python() -> bool:
    v = sys.version_info
    ok_ = v.major >= 3 and v.minor >= 10
    label = f"{v.major}.{v.minor}.{v.micro}"
    _print_check("Python ≥ 3.10", label, ok_)
    return ok_


def _check_java() -> bool:
    java = shutil.which("java")
    if not java:
        print(fail("Java not found in PATH."))
        return False

    result = subprocess.run(["java", "-version"], capture_output=True, text=True)
    version_line = result.stderr.strip().split("\n")[0] if result.stderr else "?"

    ok_ = "17" in version_line or "17" in result.stderr
    _print_check("Java 17+", version_line, ok_)
    return ok_


def _check_android_sdk() -> bool:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    if not sdk or not os.path.isdir(sdk):
        # Try common paths per platform.
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
                os.path.expanduser("~/android-sdk"),
            ]
        else:
            candidates = [
                "/root/android-sdk",
                os.path.expanduser("~/Android/Sdk"),
                os.path.expanduser("~/android-sdk"),
            ]
        for p in candidates:
            if os.path.isdir(p):
                sdk = p
                break

    if not sdk or not os.path.isdir(sdk):
        print(fail("Android SDK not found. Set ANDROID_HOME."))
        return False

    platforms = os.path.join(sdk, "platforms")
    if not os.path.isdir(platforms):
        print(warn(f"Android SDK at {sdk} but no platforms directory."))
        return False

    versions = sorted(os.listdir(platforms))
    latest = versions[-1] if versions else "none"
    _print_check("Android SDK", f"{sdk} (API {latest})", True)
    return True


def _android_sdk_dir() -> str:
    """Return the configured SDK directory, or an empty string."""
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    if sdk and os.path.isdir(sdk):
        return sdk
    candidates = ([os.path.expanduser("~\\AppData\\Local\\Android\\Sdk"), "C:\\Android\\Sdk"]
                  if sys.platform == "win32" else
                  ([os.path.expanduser("~/Library/Android/sdk"), os.path.expanduser("~/Android/Sdk")]
                   if sys.platform == "darwin" else
                   ["/root/android-sdk", os.path.expanduser("~/Android/Sdk")]))
    return next((path for path in candidates if os.path.isdir(path)), "")


def _check_ndk() -> bool:
    sdk = _android_sdk_dir()
    roots = [] if not sdk else [os.path.join(sdk, "ndk"), os.path.join(sdk, "ndk-bundle")]
    versions = []
    for root in roots:
        if os.path.basename(root) == "ndk-bundle" and os.path.isdir(root):
            versions.append("ndk-bundle")
        elif os.path.isdir(root):
            versions.extend(sorted(name for name in os.listdir(root)
                                   if os.path.isdir(os.path.join(root, name))))
    ok_ = bool(versions)
    _print_check("Android NDK", ", ".join(versions[-2:]) if versions else "not found", ok_)
    return ok_


def _check_cmake() -> bool:
    cmake = shutil.which("cmake")
    if not cmake:
        _print_check("CMake", "not found", False)
        return False
    result = subprocess.run([cmake, "--version"], capture_output=True, text=True)
    version = (result.stdout or result.stderr).splitlines()[0] if result.returncode == 0 else "unavailable"
    _print_check("CMake", version, result.returncode == 0)
    return result.returncode == 0


def _find_project(start: str) -> str | None:
    current = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(current, "pydrud.yaml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _check_chaquopy(project_dir: str) -> bool:
    gradle = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(gradle, encoding="utf-8") as handle:
            configured = "com.chaquo.python" in handle.read()
    except OSError:
        configured = False
    _print_check("Chaquopy", "configured" if configured else "missing from Android Gradle", configured)
    return configured


def _check_manifest_permissions(project_dir: str) -> bool:
    """Compare the YAML source of truth with generated manifest declarations."""
    try:
        from pydrud.commands.project_config import load_project_config
        from pydrud.commands.release import (CAPABILITY_PERMISSIONS,
                                             resolve_capability, resolve_permission)
        config = load_project_config(project_dir)
        configured = config.get("permissions", [])
        if not isinstance(configured, list):
            configured = [item.strip() for item in str(configured).split(",") if item.strip()]
        expected = {resolve_permission(name) for name in configured}
        capabilities = config.get("capabilities", [])
        if not isinstance(capabilities, list):
            capabilities = [item.strip() for item in str(capabilities).split(",") if item.strip()]
        for capability in capabilities:
            expected.update(CAPABILITY_PERMISSIONS[resolve_capability(capability)])
        manifest = os.path.join(project_dir, "android", "app", "src", "main",
                                "AndroidManifest.xml")
        root = ET.parse(manifest).getroot()
        attr = "{http://schemas.android.com/apk/res/android}name"
        declared = {node.get(attr, "").rsplit(".", 1)[-1]
                    for node in root.findall("uses-permission")}
        missing = sorted(expected - declared)
        ok_ = not missing
        detail = "YAML and manifest agree" if ok_ else "missing: " + ", ".join(missing)
        _print_check("Manifest permissions", detail, ok_)
        return ok_
    except Exception as exc:
        _print_check("Manifest permissions", f"could not verify ({exc})", False)
        return False


def _check_gradle() -> bool:
    gradle = shutil.which("gradle")
    if gradle:
        # On Windows, gradle may be a .bat file — needs cmd.exe /c
        if sys.platform == "win32" and gradle.endswith((".bat", ".cmd")):
            cmd = ["cmd.exe", "/c", "gradle", "--version"]
        else:
            cmd = ["gradle", "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        first_line = result.stdout.strip().split("\n")[0] if result.stdout else "?"
        _print_check("Gradle", first_line, True)
        return True

    # Check for wrapper.
    cwd = os.getcwd()
    wrapper_name = "gradlew.bat" if sys.platform == "win32" else "gradlew"
    wrapper = os.path.join(cwd, "android", wrapper_name)
    if os.path.isfile(wrapper):
        _print_check("Gradle", "gradlew wrapper found", True)
        return True

    print(warn("Gradle not in PATH (expected if using wrapper)."))
    return True


def _check_adb() -> bool:
    adb = shutil.which("adb")
    if not adb:
        print(warn("adb not found in PATH."))
        return False

    result = subprocess.run(["adb", "--version"], capture_output=True, text=True)
    version = result.stdout.strip().split("\n")[0] if result.stdout else "?"
    _print_check("ADB", version, True)
    return True


def _check_package(module: str, label: str) -> bool:
    try:
        __import__(module)
        _print_check(f"Python: {label}", "installed", True)
        return True
    except ImportError:
        print(fail(f"Python package {label} not installed."))
        return False


def _print_check(name: str, detail: str, ok_: bool):
    """Print a single aligned check result line."""
    detail_str = f"{tui.C_MUTED}{detail}{tui.RESET}" if detail else ""
    message = f"{name:<20} {detail_str}".rstrip()
    print(tui.ok_badge(message) if ok_ else tui.error_badge(message))
