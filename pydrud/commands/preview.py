"""Implementation of the host-driven ``pydrud dev`` workflow."""

from __future__ import annotations

import importlib
import os
import shutil
import socket
import sys
from pathlib import Path
from typing import Optional

import click

from pydrud.commands.project_config import load_project_config
from pydrud.core.preview import (
    PreviewSession,
    build_preview_uri,
    fallback_project_id,
)
from pydrud.core.qr import encode_matrix as encode_qr_matrix
from pydrud.core.preview_server import PreviewServer
from pydrud.runtime.app import App


class PreviewRunner:
    """Load a project locally and expose its renderer protocol to the LAN."""

    def __init__(
        self,
        project_dir: str,
        *,
        host: str = "0.0.0.0",
        port: int = 8597,
        connect_host: Optional[str] = None,
        show_qr: bool = True,
    ):
        self.project_dir = os.path.abspath(project_dir)
        self.host = str(host)
        self.port = int(port)
        self.connect_host = connect_host
        self.show_qr = bool(show_qr)
        self.app: Optional[App] = None
        self.server: Optional[PreviewServer] = None

    def run(self) -> int:
        """Run until interrupted, preserving the normal APK workflow."""
        previous_cwd = os.getcwd()
        os.chdir(self.project_dir)
        try:
            config = load_project_config(self.project_dir)
            app_name = str(config.get("app_name") or Path(self.project_dir).name)
            project_id = str(
                config.get("package") or fallback_project_id(self.project_dir))
            session = PreviewSession.create(project_id, app_name)

            self.app = load_preview_app(self.project_dir, config=config)
            self.app.build()
            self.app.enable_hot_reload(["src"])

            self.server = PreviewServer(
                self.app,
                session,
                host=self.host,
                port=self.port,
                on_status=self._status,
            )
            _, bound_port = self.server.start()
            connect_host = resolve_connect_host(
                self.host, override=self.connect_host)
            uri = build_preview_uri(session, connect_host, bound_port)
            print_preview_banner(
                session=session,
                bind_host=self.host,
                connect_host=connect_host,
                port=bound_port,
                uri=uri,
                show_qr=self.show_qr,
            )
            try:
                self.server.serve_forever()
            except KeyboardInterrupt:
                click.echo("\nStopping Pydrud development server...")
            return 0
        finally:
            if self.server is not None:
                self.server.stop()
            if self.app is not None:
                self.app.stop()
            os.chdir(previous_cwd)

    @staticmethod
    def _status(event: str, data: dict) -> None:
        if event == "connected":
            client = data.get("client") or {}
            label = str(client.get("name") or "preview client")
            version = str(client.get("version") or "")
            if version:
                label += f" {version}"
            click.echo(
                f"\nConnected: {label} from {data.get('peer', 'unknown')}"
                f" (revision {data.get('revision', 0)})")
        elif event == "disconnected":
            click.echo("Disconnected. Waiting for Pydash to reconnect...")
        elif event == "rejected":
            click.echo(
                f"Rejected connection from {data.get('peer', 'unknown')}: "
                f"{data.get('code', 'invalid handshake')}",
                err=True,
            )
        elif event in {"connection_error", "server_error"}:
            click.echo(
                f"Preview connection error ({data.get('peer', 'unknown')}): "
                f"{data.get('error', 'unknown error')}",
                err=True,
            )


def load_preview_app(project_dir: str, *, config: Optional[dict] = None) -> App:
    """Import a generated project's entry point without starting Android."""
    root = os.path.abspath(project_dir)
    src = os.path.join(root, "src")
    if not os.path.isdir(src):
        raise click.ClickException(
            f"Project source directory not found: {src}")
    if src not in sys.path:
        sys.path.insert(0, src)
    importlib.invalidate_caches()

    module = None
    for name in ("app.main", "main"):
        try:
            module = importlib.import_module(name)
            break
        except ModuleNotFoundError as exc:
            # Only fall back when the entry module itself is absent. Missing
            # imports inside a real entrypoint should retain their traceback.
            if exc.name not in {name, name.split(".")[0]}:
                raise
    if module is None:
        raise click.ClickException(
            "No preview entrypoint found; expected src/app/main.py "
            "with a callable main(page)")
    target = getattr(module, "main", None)
    if not callable(target):
        raise click.ClickException(
            f"{module.__name__} must define a callable main(page)")

    config = config or load_project_config(root)
    title = str(
        getattr(module, "APP_NAME", "")
        or config.get("app_name")
        or Path(root).name)
    assets = str(config.get("assets_dir") or "assets")

    theme_seed = getattr(module, "THEME_SEED", None)
    if theme_seed:
        from pydrud.widgets.theme import Theme
        Theme.seed(str(theme_seed))

    app = App(
        target=target,
        title=title,
        assets_dir=assets,
        hot_reload=False,
        dev_server=False,
    )
    runtime = sys.modules.get("app.runtime")
    bind = getattr(runtime, "bind", None) if runtime else None
    if callable(bind):
        bind(app)
    router = getattr(module, "router", None)
    if router is None and runtime is not None:
        router = getattr(runtime, "router", None)
    if router is not None:
        app.attach_router(router)
    return app


def resolve_connect_host(bind_host: str, *, override: Optional[str] = None) -> str:
    """Choose the address a physical device can use for the QR payload."""
    if override:
        return str(override).strip().strip("[]")
    bind_host = str(bind_host).strip().strip("[]")
    if bind_host not in {"0.0.0.0", "::", ""}:
        return bind_host

    # Ask the routing table which interface would carry normal LAN traffic.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        candidate = str(probe.getsockname()[0])
        if candidate and not candidate.startswith("127."):
            return candidate
    except OSError:
        pass
    finally:
        probe.close()

    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        addresses = []
    for candidate in addresses:
        if candidate and not candidate.startswith("127."):
            return candidate
    return "127.0.0.1"


def _qr_matrix(payload: str) -> list[list[bool]]:
    """Return the QR modules for ``payload`` (``True`` == dark module).

    Pydrud ships a dependency-free encoder so ``pydrud dev`` always prints a
    scannable code. The third-party ``qrcode`` package is used when it happens
    to be installed, purely to stay identical with the builtin encoder.

    Error-correction level ``L`` keeps the symbol as small as possible, which
    is the right trade-off for a high-contrast code scanned point-blank off a
    monitor.
    """
    try:
        import qrcode
    except ImportError:
        return encode_qr_matrix(payload, error_correction="L", border=2)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return [[bool(cell) for cell in row] for row in qr.get_matrix()]


# Indentation the banner adds in front of every QR line, plus a safety margin.
_QR_INDENT = 4

# Symbols up to this many modules per side stay in the roomier half-block
# rendering (two modules per character cell); anything larger switches to the
# quarter-block rendering so the code keeps a normal, compact footprint.
_HALF_BLOCK_MAX_MODULES = 45

# Quadrant glyphs indexed by the four module bits (upper-left, upper-right,
# lower-left, lower-right) where a set bit means "dark module".
_QUADRANT_GLYPHS = " ▗▖▄▝▐▞▟▘▚▌▙▀▜▛█"


def _render_half_block(matrix: list[list[bool]], ansi: bool) -> list[str]:
    """One module per column, two module rows per text line."""
    rows = [list(row) for row in matrix]
    if len(rows) % 2:
        rows.append([False] * len(rows[0]))

    lines: list[str] = []
    for row in range(0, len(rows), 2):
        top, bottom = rows[row], rows[row + 1]
        if ansi:
            parts: list[str] = []
            last = None
            styles = {
                (True, True): ("\x1b[30;40m", " "),
                (False, False): ("\x1b[37;47m", " "),
                (True, False): ("\x1b[30;47m", "▀"),
                (False, True): ("\x1b[37;40m", "▀"),
            }
            for pair in zip(top, bottom):
                style, glyph = styles[pair]
                if style != last:
                    parts.append(style)
                    last = style
                parts.append(glyph)
            parts.append("\x1b[0m")
            lines.append("".join(parts))
        else:
            glyphs = {
                (True, True): "█",
                (False, False): " ",
                (True, False): "▀",
                (False, True): "▄",
            }
            lines.append("".join(glyphs[pair] for pair in zip(top, bottom)))
    return lines


def _render_quarter_block(matrix: list[list[bool]], ansi: bool) -> list[str]:
    """Two modules per column and per text line — half the width and height."""
    width = len(matrix[0])
    pad_col = width % 2
    rows = [list(row) + [False] * pad_col for row in matrix]
    width += pad_col
    if len(rows) % 2:
        rows.append([False] * width)

    lines: list[str] = []
    for row in range(0, len(rows), 2):
        top, bottom = rows[row], rows[row + 1]
        cells = []
        for col in range(0, width, 2):
            index = (
                (8 if top[col] else 0)
                | (4 if top[col + 1] else 0)
                | (2 if bottom[col] else 0)
                | (1 if bottom[col + 1] else 0)
            )
            cells.append(_QUADRANT_GLYPHS[index])
        line = "".join(cells)
        if ansi:
            # Dark modules as black foreground on a white background so the
            # code keeps proper contrast on any terminal colour scheme.
            line = f"\x1b[30;47m{line}\x1b[0m"
        lines.append(line)
    return lines


def terminal_qr(
    payload: str,
    *,
    ansi: Optional[bool] = None,
    max_width: Optional[int] = None,
) -> str:
    """Render a clean, square, scanner-friendly terminal QR code.

    In normal terminal widths, it uses half-block unicode characters (▀, ▄, █, space)
    where 1 character width and 0.5 line height form a 1:1 square module,
    ensuring the QR code is rendered as a clean square with width == height.
    On narrow terminals with max_width constraint, it falls back to
    compact quarter-block rendering to avoid terminal line-wrapping.
    """
    matrix = _qr_matrix(payload)
    if ansi is None:
        ansi = bool(getattr(sys.stdout, "isatty", lambda: False)())
    if max_width is None:
        try:
            max_width = shutil.get_terminal_size(fallback=(80, 24)).columns
        except (OSError, ValueError):  # pragma: no cover - defensive
            max_width = 80

    size = len(matrix[0]) if matrix else 0
    available = max(16, int(max_width) - _QR_INDENT)
    if size > available:
        lines = _render_quarter_block(matrix, ansi)
    else:
        lines = _render_half_block(matrix, ansi)
    return "\n".join(lines)


def print_preview_banner(
    *,
    session: PreviewSession,
    bind_host: str,
    connect_host: str,
    port: int,
    uri: str,
    show_qr: bool,
) -> None:
    """Print connection status without hiding the exact QR payload."""
    width = 66
    click.echo("\n" + "═" * width)
    click.secho("  Pydrud Dev · Live UI Preview", bold=True)
    click.echo("═" * width)
    click.echo(f"  Project    {session.project_name} ({session.project_id})")
    click.echo(f"  Listening  {bind_host}:{port}")
    click.echo(f"  Connect    {connect_host}:{port}")
    click.echo(f"  Session    {session.short_id}")
    if connect_host.startswith("127.") or connect_host == "localhost":
        click.secho(
            "  Warning    loopback is reachable only from this computer; "
            "use --connect-host for a phone.",
            fg="yellow",
        )
    if show_qr:
        click.echo("\n  Scan with Pydash:\n")
        for line in terminal_qr(uri).splitlines():
            click.echo("  " + line)
    click.echo("\n  Connection URI (contains a one-run bearer token):")
    click.echo(f"  {uri}")
    click.echo("\n  Keep this terminal open. Press Ctrl+C to stop.")
    click.echo("  Waiting for Pydash to connect...")
    click.echo("═" * width)


__all__ = [
    "PreviewRunner", "load_preview_app", "print_preview_banner",
    "resolve_connect_host", "terminal_qr",
]
