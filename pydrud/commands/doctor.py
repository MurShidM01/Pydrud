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
    """Check host requirements and the Android toolchain when selected.

    Projects default to Pydash, whose host preview path needs no Android
    tools. A generated Android project with no explicit runtime is resolved
    as legacy Chaquopy by :func:`resolve_runtime` and keeps the full checks.
    """
    from pydrud.runtime.runtime import Runtime, resolve_runtime

    project = _find_project(os.getcwd())
    runtime = (resolve_runtime(project).runtime if project else Runtime.PYDASH)
    android_target = runtime is Runtime.CHAQUOPY
    standalone = True
    if android_target and project:
        from pydrud.commands.project import android_is_standalone
        standalone = android_is_standalone(project)
    tui.safe_print(tui.render_command_header(
        "doctor",
        "Development environment",
        subtitle=(
            "Checking host and Android build tools" if android_target
            else "Checking host requirements for the Pydash workflow"
        ),
        details=(("Python", sys.executable), ("Platform", sys.platform),
                 ("Runtime", runtime.value),
                 ("Android", "standalone" if standalone else "preview")
                 if android_target else ("Android", "—")),
    ))
    tui.safe_print(tui.render_section("Host"))

    all_ok = True
    all_ok &= _check_python()
    all_ok &= _check_package("jinja2", "Jinja2")
    all_ok &= _check_package("click", "click")

    if android_target:
        tui.safe_print(tui.render_section("Android toolchain"))
        all_ok &= _check_java()
        all_ok &= _check_android_sdk()
        if standalone:
            all_ok &= _check_ndk()
            all_ok &= _check_cmake()
        else:
            # Preview shells compile no native code and embed no
            # interpreter: NDK and CMake are genuinely not needed.
            _skip_check("Android NDK", "not required for preview shells")
            _skip_check("CMake", "not required for preview shells")
        all_ok &= _check_gradle()
        all_ok &= _check_adb()
    else:
        tui.safe_print(tui.ok_badge(
            "Android toolchain not required for the Pydash runtime"))

    if project:
        tui.safe_print(tui.render_section("Project"))
        if android_target:
            # These checks apply only to a generated Android project.
            if standalone:
                all_ok &= _check_chaquopy(project)
            else:
                all_ok &= _check_preview_shell(project)
            all_ok &= _check_manifest_permissions(project)
        all_ok &= _check_project_shadowing(project)

    tui.safe_print(tui.render_summary(
        "Environment is ready" if all_ok else "Environment needs attention",
        (("Result", "all checks passed" if all_ok else "one or more checks failed"),),
        success=all_ok,
    ))
    if not all_ok:
        tui.safe_print(tui.render_next_steps((("pydrud doctor", "run again after fixing the failed tools"),)))
    return all_ok


def _check_python() -> bool:
    v = sys.version_info
    ok_ = v.major >= 3 and v.minor >= 10
    label = f"{v.major}.{v.minor}.{v.micro}"
    _print_check("Python ≥ 3.10", label, ok_)
    return ok_


def _check_java() -> bool:
    java = shutil.which("java")
    if not java:
        tui.safe_print(fail("Java not found in PATH."))
        return False

    try:
        result = subprocess.run([java, "-version"], capture_output=True, text=True)
    except OSError as exc:
        _print_check("Java 17+", f"could not run ({exc})", False)
        return False
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
                os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk"),
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
        tui.safe_print(fail("Android SDK not found. Set ANDROID_HOME."))
        return False

    platforms = os.path.join(sdk, "platforms")
    if not os.path.isdir(platforms):
        tui.safe_print(warn(f"Android SDK at {sdk} but no platforms directory."))
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
    candidates = ([os.path.expanduser("~\\AppData\\Local\\Android\\Sdk"), os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk")]
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
    """Check PATH and CMake distributions shipped with the Android SDK.

    Android Studio installs CMake below ``$ANDROID_SDK_ROOT/cmake`` and a
    standalone CMake executable is not required for a normal Android build.
    The old PATH-only check therefore reported a false failure on otherwise
    healthy machines.
    """
    candidates: list[str] = []
    on_path = shutil.which("cmake")
    if on_path:
        candidates.append(on_path)

    sdk = _android_sdk_dir()
    if sdk:
        binary_name = "cmake.exe" if sys.platform == "win32" else "cmake"
        cmake_root = os.path.join(sdk, "cmake")
        if os.path.isdir(cmake_root):
            for version in sorted(os.listdir(cmake_root), reverse=True):
                binary = os.path.join(cmake_root, version, "bin", binary_name)
                if os.path.isfile(binary):
                    candidates.append(binary)

        # Some SDK/NDK distributions carry CMake alongside the LLVM
        # toolchain rather than in the SDK-level cmake directory.
        for ndk_root in (os.path.join(sdk, "ndk"),
                         os.path.join(sdk, "ndk-bundle")):
            if not os.path.isdir(ndk_root):
                continue
            if os.path.basename(ndk_root) == "ndk-bundle":
                ndk_versions = [ndk_root]
            else:
                ndk_versions = [
                    os.path.join(ndk_root, name)
                    for name in os.listdir(ndk_root)
                    if os.path.isdir(os.path.join(ndk_root, name))
                ]
            for root in sorted(ndk_versions, reverse=True):
                prebuilt = os.path.join(root, "toolchains", "llvm", "prebuilt")
                if not os.path.isdir(prebuilt):
                    continue
                for host in sorted(os.listdir(prebuilt), reverse=True):
                    binary = os.path.join(prebuilt, host, "bin", binary_name)
                    if os.path.isfile(binary):
                        candidates.append(binary)

    # Preserve order while avoiding duplicate PATH/SDK entries.
    for cmake in dict.fromkeys(candidates):
        try:
            result = subprocess.run([cmake, "--version"], capture_output=True,
                                    text=True)
        except OSError:
            continue
        output = result.stdout or result.stderr or ""
        version = output.splitlines()[0] if output else "unavailable"
        if result.returncode == 0:
            source = "" if on_path and cmake == on_path else " (Android SDK)"
            _print_check("CMake", version + source, True)
            return True

    _print_check("CMake", "not found (checked PATH and Android SDK)", False)
    return False


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


def _check_preview_shell(project_dir: str) -> bool:
    """Verify a Chaquopy-free preview shell is complete and consistent."""
    java_root = os.path.join(project_dir, "android", "app", "src", "main",
                             "java")
    client_found = False
    if os.path.isdir(java_root):
        for _root, _dirs, files in os.walk(java_root):
            if "PreviewClient.java" in files:
                client_found = True
                break
    gradle = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(gradle, encoding="utf-8") as handle:
            chaquopy_free = "com.chaquo.python" not in handle.read()
    except OSError:
        chaquopy_free = False
    ok_ = client_found and chaquopy_free
    detail = ("preview client ready" if ok_ else
              "run 'pydrud sync' to regenerate the preview shell")
    _print_check("Preview shell", detail, ok_)
    return ok_


def _skip_check(name: str, detail: str) -> bool:
    """Report a check that does not apply, without failing the run."""
    tui.safe_print(tui.neutral_badge(f"{name:<20} {detail}"))
    return True


def _check_project_shadowing(project_dir: str) -> bool:
    """Ensure no directory packages shadow .py modules in src/."""
    src_dir = os.path.join(project_dir, "src")
    if not os.path.isdir(src_dir):
        return True
    shadowed = []
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        py_stems = {f[:-3] for f in files if f.endswith(".py") and f != "__init__.py"}
        for d in dirs:
            if d in py_stems:
                rel = os.path.relpath(os.path.join(root, d), project_dir)
                shadowed.append(rel)
    ok_ = not shadowed
    detail = "no package shadowing" if ok_ else f"shadowing detected in: {', '.join(shadowed)}"
    _print_check("Import integrity", detail, ok_)
    return ok_


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
    """Prefer a project Gradle wrapper, then fall back to global Gradle.

    A wrapper is the source of truth for a generated project; a missing
    standalone ``gradle`` executable is not a doctor failure. All process
    launches are guarded because ``shutil.which`` can become stale between
    the lookup and ``CreateProcess`` on Windows.
    """
    cwd = os.getcwd()
    wrapper_names = ("gradlew.bat", "gradlew") if sys.platform == "win32" else ("gradlew",)
    wrapper_candidates = []
    for base in (cwd, os.path.join(cwd, "android")):
        for name in wrapper_names:
            path = os.path.join(base, name)
            if os.path.isfile(path):
                wrapper_candidates.append(path)

    for wrapper in wrapper_candidates:
        if sys.platform == "win32" and wrapper.lower().endswith((".bat", ".cmd")):
            cmd = ["cmd.exe", "/c", wrapper, "--version"]
        else:
            cmd = [wrapper, "--version"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError:
            # A Unix checkout may not retain the executable bit. Trying via
            # the shell keeps the check useful without making it fatal.
            if sys.platform != "win32":
                try:
                    result = subprocess.run(["sh", wrapper, "--version"],
                                            capture_output=True, text=True)
                except OSError:
                    continue
            else:
                continue
        if result.returncode == 0:
            output = result.stdout or result.stderr or "gradlew wrapper found"
            _print_check("Gradle", output.strip().splitlines()[0], True)
            return True

    gradle = shutil.which("gradle")
    if gradle:
        if sys.platform == "win32" and gradle.lower().endswith((".bat", ".cmd")):
            cmd = ["cmd.exe", "/c", gradle, "--version"]
        else:
            cmd = [gradle, "--version"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError:
            result = None
        if result is not None and result.returncode == 0:
            output = result.stdout or result.stderr or "gradle available"
            _print_check("Gradle", output.strip().splitlines()[0], True)
            return True

    # Gradle is informational: generated projects use the wrapper and can
    # build without a global installation.
    tui.safe_print(warn("Gradle not found (a project wrapper is recommended)."))
    return True


def _check_adb() -> bool:
    adb = shutil.which("adb")
    if not adb:
        tui.safe_print(warn("adb not found in PATH."))
        return False

    try:
        result = subprocess.run([adb, "--version"], capture_output=True, text=True)
    except OSError as exc:
        _print_check("ADB", f"could not run ({exc})", False)
        return False
    version = result.stdout.strip().split("\n")[0] if result.stdout else "?"
    _print_check("ADB", version, result.returncode == 0)
    return result.returncode == 0


def _check_package(module: str, label: str) -> bool:
    try:
        __import__(module)
        _print_check(f"Python: {label}", "installed", True)
        return True
    except ImportError:
        tui.safe_print(fail(f"Python package {label} not installed."))
        return False


def _print_check(name: str, detail: str, ok_: bool):
    """Print a single aligned check result line."""
    detail_str = f"{tui.C_MUTED}{detail}{tui.RESET}" if detail else ""
    message = f"{name:<20} {detail_str}".rstrip()
    tui.safe_print(tui.ok_badge(message) if ok_ else tui.error_badge(message))