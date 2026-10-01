"""
Native platform services.

Widgets are only half of an Android app. The other half is the platform:
dialogs, pickers, permissions, preferences, the clipboard, the share sheet,
notifications, location, haptics and device info.

Every service here is a thin, typed facade over one bridge command. Calls
that produce an answer return a :class:`~pydrud.core.results.Result`, so you
can either attach a callback::

    page.dialog.confirm("Delete this note?").then(
        lambda yes: delete() if yes else None)

or block inside a background task::

    def worker():
        if page.dialog.confirm("Delete?").wait():
            delete()
    page.run_task(worker)
"""

from pydrud.services.native import (
    Clipboard,
    DeviceInfo,
    Dialogs,
    FilePicker,
    Haptics,
    Location,
    Notifications,
    Permissions,
    Services,
    Share,
    Storage,
)
from pydrud.services.http import Http, HttpResponse

__all__ = [
    "Services",
    "Dialogs",
    "Storage",
    "Clipboard",
    "Share",
    "Permissions",
    "Notifications",
    "Location",
    "DeviceInfo",
    "FilePicker",
    "Haptics",
    "Http",
    "HttpResponse",
]
