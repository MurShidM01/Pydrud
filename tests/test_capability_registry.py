"""Coverage for the production-safe Android capability registry."""

import pytest

from pydrud.commands.release import (
    CAPABILITY_PERMISSIONS,
    KNOWN_CAPABILITIES,
    resolve_capability,
)


def test_common_native_services_have_capability_bundles():
    for name in ("camera", "contacts", "calendar", "media", "bluetooth",
                 "nfc", "biometrics", "microphone", "location"):
        assert name in KNOWN_CAPABILITIES
        assert CAPABILITY_PERMISSIONS[name]


def test_capability_aliases_are_stable():
    assert resolve_capability("photos") == "media"
    assert resolve_capability("nearby") == "bluetooth"
    assert resolve_capability("fingerprint") == "biometrics"
    with pytest.raises(ValueError, match="permissions add"):
        resolve_capability("android.permission.CAMERA")
