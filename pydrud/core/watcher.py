"""
File watcher for Hot Reload — monitors Python source files and triggers
rebuilds when they change.

Uses ``watchdog`` if available (recommended), with a fallback to polling
``os.stat`` for environments without ``watchdog`` installed.
"""

from __future__ import annotations
import os
import time
import threading
from typing import Callable, Optional

_HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object


_EXTENSIONS = (".py", ".pss")

#: Directories that never need watching.
_IGNORED_DIRS = {"__pycache__", ".git", ".venv", "venv", "build", "dist", ".idea"}


class _ReloadHandler(FileSystemEventHandler if _HAS_WATCHDOG else object):
    """Watchdog event handler that triggers on .py file changes."""

    def __init__(self, callback: Callable[[str], None], debounce: float = 0.4):
        super().__init__()
        self.callback = callback
        self._debounce: dict[str, float] = {}
        self._debounce_sec = debounce

    def _fire(self, path: str) -> None:
        if not path or not str(path).endswith(_EXTENSIONS):
            return
        abs_path = os.path.abspath(path)
        if any(part in _IGNORED_DIRS for part in abs_path.split(os.sep)):
            return
        now = time.time()
        if now - self._debounce.get(abs_path, 0) <= self._debounce_sec:
            return
        self._debounce[abs_path] = now
        try:
            self.callback(abs_path)
        except Exception as exc:
            print(f"[Pydrud] Watcher callback error: {exc}")

    def on_modified(self, event):
        if not event.is_directory:
            self._fire(event.src_path)

    def on_created(self, event):
        """A brand-new module must trigger a reload too."""
        if not event.is_directory:
            self._fire(event.src_path)

    def on_moved(self, event):
        """Most editors save atomically: write a temp file, then rename it.

        Without this hook, saving from vim/PyCharm never reloaded.
        """
        if not event.is_directory:
            self._fire(getattr(event, "dest_path", "") or event.src_path)


class FileWatcher:
    """Watches directories for Python file changes and triggers a callback.

    Args:
        paths: List of directory paths to watch.
        callback: Called with the changed file path when a change is detected.
        poll_interval: Polling interval in seconds (used only in fallback mode).
    """

    def __init__(
        self,
        paths: list[str],
        callback: Callable[[str], None],
        *,
        poll_interval: float = 0.5,
        debounce: float = 0.4,
    ):
        self.paths = [os.path.abspath(p) for p in paths]
        self.callback = callback
        self.poll_interval = poll_interval
        self._observer: Optional[Observer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._mtimes: dict[str, float] = {}
        self._scanned = False
        self._last_fired: dict[str, float] = {}
        self.debounce = debounce

    def start(self) -> None:
        """Start watching for file changes."""
        self._running = True
        if _HAS_WATCHDOG and Observer is not None:
            try:
                self._start_watchdog()
                return
            except Exception as exc:
                print(f"[Pydrud] Watchdog failed to start ({exc}), falling back to polling.")
                self._observer = None
        self._start_polling()

    def _start_watchdog(self) -> None:
        """Start watchdog-based file watching."""
        self._observer = Observer()
        handler = _ReloadHandler(self.callback, debounce=self.debounce)
        for path in self.paths:
            if os.path.isdir(path):
                self._observer.schedule(handler, path, recursive=True)
        self._observer.start()

    def _start_polling(self) -> None:
        """Fallback: poll file mtimes in a background thread."""
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="pydrud-watcher",
        )
        self._thread.start()

    def _poll_loop(self) -> None:
        """Polling loop for environments without watchdog."""
        while self._running:
            for path in self.paths:
                if os.path.isdir(path):
                    self._walk_and_check(path)
                elif os.path.isfile(path) and path.endswith(_EXTENSIONS):
                    self._check_file(path)
            self._scanned = True
            time.sleep(self.poll_interval)

    def _check_file(self, fpath: str) -> None:
        fpath = os.path.abspath(fpath)
        try:
            mtime = os.stat(fpath).st_mtime
        except OSError:
            return
        last = self._mtimes.get(fpath, 0)
        if self._scanned:
            if mtime > last or last == 0:
                now = time.time()
                if now - self._last_fired.get(fpath, 0) > self.debounce:
                    self._last_fired[fpath] = now
                    try:
                        self.callback(fpath)
                    except Exception as exc:
                        print(f"[Pydrud] Watcher callback error: {exc}")
        self._mtimes[fpath] = mtime

    def _walk_and_check(self, directory: str) -> None:
        """Walk a directory and check for modified .py files."""
        try:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
                for fname in files:
                    if not fname.endswith(_EXTENSIONS):
                        continue
                    fpath = os.path.abspath(os.path.join(root, fname))
                    try:
                        mtime = os.stat(fpath).st_mtime
                    except OSError:
                        continue
                    last = self._mtimes.get(fpath, 0)
                    # After the first scan, an unseen file is a *new* module
                    # and must trigger a reload just like an edited one.
                    if (mtime > last) if self._scanned else (last > 0 and mtime > last):
                        now = time.time()
                        if now - self._last_fired.get(fpath, 0) > self.debounce:
                            self._last_fired[fpath] = now
                            try:
                                self.callback(fpath)
                            except Exception as exc:
                                print(f"[Pydrud] Watcher callback error: {exc}")
                    self._mtimes[fpath] = mtime
        except OSError:
            pass

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval * 3)
            self._thread = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
