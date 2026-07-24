"""
Build system — Gradle integration, APK assembly, and ADB deployment.

Relies on the system-installed JDK, Android SDK, and Gradle wrapper.
"""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import time

from pydrud.utils.colors import ok, fail, info, warn, header, print_step


class Builder:
    """Manages building, installing, and running the Pydrud app on a device."""

    def __init__(self, project_root: str):
        self.root = project_root
        self.android_dir = os.path.join(project_root, "android")
        self.sdk_dir = self._detect_sdk()

    # ── public ────────────────────────────────────────────────────────────

    def build(self, release: bool = False) -> str | None:
        """Run the Gradle build and return the output APK path."""
        print(header("\n  Building Pydrud APK\n"))

        gradlew = self._gradlew()
        if not gradlew:
            print(fail("Gradle wrapper not found. Run `pydrud init` first."))
            return None

        self._validate_environment()

        task = "assembleRelease" if release else "assembleDebug"

        gradle_cmd = os.path.basename(gradlew) if gradlew else "gradle"
        print(info(f"Running: {gradle_cmd} {task}"))
        print()

        result = subprocess.run(
            self._gradle_cmd(task, "--daemon"),
            cwd=self.android_dir,
            env=self._build_env(),
            capture_output=False,
        )

        if result.returncode != 0:
            print(fail("Build failed. Check the output above."))
            return None

        apk_dir = os.path.join(
            self.android_dir,
            "app",
            "build",
            "outputs",
            "apk",
            "release" if release else "debug",
        )

        variant = "-release" if release else "-debug"
        apk_name = f"app{variant}.apk"
        apk_path = os.path.join(apk_dir, apk_name)

        if os.path.isfile(apk_path):
            size = os.path.getsize(apk_path) / (1024 * 1024)
            print(ok(f"APK generated: {apk_path} ({size:.1f} MB)"))
            return apk_path

        # Try unsigned variant.
        if release:
            alt = os.path.join(apk_dir, f"app-release-unsigned.apk")
            if os.path.isfile(alt):
                print(ok(f"APK generated (unsigned): {alt}"))
                return alt

        print(fail("APK not found at expected path."))
        return None

    def run(self, device: str | None = None, release: bool = False):
        """Build, install, launch the app and tail debug logs (like ``flutter run``)."""
        import signal

        apk = self.build(release=release)
        if not apk:
            sys.exit(1)

        if not self._check_adb():
            sys.exit(1)

        device_arg = ["-s", device] if device else []

        # 1. Install.
        print_step("Installing APK on device")
        install_cmd = ["adb"] + device_arg + ["install", "-r", "-d", apk]
        result = subprocess.run(install_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(fail(f"Install failed: {result.stderr.strip()}"))
            sys.exit(1)
        print(ok("Install succeeded."))

        # 2. Clear old logs for this package.
        package_name = self._get_package_name()
        activity_class = self._get_activity_class()
        log_tag = "Pydrud"

        subprocess.run(
            ["adb"] + device_arg + ["logcat", "-c"],
            capture_output=True,
        )

        # 3. Launch the app.
        if package_name and activity_class:
            print_step("Launching app")
            launch_cmd = [
                "adb"] + device_arg + [
                "shell", "am", "start", "-n",
                f"{package_name}/{activity_class}",
            ]
            subprocess.run(launch_cmd, capture_output=True)
            print(ok("App launched!"))

        # 4. Tail logcat — show Pydrud + Python + crash logs in real-time.
        print()
        print(header("═══════════════════ Live Debug Log ═══════════════════"))
        print(info("Press Ctrl+C to stop."))
        print()

        try:
            logcat_args = ["adb"] + device_arg + [
                "logcat",
                "-v", "time",
                "-s",
                f"{log_tag}:V",            # Pydrud
                "PydrudActivity:V",        # MainActivity
                "PydrudBridge:V",          # BridgeService
                "PydrudViewFactory:V",     # ViewFactory
                "PydrudEvents:V",          # EventDispatcher
                "Python:V",                # Chaquopy stdout
                "PythonUtil:V",            # Chaquopy utility
                "Python.android:V",        # Chaquopy internals
                "AndroidRuntime:E",        # Java crashes
                "chaquopy:V",
                "ActivityManager:I",       # Activity lifecycle
                "dalvikvm:W",
                "art:W",
                "DEBUG:W",
            ]
            proc = subprocess.Popen(
                logcat_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )

            # Handle Ctrl+C gracefully.
            def _on_sigint(s, f):
                raise KeyboardInterrupt()
            signal.signal(signal.SIGINT, _on_sigint)

            for line in proc.stdout:
                line = line.rstrip()
                # Colour by severity keyword.
                if "Error" in line or "FATAL" in line or "null" in line.lower():
                    print(fail(line))
                elif "Warning" in line or "incompatible" in line.lower():
                    print(warn(line))
                elif "Started" in line or "connected" in line.lower() or "render" in line.lower():
                    print(ok(line))
                else:
                    print(f"  {line}")

        except KeyboardInterrupt:
            print()
            print(info("Stopped."))
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        except Exception as e:
            print(fail(f"Logcat error: {e}"))

        print()

    def clean(self):
        """Clean Gradle build artifacts."""
        print(header("\n  Cleaning Pydrud project\n"))
        gradlew = self._gradlew()
        if gradlew:
            result = subprocess.run(
                self._gradle_cmd("clean"),
                cwd=self.android_dir,
                capture_output=False,
            )
            if result.returncode == 0:
                print(ok("Build cleaned."))
            else:
                print(fail("Clean failed."))

        # Also remove Python cache files.
        removed = 0
        for root, dirs, files in os.walk(self.root):
            for d in dirs:
                if d == "__pycache__":
                    full = os.path.join(root, d)
                    shutil.rmtree(full, ignore_errors=True)
                    removed += 1

        print(ok(f"Removed {removed} __pycache__ directories."))

    # ── internal ──────────────────────────────────────────────────────────

    def _gradlew(self) -> str | None:
        """Find a usable Gradle launcher.

        Tries, in order:
          1. The Gradle wrapper script (project/android/gradlew[.bat])
          2. The cached Gradle distribution (from gradle-wrapper.properties)
          3. A system-installed ``gradle`` command
        """
        wrapper_name = "gradlew.bat" if sys.platform == "win32" else "gradlew"

        # 1. Wrapper script.
        path = os.path.join(self.android_dir, wrapper_name)
        if os.path.isfile(path):
            # Check if the wrapper JAR exists too.
            jar = os.path.join(self.android_dir, "gradle", "wrapper", "gradle-wrapper.jar")
            if os.path.isfile(jar):
                return path
            # JAR missing — try extracting the cached distribution.
            cached = self._cached_gradle_bin()
            if cached:
                return cached

        # 2. Just try the wrapper anyway — Gradle may handle it.
        if os.path.isfile(path):
            return path

        # 3. System-installed Gradle.
        sys_gradle = shutil.which("gradle")
        if sys_gradle:
            return sys_gradle

        # 4. Fall back to cached distribution binary.
        return self._cached_gradle_bin()

    def _cached_gradle_bin(self) -> str | None:
        """Resolve the gradle binary from the Gradle wrapper cache."""
        import glob
        gradle_exe = "gradle.bat" if sys.platform == "win32" else "gradle"
        dist_root = os.path.expanduser("~/.gradle/wrapper/dists")
        pattern = os.path.join(dist_root, "gradle-*-bin", "*", "gradle-*", "bin", gradle_exe)
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[0]
        # Also try without the hash intermediate directory.
        pattern2 = os.path.join(dist_root, "gradle-*-bin", "gradle-*", "bin", gradle_exe)
        matches2 = sorted(glob.glob(pattern2))
        if matches2:
            return matches2[0]
        return None

    def _gradle_cmd(self, *args: str) -> list[str]:
        """Build the platform-appropriate Gradle command list.

        On Windows, batch files (gradlew.bat) must be run via ``cmd.exe /c``
        because ``CreateProcess`` cannot execute them directly.
        """
        gradlew = self._gradlew()
        if not gradlew:
            return []
        if sys.platform == "win32":
            return ["cmd.exe", "/c", gradlew, *args]
        return [gradlew, *args]

    @staticmethod
    def _detect_sdk() -> str:
        """Locate the Android SDK installation directory."""
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

        return candidates[0]

    @staticmethod
    def _load_config(project_root: str) -> dict:
        """Read ``pydrud.yaml`` and return its values as a flat dict.

        Uses simple line-by-line parsing (no YAML dependency needed for the
        flat key-value format Pydrud uses).
        """
        import re
        config_path = os.path.join(project_root, "pydrud.yaml")
        if not os.path.isfile(config_path):
            return {}

        config = {}
        try:
            with open(config_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)', line)
                    if m:
                        key = m.group(1)
                        value = m.group(2).strip().strip("\"'")
                        config[key] = value
        except Exception:
            pass
        return config

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env["ANDROID_HOME"] = self.sdk_dir
        env["ANDROID_SDK_ROOT"] = self.sdk_dir
        env["PYDRUD_PYTHON"] = shutil.which("python") or shutil.which("python3") or sys.executable

        # NDK version: pydrud.yaml > SDK auto-detection > hardcoded fallback.
        config = self._load_config(self.root)
        ndk_version = config.get("ndk", "")
        if not ndk_version:
            ndk_dir = os.path.join(self.sdk_dir, "ndk")
            ndk_version = "29.0.14206865"
            if os.path.isdir(ndk_dir):
                try:
                    versions = sorted(os.listdir(ndk_dir))
                    if versions:
                        ndk_version = versions[-1]
                except Exception:
                    pass
        env["PYDRUD_NDK_VERSION"] = ndk_version
        # Forward proxy env vars so Gradle can reach remote repos.
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
                    "GRADLE_OPTS", "JAVA_OPTS"):
            if var in os.environ:
                env[var] = os.environ[var]
        # Inject proxy into GRADLE_OPTS if not already present.
        proxy_host = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY", "")
        if proxy_host and "-Dhttp.proxyHost" not in env.get("GRADLE_OPTS", ""):
            proxy = proxy_host.replace("http://", "").replace("https://", "")
            if ":" in proxy:
                host, port = proxy.split(":", 1)
                opts = env.get("GRADLE_OPTS", "")
                opts += f" -Dhttp.proxyHost={host} -Dhttp.proxyPort={port}"
                opts += f" -Dhttps.proxyHost={host} -Dhttps.proxyPort={port}"
                env["GRADLE_OPTS"] = opts
        return env

    def _validate_environment(self):
        sdk = self.sdk_dir
        if not os.path.isdir(sdk):
            print(warn(f"Android SDK not found at {sdk}"))
        else:
            platforms = os.path.join(sdk, "platforms")
            build_tools = os.path.join(sdk, "build-tools")
            print(ok(f"Android SDK:  {sdk}"))
            if os.path.isdir(platforms):
                dirs = sorted(os.listdir(platforms))
                print(info(f"  Platforms:   {', '.join(dirs[-3:])}"))
            if os.path.isdir(build_tools):
                dirs = sorted(os.listdir(build_tools))
                print(info(f"  Build tools: {', '.join(dirs[-3:])}"))

    def _check_adb(self) -> bool:
        adb = shutil.which("adb")
        if not adb:
            print(fail("adb not found in PATH."))
            print(info("Install Android platform-tools and add to PATH."))
            return False

        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if result.returncode != 0:
            print(fail("adb not working."))
            return False

        lines = result.stdout.strip().split("\n")
        devices = [l for l in lines if l and not l.startswith("List") and "device" in l]
        if not devices:
            print(warn("No devices/emulators connected."))
            print(info("Connect a device or start an emulator."))
            return False

        print(ok("Device(s) connected:"))
        for d in devices:
            print(f"    {d}")
        return True

    def _get_package_name(self) -> str | None:
        """Read the package name from the generated build config."""
        build_file = os.path.join(self.android_dir, "app", "build.gradle.kts")
        if os.path.isfile(build_file):
            with open(build_file, encoding="utf-8") as f:
                for line in f:
                    if "namespace" in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            return parts[-1].strip('"')
        return None

    def _get_activity_class(self) -> str | None:
        """Read the Activity class name from the AndroidManifest."""
        manifest = os.path.join(self.android_dir, "app", "src", "main", "AndroidManifest.xml")
        if os.path.isfile(manifest):
            with open(manifest, encoding="utf-8") as f:
                import re
                m = re.search(r'android:name="\.(\w+Activity)"', f.read())
                if m:
                    pkg = self._get_package_name()
                    if pkg:
                        return f"{pkg}.{m.group(1)}"
        return None
