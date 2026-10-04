"""
DevRunner -- interactive Flutter-like development runner for Pydrud apps.

Provides:
  • Incremental Hot Reload (sync Python code changes in milliseconds without APK rebuilds)
  • Hot Restart (R / Shift+r to reset state & re-render from initial route)
  • Flutter-like interactive keyboard commands (r, R, t, c, h, d, q)
  • Live Logcat streaming with real-time error & traceback formatting in the TUI
  • Device detection and ADB port forwarding
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from pydrud.commands.builder import Builder
from pydrud.core.watcher import FileWatcher
from pydrud.utils import tui


class DevRunner:
    """Manages the interactive dev lifecycle: build, deploy, hot reload, and logs."""

    def __init__(
        self,
        project_root: str,
        device: Optional[str] = None,
        release: bool = False,
        interactive: bool = True,
        dev_port: int = 8596,
        bridge_port: int = 8595,
    ):
        self.root = os.path.abspath(project_root)
        self.device = device
        self.release = release
        self.interactive = interactive and sys.stdin.isatty()
        self.dev_port = dev_port
        self.bridge_port = bridge_port

        self.builder = Builder(self.root)
        self._dev_sock: Optional[socket.socket] = None
        self._running = False
        self._watcher: Optional[FileWatcher] = None
        self._key_reader: Optional[_KeyReader] = None
        self._logcat_proc: Optional[subprocess.Popen] = None
        self._logcat_thread: Optional[threading.Thread] = None
        self._app_pid: Optional[str] = None
        self._dev_listener_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._pending_files: set[str] = set()
        self._reload_timer: Optional[threading.Timer] = None
        self._last_mtimes: dict[str, float] = {}

        self.package_name = self.builder._get_package_name() or "com.pydrud.app"
        self.activity_class = self.builder._get_activity_class() or "MainActivity"
        self.app_name = os.path.basename(self.root)

    # ── Main Entry Point ──────────────────────────────────────────────────

    def run(self) -> int:
        """Run the dev loop: build, deploy, start watcher & interactive listener."""
        self._running = True

        # 1. Device detection
        device_id = self._detect_device()
        self.device = device_id
        device_label = self.device or "connected device"

        # 2. Build APK
        apk = self.builder.build(release=self.release)
        if not apk:
            return 1

        if not self.builder._check_adb():
            return 1

        # 3. Forward ports before launch
        self._setup_port_forward()

        # 4. Install and clear logs
        installed = self.builder._install_and_launch(apk, self.device)
        if not installed:
            return 1

        # 5. Clear old logcat buffer
        device_arg = ["-s", self.device] if self.device else []
        try:
            subprocess.run(["adb"] + device_arg + ["logcat", "-c"], capture_output=True)
        except Exception:
            pass

        # 6. Connect to on-device DevServer
        self._connect_dev_server(timeout=10.0)

        # 7. Print TUI Header & Shortcuts
        tui.clear_screen()
        banner = tui.render_header_banner(
            app_name=self.app_name,
            package_name=self.package_name,
            device_name=device_label,
            python_version="3.11",
        )
        sys.stdout.write(banner)
        sys.stdout.write(tui.ok_badge("App running on device\n"))
        if self._dev_sock is not None:
            sys.stdout.write(tui.ok_badge(f"DevServer connected on port {self.dev_port} (Hot Reload active)\n"))
        else:
            sys.stdout.write(tui.warn_badge("DevServer connecting in background...\n"))
        sys.stdout.write(tui.ok_badge("File watcher active (src/, assets/)\n\n"))
        sys.stdout.write(tui.render_shortcuts_bar() + "\n\n")
        sys.stdout.write(tui.render_log_divider())
        sys.stdout.flush()

        # 8. Start Background Services
        self._start_file_watcher()
        self._start_logcat_streamer()
        self._start_dev_listener()

        if self.interactive:
            self._key_reader = _KeyReader(self._handle_key)
            self._key_reader.start()

        # 9. Register Signal Handlers
        def _on_sig(sig, frame):
            self.stop(terminate_app=True)
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _on_sig)
            signal.signal(signal.SIGTERM, _on_sig)
        except Exception:
            pass

        # 10. Wait loop
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop(terminate_app=True)
        return 0

    # ── Device & Port Forwarding ──────────────────────────────────────────

    def _detect_device(self) -> Optional[str]:
        """Detect connected ADB devices and pick the active target."""
        if self.device:
            return self.device
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            if res.returncode != 0:
                return None
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip() and not l.startswith("List of")]
            devices = [l.split()[0] for l in lines if "device" in l]
            if devices:
                return devices[0]
        except Exception:
            pass
        return None

    def _setup_port_forward(self) -> None:
        """Forward DevServer (8596) and Bridge (8595) ports over ADB."""
        device_arg = ["-s", self.device] if self.device else []
        try:
            subprocess.run(
                ["adb"] + device_arg + ["forward", f"tcp:{self.dev_port}", f"tcp:{self.dev_port}"],
                capture_output=True,
            )
            subprocess.run(
                ["adb"] + device_arg + ["forward", f"tcp:{self.bridge_port}", f"tcp:{self.bridge_port}"],
                capture_output=True,
            )
        except Exception as exc:
            sys.stdout.write(tui.warn_badge(f"Port forward notice: {exc}\n"))

    # ── DevServer Socket Client ───────────────────────────────────────────

    def _connect_dev_server(self, timeout: float = 8.0) -> bool:
        """Connect to the DevServer running inside the Android app."""
        start_time = time.time()
        while time.time() - start_time < timeout and self._running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(("127.0.0.1", self.dev_port))
                # Send ping
                sock.sendall((json.dumps({"cmd": "ping"}) + "\n").encode("utf-8"))
                resp_line = sock.makefile().readline()
                if resp_line:
                    resp = json.loads(resp_line)
                    if resp.get("status") == "ok":
                        self._dev_sock = sock
                        sock.settimeout(None)
                        return True
            except Exception:
                time.sleep(0.3)
        return False

    def _send_dev_command(self, cmd_dict: dict) -> Optional[dict]:
        """Send a JSON command to the DevServer and read response."""
        with self._lock:
            if self._dev_sock is None:
                # Try reconnecting
                if not self._connect_dev_server(timeout=1.5):
                    return None

            try:
                payload = (json.dumps(cmd_dict) + "\n").encode("utf-8")
                self._dev_sock.sendall(payload)
                self._dev_sock.settimeout(8.0)
                rfile = self._dev_sock.makefile(encoding="utf-8")
                line = rfile.readline()
                if line:
                    return json.loads(line.strip())
            except Exception:
                try:
                    if self._dev_sock:
                        self._dev_sock.close()
                except Exception:
                    pass
                self._dev_sock = None
        return None

    # ── Hot Reload & Hot Restart Execution ────────────────────────────────

    def trigger_hot_reload(self, specific_files: Optional[list[str]] = None) -> None:
        """Perform fast Hot Reload without rebuilding the APK."""
        files_to_sync = []
        src_dir = os.path.join(self.root, "src")

        if specific_files:
            target_files = [os.path.abspath(f) for f in specific_files]
        else:
            # Gather all .py files in src/
            target_files = []
            if os.path.isdir(src_dir):
                for root, _, files in os.walk(src_dir):
                    if any(ign in root for ign in ("__pycache__", ".git")):
                        continue
                    for f in files:
                        if f.endswith(".py"):
                            target_files.append(os.path.join(root, f))

        for fpath in target_files:
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    content = fp.read()
                rel = os.path.relpath(fpath, self.root)
                files_to_sync.append({"path": rel, "content": content})
            except Exception as e:
                sys.stdout.write(tui.warn_badge(f"Could not read {fpath}: {e}\n"))

        if not files_to_sync:
            sys.stdout.write(tui.warn_badge("No source files found to reload.\n"))
            return

        response = self._send_dev_command({"cmd": "hot_reload", "files": files_to_sync})
        if response is None:
            sys.stdout.write(tui.warn_badge("DevServer not reachable -- app might be busy or restarting.\n"))
            return

        if response.get("status") == "ok":
            duration = response.get("duration_ms", 0.0)
            reloaded = response.get("reloaded", [])
            states = response.get("states_preserved", 0)
            names = [f["path"] for f in files_to_sync]
            sys.stdout.write(tui.hot_reload_success(duration, names if len(names) <= 3 else reloaded, states))
            sys.stdout.flush()
        else:
            err_type = response.get("error_type", "Error")
            if err_type == "SyntaxError":
                sys.stdout.write(
                    tui.render_syntax_error_box(
                        filename=response.get("filename", "unknown"),
                        lineno=response.get("lineno", 1),
                        offset=response.get("offset", 1),
                        text=response.get("text", ""),
                        message=response.get("message", "Syntax error"),
                    )
                )
            else:
                sys.stdout.write(
                    tui.render_error_box(
                        title=f"Hot Reload Error ({err_type})",
                        message=response.get("message") or response.get("error", "Reload failed"),
                        traceback_str=response.get("traceback"),
                        filename=response.get("filename"),
                    )
                )
            sys.stdout.flush()

    def trigger_hot_restart(self) -> None:
        """Perform full Hot Restart: reset state, reload all modules, re-render from root."""
        files_to_sync = []
        src_dir = os.path.join(self.root, "src")
        if os.path.isdir(src_dir):
            for root, _, files in os.walk(src_dir):
                if any(ign in root for ign in ("__pycache__", ".git")):
                    continue
                for f in files:
                    if f.endswith(".py"):
                        fpath = os.path.join(root, f)
                        try:
                            with open(fpath, "r", encoding="utf-8") as fp:
                                content = fp.read()
                            rel = os.path.relpath(fpath, self.root)
                            files_to_sync.append({"path": rel, "content": content})
                        except Exception:
                            pass

        response = self._send_dev_command({"cmd": "hot_restart", "files": files_to_sync})
        if response is None:
            sys.stdout.write(tui.warn_badge("DevServer not reachable -- app might be restarting.\n"))
            return

        if response.get("status") == "ok":
            duration = response.get("duration_ms", 0.0)
            sys.stdout.write(tui.hot_restart_success(duration))
            sys.stdout.flush()
        else:
            sys.stdout.write(
                tui.render_error_box(
                    title="Hot Restart Error",
                    message=response.get("error", "Restart failed"),
                    traceback_str=response.get("traceback"),
                )
            )
            sys.stdout.flush()

    def dump_widget_tree(self) -> None:
        """Inspect and print the current widget tree."""
        response = self._send_dev_command({"cmd": "dump_tree"})
        if response and response.get("tree"):
            from pydrud.commands.inspector import render_tree
            tree_dict = response.get("tree")
            sys.stdout.write("\n" + tui.BOLD + "  Widget Tree:\n" + tui.RESET)
            for line in render_tree(tree_dict).splitlines():
                sys.stdout.write(f"    {line}\n")
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            sys.stdout.write(tui.warn_badge("Could not retrieve widget tree from app.\n"))

    # ── File Watcher ──────────────────────────────────────────────────────

    def _start_file_watcher(self) -> None:
        """Start monitoring project directories for source changes."""
        watch_dirs = [
            os.path.join(self.root, p) for p in ["src", "assets"]
        ]
        watch_dirs = [p for p in watch_dirs if os.path.isdir(p)]
        if not watch_dirs:
            watch_dirs = [self.root]

        def _on_file_changed(fpath: str) -> None:
            with self._lock:
                self._pending_files.add(fpath)
                if self._reload_timer is not None:
                    self._reload_timer.cancel()
                self._reload_timer = threading.Timer(0.18, self._flush_reload)
                self._reload_timer.daemon = True
                self._reload_timer.start()

        self._watcher = FileWatcher(watch_dirs, _on_file_changed, debounce=0.15)
        self._watcher.start()

    def _flush_reload(self) -> None:
        with self._lock:
            files = list(self._pending_files)
            self._pending_files.clear()
            self._reload_timer = None

        if files:
            self.trigger_hot_reload(files)

    # ── Interactive Keyboard Handling ────────────────────────────────────

    def _handle_key(self, key: str) -> None:
        """Handle single-key interactive commands (Flutter-style)."""
        if key == "r":
            self.trigger_hot_reload()
        elif key == "R":
            self.trigger_hot_restart()
        elif key in ("h", "?"):
            sys.stdout.write(tui.render_help_box())
            sys.stdout.flush()
        elif key == "c":
            tui.clear_screen()
            device_label = self.device or "connected device"
            sys.stdout.write(
                tui.render_header_banner(
                    app_name=self.app_name,
                    package_name=self.package_name,
                    device_name=device_label,
                )
            )
            sys.stdout.write(tui.render_shortcuts_bar() + "\n\n")
            sys.stdout.write(tui.render_log_divider())
            sys.stdout.flush()
        elif key in ("t", "p"):
            self.dump_widget_tree()
        elif key == "d":
            sys.stdout.write("\n" + tui.info_badge(
                "Detached from app. App remains running on device.") + "\n\n")
            sys.stdout.flush()
            self.stop(terminate_app=False)
            os._exit(0)
        elif key in ("q", "\x03"):  # q or Ctrl+C
            sys.stdout.write(f"\n  {tui.C_MUTED}Terminating app and stopping runner...{tui.RESET}\n")
            sys.stdout.flush()
            self.stop(terminate_app=True)
            os._exit(0)

    # ── DevServer Error Streamer ──────────────────────────────────────────

    def _start_dev_listener(self) -> None:
        """Background thread listening for async error notifications from DevServer."""
        def _listen():
            while self._running:
                if self._dev_sock is None:
                    time.sleep(0.5)
                    continue
                try:
                    # DevServer messages are handled during command exchange, but if extra
                    # async broadcasts arrive, read them
                    time.sleep(0.5)
                except Exception:
                    time.sleep(0.5)

        self._dev_listener_thread = threading.Thread(target=_listen, daemon=True, name="pydrud-dev-listener")
        self._dev_listener_thread.start()

    # ── Logcat Streamer & Error Parser ───────────────────────────────────

    def _resolve_app_pid(self) -> Optional[str]:
        """Return the running app PID, if Android can resolve it.

        Tag-only logcat filters are global: an OEM service which writes to
        ``System.err`` used to appear as if it had crashed the Pydrud app.
        Scoping logcat to the package process keeps live output actionable.
        """
        device_arg = ["-s", self.device] if self.device else []
        try:
            result = subprocess.run(
                ["adb"] + device_arg
                + ["shell", "pidof", "-s", self.package_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                pid = result.stdout.strip().split()
                if pid and pid[0].isdigit():
                    return pid[0]
        except Exception:
            pass
        return None

    def _logcat_command(self) -> list[str]:
        """Build a package-scoped logcat command.

        ``System.err`` and ``AndroidRuntime`` are useful only with a PID
        filter; without one they contain unrelated framework and OEM errors.
        Pydrud/Chaquopy tags remain available as a safe fallback on older adb
        versions where ``pidof`` is unavailable.
        """
        device_arg = ["-s", self.device] if self.device else []
        self._app_pid = self._resolve_app_pid()
        command = ["adb"] + device_arg + ["logcat", "-v", "time"]
        if self._app_pid:
            command.append(f"--pid={self._app_pid}")
        command.extend([
            "-s",
            "Pydrud:V",
            "PydrudActivity:V",
            "PydrudBridge:V",
            "PydrudViewFactory:V",
            "PydrudEvents:V",
            "Python:V",
            "Python.android:V",
            "chaquopy:V",
        ])
        if self._app_pid:
            command.extend(["AndroidRuntime:E", "DEBUG:W", "System.err:W"])
        return command

    def _start_logcat_streamer(self) -> None:
        """Stream this app's logcat and format Python errors in the TUI."""
        logcat_cmd = self._logcat_command()

        try:
            self._logcat_proc = subprocess.Popen(
                logcat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                errors="replace",
            )
        except Exception as exc:
            sys.stdout.write(tui.warn_badge(f"Logcat start warning: {exc}\n"))
            return

        def _log_reader():
            tb_buffer: list[str] = []
            in_traceback = False

            while self._running and self._logcat_proc and self._logcat_proc.stdout:
                line = self._logcat_proc.stdout.readline()
                if not line:
                    break
                line = line.rstrip()
                if not line:
                    continue

                # Filter out pure noisy lines
                if "--------- beginning of" in line:
                    continue

                # Detect Python Traceback block
                if "Traceback (most recent call last):" in line or "[Pydrud] Error:" in line:
                    in_traceback = True
                    tb_buffer = [line]
                    continue

                if in_traceback:
                    tb_buffer.append(line)
                    # Traceback usually ends with exception line (e.g. "ValueError: ...", "ZeroDivisionError: ...")
                    if re.match(r"^[A-Za-z0-9_]+Error.*", line) or re.match(r"^[A-Za-z0-9_]+Exception.*", line):
                        in_traceback = False
                        tb_text = "\n".join(tb_buffer)
                        sys.stdout.write(tui.render_error_box("Python Runtime Error", "", tb_text))
                        sys.stdout.flush()
                        tb_buffer.clear()
                    elif len(tb_buffer) > 25:  # safeguard max lines
                        in_traceback = False
                        tb_text = "\n".join(tb_buffer)
                        sys.stdout.write(tui.render_error_box("Python Runtime Error", "", tb_text))
                        sys.stdout.flush()
                        tb_buffer.clear()
                    continue

                # Detect AndroidRuntime crash
                if "FATAL EXCEPTION" in line or "AndroidRuntime: FATAL" in line:
                    sys.stdout.write(tui.render_error_box("Android Fatal Exception", line))
                    sys.stdout.flush()
                    continue

                # Format log messages
                self._format_and_print_log(line)

        self._logcat_thread = threading.Thread(target=_log_reader, daemon=True, name="pydrud-logcat")
        self._logcat_thread.start()

    def _format_and_print_log(self, line: str) -> None:
        """Format regular logcat lines cleanly."""
        # Strip timestamp prefix if in standard logcat time format: "04-20 12:34:56.789 I/Tag( 1234): message"
        match = re.match(r"^\d{2}-\d{2}\s+(\d{2}:\d{2}:\d{2})\.\d+\s+([VDIWEF])/([^(\s]+)(?:\(\s*\d+\))?:\s*(.*)$", line)
        if match:
            t_str, level, tag, msg = match.groups()
            msg = msg.strip()
            if not msg:
                return

            # Skip internal bridge spam
            if tag == "PydrudBridge" and ("sent" in msg or "received" in msg or "Bridge frame" in msg):
                return

            if level in ("E", "F") or "error" in msg.lower() or "exception" in msg.lower():
                sys.stdout.write(f"  {tui.C_MUTED}[{t_str}]{tui.RESET} {tui.C_ERROR}[{tag}]{tui.RESET} {tui.BOLD}{msg}{tui.RESET}\n")
            elif level == "W" or "warn" in msg.lower():
                sys.stdout.write(f"  {tui.C_MUTED}[{t_str}]{tui.RESET} {tui.C_WARN}[{tag}]{tui.RESET} {msg}\n")
            elif tag in ("Python", "Python.android"):
                sys.stdout.write(f"  {tui.C_MUTED}[{t_str}]{tui.RESET} {tui.C_PRIMARY}[{tag}]{tui.RESET} {msg}\n")
            else:
                sys.stdout.write(f"  {tui.C_MUTED}[{t_str}]{tui.RESET} {tui.C_MUTED}[{tag}]{tui.RESET} {msg}\n")
        else:
            # Fallback for plain lines
            if "Error" in line or "FATAL" in line:
                sys.stdout.write(f"  {tui.C_ERROR}{line}{tui.RESET}\n")
            elif "Warning" in line:
                sys.stdout.write(f"  {tui.C_WARN}{line}{tui.RESET}\n")
            else:
                sys.stdout.write(f"  {tui.C_MUTED}{line}{tui.RESET}\n")
        sys.stdout.flush()

    # ── Shutdown & Cleanup ────────────────────────────────────────────────

    def stop(self, terminate_app: bool = False) -> None:
        """Stop all background services and clean up."""
        self._running = False

        if self._key_reader:
            try:
                self._key_reader.stop()
            except Exception:
                pass
            self._key_reader = None

        if self._watcher:
            try:
                self._watcher.stop()
            except Exception:
                pass
            self._watcher = None

        if self._dev_sock:
            try:
                self._dev_sock.close()
            except Exception:
                pass
            self._dev_sock = None

        if self._logcat_proc:
            try:
                self._logcat_proc.terminate()
            except Exception:
                pass
            self._logcat_proc = None

        if terminate_app and self.package_name:
            device_arg = ["-s", self.device] if self.device else []
            try:
                subprocess.run(
                    ["adb"] + device_arg + ["shell", "am", "force-stop", self.package_name],
                    capture_output=True,
                )
            except Exception:
                pass


# ── Terminal Key Reader ──────────────────────────────────────────────────────


class _KeyReader:
    """Non-blocking single-key reader supporting Linux, macOS, and Windows."""

    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._orig_termios = None

    def start(self) -> bool:
        if not sys.stdin.isatty():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pydrud-key-reader")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        self._restore_terminal()

    def _restore_terminal(self) -> None:
        if self._orig_termios is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._orig_termios)
            except Exception:
                pass
            self._orig_termios = None

    def _loop(self) -> None:
        if os.name == "nt":
            import msvcrt
            while self._running:
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getwch()
                        if ch:
                            self.callback(ch)
                except Exception:
                    pass
                time.sleep(0.04)
        else:
            import termios
            import tty
            import select
            try:
                fd = sys.stdin.fileno()
                self._orig_termios = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                while self._running:
                    r, _, _ = select.select([sys.stdin], [], [], 0.08)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch:
                            self.callback(ch)
            except Exception:
                pass
            finally:
                self._restore_terminal()
