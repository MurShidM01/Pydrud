"""
Pydrud CLI — ``pydrud init``, ``run``, ``build``, ``clean``, ``doctor``.

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
@click.option("--target-sdk", default=35, help="Target Android API level.", show_default=True)
def init(name, org, min_sdk, target_sdk):
    """Create a new Pydrud project."""
    from pydrud.commands.project import create_project
    create_project(name, org=org, min_sdk=min_sdk, target_sdk=target_sdk)


@main.command()
@click.option("--device", default=None, help="Target device ID (adb).")
@click.option("--release", is_flag=True, default=False, help="Build in release mode.")
@click.option("--watch", is_flag=True, default=False, help="Rebuild, reinstall and relaunch whenever a source file changes.")
def run(device, release, watch):
    """Build the APK, install and launch on a connected device."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
        sys.exit(1)

    builder = Builder(root)
    builder.run(device=device, release=release, watch=watch)


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
def watch(device, release):
    """Watch sources and rebuild/reinstall the app on every change."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
        sys.exit(1)

    builder = Builder(root)
    apk = builder.build(release=release)
    if not apk:
        sys.exit(1)
    builder._install_and_launch(apk, device)
    builder.watch(device=device, release=release)


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
