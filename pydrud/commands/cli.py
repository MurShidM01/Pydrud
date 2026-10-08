"""
Pydrud CLI — ``pydrud create``, ``init``, ``run``, ``sync``, ``build``, ``clean``, ``doctor``.

Powered by Click.
"""

from __future__ import annotations
import os
import sys
import click

from pydrud import __version__
from pydrud.runtime.runtime import Runtime
from pydrud.utils import tui


# Ensure the project root is in sys.path when running.
_project_path: str | None = None


def _find_project_root() -> str | None:
    """Walk up from cwd looking for a ``pydrud.yaml`` or ``pyproject.toml``
    with a [tool.pydrud] section."""
    cwd = os.getcwd()
    current = cwd
    while True:
        if os.path.isfile(os.path.join(current, "pydrud.yaml")):
            return current
        if os.path.isfile(os.path.join(current, "pydrud.yml")):
            return current
        # Check pyproject.toml for [tool.pydrud]
        pyproject = os.path.join(current, "pyproject.toml")
        if os.path.isfile(pyproject):
            try:
                with open(pyproject, encoding="utf-8") as f:
                    if "[tool.pydrud]" in f.read():
                        return current
            except Exception:
                pass
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


class _PydrudCommand(click.Command):
    """Command help with the same branded surface as command execution."""

    def format_help(self, ctx, formatter):
        formatter.write(tui.render_command_header(
            ctx.info_name or "help", "Command reference",
            subtitle=self.help or self.short_help or "Pydrud command",
        ))
        super().format_help(ctx, formatter)


class _PydrudGroup(click.Group):
    """Click group with the same branded header as the interactive runner."""

    command_class = _PydrudCommand
    group_class = type

    def format_help(self, ctx, formatter):
        formatter.write(tui.render_brand_banner(__version__))
        super().format_help(ctx, formatter)


@click.group(cls=_PydrudGroup, context_settings={
    "help_option_names": ["-h", "--help"],
    "max_content_width": 100,
})
@click.version_option(version=__version__, prog_name="pydrud")
def main():
    """Pydrud — build cross-platform Python interfaces and Android apps.

    \b
    Quick start:
        pydrud create my_app
        cd my_app
        pydrud dev
    """
    pass


def _show_header(command: str, title: str, subtitle: str = "", *,
                 details=()) -> None:
    click.echo(tui.render_command_header(
        command, title, subtitle=subtitle, details=tuple(details)
    ))


def _show_error(message: str, hint: str = "") -> None:
    click.echo(tui.error_badge(message), err=True)
    if hint:
        click.echo(tui.info_badge(hint), err=True)


@main.command()
@click.argument("name", default="my_app")
@click.option("--org", default="com.example", help="Package / organisation prefix.")
@click.option("--min-sdk", default=24, help="Minimum Android API level (Chaquopy only).")
@click.option("--target-sdk", default=36,
              help="Target Android API level (Chaquopy only).", show_default=True)
@click.option("--accent", default=None, metavar="COLOR",
              help="Brand colour the whole UI is generated from, "
                   "e.g. --accent '#FF0EA5E9'.")
@click.option("--runtime", "runtime_", default=None,
              type=click.Choice(["pydash", "chaquopy"], case_sensitive=False),
              help="Runtime for the new project. Defaults to pydash (live preview).")
def create(name, org, min_sdk, target_sdk, accent, runtime_):
    """Create a new Pydrud project.

    By default creates a pydash project (live preview — no Android
    toolchain required). Pass ``--runtime chaquopy`` for a standalone
    Android APK build path, or add the Android platform later with
    ``pydrud init android`` inside the project.
    """
    from pydrud.commands.project import create_project
    create_project(name, org=org, min_sdk=min_sdk, target_sdk=target_sdk,
                   runtime=runtime_ or "pydash", accent=accent)


@main.command()
@click.argument("platform", required=False, default=None)
@click.option("--backend", default="chaquopy",
              type=click.Choice(["chaquopy", "host", "none"],
                                case_sensitive=False),
              help="Android Python runtime backend. 'chaquopy' embeds CPython "
                   "in the APK; 'host' runs Python on your machine; 'none' "
                   "builds a renderer with no runtime.")
def init(platform, backend):
    """Add a native platform to this project (``pydrud init android``).

    ``android`` builds a standalone target. By default it embeds Python with
    Chaquopy so the APK runs fully offline; pass ``--backend host`` (no
    on-device interpreter) or ``--backend none`` (renderer only) to build
    without Chaquopy. Run inside a project created with ``pydrud create``.
    Only ``android`` is supported in this release; ios, linux, windows, web
    and macos are reserved for future platforms.
    """
    from pydrud.commands.project import (
        FUTURE_PLATFORMS, SUPPORTED_PLATFORMS, init_platform,
    )

    if not platform:
        root = _find_project_root()
        _show_header("init", "Add a native platform",
                     "Generate a native shell from this project's configuration",
                     details=(("Project", os.path.basename(root) if root else "—"),))
        for name in SUPPORTED_PLATFORMS:
            present = root and os.path.isdir(os.path.join(root, name))
            click.echo(tui.neutral_badge(
                f"{name} — {'already added' if present else 'available'}"))
        click.echo(tui.neutral_badge(
            "planned: " + ", ".join(n for n in FUTURE_PLATFORMS
                                    if n != "window")))
        click.echo(tui.render_next_steps((
            ("pydrud init android", "add the Android platform"),
            ("pydrud create <name>", "create a new app instead"),
        )))
        return

    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        if platform in FUTURE_PLATFORMS:
            _show_error(f"Platform '{platform}' is not available yet.",
                        "Only 'android' is supported in this release.")
            sys.exit(1)
        _show_error(f"Unknown platform '{platform}'.",
                    "To create a new app, use 'pydrud create <name>'. "
                    "To add Android to this project, use 'pydrud init android'.")
        sys.exit(1)

    root = _project_or_exit()
    if not init_platform(root, platform, backend=backend.lower()):
        sys.exit(1)


@main.command()
@click.option("--no-runtime", is_flag=True, default=False,
              help="Only refresh the Java layer, keep the bundled Python runtime.")
def sync(no_runtime):
    """Apply pydrud.yaml and upgrade the generated Android project.

    Rewrites managed Java, manifest, Gradle, theme and generated metadata,
    plus the bundled runtime. Your app code in ``src/app/`` is left alone.
    """
    from pydrud.commands.project import sync_project

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)
    if not sync_project(root, update_runtime=not no_runtime):
        sys.exit(1)


@main.command()
@click.option("--device", default=None, help="Target device ID (adb).")
@click.option("--debug", "debug", is_flag=True, default=False,
              help="Build and install the debuggable debug APK (the default).")
@click.option("--release", is_flag=True, default=False, help="Build in release mode.")
@click.option("--watch", is_flag=True, default=False, help="Legacy flag: watch mode with hot reload (default behavior).")
@click.option("--no-interactive", is_flag=True, default=False, help="Disable interactive terminal shortcuts.")
def run(device, debug, release, watch, no_interactive):
    """Build the APK, install, launch and start interactive Hot Reload on a connected device."""
    _require_android_target("run")
    from pydrud.commands.builder import Builder

    if release and debug:
        _show_error("Pass either --debug or --release, not both.",
                    "Debug is the default: 'pydrud run' and "
                    "'pydrud run --debug' are the same thing.")
        sys.exit(2)

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    builder = Builder(root)
    builder.run(device=device, release=release, watch=watch,
                interactive=not no_interactive, debug=debug)


@main.command()
@click.option("--debug", "debug", is_flag=True, default=False,
              help="Produce a debuggable debug APK (the default variant).")
@click.option("--release", is_flag=True, default=False, help="Produce a release APK.")
@click.option("--output", default=None, help="Output APK path.")
def build(debug, release, output):
    """Build the APK only (no install).

    ``pydrud build`` produces a debug APK. Pass ``--debug`` to say so
    explicitly (handy in scripts and CI logs), or ``--release`` for a
    signed release APK.
    """
    _require_android_target("build")
    from pydrud.commands.builder import Builder

    if release and debug:
        _show_error("Pass either --debug or --release, not both.",
                    "Debug is the default: 'pydrud build' and "
                    "'pydrud build --debug' are the same thing.")
        sys.exit(2)

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    builder = Builder(root)
    apk_path = builder.build(release=release, debug=debug)
    if not apk_path:
        sys.exit(1)

    if output:
        import shutil
        apks = builder.last_apks or [apk_path]
        # A split build produces several APKs. Treat `--output` as a
        # directory in that case so nothing is silently dropped; a plain
        # build keeps the original "copy to this path" behaviour.
        if len(apks) > 1 and (output.endswith(("/", os.sep)) or os.path.isdir(output)):
            os.makedirs(output, exist_ok=True)
            for path in apks:
                shutil.copy2(path, os.path.join(output, os.path.basename(path)))
            click.echo(tui.ok_badge(f"Copied {len(apks)} artifacts to {output}"))
        else:
            shutil.copy2(apk_path, output)
            click.echo(tui.ok_badge(f"Copied artifact to {output}"))


@main.command()
@click.option("--device", default=None, help="Target device ID.")
def clean(device):
    """Clean generated build artifacts."""
    _require_android_target("clean")
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    builder = Builder(root)
    builder.clean()


@main.command()
@click.argument("project_dir", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--host", default="0.0.0.0", show_default=True,
    help="Interface to bind. The default exposes preview on the local network.",
)
@click.option(
    "--port", default=8597, show_default=True,
    type=click.IntRange(1, 65535), help="Preview server TCP port.",
)
@click.option(
    "--connect-host", default=None, metavar="HOST",
    help="Address encoded in the QR code (useful for VPNs or multiple NICs).",
)
@click.option("--no-qr", is_flag=True, help="Print the connection URI without a QR code.")
@click.option(
    "--bridge", is_flag=True,
    help="Serve a host-backend APK over the device bridge instead of Pydash.",
)
@click.option(
    "--device", default=None, metavar="SERIAL",
    help="Device serial for 'adb reverse' (default: the only attached device).",
)
@click.option(
    "--no-reverse", is_flag=True,
    help="Skip the automatic 'adb reverse' port forward.",
)
def dev(project_dir, host, port, connect_host, no_qr, bridge, device, no_reverse):
    """Run project Python locally for a Pydash live UI preview."""
    requested = os.path.abspath(project_dir)
    root = requested
    while not os.path.isfile(os.path.join(root, "pydrud.yaml")):
        parent = os.path.dirname(root)
        if parent == root:
            raise click.ClickException(
                f"Not a Pydrud project: {requested} (pydrud.yaml not found)")
        root = parent

    if bridge:
        from pydrud.commands.bridge import BridgeRunner

        try:
            BridgeRunner(
                root,
                host=host if host != "0.0.0.0" else "127.0.0.1",
                port=port,
                device=device,
                reverse=not no_reverse,
            ).run()
        except click.ClickException:
            raise
        except (OSError, ValueError) as exc:
            raise click.ClickException(
                f"Could not start the device bridge: {exc}") from exc
        return

    from pydrud.commands.preview import PreviewRunner

    try:
        PreviewRunner(
            root,
            host=host,
            port=port,
            connect_host=connect_host,
            show_qr=not no_qr,
        ).run()
    except click.ClickException:
        raise
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Could not start preview server: {exc}") from exc


@main.command()
@click.option("--device", default=None, help="Target device ID (adb).")
@click.option("--release", is_flag=True, default=False, help="Build in release mode.")
@click.option("--no-interactive", is_flag=True, default=False, help="Disable interactive terminal shortcuts.")
def watch(device, release, no_interactive):
    """Start the Chaquopy Android Hot Reload runner."""
    _require_android_target("watch")
    from pydrud.commands.builder import Builder
    from pydrud.commands.project import android_is_standalone

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    if not android_is_standalone(root):
        _show_error("'pydrud watch' pushes code to on-device Python, but "
                    "this Android target has no embedded interpreter.",
                    "Run 'pydrud init android' (or 'pydrud sync') to "
                    "generate the standalone shell.")
        sys.exit(1)
    builder = Builder(root)
    builder.run(device=device, release=release, watch=True, interactive=not no_interactive)


@main.command()
def devices():
    """List connected Android devices."""
    import shutil as _shutil
    import subprocess

    _show_header("devices", "Connected Android devices",
                 "Discovering phones and emulators available through ADB")
    if not _shutil.which("adb"):
        _show_error("ADB was not found in PATH.",
                    "Install Android platform-tools, then run pydrud doctor.")
        sys.exit(1)
    result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        _show_error("ADB could not list devices.",
                    (result.stderr or result.stdout or "Run pydrud doctor.").strip())
        sys.exit(1)
    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        fields = line.split()
        rows.append((fields[0], fields[1] if len(fields) > 1 else "unknown",
                     " ".join(fields[2:]) or "—"))
    if rows:
        click.echo(tui.render_table(("DEVICE", "STATE", "DETAILS"), rows))
        click.echo(tui.render_summary(
            f"{len(rows)} device(s) available", (("ADB", "ready"),)
        ))
    else:
        click.echo(tui.warn_badge("No devices or emulators are connected."))
        click.echo(tui.render_next_steps((
            ("adb devices", "verify the connection"),
            ("pydrud run", "launch after a device is available"),
        )))


@main.command()
def doctor():
    """Check the development environment for required tools."""
    from pydrud.commands.doctor import run_doctor
    run_doctor()


@main.command()
@click.option("--path", default="src", help="Source directory to analyze.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
def analyze(path, json_output):
    """Statically analyze Pydrud Python code for common issues."""
    from pydrud.commands.analyzer import run_analysis, format_report
    from pydrud.runtime.runtime import resolve_runtime

    root = _find_project_root()
    runtime = resolve_runtime(root).runtime.value if root else "pydash"
    issues = run_analysis(path, runtime=runtime)
    click.echo(format_report(issues, json_output=json_output))


# ──────────────────────────────────────────────────────────────────────────
# Python packages (runtime-aware)
# ──────────────────────────────────────────────────────────────────────────


@main.group()
def pip():
    """Manage Python packages for this project.

    \b
        pydrud pip add yt-dlp requests
        pydrud pip list
        pydrud pip search qr
        pydrud pip remove requests
        pydrud pip sync

    Chaquopy projects: verified packages are bundled into the APK at build time.
    Pydash projects: any valid host dependency can be recorded; install it in
    the Python environment used by ``pydrud dev``.
    """


def _project_or_exit() -> str:
    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)
    return root


def _require_android_target(command: str) -> None:
    """Exit with a helpful message when *command* needs the Android target.

    Any non-pydash runtime (chaquopy, host, none) produces an Android app
    binary, so this only rejects projects that have no Android target at all.
    """
    from pydrud.runtime.runtime import resolve_runtime
    descriptor = resolve_runtime(_project_or_exit())
    if descriptor.runtime is Runtime.PYDASH:
        if command in {"run", "build", "clean"}:
            message = (
                f"'pydrud {command}' builds an Android app binary, but this "
                "project runs in pydash mode (no binary is produced)."
            )
        else:
            message = (
                f"'pydrud {command}' requires an Android target; this project "
                "runs in pydash mode and has no Android project."
            )
        _show_error(
            message,
            hint=(
                "Use 'pydrud dev' for live preview, or add the Android "
                "platform with 'pydrud init android'."
            ),
        )
        sys.exit(1)


def _resolve_pip_backend(project_dir: str):
    """Resolve the runtime and return the matching PackageBackend."""
    from pydrud.runtime.runtime import resolve_runtime
    from pydrud.commands.packages import get_backend
    descriptor = resolve_runtime(project_dir)
    return get_backend(descriptor.runtime.value), descriptor.runtime.value


@pip.command("add")
@click.argument("packages", nargs=-1, required=True)
@click.option("--force", is_flag=True, default=False,
              help="Allow an unverified package for Chaquopy builds; "
                   "Pydash accepts host dependencies without registry checks.")
@click.option("--no-sync", is_flag=True, default=False,
              help="Only record it in pydrud.toml; do not touch Gradle.")
def pip_add(packages, force, no_sync):
    """Add one or more packages (e.g. ``pydrud pip add yt-dlp``)."""
    root = _project_or_exit()
    backend, runtime = _resolve_pip_backend(root)
    subtitle = ("Recording dependencies for the Android build"
                if runtime == "chaquopy" else
                "Recording host dependencies (not installed automatically)")
    _show_header("pip add", "Add Python packages", subtitle,
                 details=(("Project", os.path.basename(root)),
                          ("Runtime", runtime)))
    added = []
    for requirement in packages:
        result = backend.add(root, requirement, force=force)
        if not result.success:
            _show_error(result.message)
            sys.exit(1)
        entry = result.details or {}
        added.append(entry)
        cat = entry.get("support_category", "native_equivalent")
        warning = ""
        if runtime == "pydash":
            warning = " · recorded only; install in the host Python environment"
        elif cat == "device_native":
            warning = " · native wheel, increases APK size"
        elif cat == "host_only":
            warning = " · host-only package"
        click.echo(tui.add_badge(
            f"{entry['name']}{entry.get('spec', '')} — "
            f"{entry['description']}{warning}"))

    gradle_info = "—"
    if runtime == "chaquopy" and not no_sync:
        result = backend.sync_gradle(root)
        if result.success:
            gradle_info = "updated"
        else:
            click.echo(tui.warn_badge(result.message), err=True)
    elif runtime == "pydash":
        gradle_info = "not applicable (pydash)"
    click.echo(tui.render_summary(
        f"{len(added)} package(s) ready",
        (("Gradle", gradle_info),
         ("Install", "next Android build" if runtime == "chaquopy" else "host run")),
    ))


@pip.command("remove")
@click.argument("packages", nargs=-1, required=True)
def pip_remove(packages):
    """Remove packages from the project."""
    root = _project_or_exit()
    backend, runtime = _resolve_pip_backend(root)
    subtitle = (
        "Updating pydrud.toml and the generated Chaquopy build block"
        if runtime == "chaquopy" else
        "Removing a host-side declaration; the Python environment is unchanged"
    )
    _show_header("pip remove", "Remove Python packages", subtitle,
                 details=(("Project", os.path.basename(root)),
                          ("Runtime", runtime)))
    removed = 0
    for name in packages:
        result = backend.remove(root, name)
        if result.success:
            click.echo(tui.remove_badge(name))
            removed += 1
        else:
            click.echo(tui.neutral_badge(name))
    if runtime == "chaquopy":
        result = backend.sync_gradle(root)
        if not result.success:
            click.echo(tui.warn_badge(result.message), err=True)
    click.echo(tui.render_summary(
        f"Removed {removed} package(s)", (("Manifest", "pydrud.toml"),)
    ))


@pip.command("list")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="List every package Pydrud supports, not just this project's.")
@click.option("--category", default=None, help="Filter --all by category.")
def pip_list(show_all, category):
    """Show installed packages, or the whole verified registry."""
    from pydrud.commands.packages import by_category

    if show_all:
        _show_header("pip list", "Verified packages",
                     "Packages tested with Chaquopy and available to Pydrud apps",
                     details=(("Filter", category or "all categories"),))
        groups = by_category()
        if category:
            groups = {k: v for k, v in groups.items() if k == category}
            if not groups:
                _show_error(f"No such package category: {category}")
                sys.exit(1)
        total = 0
        for name, entries in groups.items():
            click.echo(tui.render_section(name.upper()))
            click.echo(tui.render_table(
                ("PACKAGE", "SUPPORT", "DESCRIPTION"),
                ((entry["name"], entry.get("support_category", "native_equivalent"),
                  entry["description"]) for entry in entries),
            ))
            total += len(entries)
        click.echo(tui.render_summary(
            f"{total} verified packages",
            (("Support", "native_equivalent | device_native | host_only"),),
        ))
        return

    root = _project_or_exit()
    backend, runtime = _resolve_pip_backend(root)
    rows = backend.list_packages(root)
    if not rows:
        click.echo(tui.neutral_badge(
            "No extra packages. Add one with 'pydrud pip add <name>'."))
        return
    click.echo(tui.render_table(
        ("PACKAGE", "VERSION", "SUPPORT", "DESCRIPTION"),
        ((row["name"], row["spec"],
          row.get("support_category", "native_equivalent"),
          row["description"]) for row in rows),
    ))
    click.echo(tui.render_summary(
        f"{len(rows)} package(s)", (("Manifest", "pydrud.toml"),
                                     ("Runtime", runtime))))


@pip.command("search")
@click.argument("query")
def pip_search(query):
    """Search the verified registry."""
    from pydrud.commands.packages import search

    _show_header(
        "pip search", f"Package search · {query}",
        "Searching Chaquopy's verified catalogue; Pydash also accepts "
        "other host-side PyPI dependencies",
    )
    results = search(query)
    if not results:
        click.echo(tui.warn_badge(
            f"Nothing matches {query!r}. Try 'pydrud pip list --all'."))
        return
    click.echo(tui.render_table(
        ("PACKAGE", "CATEGORY", "SUPPORT", "DESCRIPTION"),
        ((entry["name"], entry["category"],
          entry.get("support_category", "native_equivalent"),
          entry["description"])
         for entry in results),
    ))
    click.echo(tui.render_summary(
        f"{len(results)} match(es)", (("Query", query),)
    ))


@pip.command("sync")
def pip_sync():
    """Re-apply pydrud.toml to the build system (after editing it by hand)."""
    from pydrud.commands.packages import Requirements

    root = _project_or_exit()
    backend, runtime = _resolve_pip_backend(root)
    if runtime == "pydash":
        result = backend.sync_gradle(root)
        _show_header("pip sync", "Synchronize Python packages",
                     result.message,
                     details=(("Project", os.path.basename(root)),
                              ("Runtime", runtime)))
        return
    _show_header("pip sync", "Synchronize Python packages",
                 "Applying pydrud.toml dependencies to the Chaquopy Gradle block",
                 details=(("Project", os.path.basename(root)),
                          ("Runtime", runtime)))
    result = backend.sync_gradle(root)
    if not result.success:
        _show_error(result.message)
        sys.exit(1)
    count = len(Requirements(root))
    click.echo(tui.render_summary(
        f"Synced {count} package(s)",
        (("Gradle", "updated"),),
    ))


# ──────────────────────────────────────────────────────────────────────────
# Distribution
# ──────────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--alias", default="release", help="Key alias inside the keystore.")
@click.option("--password", default=None, help="Keystore password (prompted if omitted).")
@click.option("--validity", default=10000, help="Validity in days.")
@click.option("--dname", default=None, help="X.500 distinguished name.")
def keygen(alias, password, validity, dname):
    """Create an upload keystore and wire it into release builds."""
    _require_android_target("keygen")
    from pydrud.commands.release import create_keystore

    root = _project_or_exit()
    _show_header("keygen", "Create an Android upload key",
                 "Generating release-signing credentials for Google Play",
                 details=(("Alias", alias), ("Validity", f"{validity} days")))
    if password is None:
        password = click.prompt("Keystore password", hide_input=True,
                                confirmation_prompt=True)
    ok_ = create_keystore(root, alias=alias, password=password,
                          validity=validity, dname=dname)
    sys.exit(0 if ok_ else 1)


@main.command()
@click.option("--source", default=None,
              help="Source image (1024x1024 PNG recommended).")
@click.option("--background", default=None,
              help="Adaptive icon background colour (default: sampled "
                   "from the source art).")
def icons(source, background):
    """Generate launcher, round and adaptive icons from one image.

    The splash screen is not touched: it is a customisable screen that
    follows the app theme (see the generated themes.xml), not a surface
    for the launcher icon.
    """
    _require_android_target("icons")
    from pydrud.commands.release import generate_icons

    root = _project_or_exit()
    _show_header("icons", "Generate Android app artwork",
                 "Creating launcher, round and adaptive icon resources",
                 details=(("Source", source or "generated lettermark"),
                          ("Background", background or "auto (from source)")))
    written = generate_icons(root, source=source, background=background)
    click.echo(tui.render_summary(
        f"{len(written)} resource file(s) written",
        (("Output", "android/app/src/main/res"),),
        success=bool(written),
    ))


@main.group()
def permissions():
    """Manage Android permissions in YAML and the generated manifest."""


@permissions.command("add")
@click.argument("names", nargs=-1, required=True)
def permissions_add(names):
    """Add permissions, e.g. ``pydrud permissions add camera location``."""
    _require_android_target("permissions add")
    from pydrud.commands.release import update_permissions

    root = _project_or_exit()
    _show_header("permissions add", "Add Android permissions",
                 "Updating pydrud.yaml and AndroidManifest.xml",
                 details=(("Project", os.path.basename(root)),))
    added = update_permissions(root, add=list(names))
    for name in added:
        click.echo(tui.add_badge(name))
    if not added:
        click.echo(tui.neutral_badge("All requested permissions were already present."))
    click.echo(tui.render_summary(
        f"Added {len(added)} permission(s)", (("Source", "pydrud.yaml"),)
    ))


@permissions.command("remove")
@click.argument("names", nargs=-1, required=True)
def permissions_remove(names):
    """Remove permissions from the manifest."""
    _require_android_target("permissions remove")
    from pydrud.commands.release import update_permissions

    root = _project_or_exit()
    _show_header("permissions remove", "Remove Android permissions",
                 "Updating pydrud.yaml and AndroidManifest.xml",
                 details=(("Project", os.path.basename(root)),))
    removed = update_permissions(root, remove=list(names))
    for name in removed:
        click.echo(tui.remove_badge(name))
    if not removed:
        click.echo(tui.neutral_badge("None of the requested permissions were present."))
    click.echo(tui.render_summary(
        f"Removed {len(removed)} permission(s)", (("Source", "pydrud.yaml"),)
    ))


@permissions.command("list")
@click.option("--all", "show_all", is_flag=True,
              help="Show every permission alias Pydrud knows.")
def permissions_list(show_all: bool):
    """List the manifest permissions, or every known permission alias.

    The counterpart to ``capabilities list`` (DOC-001).
    """
    from pydrud.commands.release import PERMISSIONS, list_permissions

    root = _project_or_exit()
    enabled = set(list_permissions(root))
    title = ("Every permission Pydrud knows" if show_all
             else "Permissions in AndroidManifest.xml")
    _show_header("permissions list", title,
                 details=(("Project", os.path.basename(root)),))
    if show_all:
        for alias in sorted(PERMISSIONS):
            canonical = PERMISSIONS[alias].rsplit(".", 1)[-1]
            marker = "[enabled] " if canonical in enabled else ""
            click.echo(tui.neutral_badge(f"{marker}{alias} — {canonical}"))
    elif enabled:
        for name in sorted(enabled):
            click.echo(tui.neutral_badge(name))
    else:
        click.echo(tui.neutral_badge(
            "No permissions declared in AndroidManifest.xml."))
    click.echo(tui.render_summary(
        f"{len(enabled)} permission(s) in the manifest",
        (("Source", "AndroidManifest.xml"),),
    ))


@main.group()
def capabilities():
    """Manage generated Android capabilities in pydrud.yaml."""


@capabilities.command("add")
@click.argument("names", nargs=-1, required=True)
def capabilities_add(names):
    """Enable capabilities, e.g. ``pydrud capabilities add haptics``."""
    _require_android_target("capabilities add")
    from pydrud.commands.release import update_capabilities

    root = _project_or_exit()
    _show_header("capabilities add", "Enable Android capabilities",
                 "Updating pydrud.yaml and generated manifest permissions",
                 details=(("Project", os.path.basename(root)),))
    try:
        added = update_capabilities(root, add=list(names))
    except ValueError as exc:
        # Click turns this into a compact, user-facing error rather than a
        # raw Python traceback. In particular it explains the frequent
        # camera-vs-capability mix-up with the exact replacement command.
        raise click.UsageError(str(exc)) from exc
    for name in added:
        click.echo(tui.add_badge(name))
    if not added:
        click.echo(tui.neutral_badge("All requested capabilities were already enabled."))
    click.echo(tui.render_summary(
        f"Enabled {len(added)} capability/capabilities",
        (("Source", "pydrud.yaml"), ("Next", "pydrud sync after manual YAML edits")),
    ))


@capabilities.command("remove")
@click.argument("names", nargs=-1, required=True)
def capabilities_remove(names):
    """Disable generated capabilities."""
    _require_android_target("capabilities remove")
    from pydrud.commands.release import update_capabilities

    root = _project_or_exit()
    _show_header("capabilities remove", "Disable Android capabilities",
                 "Updating pydrud.yaml and generated manifest permissions",
                 details=(("Project", os.path.basename(root)),))
    try:
        removed = update_capabilities(root, remove=list(names))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    for name in removed:
        click.echo(tui.remove_badge(name))
    if not removed:
        click.echo(tui.neutral_badge("None of the requested capabilities were enabled."))
    click.echo(tui.render_summary(
        f"Disabled {len(removed)} capability/capabilities",
        (("Source", "pydrud.yaml"),),
    ))


@capabilities.command("list")
@click.option("--all", "show_all", is_flag=True,
              help="Show every supported capability and its description.")
def capabilities_list(show_all: bool):
    """List enabled capabilities, or all supported capability bundles."""
    from pydrud.commands.release import (CAPABILITY_DESCRIPTIONS,
                                         list_capabilities)

    root = _project_or_exit()
    enabled = set(list_capabilities(root))
    title = "Supported Android capabilities" if show_all else "Enabled Android capabilities"
    _show_header("capabilities list", title,
                 details=(("Project", os.path.basename(root)),))
    names = sorted(CAPABILITY_DESCRIPTIONS if show_all else enabled)
    if names:
        for name in names:
            marker = "[enabled] " if name in enabled else ""
            description = CAPABILITY_DESCRIPTIONS.get(name, "")
            click.echo(tui.neutral_badge(f"{marker}{name} — {description}"))
    else:
        click.echo(tui.neutral_badge("No optional capabilities enabled."))


# ──────────────────────────────────────────────────────────────────────────
# Developer experience
# ──────────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--output", default="docs", help="Output directory.")
@click.option("--serve", is_flag=True, default=False,
              help="Serve the docs on http://localhost:8000 afterwards.")
def docs(output, serve):
    """Generate a static HTML API reference for your app and Pydrud."""
    from pydrud.commands.docs import build_docs, serve_docs

    root = _find_project_root() or os.getcwd()
    _show_header("docs", "Build API documentation",
                 "Generating an offline reference for the project",
                 details=(("Project", os.path.basename(root)), ("Output", output)))
    path = build_docs(root, output)
    click.echo(tui.render_summary(
        "Documentation generated", (("Output", path),)
    ))
    if serve:
        serve_docs(path)


@main.command()
@click.option("--port", default=8595, help="Bridge port the app is using.")
@click.option("--tree", is_flag=True, default=False, help="Dump the widget tree and exit.")
@click.option("--watch", "follow", is_flag=True, default=False,
              help="Stream bridge traffic live.")
def inspect(port, tree, follow):
    """Inspect a running app: widget tree, events and performance."""
    from pydrud.commands.inspector import run_inspector

    run_inspector(port=port, dump_tree=tree, follow=follow)
