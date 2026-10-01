"""
File watcher for Hot Reload — monitors Python source files and triggers
rebuilds when they change.

Uses ``watchdog`` if available (recommended), with a fallback to polling
``os.stat`` for environments without ``watchdog`` installed.
"""

from __future__ import annotations
import os
import sys
import time
import threading
from typing import Callable, Optional

_HAS_WATCHDOG = False
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    _HAS_WATCHDOG = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object


_EXTENSIONS = (".py",)


class _ReloadHandler(FileSystemEventHandler if _HAS_WATCHDOG else object):
    """Watchdog event handler that triggers on .py file changes."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback
        self._debounce: dict[str, float] = {}
        self._debounce_sec = 0.5

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(_EXTENSIONS):
            now = time.time()
            last = self._debounce.get(event.src_path, 0)
            if now - last > self._debounce_sec:
                self._debounce[event.src_path] = now
                self.callback(event.src_path)


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
    ):
        self.paths = [os.path.abspath(p) for p in paths]
        self.callback = callback
        self.poll_interval = poll_interval
        self._observer: Optional[Observer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._mtimes: dict[str, float] = {}

    def start(self) -> None:
        """Start watching for file changes."""
        self._running = True
        if _HAS_WATCHDOG and Observer is not None:
            self._start_watchdog()
        else:
            self._start_polling()

    def _start_watchdog(self) -> None:
        """Start watchdog-based file watching."""
        self._observer = Observer()
        handler = _ReloadHandler(self.callback)
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
                self._walk_and_check(path)
            time.sleep(self.poll_interval)

    def _walk_and_check(self, directory: str) -> None:
        """Walk a directory and check for modified .py files."""
        try:
            for root, _dirs, files in os.walk(directory):
                for fname in files:
                    if not fname.endswith(_EXTENSIONS):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        mtime = os.stat(fpath).st_mtime
                    except OSError:
                        continue
                    last = self._mtimes.get(fpath, 0)
                    if last > 0 and mtime > last:
                        self.callback(fpath)
                    self._mtimes[fpath] = mtime
        except Exception:
            pass

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
