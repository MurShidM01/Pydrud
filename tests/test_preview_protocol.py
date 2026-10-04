import socket
import threading
import time
import urllib.parse

import pytest
from click.testing import CliRunner

from pydrud.commands.cli import main as cli
from pydrud.commands.preview import load_preview_app, terminal_qr
from pydrud.core.preview import (
    PREVIEW_PROTOCOL,
    PREVIEW_PROTOCOL_VERSION,
    PreviewProtocolError,
    PreviewSession,
    build_preview_uri,
    parse_preview_uri,
    validate_client_hello,
)
from pydrud.core.preview_server import PreviewServer
from pydrud.core.protocol import PROTOCOL_VERSION, decode_envelope, encode_envelope
from pydrud.runtime.app import App
from pydrud.widgets import Text


CAPABILITIES = {
    "transactional_render": True,
    "revisioned_render": True,
    "ack_nack": True,
    "resync": True,
}


def hello(session, *, token=None, revision=0, capabilities=None):
    return {
        "type": "preview_hello",
        "protocol": PREVIEW_PROTOCOL,
        "protocol_version": PREVIEW_PROTOCOL_VERSION,
        "renderer_protocol_version": PROTOCOL_VERSION,
        "session_id": session.session_id,
        "token": session.token if token is None else token,
        "client": {"name": "Protocol test client", "version": "1.0"},
        "capabilities": CAPABILITIES if capabilities is None else capabilities,
        "last_revision": revision,
        "metrics": {"width": 412, "height": 915, "density": 2.75},
    }


def read_message(stream):
    line = stream.readline()
    assert line, "preview server closed the connection"
    return decode_envelope(line.decode("utf-8"))


def read_initial_sync(stream):
    welcome = read_message(stream)
    theme = read_message(stream)
    transaction = read_message(stream)
    assert welcome["type"] == "preview_welcome"
    assert theme["cmd"] == "theme"
    assert transaction["cmd"] == "render_transaction"
    assert transaction["kind"] == "snapshot"
    return welcome, transaction


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_qr_payload_round_trip_contains_session_and_connection_identity():
    session = PreviewSession.create("com.example.preview", "Preview App")
    uri = build_preview_uri(session, "192.168.1.24", 8597)
    parsed = parse_preview_uri(uri)

    assert uri.startswith("pydrud://preview/connect?")
    assert parsed == {
        "host": "192.168.1.24",
        "port": 8597,
        "session_id": session.session_id,
        "token": session.token,
        "protocol_version": PREVIEW_PROTOCOL_VERSION,
        "renderer_protocol_version": PROTOCOL_VERSION,
        "project_id": "com.example.preview",
        "project_name": "Preview App",
    }
    assert "token=" in urllib.parse.urlparse(uri).query


def test_qr_payload_refuses_non_connectable_wildcard_address():
    session = PreviewSession.create("com.example.preview", "Preview App")
    with pytest.raises(ValueError, match="connectable"):
        build_preview_uri(session, "0.0.0.0", 8597)


def test_terminal_qr_is_compact_and_contains_finder_pattern_modules():
    session = PreviewSession.create("com.example.preview", "Preview App")
    rendered = terminal_qr(
        build_preview_uri(session, "192.168.1.24", 8597), ansi=False)
    lines = rendered.splitlines()
    # Preview URIs use the compact quarter-block rendering: two modules per
    # column and per line, so the code stays a normal terminal size.
    assert 10 < len(lines) < 40
    assert max(map(len, lines)) < 50
    # Top-left finder pattern as drawn with quadrant glyphs.
    assert any("▛▀▀▌" in line for line in lines)


def test_terminal_qr_adapts_to_narrow_terminals():
    session = PreviewSession.create("com.example.preview", "Preview App")
    uri = build_preview_uri(session, "192.168.1.24", 8597)
    narrow = terminal_qr(uri, ansi=False, max_width=40)
    assert max(map(len, narrow.splitlines())) <= 40


def test_hello_authentication_and_capability_negotiation():
    session = PreviewSession.create("com.example.preview", "Preview App")
    normalized = validate_client_hello(hello(session), session)
    assert normalized["last_revision"] == 0
    assert normalized["client"]["name"] == "Protocol test client"

    with pytest.raises(PreviewProtocolError) as auth:
        validate_client_hello(hello(session, token="wrong"), session)
    assert auth.value.code == "authentication_failed"

    with pytest.raises(PreviewProtocolError) as missing:
        validate_client_hello(
            hello(session, capabilities={"transactional_render": True}), session)
    assert missing.value.code == "missing_capabilities"
    assert "ack_nack" in missing.value.message

    malformed = hello(session)
    malformed["metrics"] = {"width": float("inf"), "height": 640}
    with pytest.raises(PreviewProtocolError) as invalid_metrics:
        validate_client_hello(malformed, session)
    assert invalid_metrics.value.code == "invalid_metrics"


def test_preview_server_initial_sync_patch_and_reconnect_snapshot():
    model = {"text": "one"}

    def target(page):
        page.add(Text(model["text"], key="label"))

    app = App(target=target, dev_server=False)
    app.build()
    session = PreviewSession.create("com.example.preview", "Preview App")
    server = PreviewServer(app, session, host="127.0.0.1", port=0)
    _, port = server.start()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    first = socket.create_connection(("127.0.0.1", port), timeout=2)
    first.settimeout(2)
    first.sendall(encode_envelope(hello(session)).encode("utf-8"))
    stream = first.makefile("rb")
    welcome, initial = read_initial_sync(stream)
    assert welcome["project"]["id"] == "com.example.preview"
    assert welcome["limits"]["max_frame_bytes"] > 1000
    assert initial["base_revision"] == 0
    revision = initial["revision"]

    first.sendall(encode_envelope({
        "type": "render_ack",
        "data": {
            "transaction_id": initial["transaction_id"],
            "revision": revision,
        },
    }).encode("utf-8"))
    assert wait_until(lambda: app._confirmed_revision == revision)

    def change_text():
        model["text"] = "two"
        app.update()

    app.run_on_ui(change_text)
    patch = read_message(stream)
    assert patch["cmd"] == "render_transaction"
    assert patch["kind"] == "patch"
    assert patch["base_revision"] == revision
    patch_revision = patch["revision"]
    first.sendall(encode_envelope({
        "type": "render_ack",
        "data": {
            "transaction_id": patch["transaction_id"],
            "revision": patch_revision,
        },
    }).encode("utf-8"))
    assert wait_until(lambda: app._confirmed_revision == patch_revision)
    stream.close()
    first.close()
    assert wait_until(lambda: not server.active)

    second = socket.create_connection(("127.0.0.1", port), timeout=2)
    second.settimeout(2)
    second.sendall(encode_envelope(
        hello(session, revision=patch_revision)).encode("utf-8"))
    second_stream = second.makefile("rb")
    _, resync = read_initial_sync(second_stream)
    assert resync["kind"] == "snapshot"
    assert resync["base_revision"] == patch_revision
    assert resync["revision"] > patch_revision

    second_stream.close()
    second.close()
    server.stop()
    app.stop()
    worker.join(timeout=2)
    assert not worker.is_alive()


def test_nack_forces_full_resync_and_recovery_ack_confirms_tree():
    app = App(target=lambda page: page.add(Text("resync", key="label")),
              dev_server=False)
    session = PreviewSession.create("com.example.preview", "Preview App")
    server = PreviewServer(app, session, host="127.0.0.1", port=0)
    _, port = server.start()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    client.settimeout(2)
    client.sendall(encode_envelope(hello(session)).encode("utf-8"))
    stream = client.makefile("rb")
    _, initial = read_initial_sync(stream)
    client.sendall(encode_envelope({
        "type": "render_nack",
        "data": {
            "transaction_id": initial["transaction_id"],
            "revision": initial["revision"],
            "native_revision": 0,
            "code": "stale_base",
        },
    }).encode("utf-8"))

    recovery = read_message(stream)
    assert recovery["kind"] == "snapshot"
    assert recovery["base_revision"] == 0
    client.sendall(encode_envelope({
        "type": "render_ack",
        "data": {
            "transaction_id": recovery["transaction_id"],
            "revision": recovery["revision"],
        },
    }).encode("utf-8"))
    assert wait_until(lambda: app._confirmed_revision == recovery["revision"])
    assert app._snapshot is not None

    stream.close()
    client.close()
    server.stop()
    app.stop()
    worker.join(timeout=2)


def test_preview_server_allows_only_one_authenticated_renderer():
    app = App(target=lambda page: page.add(Text("single client")),
              dev_server=False)
    session = PreviewSession.create("com.example.preview", "Preview App")
    server = PreviewServer(app, session, host="127.0.0.1", port=0)
    _, port = server.start()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    first = socket.create_connection(("127.0.0.1", port), timeout=2)
    first.sendall(encode_envelope(hello(session)).encode("utf-8"))
    first_stream = first.makefile("rb")
    read_initial_sync(first_stream)
    assert server.active

    second = socket.create_connection(("127.0.0.1", port), timeout=2)
    second.sendall(encode_envelope(hello(session)).encode("utf-8"))
    second_stream = second.makefile("rb")
    rejection = read_message(second_stream)
    assert rejection["type"] == "preview_reject"
    assert rejection["code"] == "client_busy"

    second_stream.close()
    second.close()
    first_stream.close()
    first.close()
    server.stop()
    app.stop()
    worker.join(timeout=2)


def test_preview_server_rejects_bad_token_before_attaching_app():
    app = App(target=lambda page: page.add(Text("secure")), dev_server=False)
    session = PreviewSession.create("com.example.preview", "Preview App")
    server = PreviewServer(app, session, host="127.0.0.1", port=0)
    _, port = server.start()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    client.sendall(encode_envelope(
        hello(session, token="not-the-token")).encode("utf-8"))
    rejection = read_message(client.makefile("rb"))
    assert rejection["type"] == "preview_reject"
    assert rejection["code"] == "authentication_failed"
    assert app.connected is False

    client.close()
    server.stop()
    app.stop()
    worker.join(timeout=2)


def test_failed_host_reload_keeps_last_good_ui(tmp_path, capsys):
    broken = tmp_path / "src" / "app" / "screen.py"
    broken.parent.mkdir(parents=True)
    broken.write_text("def broken(:\n", encoding="utf-8")
    app = App(target=lambda page: page.add(Text("last good")), dev_server=False)
    app._project_root = str(tmp_path)
    updates = []
    app.update = lambda: updates.append(True)

    app._on_hot_reload(str(broken))

    assert updates == []
    output = capsys.readouterr()
    assert "Keeping the last good preview" in output.out
    assert "SyntaxError" in output.err


def test_local_project_loader_imports_entrypoint_without_android(tmp_path):
    import sys

    source = tmp_path / "src" / "app"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    (source / "main.py").write_text(
        "from pydrud import Text\n"
        "def main(page):\n"
        "    page.add(Text('host python', key='message'))\n",
        encoding="utf-8",
    )
    src_path = str(tmp_path / "src")
    try:
        app = load_preview_app(
            str(tmp_path), config={"app_name": "Local Preview"})
        tree = app.build().to_dict()
        assert app.title == "Local Preview"
        assert tree["children"][0]["children"][0]["props"]["value"] == "host python"
    finally:
        for name in ("app.main", "app"):
            sys.modules.pop(name, None)
        if src_path in sys.path:
            sys.path.remove(src_path)


def test_cli_dev_delegates_without_using_apk_builder(tmp_path, monkeypatch):
    (tmp_path / "pydrud.yaml").write_text(
        'app_name: "CLI Preview"\npackage: "com.example.cli"\n',
        encoding="utf-8",
    )
    captured = {}

    class FakeRunner:
        def __init__(self, project_dir, **kwargs):
            captured["project_dir"] = project_dir
            captured.update(kwargs)

        def run(self):
            captured["ran"] = True
            return 0

    monkeypatch.setattr("pydrud.commands.preview.PreviewRunner", FakeRunner)
    result = CliRunner().invoke(cli, [
        "dev", str(tmp_path), "--host", "127.0.0.1", "--port", "9001",
        "--connect-host", "10.0.0.7", "--no-qr",
    ])

    assert result.exit_code == 0, result.output
    assert captured == {
        "project_dir": str(tmp_path),
        "host": "127.0.0.1",
        "port": 9001,
        "connect_host": "10.0.0.7",
        "show_qr": False,
        "ran": True,
    }
