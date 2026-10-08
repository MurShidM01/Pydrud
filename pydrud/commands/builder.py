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

from pydrud.utils.colors import ok, fail, info, warn, print_step
from pydrud.utils import tui


class Builder:
    """Manages building, installing, and running the Pydrud app on a device."""

    def __init__(self, project_root: str):
        self.root = project_root
        self.android_dir = os.path.join(project_root, "android")
        self.sdk_dir = self._detect_sdk()
        # Every APK the most recent build produced. A plain build writes one;
        # an `abi_splits` build writes one per ABI plus a universal APK.
        self.last_apks: list[str] = []

    # ── public ────────────────────────────────────────────────────────────

    def build(self, release: bool = False, debug: bool = False) -> str | None:
        """Run the Gradle build and return the output APK path.

        ``--debug`` is the default variant; it exists so scripts and CI logs
        can state the intent instead of relying on the absence of
        ``--release``.
        """
        started = time.perf_counter()
        variant_name = "release" if release else "debug"
        details: list[tuple[str, str]] = [("Variant", variant_name)]
        if debug and not release:
            details.append(("Debug", "debuggable APK (default variant)"))
        details.append(("Project", self.root))
        print(tui.render_command_header(
            "build",
            f"Building {os.path.basename(os.path.abspath(self.root))}",
            subtitle="Compiling Python and Android sources into a native APK",
            details=tuple(details),
        ))

        gradlew = self._gradlew()
        if not gradlew:
            print(fail("Gradle wrapper not found. Run `pydrud init android` first."))
            return None

        if not self._validate_environment():
            return None

        self._clean_pycache()
        self._warn_if_stale()
        if not self._preflight_java():
            return None

        task = "assembleRelease" if release else "assembleDebug"

        gradle_cmd = os.path.basename(gradlew) if gradlew else "gradle"
        print(tui.render_section("Gradle output"))
        print(info(f"Running {gradle_cmd} {task}"))
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

        apks = self._collect_apks(apk_dir, release)
        if not apks:
            print(fail("APK not found at expected path."))
            return None

        self.last_apks = apks
        elapsed = time.perf_counter() - started

        if len(apks) == 1:
            size = os.path.getsize(apks[0]) / (1024 * 1024)
            print(tui.render_summary(
                "APK generated",
                (("Artifact", apks[0]), ("Size", f"{size:.1f} MB"),
                 ("Variant", variant_name), ("Elapsed", f"{elapsed:.1f}s")),
            ))
            return apks[0]

        # An `abi_splits` build: one APK per ABI plus a universal APK.
        rows: list[tuple[str, str]] = [
            (os.path.basename(path), f"{os.path.getsize(path) / (1024 * 1024):.1f} MB")
            for path in apks
        ]
        rows.append(("Variant", variant_name))
        rows.append(("Elapsed", f"{elapsed:.1f}s"))
        print(tui.render_summary(f"{len(apks)} APKs generated", tuple(rows)))
        # The universal APK (sorted first) installs on any device, so it is
        # the safe default for `run` and for a single-path `--output`.
        return apks[0]

    def _collect_apks(self, apk_dir: str, release: bool) -> list[str]:
        """Return every APK the last Gradle build produced.

        A plain build writes a single ``app-<variant>.apk``. With
        ``abi_splits`` enabled Gradle writes one ``app-<abi>-<variant>.apk``
        per ABI plus an ``app-universal-<variant>.apk`` instead, so a lookup
        for the single name would miss them all.
        """
        variant = "release" if release else "debug"

        single = os.path.join(apk_dir, f"app-{variant}.apk")
        if os.path.isfile(single):
            return [single]

        if release:
            unsigned = os.path.join(apk_dir, "app-release-unsigned.apk")
            if os.path.isfile(unsigned):
                return [unsigned]

        if not os.path.isdir(apk_dir):
            return []

        import glob
        matches = glob.glob(os.path.join(apk_dir, f"app-*-{variant}.apk"))
        # Universal first (installs anywhere), then ABI splits by name, so
        # the order — and therefore the default artifact — is stable.
        matches.sort(key=lambda p: ("universal" not in os.path.basename(p),
                                    os.path.basename(p)))
        return matches

    def run(self, device: str | None = None, release: bool = False,
            watch: bool = False, interactive: bool = True, debug: bool = False):
        """Build, install, launch the app and start interactive Hot Reload (like ``flutter run``).

        The Android target always carries a Pydrud runtime backend (Chaquopy,
        host or none), so this starts the on-device Hot Reload runner. A
        legacy target generated before the runtime layer existed carries no
        backend and must be regenerated first.
        """
        from pydrud.commands.project import android_is_standalone

        if not android_is_standalone(self.root):
            print(fail("This Android target has no embedded Python interpreter."))
            print(info("Regenerate it with 'pydrud init android' (or "
                       "'pydrud sync') to add the standalone Chaquopy shell."))
            return 1

        from pydrud.commands.devrunner import DevRunner

        runner = DevRunner(
            project_root=self.root,
            device=device,
            release=release,
            interactive=interactive,
        )
        return runner.run()

    # ── install / launch / watch ──────────────────────────────────────────

    def _install_and_launch(self, apk: str, device: str | None = None) -> bool:
        """Install the APK and start the main activity. Returns success."""
        device_arg = ["-s", device] if device else []

        print_step("Installing APK on device")
        result = subprocess.run(
            ["adb"] + device_arg + ["install", "-r", "-d", apk],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or "Failure" in (result.stdout or ""):
            message = (result.stderr or result.stdout or "").strip()
            print(fail(f"Install failed: {message}"))
            return False
        print(ok("Install succeeded."))

        package_name = self._get_package_name()
        activity_class = self._get_activity_class()
        if package_name and activity_class:
            print_step("Launching app")
            subprocess.run(
                ["adb"] + device_arg
                + ["shell", "am", "start", "-n", f"{package_name}/{activity_class}"],
                capture_output=True,
            )
            print(ok("App launched!"))
        else:
            print(warn("Could not resolve the launch activity; start the app manually."))
        return True

    def watch(self, device: str | None = None, release: bool = False,
              paths: list[str] | None = None) -> None:
        """Run interactive Hot Reload development runner."""
        from pydrud.commands.devrunner import DevRunner

        runner = DevRunner(
            project_root=self.root,
            device=device,
            release=release,
        )
        runner.run()

    def _clean_pycache(self) -> int:
        """Remove Python bytecode caches before building or syncing."""
        removed = 0
        for root, dirs, _files in os.walk(self.root):
            for d in dirs:
                if d == "__pycache__":
                    full = os.path.join(root, d)
                    shutil.rmtree(full, ignore_errors=True)
                    removed += 1
        return removed

    def clean(self):
        """Clean Gradle build artifacts."""
        print(tui.render_command_header(
            "clean",
            f"Cleaning {os.path.basename(os.path.abspath(self.root))}",
            subtitle="Removing Gradle outputs and Python bytecode caches",
            details=(("Project", self.root),),
        ))
        gradlew = self._gradlew()
        gradle_status = "not available"
        if gradlew:
            print(tui.render_section("Gradle output"))
            result = subprocess.run(
                self._gradle_cmd("clean"),
                cwd=self.android_dir,
                capture_output=False,
            )
            gradle_status = "cleaned" if result.returncode == 0 else "failed"
            if result.returncode != 0:
                print(fail("Gradle clean failed."))

        # Also remove Python cache files.
        removed = self._clean_pycache()

        print(tui.render_summary(
            "Project cleaned",
            (("Gradle", gradle_status), ("Python caches", removed)),
            success=gradle_status != "failed",
        ))

    # ── internal ──────────────────────────────────────────────────────────

    def _gradlew(self) -> str | None:
        """Find a usable Gradle launcher.

        Order:
          1. The project's ``gradlew`` script — Pydrud generates a
             self-bootstrapping launcher that downloads Gradle on first use,
             so it works even without ``gradle-wrapper.jar``.
          2. A system-installed ``gradle``.
          3. A Gradle distribution already in the wrapper cache.
        """
        wrapper_name = "gradlew.bat" if sys.platform == "win32" else "gradlew"
        path = os.path.join(self.android_dir, wrapper_name)
        if os.path.isfile(path):
            if sys.platform != "win32" and not os.access(path, os.X_OK):
                try:
                    os.chmod(path, 0o755)
                except OSError:
                    pass
            return path

        sys_gradle = shutil.which("gradle")
        if sys_gradle:
            return sys_gradle

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
                os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk"),
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
        flat key-value format Pydrud writes). Only *top-level* keys are
        read — indented lines belong to a nested block and must not shadow a
        real setting (an ``ndk:`` nested under some other section used to be
        picked up as the project's NDK). Inline ``# comments`` are stripped.
        """
        import re
        config_path = os.path.join(project_root, "pydrud.yaml")
        if not os.path.isfile(config_path):
            return {}

        config: dict = {}
        try:
            with open(config_path, encoding="utf-8") as f:
                raw_lines = f.readlines()
        except OSError as exc:
            print(warn(f"Could not read {config_path}: {exc}"))
            return {}

        for raw in raw_lines:
            if raw[:1].isspace() or raw.lstrip().startswith(("#", "-")):
                continue  # nested entry, list item or comment
            m = re.match(r'^(\w[\w_]*)\s*:\s*(.*)$', raw.rstrip("\n"))
            if not m:
                continue
            value = m.group(2).strip()
            if value[:1] and value[0] in "\"'":
                quote = value[0]
                end = value.find(quote, 1)
                value = value[1:end] if end > 0 else value[1:]
            else:
                value = value.split(" #", 1)[0].strip()
            config[m.group(1)] = value
        return config

    def _build_env(self) -> dict:
        env = os.environ.copy()
        env["ANDROID_HOME"] = self.sdk_dir
        env["ANDROID_SDK_ROOT"] = self.sdk_dir

        config = self._load_config(self.root)

        # buildPython only exists for the embedded-interpreter (Chaquopy)
        # backend: a host/none target ships no interpreter, so probing — and
        # reporting — a Python version there is pure noise.
        from pydrud.commands.project import (
            APP_PYTHON_VERSION, _detect_build_python, _python_version_of,
        )
        from pydrud.runtime.runtime import resolve_runtime
        if resolve_runtime(self.root).backend == "chaquopy":
            # An explicit PYDRUD_PYTHON wins, otherwise pick an interpreter
            # matching the app's Python. If only a different minor version
            # is installed, disable source bytecode compilation instead of
            # letting Chaquopy print an alarming (but harmless) warning.
            target = config.get("python_version", "") or APP_PYTHON_VERSION
            if not os.environ.get("PYDRUD_PYTHON"):
                env["PYDRUD_PYTHON"] = _detect_build_python(target)
            selected_python = env.get("PYDRUD_PYTHON", "")
            selected_version = _python_version_of(selected_python)
            env["PYDRUD_COMPILE_PYC"] = (
                "true" if selected_version == target else "false"
            )

        # NDK version: pydrud.yaml > SDK auto-detection > hardcoded fallback.
        ndk_version = config.get("ndk", "")
        if not ndk_version:
            from pydrud.commands.project import _detect_ndk

            ndk_version = _detect_ndk(self.sdk_dir)
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

    def _validate_environment(self) -> bool:
        """Report the toolchain state. Returns False when a build is impossible."""
        java_home = os.environ.get("JAVA_HOME", "")
        java = shutil.which("java") or (
            os.path.join(java_home, "bin", "java") if java_home else ""
        )
        if not java or (os.path.sep in java and not os.path.isfile(java)):
            print(fail("Java (JDK 17+) not found."))
            print(info("Install a JDK and set JAVA_HOME, then run `pydrud doctor`."))
            return False

        sdk = self.sdk_dir
        if not os.path.isdir(sdk):
            print(fail(f"Android SDK not found at {sdk}"))
            print(info("Install the Android SDK and set ANDROID_HOME "
                       "(see `pydrud doctor`)."))
            return False
        else:
            platforms = os.path.join(sdk, "platforms")
            build_tools = os.path.join(sdk, "build-tools")
            print(ok(f"Android SDK:  {sdk}"))
            if os.path.isdir(platforms):
                dirs = sorted(os.listdir(platforms))
                print(info(f"Platforms:   {', '.join(dirs[-3:])}"))
            if os.path.isdir(build_tools):
                dirs = sorted(os.listdir(build_tools))
                print(info(f"Build tools: {', '.join(dirs[-3:])}"))
        return True

    # ── pre-flight ────────────────────────────────────────────────────────

    def _warn_if_stale(self) -> None:
        """Tell the user when the project was generated by another version.

        The Java renderer lives *inside* the project, so upgrading the
        ``pydrud`` package alone leaves the old (possibly incompatible)
        sources in place. ``pydrud sync`` rewrites them.
        """
        from pydrud import __version__

        project_version = self._load_config(self.root).get("pydrud_version", "")
        if project_version and project_version != __version__:
            print(warn(
                f"Project was generated by Pydrud {project_version}, "
                f"but {__version__} is installed."))
            print(info("Run `pydrud sync` to refresh the native layer."))

    def _preflight_java(self) -> bool:
        """Resolve the generated Java sources before paying for Gradle.

        A missing method on a generated class costs two minutes of Gradle
        before javac complains; this finds it in well under a second. The
        check needs ``javalang`` (an optional dev dependency) and is simply
        skipped when it is absent — it can only ever *save* a build.
        """
        try:
            from pydrud.android.javacheck import check_sources
        except ImportError:
            return True

        java_root = os.path.join(self.android_dir, "app", "src", "main", "java")
        if not os.path.isdir(java_root):
            return True

        sources: dict[str, str] = {}
        for folder, _dirs, files in os.walk(java_root):
            for name in files:
                if not name.endswith(".java"):
                    continue
                path = os.path.join(folder, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        sources[os.path.relpath(path, java_root)] = handle.read()
                except OSError:
                    continue
        if not sources:
            return True

        try:
            problems = check_sources(sources)
        except Exception:
            return True  # never block a build on the linter itself

        if not problems:
            return True
        print(fail("Generated Java will not compile:"))
        for problem in problems[:10]:
            print(f"    {problem}")
        if len(problems) > 10:
            print(f"    … and {len(problems) - 10} more")
        print(info("Run `pydrud sync` to regenerate the native layer."))
        return False

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