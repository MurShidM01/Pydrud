import json
import pytest

from pydrud import Column, Text, State
from pydrud.core.diff import TreeDiff
from pydrud.core.results import ResultError
from pydrud.core.protocol import RenderTransaction, decode_envelope, encode_envelope


def test_duplicate_keys_are_rejected():
    tree = Column(children=[Text("a", key="same"), Text("b", key="same")])
    with pytest.raises(ValueError, match="Duplicate Pydrud widget key"):
        tree.to_dict()


def test_diff_rejects_duplicate_keys_on_new_tree():
    old = Column(children=[Text("a", key="a")], key="root")
    new = Column(children=[Text("a", key="a"), Text("b", key="a")], key="root")
    with pytest.raises(ValueError, match="Duplicate Pydrud widget key"):
        TreeDiff.diff(old, new)


def test_protocol_transaction_round_trip():
    tx = RenderTransaction.create(
        revision=10,
        base_revision=9,
        kind="snapshot",
        payload={"tree": {"type": "Text", "key": "x"}},
    )
    raw = encode_envelope(tx.envelope())
    decoded = decode_envelope(raw)
    assert decoded["transaction_id"] == tx.tx_id
    assert decoded["revision"] == 10
    assert decoded["base_revision"] == 9
    assert decoded["kind"] == "snapshot"


def test_state_distinct_is_opt_in():
    state = State(1, distinct=True)
    seen = []
    subscription = state.watch(lambda old, new: seen.append((old, new)))
    state.value = 1
    state.value = 2
    subscription.cancel()
    state.value = 3
    assert seen == [(1, 2)]


def test_state_scheduler_receives_callback():
    state = State(0)
    scheduled = []
    seen = []
    state.watch(lambda old, new: seen.append((old, new)),
                scheduler=lambda fn: scheduled.append(fn))
    state.value = 1
    assert seen == []
    scheduled.pop()()
    assert seen == [(0, 1)]
