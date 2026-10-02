import pytest

from pydrud.core.elements import ElementTree
from pydrud.core.protocol import (
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    RenderTransaction,
    decode_envelope,
    encode_envelope,
)


def test_element_reuse_and_type_safety():
    tree = ElementTree()
    first, created = tree.upsert("card", "Card", parent_key="root", index=0)
    assert created is True
    first.native_ref = object()

    second, created = tree.upsert("card", "Card", parent_key="root", index=1)
    assert created is False
    assert second is first
    assert second.native_ref is not None

    with pytest.raises(TypeError):
        tree.upsert("card", "Text")


def test_render_transaction_has_revision_and_base():
    tx = RenderTransaction.create(
        revision=4,
        base_revision=3,
        kind="patch",
        payload={"patches": [{"op": "update"}]},
    )
    envelope = tx.envelope()
    assert envelope["protocol_version"] == PROTOCOL_VERSION
    assert envelope["revision"] == 4
    assert envelope["base_revision"] == 3
    assert envelope["transaction_id"] == tx.tx_id


def test_protocol_round_trip_and_size_limit():
    raw = encode_envelope({"cmd": "ping", "value": "hello"})
    assert decode_envelope(raw) == {"cmd": "ping", "value": "hello"}

    with pytest.raises(ProtocolError):
        encode_envelope({"cmd": "oversized", "value": "x" * (MAX_FRAME_BYTES + 1)})


def test_decode_rejects_non_objects_and_bad_json():
    with pytest.raises(ProtocolError):
        decode_envelope("[]")
    with pytest.raises(ProtocolError):
        decode_envelope("{")
