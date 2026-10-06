"""
Shared base class and validators for the native service facades.

``_Service`` holds the page's ``invoke`` callable; ``_iso_date`` and
``_hhmm`` validate the date/time arguments some facades accept; and
``UNIMPLEMENTED_COMMANDS`` documents the (currently empty) list of bridge
commands the Python API exposes without a native handler.
"""

from __future__ import annotations

from typing import Callable, Optional

from pydrud.core.results import Result

Invoke = Callable[..., Result]



#: Commands this Python API exposes that the Android layer does not
#: implement. As of 1.6.0 this is **empty**: Bluetooth LE, NFC, the camera
#: extras, speech recognition, the colour picker, continuous location and
#: notification channels all have native handlers.
#:
#: Anything listed here must *fail* rather than leave a
#: :class:`~pydrud.core.results.Result` pending forever; ``BridgeService``
#: answers the same way on-device, so tests, the previewer and the analyzer
#: behave identically.
#:
#: Keep in sync with ``tests/test_native_coverage.py``.
UNIMPLEMENTED_COMMANDS: frozenset = frozenset()


class _Service:
    """Base class holding the page's ``invoke`` function."""

    def __init__(self, invoke: Invoke):
        self._invoke = invoke


def _iso_date(value: Optional[str], name: str) -> Optional[str]:
    """Validate a ``YYYY-MM-DD`` argument, or ``None`` when omitted."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    parts = text.split("-")
    if len(parts) != 3 or [len(p) for p in parts] != [4, 2, 2]:
        raise ValueError(f"{name} must be an ISO date like '2026-10-06', "
                         f"got {value!r}")
    try:
        year, month, day = (int(p) for p in parts)
    except ValueError:
        raise ValueError(f"{name} must be an ISO date like '2026-10-06', "
                         f"got {value!r}") from None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"{name} is not a real calendar date: {value!r}")
    return f"{year:04d}-{month:02d}-{day:02d}"


def _hhmm(value: Optional[str], name: str = "initial") -> Optional[str]:
    """Validate an ``HH:MM`` argument, or ``None`` when omitted."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) != 2 or [len(p) for p in parts] != [2, 2]:
        raise ValueError(f"{name} must be a 24-hour time like '09:30', "
                         f"got {value!r}")
    try:
        hour, minute = (int(p) for p in parts)
    except ValueError:
        raise ValueError(f"{name} must be a 24-hour time like '09:30', "
                         f"got {value!r}") from None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"{name} is not a real time of day: {value!r}")
    return f"{hour:02d}:{minute:02d}"
