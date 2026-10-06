"""
Encrypted key/value storage backed by the Android Keystore.
"""

from __future__ import annotations

from typing import Any

from pydrud.core.results import Result
from pydrud.services.native._base import _Service



class Secure(_Service):
    """Encrypted key/value storage backed by the Android Keystore.

    Values are written through ``EncryptedSharedPreferences`` (AES-256-GCM
    with a hardware-backed master key when the device has a TEE), so tokens
    and credentials never sit in plaintext on disk::

        page.secure.set("token", jwt)
        page.secure.get("token").then(use_token)
        page.secure.delete("token")
    """

    def set(self, key: str, value: str) -> Result:
        return self._invoke("secure_set", key=str(key), value=str(value))

    def get(self, key: str, default: Any = None) -> Result:
        return self._invoke("secure_get", key=str(key), default=default)

    def delete(self, key: str) -> Result:
        return self._invoke("secure_remove", key=str(key))

    def keys(self) -> Result:
        return self._invoke("secure_keys")

    def clear(self) -> Result:
        return self._invoke("secure_clear")

    def available(self) -> Result:
        """Whether hardware-backed encryption is available on this device."""
        return self._invoke("secure_available")
