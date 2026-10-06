"""
Dialogs, bottom sheets and the date/time/colour pickers.
"""

from __future__ import annotations

from typing import Optional, Sequence

from pydrud.core.results import Result
from pydrud.services.native._base import _Service, _hhmm, _iso_date



class Dialogs(_Service):
    """Material dialogs, bottom sheets and the date/time pickers."""

    def alert(self, message: str, *, title: str = "", ok: str = "OK") -> Result:
        """Show a one-button dialog. Resolves with ``True`` when dismissed."""
        return self._invoke("dialog", kind="alert", title=title,
                            message=str(message), ok=ok)

    def confirm(self, message: str, *, title: str = "", ok: str = "OK",
                cancel: str = "Cancel", destructive: bool = False) -> Result:
        """Ask a yes/no question. Resolves with ``True`` or ``False``."""
        return self._invoke("dialog", kind="confirm", title=title,
                            message=str(message), ok=ok, cancel=cancel,
                            destructive=bool(destructive))

    def prompt(self, message: str, *, title: str = "", value: str = "",
               hint: str = "", ok: str = "OK", cancel: str = "Cancel",
               obscure: bool = False) -> Result:
        """Ask for text. Resolves with the string, or ``None`` if cancelled."""
        return self._invoke("dialog", kind="prompt", title=title,
                            message=str(message), value=value, hint=hint,
                            ok=ok, cancel=cancel, obscure=bool(obscure))

    def choose(self, options: Sequence[str], *, title: str = "",
               selected: int = -1, multi: bool = False) -> Result:
        """Single- or multi-choice list. Resolves with index/list of indices."""
        items = [str(o) for o in options]
        if not items:
            raise ValueError("choose() needs at least one option")
        return self._invoke("dialog", kind="choose", title=title,
                            options=items, selected=int(selected),
                            multi=bool(multi))

    def bottom_sheet(self, options: Sequence[str], *, title: str = "",
                     icons: Optional[Sequence[str]] = None) -> Result:
        """A modal bottom sheet menu. Resolves with the chosen index.

        Cancelling (tapping outside or swiping down) resolves with ``-1``,
        matching :meth:`choose`.
        """
        items = [str(o) for o in options]
        if not items:
            raise ValueError("bottom_sheet() needs at least one option")
        return self._invoke("bottom_sheet", title=str(title), options=items,
                            icons=[str(i) for i in (icons or [])])

    def date(self, *, initial: Optional[str] = None, min: Optional[str] = None,
             max: Optional[str] = None) -> Result:
        """Date picker. Resolves with an ISO ``YYYY-MM-DD`` string or None.

        ``initial`` seeds the calendar; ``min``/``max`` bound the selectable
        range (so a "date of birth" picker cannot offer tomorrow). Every
        argument must be ``YYYY-MM-DD`` — a typo raises here rather than
        silently dropping the bound on the device::

            page.dialog.date(min="1900-01-01", max="2026-12-31")
        """
        initial = _iso_date(initial, "initial")
        min_date = _iso_date(min, "min")
        max_date = _iso_date(max, "max")
        if min_date and max_date and min_date > max_date:
            raise ValueError(
                f"date(min={min_date!r}) is after date(max={max_date!r})")
        return self._invoke("date_picker", initial=initial,
                            min=min_date, max=max_date)

    def time(self, *, initial: Optional[str] = None,
             use_24h: bool = True) -> Result:
        """Time picker. Resolves with ``HH:MM`` or None.

        ``initial`` must be ``HH:MM`` (24-hour) and is honoured even when
        ``use_24h`` is False::

            page.dialog.time(initial="09:30", use_24h=False)
        """
        return self._invoke("time_picker", initial=_hhmm(initial),
                            use24h=bool(use_24h))

    def color(self, *, initial: str = "#FF6366F1") -> Result:
        """Colour picker. Resolves with an ARGB string or None.
        """
        return self._invoke("color_picker", initial=initial)

    def progress(self, message: str = "Please wait…", *,
                 cancellable: bool = False) -> Result:
        """Show a blocking progress dialog; dismiss with :meth:`dismiss`."""
        return self._invoke("progress_dialog", show=True, message=message,
                            cancellable=cancellable)

    def dismiss(self) -> Result:
        """Dismiss the progress dialog."""
        return self._invoke("progress_dialog", show=False)
