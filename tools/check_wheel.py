#!/usr/bin/env python3
"""
Verify the built sdist and wheel can actually scaffold a project.

``pydrud create`` renders ``pydrud/android/templates/**`` from the installed
package, so a wheel that drops those files installs without a warning and
then fails the moment anyone runs the CLI. The test suite cannot catch that:
it imports from the source tree, where the templates are always present.

    pip install build && python -m build
    python tools/check_wheel.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(REPO, "dist")
TEMPLATES = os.path.join(REPO, "pydrud", "android", "templates")


def required_templates() -> list[str]:
    """Every template in the source tree, as repo-relative POSIX paths.

    Derived from the tree instead of hard-coded: ``pydrud create`` renders
    whatever is on disk, so a fixed name list rots the moment a template is
    added, renamed or removed. It once pinned a screen that had been deleted
    and failed the release job; walking the tree keeps the check honest with
    no maintenance.
    """
    found: list[str] = []
    for root, dirs, files in os.walk(TEMPLATES):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            path = os.path.join(root, name)
            found.append(os.path.relpath(path, REPO).replace(os.sep, "/"))
    return found


def find_artifacts() -> tuple[str, str]:
    """The built wheel and sdist, or an explanation of what is missing."""
    wheels = sorted(f for f in os.listdir(DIST) if f.endswith(".whl"))
    sdists = sorted(f for f in os.listdir(DIST) if f.endswith(".tar.gz"))
    if not wheels or not sdists:
        raise SystemExit(
            f"expected one wheel and one sdist in {DIST}, found:\n  "
            + "\n  ".join(sorted(os.listdir(DIST)) or ["(empty)"])
            + "\nRun `python -m build` first."
        )
    return os.path.join(DIST, wheels[-1]), os.path.join(DIST, sdists[-1])


def names(artifact: str) -> set[str]:
    if artifact.endswith(".whl"):
        with zipfile.ZipFile(artifact) as archive:
            return set(archive.namelist())
    with tarfile.open(artifact) as archive:
        return {member.name.split("/", 1)[-1] for member in archive.getmembers()}


def main() -> int:
    wheel, sdist = find_artifacts()
    failures: list[str] = []
    templates = required_templates()

    for artifact in (wheel, sdist):
        print(f"── {os.path.basename(artifact)} ──")
        contents = names(artifact)
        for template in templates:
            present = template in contents
            print(f"   {'OK  ' if present else 'FAIL'} {template}")
            if not present:
                failures.append(f"{os.path.basename(artifact)}: {template}")

    # The strongest check: install the wheel somewhere clean and scaffold.
    venv = os.path.join(tempfile.mkdtemp(prefix="pydrud-wheel-"), "venv")
    print(f"── install {os.path.basename(wheel)} in a clean venv ──")
    subprocess.run([sys.executable, "-m", "venv", venv], check=True)
    bindir = os.path.join(venv, "Scripts" if os.name == "nt" else "bin")
    python = os.path.join(bindir, "python.exe" if os.name == "nt" else "python")
    pydrud = os.path.join(bindir, "pydrud.exe" if os.name == "nt" else "pydrud")
    subprocess.run([python, "-m", "pip", "install", "-q", wheel], check=True)
    if not os.path.isfile(pydrud):  # pragma: no cover - guards the check
        raise SystemExit("the wheel installed no `pydrud` console script")
    project = tempfile.mkdtemp(prefix="pydrud-wheel-project-")
    result = subprocess.run([pydrud, "create", "wheelcheck",
                             "--org", "com.example"],
                            cwd=project, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        failures.append("`pydrud create` failed from the installed wheel")
    else:
        created = os.path.join(project, "wheelcheck", "pydrud.yaml")
        if os.path.isfile(created):
            print("   OK   pydrud create (installed wheel)")
        else:
            failures.append("`pydrud create` produced no pydrud.yaml")

    if failures:
        print("\n".join(failures))
        return 1
    print("\nwheel: templates present and the CLI runs from an installed wheel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
