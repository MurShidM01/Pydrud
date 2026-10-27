"""Restart resilience: an Android Activity can die without the process.

Pressing BACK finishes the Activity but leaves the CPython interpreter (and
its ``App``) alive. Relaunching then starts a second bridge against the same
port. These tests pin the invariants that make that safe:

* a reader thread from the dead Activity cannot stop the new event loop;
* ``App._halt_run`` releases the old transport without tearing down tasks;
* a failed ``DevServer`` bind does not leak sockets.
"""

from __future__ import annotations

import unittest
from unittest import mock

from pydrud.platforms.android.devserver import DevServer
from pydrud.runtime.app import App


class _FakeSocket:
    """A socket whose ``recv`` immediately reports end-of-stream."""

    def __init__(self) -> None:
        self.closed = False

    def recv(self, _size: int) -> bytes:
        return b""

    def close(self) -> None:
        self.closed = True


class _FakeTransport:
    """The subset of ``socket.socket`` that ``_halt_run`` touches."""

    def __init__(self) -> None:
        self.shutdown_called = False
        self.closed = False

    def shutdown(self, _how: int) -> None:
        self.shutdown_called = True

    def close(self) -> None:
        self.closed = True


def _app() -> App:
    return App(target=lambda page: None)


class _AppCase(unittest.TestCase):
    """Keeps ``App._active`` from leaking into unrelated test modules."""

    def setUp(self) -> None:
        self._previous_active = App._active
        App._active = None

    def tearDown(self) -> None:
        App._active = self._previous_active


class TestReaderOwnership(_AppCase):
    def test_current_reader_stops_the_loop(self):
        app = _app()
        sock = _FakeSocket()
        app._running = True
        app._transport = sock
        app._reader_loop(sock)
        self.assertIsNone(app._event_queue.get_nowait())

    def test_stale_reader_cannot_stop_a_newer_connection(self):
        app = _app()
        sock = _FakeSocket()
        app._running = True
        # A newer Activity already replaced the transport; the old reader's
        # sentinel must not reach the queue that the new loop is draining.
        app._transport = object()
        app._reader_loop(sock)
        self.assertTrue(app._event_queue.empty())


class TestHaltRun(_AppCase):
    def test_releases_the_transport_but_keeps_the_task_pool(self):
        app = _app()
        transport = _FakeTransport()
        app._running = True
        app._transport = transport  # type: ignore[assignment]

        app._halt_run()

        self.assertFalse(app._running)
        self.assertTrue(transport.shutdown_called)
        self.assertTrue(transport.closed)
        self.assertIsNone(app._transport)
        # A later Activity reuses the same App, so the pool must still work.
        self.assertEqual(app._tasks.run(lambda: 42).result(timeout=5), 42)


class TestDevServerBind(_AppCase):
    def test_failed_binds_close_every_candidate_socket(self):
        created: list[_FakeSocket] = []

        class Busy:
            def __init__(self) -> None:
                created.append(self)
                self.closed = False

            def setsockopt(self, *_args) -> None:
                pass

            def bind(self, *_args) -> None:
                raise OSError("address already in use")

            def close(self) -> None:
                self.closed = True

        app = _app()
        with mock.patch(
            "pydrud.platforms.android.devserver.socket.socket",
            side_effect=lambda *a, **k: Busy(),
        ):
            server = DevServer(app, port=8600)
            self.assertFalse(server.start())

        self.assertEqual(len(created), 5)
        self.assertTrue(all(sock.closed for sock in created))


if __name__ == "__main__":
    unittest.main()
