"""
Pydrud CLI — ``pydrud init``, ``run``, ``sync``, ``build``, ``clean``, ``doctor``.

Powered by Click.
"""

from __future__ import annotations
import os
import sys
import click

from pydrud import __version__
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
    """Pydrud — build native Android apps with Python.

    \b
    Quick start:
        pydrud init my_app
        cd my_app
        pydrud run
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
@click.option("--org", default="com.example", help="Android package / organisation prefix.")
@click.option("--min-sdk", default=24, help="Minimum Android API level.")
@click.option("--target-sdk", default=36, help="Target Android API level.", show_default=True)
@click.option("--accent", default=None, metavar="COLOR",
              help="Brand colour the whole UI is generated from, "
                   "e.g. --accent '#FF0EA5E9'.")
def init(name, org, min_sdk, target_sdk, accent):
    """Create a new Pydrud project."""
    from pydrud.commands.project import create_project
    create_project(name, org=org, min_sdk=min_sdk, target_sdk=target_sdk,
                   accent=accent)


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
@click.option("--release", is_flag=True, default=False, help="Build in release mode.")
@click.option("--watch", is_flag=True, default=False, help="Legacy flag: watch mode with hot reload (default behavior).")
@click.option("--no-interactive", is_flag=True, default=False, help="Disable interactive terminal shortcuts.")
def run(device, release, watch, no_interactive):
    """Build the APK, install, launch and start interactive Hot Reload on a connected device."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    builder = Builder(root)
    builder.run(device=device, release=release, watch=watch, interactive=not no_interactive)


@main.command()
@click.option("--release", is_flag=True, default=False, help="Produce a release APK.")
@click.option("--output", default=None, help="Output APK path.")
def build(release, output):
    """Build the APK only (no install)."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)

    builder = Builder(root)
    apk_path = builder.build(release=release)
    if not apk_path:
        sys.exit(1)

    if output:
        import shutil
        shutil.copy2(apk_path, output)
        click.echo(tui.ok_badge(f"Copied artifact to {output}"))


@main.command()
@click.option("--device", default=None, help="Target device ID.")
def clean(device):
    """Clean generated build artifacts."""
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
def dev(project_dir, host, port, connect_host, no_qr):
    """Run project Python locally for a Pydash live UI preview."""
    requested = os.path.abspath(project_dir)
    root = requested
    while not os.path.isfile(os.path.join(root, "pydrud.yaml")):
        parent = os.path.dirname(root)
        if parent == root:
            raise click.ClickException(
                f"Not a Pydrud project: {requested} (pydrud.yaml not found)")
        root = parent
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
    """Start interactive Hot Reload development runner."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
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
    issues = run_analysis(path)
    click.echo(format_report(issues, json_output=json_output))


# ──────────────────────────────────────────────────────────────────────────
# Python packages (Chaquopy pip)
# ──────────────────────────────────────────────────────────────────────────


@main.group()
def pip():
    """Manage Python packages bundled into the APK.

    \b
        pydrud pip add yt-dlp requests
        pydrud pip list
        pydrud pip search qr
        pydrud pip remove requests

    Only packages verified to work under Chaquopy on Android are accepted;
    pass --force to install something unverified anyway.
    """


def _project_or_exit() -> str:
    root = _find_project_root()
    if not root:
        _show_error("Not inside a Pydrud project.",
                    "Run this command from a directory containing pydrud.yaml.")
        sys.exit(1)
    return root


@pip.command("add")
@click.argument("packages", nargs=-1, required=True)
@click.option("--force", is_flag=True, default=False,
              help="Install a package that is not in the verified registry.")
@click.option("--no-sync", is_flag=True, default=False,
              help="Only record it in pydrud.toml; do not touch Gradle.")
def pip_add(packages, force, no_sync):
    """Add one or more packages (e.g. ``pydrud pip add yt-dlp``)."""
    from pydrud.commands.packages import PackageError, Requirements, sync_gradle

    root = _project_or_exit()
    _show_header("pip add", "Add Python packages",
                 "Recording Chaquopy-compatible dependencies for the Android build",
                 details=(("Project", os.path.basename(root)),))
    requirements = Requirements(root)
    added = []
    for requirement in packages:
        try:
            entry = requirements.add(requirement, force=force)
        except PackageError as exc:
            _show_error(str(exc))
            sys.exit(1)
        added.append(entry)
        warning = " · native wheel, increases APK size" if entry["native"] else ""
        click.echo(tui.add_badge(
            f"{entry['name']}{entry.get('spec', '')} — "
            f"{entry['description']}{warning}"))

    gradle_path = "not updated (--no-sync)"
    if not no_sync:
        try:
            path = sync_gradle(root)
            gradle_path = os.path.relpath(path, root)
            click.echo(tui.info_badge(f"Updated {gradle_path}"))
        except PackageError as exc:
            click.echo(tui.warn_badge(str(exc)), err=True)
    click.echo(tui.render_summary(
        f"{len(added)} package(s) ready",
        (("Gradle", gradle_path), ("Install", "next Android build")),
    ))


@pip.command("remove")
@click.argument("packages", nargs=-1, required=True)
def pip_remove(packages):
    """Remove packages from the project."""
    from pydrud.commands.packages import PackageError, Requirements, sync_gradle

    root = _project_or_exit()
    _show_header("pip remove", "Remove Python packages",
                 "Updating pydrud.toml and the generated Chaquopy build block",
                 details=(("Project", os.path.basename(root)),))
    requirements = Requirements(root)
    removed = 0
    for name in packages:
        if requirements.remove(name):
            click.echo(tui.remove_badge(name))
            removed += 1
        else:
            click.echo(tui.neutral_badge(f"{name} was not installed"))
    try:
        sync_gradle(root)
    except PackageError as exc:
        click.echo(tui.warn_badge(str(exc)), err=True)
    click.echo(tui.render_summary(
        f"Removed {removed} package(s)", (("Manifest", "pydrud.toml"),)
    ))


@pip.command("list")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="List every package Pydrud supports, not just this project's.")
@click.option("--category", default=None, help="Filter --all by category.")
def pip_list(show_all, category):
    """Show installed packages, or the whole verified registry."""
    from pydrud.commands.packages import by_category, installed_summary

    if show_all:
        _show_header("pip list", "Verified Android packages",
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
                ("PACKAGE", "WHEEL", "DESCRIPTION"),
                ((entry["name"], "native" if entry["native"] else "pure",
                  entry["description"]) for entry in entries),
            ))
            total += len(entries)
        click.echo(tui.render_summary(
            f"{total} verified packages",
            (("Native", "marked in the WHEEL column"),),
        ))
        return

    root = _project_or_exit()
    _show_header("pip list", "Project packages",
                 "Dependencies bundled into this application's APK",
                 details=(("Project", os.path.basename(root)),))
    rows = installed_summary(root)
    if not rows:
        click.echo(tui.neutral_badge(
            "No extra packages. Add one with 'pydrud pip add <name>'."))
        return
    click.echo(tui.render_table(
        ("PACKAGE", "VERSION", "DESCRIPTION"),
        ((row["name"], row["spec"], row["description"]) for row in rows),
    ))
    click.echo(tui.render_summary(
        f"{len(rows)} package(s)", (("Manifest", "pydrud.toml"),)
    ))


@pip.command("search")
@click.argument("query")
def pip_search(query):
    """Search the verified registry."""
    from pydrud.commands.packages import search

    _show_header("pip search", f"Package search · {query}",
                 "Searching Pydrud's verified Android package registry")
    results = search(query)
    if not results:
        click.echo(tui.warn_badge(
            f"Nothing matches {query!r}. Try 'pydrud pip list --all'."))
        return
    click.echo(tui.render_table(
        ("PACKAGE", "CATEGORY", "WHEEL", "DESCRIPTION"),
        ((entry["name"], entry["category"],
          "native" if entry["native"] else "pure", entry["description"])
         for entry in results),
    ))
    click.echo(tui.render_summary(
        f"{len(results)} match(es)", (("Query", query),)
    ))


@pip.command("sync")
def pip_sync():
    """Re-apply pydrud.toml to the Gradle build (after editing it by hand)."""
    from pydrud.commands.packages import PackageError, Requirements, sync_gradle

    root = _project_or_exit()
    _show_header("pip sync", "Synchronize Python packages",
                 "Applying pydrud.toml dependencies to the Chaquopy Gradle block",
                 details=(("Project", os.path.basename(root)),))
    try:
        path = sync_gradle(root)
    except PackageError as exc:
        _show_error(str(exc))
        sys.exit(1)
    click.echo(tui.render_summary(
        f"Synced {len(Requirements(root))} package(s)",
        (("Gradle", os.path.relpath(path, root)),),
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


@main.group()
def capabilities():
    """Manage generated Android capabilities in pydrud.yaml."""


@capabilities.command("add")
@click.argument("names", nargs=-1, required=True)
def capabilities_add(names):
    """Enable capabilities, e.g. ``pydrud capabilities add haptics``."""
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
def capabilities_list():
    """List capabilities enabled for this project."""
    from pydrud.commands.release import list_capabilities

    root = _project_or_exit()
    enabled = list_capabilities(root)
    _show_header("capabilities list", "Enabled Android capabilities",
                 details=(("Project", os.path.basename(root)),))
    if enabled:
        for name in enabled:
            click.echo(tui.neutral_badge(name))
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
