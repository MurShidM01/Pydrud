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
    for parent in [cwd] + [os.path.dirname(cwd)[:idx] for idx in range(len(cwd), 0, -1) if cwd[:idx] == cwd[:idx] and os.path.isdir(cwd[:idx])]:
        # Actually just walk up properly
        pass

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
@click.option("--watch", is_flag=True, default=False, help="Enable hot-reload polling (future).")
def run(device, release, watch):
    """Build the APK, install and launch on a connected device."""
    from pydrud.commands.builder import Builder

    root = _find_project_root()
    if not root:
        click.echo("Error: not inside a Pydrud project (no pydrud.yaml found)", err=True)
        sys.exit(1)

    builder = Builder(root)
    builder.run(device=device, release=release)


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
    if apk_path:
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
def doctor():
    """Check the development environment for required tools."""
    from pydrud.commands.doctor import run_doctor
    run_doctor()
