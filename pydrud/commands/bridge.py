"""``pydrud dev --bridge`` — serve a host-backend APK from this machine.

A project built with the ``host`` backend carries no interpreter: the app
dials out to the developer's machine. This runner loads the project Python
exactly like the preview server and exposes the plain bridge protocol on
loopback, so an ``adb reverse`` forward is all a device needs to attach. No
QR code, session token or on-device connect screen is involved.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click

from pydrud.commands.project_config import load_project_config
from pydrud.core.bridge_server import BridgeServer


class BridgeRunner:
    """Load a project locally and expose the device bridge on loopback."""

    def __init__(
        self,
        project_dir: str,
        *,
        host: str = "127.0.0.1",
        port: int = 8597,
        device: Optional[str] = None,
        reverse: bool = True,
    ):
        self.project_dir = os.path.abspath(project_dir)
        self.host = str(host)
        self.port = int(port)
        self.device = device
        self.reverse = bool(reverse)
        self.app = None
        self.server: Optional[BridgeServer] = None

    def run(self) -> int:
        previous_cwd = os.getcwd()
        os.chdir(self.project_dir)
        try:
            from pydrud.commands.preview import load_preview_app

            config = load_project_config(self.project_dir)
            app_name = str(config.get("app_name") or Path(self.project_dir).name)
            self.app = load_preview_app(self.project_dir, config=config)
            self.app.build()
            self.app.enable_hot_reload(["src"])

            self.server = BridgeServer(
                self.app, host=self.host, port=self.port,
                on_status=self._status,
            )
            bound_host, bound_port = self.server.start()
            if self.reverse:
                self._adb_reverse(bound_port)
            print_bridge_banner(
                app_name=app_name,
                bind_host=bound_host,
                port=bound_port,
                device=self.device,
            )
            try:
                self.server.serve_forever()
            except KeyboardInterrupt:
                click.echo("\nStopping Pydrud device bridge...")
            return 0
        finally:
            if self.server is not None:
                self.server.stop()
            if self.app is not None:
                self.app.stop()
            os.chdir(previous_cwd)

    def _adb_reverse(self, port: int) -> None:
        """Forward ``tcp:port`` on the device back to this machine.

        This is what lets a host-backend APK reach ``127.0.0.1:port`` without
        knowing the machine's LAN address — it works for an emulator and for a
        USB-attached device alike.
        """
        adb = shutil.which("adb")
        if adb is None:
            click.echo(
                "  adb was not found on PATH — run "
                f"'adb reverse tcp:{port} tcp:{port}' yourself if the app "
                "cannot connect.", err=True)
            return
        command = [adb]
        if self.device:
            command += ["-s", self.device]
        command += ["reverse", f"tcp:{port}", f"tcp:{port}"]
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            click.echo(f"  adb reverse failed: {exc}", err=True)
            return
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            click.echo(f"  adb reverse failed: {detail}", err=True)

    @staticmethod
    def _status(event: str, data: dict) -> None:
        if event == "connected":
            click.echo(f"\nDevice connected from {data.get('peer', 'unknown')}")
        elif event == "disconnected":
            click.echo("Device disconnected. Waiting for the app to reconnect...")
        elif event in {"connection_error", "server_error"}:
            click.echo(
                f"Bridge connection error ({data.get('peer', 'unknown')}): "
                f"{data.get('error', 'unknown error')}", err=True)


def print_bridge_banner(*, app_name: str, bind_host: str, port: int,
                        device: Optional[str] = None) -> None:
    """Print connection status for the device bridge."""
    width = 66
    click.echo("\n" + "═" * width)
    click.secho("  Pydrud Dev · Device Bridge (host backend)", bold=True)
    click.echo("═" * width)
    click.echo(f"  Project    {app_name}")
    click.echo(f"  Listening  {bind_host}:{port}")
    if device:
        click.echo(f"  Device     {device}")
    click.echo("  Forward    adb reverse "
               f"tcp:{port} tcp:{port}")
    click.echo("\n  Launch the host-backend app on the device. It will dial")
    click.echo(f"  {bind_host}:{port} and draw your Python UI. Keep this")
    click.echo("  terminal open. Press Ctrl+C to stop.")
    click.echo("═" * width)


__all__ = ["BridgeRunner", "print_bridge_banner"]
