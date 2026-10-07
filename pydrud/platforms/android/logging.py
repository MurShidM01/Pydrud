"""
Stable logging for framework and app output (DX-004).

On Android, Python's ``print`` and uncaught-traceback output is routed by
Chaquopy to logcat under ``python.stdout`` / ``python.stderr`` — tags that
are easy to lose in the noise. :func:`install` tees ``sys.stdout`` and
``sys.stderr`` to logcat under the single, documented :data:`TAG`
(``Pydrud``), so::

    adb logcat -s Pydrud

shows the framework's output, the app's ``print`` calls and every error
traceback in one place. On the host (no ``android.util.Log``) it is a
no-op and output behaves exactly as before.
"""

from __future__ import annotations

import io
import sys

__all__ = ["TAG", "install", "log", "log_exception"]

#: The one tag every framework log line uses.
TAG = "Pydrud"

# android.util.Log priorities.
_DEBUG, _INFO, _WARN, _ERROR = 3, 4, 5, 6

_installed = False
_original_stdout = None
_original_stderr = None


def _android_log():
    """The ``android.util.Log`` class, or ``None`` off-device."""
    try:
        from java import jclass  # type: ignore
    except Exception:
        return None
    try:
        return jclass("android.util.Log")
    except Exception:
        return None


def _emit(line: str, priority: int) -> None:
    log_class = _android_log()
    if log_class is None or not line:
        return
    try:
        log_class.println(priority, TAG, line)
    except Exception:
        pass


class _LogcatWriter(io.TextIOBase):
    """Tee a text stream to the original stream *and* to logcat."""

    def __init__(self, original, priority: int):
        self._original = original
        self._priority = priority
        self._buffer = ""

    def write(self, text: str) -> int:      # noqa: D102 - io API
        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            _emit(line, self._priority)
        return len(text)

    def flush(self) -> None:                # noqa: D102 - io API
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass
        if self._buffer:
            _emit(self._buffer, self._priority)
            self._buffer = ""

    def isatty(self) -> bool:               # noqa: D102 - io API
        return False

    @property
    def encoding(self) -> str:              # noqa: D102 - io API
        return "utf-8"


def install() -> bool:
    """Route ``stdout``/``stderr`` to logcat under :data:`TAG`.

    Returns ``True`` when the redirect was installed (i.e. we are on
    Android), ``False`` on the host or when it was already installed.
    """
    global _installed, _original_stdout, _original_stderr
    if _installed or _android_log() is None:
        return False
    _original_stdout, _original_stderr = sys.stdout, sys.stderr
    sys.stdout = _LogcatWriter(_original_stdout, _INFO)
    sys.stderr = _LogcatWriter(_original_stderr, _ERROR)
    _installed = True
    return True


def log(message: str, *, warn: bool = False, error: bool = False) -> None:
    """Write one line under :data:`TAG` (and to stderr on the host)."""
    priority = _ERROR if error else _WARN if warn else _INFO
    text = str(message)
    if _android_log() is not None:
        _emit(text, priority)
    else:
        stream = sys.stderr if (warn or error) else sys.stdout
        try:
            stream.write(text + "\n")
            stream.flush()
        except Exception:
            pass


def log_exception(exc: BaseException, tb: str = "") -> None:
    """Report an exception under :data:`TAG`, traceback included."""
    log(f"Error: {exc}", error=True)
    if tb.strip() and tb.strip() != "NoneType: None":
        for line in tb.rstrip().splitlines():
            log(line, error=True)
