"""
Doctor — check the development environment for required tools.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys

from pydrud.utils.colors import ok, fail, warn, info, header

_MIN_JAVA_VERSION = 17
_MIN_SDK_VERSION = 33


def run_doctor():
    """Run all environment checks and print a summary."""
    print(header("\n  Pydrud Doctor — Environment Check\n"))

    all_ok = True

    # 1. Python
    all_ok &= _check_python()
    # 2. Java / JDK
    all_ok &= _check_java()
    # 3. Android SDK
    all_ok &= _check_android_sdk()
    # 4. Gradle
    all_ok &= _check_gradle()
    # 5. ADB
    all_ok &= _check_adb()
    # 6. Jinja2
    all_ok &= _check_package("jinja2", "Jinja2")
    # 7. Click
    all_ok &= _check_package("click", "click")

    print()
    if all_ok:
        print(ok("All checks passed. Environment is ready."))
    else:
        print(fail("Some checks failed. See messages above."))

    print()


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
    """Print a single check result line."""
    icon = ok("") if ok_ else fail("")
    detail_str = f" — {detail}" if detail else ""
    print(f"  {icon} {name}{detail_str}")
