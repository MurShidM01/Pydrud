"""
Key/value persistence and the Storage Access Framework file helpers.
"""

from __future__ import annotations

from typing import Any

from pydrud.core.results import Result
from pydrud.services.native._base import _Service



class Storage(_Service):
    """Key/value persistence backed by ``SharedPreferences``.

    Values are JSON-encoded on the Python side, so lists and dicts survive a
    round trip::

        page.storage.set("profile", {"name": "Ada", "pro": True})
        page.storage.get("profile", default={}).then(show_profile)
    """

    def get(self, key: str, default: Any = None) -> Result:
        """Request a stored value and return a :class:`~pydrud.Result`.

        Native calls are asynchronous by design. Use ``.then(callback)`` in
        an event handler or ``.wait(default=...)`` from a worker started with
        ``page.run_task``; the ``Result`` wrapper must not be used as the
        value itself (for example, do not call ``len(page.storage.get(...))``).
        """
        return self._invoke("prefs_get", key=str(key), default=default)

    def set(self, key: str, value: Any) -> Result:
        return self._invoke("prefs_set", key=str(key), value=value)

    def remove(self, key: str) -> Result:
        return self._invoke("prefs_remove", key=str(key))

    def keys(self) -> Result:
        return self._invoke("prefs_keys")

    def clear(self) -> Result:
        return self._invoke("prefs_clear")

    def secure_set(self, key: str, value: str) -> Result:
        """Store a secret in the Android keystore-backed encrypted prefs."""
        return self._invoke("prefs_set", key=str(key), value=value, secure=True)

    def secure_get(self, key: str, default: Any = None) -> Result:
        return self._invoke("prefs_get", key=str(key), default=default,
                            secure=True)


class FilePicker(_Service):
    """The Storage Access Framework: pick, save and read files."""

    def pick(self, *, mime: str = "*/*", multiple: bool = False) -> Result:
        """Pick existing file(s). Resolves with a path (or list of paths)."""
        return self._invoke("pick_file", mime=mime, multiple=bool(multiple))

    def pick_image(self, *, camera: bool = False, multiple: bool = False) -> Result:
        """Pick an image from the gallery, or capture one with the camera."""
        return self._invoke("pick_image", camera=bool(camera),
                            multiple=bool(multiple))

    def save(self, filename: str, content: str, *,
             mime: str = "text/plain") -> Result:
        """Prompt for a location and write *content* there."""
        return self._invoke("save_file", filename=filename, content=content,
                            mime=mime)

    def read(self, path: str) -> Result:
        """Read a previously picked file as text."""
        return self._invoke("read_file", path=str(path))

    def documents_dir(self) -> Result:
        """The app's private documents directory (usable from Python ``open``)."""
        return self._invoke("app_dir", kind="documents")

    def cache_dir(self) -> Result:
        return self._invoke("app_dir", kind="cache")
