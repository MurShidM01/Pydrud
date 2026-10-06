"""
Native platform services.

The thin, typed facades in this package each own one area of the Android
platform and translate Python keyword arguments into a single bridge
command. ``Services`` wires them all onto a page's ``invoke`` callable so a
page exposes them as ``page.dialog``, ``page.storage`` and friends.
"""

from pydrud.services.native._base import Invoke, UNIMPLEMENTED_COMMANDS
from pydrud.services.native.background import Background
from pydrud.services.native.dialogs import Dialogs
from pydrud.services.native.hardware import (
    Audio, Biometrics, Bluetooth, Camera, Nfc, Sensors,
)
from pydrud.services.native.secure import Secure
from pydrud.services.native.storage import FilePicker, Storage
from pydrud.services.native.system import (
    Clipboard, DeviceInfo, Haptics, Location, Notifications,
    Permissions, Push, Share, Shortcuts,
)




class Services:
    """All native services, lazily constructed and cached."""

    def __init__(self, invoke: Invoke):
        self._invoke = invoke
        self.dialog = Dialogs(invoke)
        self.storage = Storage(invoke)
        self.clipboard = Clipboard(invoke)
        self.share = Share(invoke)
        self.permissions = Permissions(invoke)
        self.notifications = Notifications(invoke)
        self.location = Location(invoke)
        self.device = DeviceInfo(invoke)
        self.files = FilePicker(invoke)
        self.haptics = Haptics(invoke)
        self.secure = Secure(invoke)
        self.background = Background(invoke)
        self.push = Push(invoke)
        self.shortcuts = Shortcuts(invoke)
        self.camera = Camera(invoke)
        self.sensors = Sensors(invoke)
        self.bluetooth = Bluetooth(invoke)
        self.nfc = Nfc(invoke)
        self.biometrics = Biometrics(invoke)
        self.audio = Audio(invoke)

    def __repr__(self) -> str:
        return "<Services dialog storage clipboard share permissions " \
               "notifications location device files haptics secure " \
               "background push shortcuts camera sensors bluetooth nfc " \
               "biometrics audio>"


__all__ = [
    "UNIMPLEMENTED_COMMANDS",
    "Services",
    "Dialogs", "Storage", "FilePicker",
    "Clipboard", "Share", "Permissions", "Notifications",
    "Location", "DeviceInfo", "Haptics", "Push", "Shortcuts",
    "Secure", "Background",
    "Camera", "Sensors", "Bluetooth", "Nfc", "Biometrics", "Audio",
]
