"""
Pydrud CLI — ``pydrud init``, ``run``, ``sync``, ``build``, ``clean``, ``doctor``.

Powered by Click.
"""

from __future__ import annotations
import os
import sys
import click

from pydrud import __version__


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
                with open(pyproject) as f:
                    if "[tool.pydrud]" in f.read():
                        return current
            except Exception:
                pass
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


@click.group()
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
    """Upgrade an existing project to this version of Pydrud.

    Rewrites the generated Android renderer, theme resources and the
    bundled runtime. Your app code in ``src/app/`` is left alone.
    """
    from pydrud.commands.project import sync_project

    root = _find_project_root()
    if not root:
        click.echo("Not inside a Pydrud project (no pydrud.yaml found).")
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
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
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
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
        sys.exit(1)

    builder = Builder(root)
    apk_path = builder.build(release=release)
    if not apk_path:
        sys.exit(1)

    click.echo(f"APK ready: {apk_path}")
    if output:
        import shutil
        shutil.copy2(apk_path, output)
        click.echo(f"Copied to: {output}")


@main.command()
@click.option("--device", default=None, help="Target device ID.")
def clean(device):
    """Clean generated build artifacts."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        click.echo("Error: not inside a Pydrud project", err=True)
        sys.exit(1)

    builder = Builder(root)
    builder.clean()


@main.command()
@click.option("--device", default=None, help="Target device ID (adb).")
@click.option("--release", is_flag=True, default=False, help="Build in release mode.")
@click.option("--no-interactive", is_flag=True, default=False, help="Disable interactive terminal shortcuts.")
def watch(device, release, no_interactive):
    """Start interactive Hot Reload development runner."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
        sys.exit(1)

    builder = Builder(root)
    builder.run(device=device, release=release, watch=True, interactive=not no_interactive)


@main.command()
def devices():
    """List connected Android devices."""
    import shutil as _shutil
    import subprocess

    if not _shutil.which("adb"):
        click.echo("adb not found in PATH. Install Android platform-tools.", err=True)
        sys.exit(1)
    result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    click.echo(result.stdout.strip() or "No devices found.")


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
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)",
                   err=True)
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
    requirements = Requirements(root)
    added = []
    for requirement in packages:
        try:
            entry = requirements.add(requirement, force=force)
        except PackageError as exc:
            click.echo(f"  [x] {exc}", err=True)
            sys.exit(1)
        added.append(entry)
        warning = "  (native wheel — adds a few MB per ABI)" if entry["native"] else ""
        click.echo(f"  [+] {entry['name']}{entry.get('spec', '')} "
                   f"— {entry['description']}{warning}")

    if not no_sync:
        try:
            path = sync_gradle(root)
            click.echo(f"\n  Updated {os.path.relpath(path, root)}")
        except PackageError as exc:
            click.echo(f"  [!] {exc}", err=True)
    click.echo(f"  {len(added)} package(s) will be installed on the next build.")


@pip.command("remove")
@click.argument("packages", nargs=-1, required=True)
def pip_remove(packages):
    """Remove packages from the project."""
    from pydrud.commands.packages import PackageError, Requirements, sync_gradle

    root = _project_or_exit()
    requirements = Requirements(root)
    for name in packages:
        if requirements.remove(name):
            click.echo(f"  [-] {name}")
        else:
            click.echo(f"  [ ] {name} was not installed")
    try:
        sync_gradle(root)
    except PackageError as exc:
        click.echo(f"  [!] {exc}", err=True)


@pip.command("list")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="List every package Pydrud supports, not just this project's.")
@click.option("--category", default=None, help="Filter --all by category.")
def pip_list(show_all, category):
    """Show installed packages, or the whole verified registry."""
    from pydrud.commands.packages import by_category, installed_summary

    if show_all:
        groups = by_category()
        if category:
            groups = {k: v for k, v in groups.items() if k == category}
            if not groups:
                click.echo(f"No such category: {category}", err=True)
                sys.exit(1)
        total = 0
        for name, entries in groups.items():
            click.echo(f"\n  {name.upper()}")
            for entry in entries:
                flag = "*" if entry["native"] else " "
                click.echo(f"   {flag} {entry['name']:<26} {entry['description']}")
                total += 1
        click.echo(f"\n  {total} verified packages  "
                   f"(* = native wheel, larger APK)")
        return

    root = _project_or_exit()
    rows = installed_summary(root)
    if not rows:
        click.echo("  No extra packages. Add one with 'pydrud pip add <name>'.")
        return
    for row in rows:
        click.echo(f"  {row['name']:<26} {row['spec']:<12} {row['description']}")
    click.echo(f"\n  {len(rows)} package(s) in pydrud.toml")


@pip.command("search")
@click.argument("query")
def pip_search(query):
    """Search the verified registry."""
    from pydrud.commands.packages import search

    results = search(query)
    if not results:
        click.echo(f"  Nothing matches {query!r}. "
                   f"Try 'pydrud pip list --all'.")
        return
    for entry in results:
        flag = "*" if entry["native"] else " "
        click.echo(f"   {flag} {entry['name']:<26} [{entry['category']}] "
                   f"{entry['description']}")


@pip.command("sync")
def pip_sync():
    """Re-apply pydrud.toml to the Gradle build (after editing it by hand)."""
    from pydrud.commands.packages import PackageError, Requirements, sync_gradle

    root = _project_or_exit()
    try:
        path = sync_gradle(root)
    except PackageError as exc:
        click.echo(f"  [x] {exc}", err=True)
        sys.exit(1)
    click.echo(f"  Synced {len(Requirements(root))} package(s) into "
               f"{os.path.relpath(path, root)}")


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
    if password is None:
        password = click.prompt("Keystore password", hide_input=True,
                                confirmation_prompt=True)
    ok_ = create_keystore(root, alias=alias, password=password,
                          validity=validity, dname=dname)
    sys.exit(0 if ok_ else 1)


@main.command()
@click.option("--source", default=None,
              help="Source image (1024x1024 PNG recommended).")
@click.option("--background", default="#FF6366F1", help="Splash/adaptive background.")
@click.option("--splash-text", default=None, help="Text shown on the splash screen.")
def icons(source, background, splash_text):
    """Generate launcher icons and a splash screen from one image."""
    from pydrud.commands.release import generate_icons

    root = _project_or_exit()
    written = generate_icons(root, source=source, background=background,
                             splash_text=splash_text)
    click.echo(f"  {len(written)} resource file(s) written.")


@main.group()
def permissions():
    """Add or remove Android permissions in the manifest."""


@permissions.command("add")
@click.argument("names", nargs=-1, required=True)
def permissions_add(names):
    """Add permissions, e.g. ``pydrud permissions add camera location``."""
    from pydrud.commands.release import update_permissions

    root = _project_or_exit()
    added = update_permissions(root, add=list(names))
    for name in added:
        click.echo(f"  [+] {name}")


@permissions.command("remove")
@click.argument("names", nargs=-1, required=True)
def permissions_remove(names):
    """Remove permissions from the manifest."""
    from pydrud.commands.release import update_permissions

    root = _project_or_exit()
    removed = update_permissions(root, remove=list(names))
    for name in removed:
        click.echo(f"  [-] {name}")


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
    path = build_docs(root, output)
    click.echo(f"  Docs written to {path}")
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
