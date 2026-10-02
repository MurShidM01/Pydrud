"""
DevServer — lightweight on-device development server for Hot Reload & Hot Restart.

Runs inside the Python application runtime (Chaquopy on Android, or local host)
and accepts commands over TCP (default port 8596):
  • hot_reload: sync modified Python files, reload modules, preserve state, re-render
  • hot_restart: reset state, reload all user modules, re-render from initial route
  • dump_tree: return serialised widget tree
  • eval: evaluate Python expressions in the live app context
  • stream_logs / broadcast_error: stream errors and tracebacks to host CLI TUI
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import traceback
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pydrud.runtime.app import App

DEFAULT_DEV_PORT = 8596
DEV_PROTOCOL_VERSION = 2

logger = logging.getLogger("pydrud.devserver")


class DevServer:
    """Socket server for hot reload and live dev diagnostics."""

    def __init__(
        self,
        app: "App",
        host: str = "127.0.0.1",
        port: int = DEFAULT_DEV_PORT,
    ):
        self.app = app
        self.host = host
        self.requested_port = port
        self.port = port
        self._server_socket: Optional[socket.socket] = None
        self._clients: set[socket.socket] = set()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Start listening for incoming dev connections."""
        if self._running:
            return True

        # Try requested port, then a few sequential ports if occupied
        bound = False
        port_range = [self.requested_port] if self.requested_port == 0 else range(self.requested_port, self.requested_port + 5)
        for p in port_range:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, p))
                sock.listen(5)
                sock.settimeout(0.5)
                self._server_socket = sock
                self.port = sock.getsockname()[1]
                bound = True
                break
            except OSError:
                continue

        if not bound or self._server_socket is None:
            logger.warning("Could not bind DevServer to port %s", self.requested_port)
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="pydrud-devserver",
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop dev server and close all client connections."""
        self._running = False
        with self._lock:
            for client in list(self._clients):
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    client.close()
                except Exception:
                    pass
            self._clients.clear()

        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        if self._thread is not None and threading.current_thread() != self._thread:
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass

    def _listen_loop(self) -> None:
        while self._running:
            if not self._server_socket:
                break
            try:
                client_sock, addr = self._server_socket.accept()
                client_sock.settimeout(None)
                with self._lock:
                    self._clients.add(client_sock)
                t = threading.Thread(
                    target=self._client_handler,
                    args=(client_sock,),
                    daemon=True,
                    name=f"pydrud-dev-client-{addr[1]}",
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                if self._running:
                    logger.debug("DevServer accept error: %s", e)
                break

    def _client_handler(self, client: socket.socket) -> None:
        buffer = ""
        try:
            while self._running:
                data = client.recv(65536)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        response = self._handle_message(msg)
                        if response is not None:
                            payload = json.dumps(response, default=str) + "\n"
                            client.sendall(payload.encode("utf-8"))
                    except json.JSONDecodeError:
                        err_res = {"status": "error", "error": "Invalid JSON payload"}
                        client.sendall((json.dumps(err_res) + "\n").encode("utf-8"))
                    except Exception as exc:
                        err_res = {
                            "status": "error",
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        }
                        client.sendall((json.dumps(err_res) + "\n").encode("utf-8"))
        except (OSError, BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with self._lock:
                self._clients.discard(client)
            try:
                client.close()
            except Exception:
                pass

    def _handle_message(self, msg: dict) -> dict:
        cmd = msg.get("cmd") or msg.get("type") or ""

        if cmd == "ping":
            return {
                "status": "ok",
                "app": getattr(self.app, "title", "Pydrud App"),
                "protocol": DEV_PROTOCOL_VERSION,
                "port": self.port,
                "pid": os.getpid(),
                "capabilities": [
                    "hot_reload",
                    "hot_restart",
                    "dump_tree",
                    "eval",
                    "metrics",
                    "stream_errors",
                ],
            }

        elif cmd == "hot_reload":
            files = msg.get("files") or []
            return self.app.apply_hot_reload(files)

        elif cmd == "hot_restart":
            files = msg.get("files") or []
            return self.app.apply_hot_restart(files)

        elif cmd == "dump_tree":
            tree = None
            if hasattr(self.app, "_current_tree") and self.app._current_tree:
                tree = self.app._current_tree.to_dict()
            elif hasattr(self.app, "build"):
                try:
                    built = self.app.build()
                    if built:
                        tree = built.to_dict()
                except Exception:
                    pass
            return {"status": "ok", "tree": tree}

        elif cmd == "eval":
            expr = msg.get("code") or ""
            try:
                scope = {
                    "app": self.app,
                    "page": getattr(self.app, "_page", None),
                    "router": getattr(self.app, "_router", None),
                }
                result = eval(expr, globals(), scope)
                return {"status": "ok", "result": repr(result)}
            except Exception as exc:
                return {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }

        elif cmd == "get_metrics":
            tree_nodes = 0
            if hasattr(self.app, "_current_tree") and self.app._current_tree:
                def _count(w):
                    return 1 + sum(_count(c) for c in getattr(w, "children", []))
                tree_nodes = _count(self.app._current_tree)
            return {
                "status": "ok",
                "tree_nodes": tree_nodes,
                "bound_states": len(getattr(self.app, "_bound_states", [])),
                "bound_stores": len(getattr(self.app, "_bound_stores", [])),
                "current_route": getattr(self.app._router, "current_route", "/") if getattr(self.app, "_router", None) else "/",
            }

        return {"status": "error", "error": f"Unknown command: {cmd}"}

    def broadcast(self, payload: dict) -> None:
        """Send a JSON notification message to all connected clients."""
        msg = (json.dumps(payload, default=str) + "\n").encode("utf-8")
        dead = []
        with self._lock:
            for client in self._clients:
                try:
                    client.sendall(msg)
                except Exception:
                    dead.append(client)
            for d in dead:
                self._clients.discard(d)
                try:
                    d.close()
                except Exception:
                    pass

    def broadcast_error(
        self,
        exc: BaseException,
        tb: Optional[str] = None,
        title: str = "Python Runtime Error",
        filename: Optional[str] = None,
        lineno: Optional[int] = None,
    ) -> None:
        """Broadcast a structured runtime error to all connected CLI runners."""
        payload = {
            "type": "error",
            "title": title,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": tb or traceback.format_exc(),
            "filename": filename,
            "lineno": lineno,
            "timestamp": time.time(),
        }
        self.broadcast(payload)

    def broadcast_log(self, level: str, message: str) -> None:
        """Broadcast an application log line to connected CLI runners."""
        payload = {
            "type": "log",
            "level": level,
            "message": message,
            "timestamp": time.time(),
        }
        self.broadcast(payload)
