#!/usr/bin/env python3
"""
End-to-end smoke test for the installed ``pydrud`` command.

The unit suite calls Pydrud's Python API directly, which can hide a broken
console script, a missing package-data file or a command that only fails
once it touches a real project directory. This script drives the installed
executable the way a developer does and fails loudly on the first bad exit:

    pip install -e .
    python tools/smoke.py

It covers both project shapes — Pydash (host preview) and Chaquopy
(standalone APK) — and asserts the camera stack is not bundled until a
project asks for it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

#: Every step runs in a throwaway directory, so nothing is left behind.
STEPS: tuple[tuple[str, ...], ...] = (
    ("create", "smoke_pydash", "--org", "com.example.smoke"),
    ("create", "smoke_apk", "--org", "com.example.smoke", "--runtime", "chaquopy"),
)


def command_prefix() -> list[str]:
    """How to invoke Pydrud here.

    The installed ``pydrud`` console script is preferred — it is what users
    actually run, so a broken entry point shows up here rather than in a
    release. Fall back to the module when the script is not on PATH.
    """
    script = shutil.which("pydrud")
    if script:
        return [script]
    return [sys.executable, "-c",
            "from pydrud.commands.cli import main; main()"]


_PREFIX = command_prefix()


def run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    """Run one Pydrud command, capturing output for the failure report."""
    return subprocess.run(
        [*_PREFIX, *args], cwd=cwd, capture_output=True, text=True,
    )


def check(args: list[str], cwd: str, label: str) -> None:
    """Run *args* and raise with its output when it exits non-zero."""
    result = run(args, cwd)
    if result.returncode != 0:
        raise SystemExit(
            f"smoke: '{label}' failed with exit code {result.returncode}\n"
            f"  command: pydrud {' '.join(args)}\n"
            f"  stdout:\n{indent(result.stdout)}\n"
            f"  stderr:\n{indent(result.stderr)}"
        )


def indent(text: str) -> str:
    return "\n".join("    " + line for line in (text or "").splitlines()) or "    (empty)"


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    workspace = tempfile.mkdtemp(prefix="pydrud-smoke-")
    failures = 0
    try:
        for create_args in STEPS:
            name = create_args[1]
            root = os.path.join(workspace, name)
            print(f"── {name} ──")
            check(list(create_args), workspace, f"{name}: create")

            if "chaquopy" not in create_args:
                check(["init", "android"], root, f"{name}: init android")
            check(["sync"], root, f"{name}: sync")
            check(["analyze"], root, f"{name}: analyze")
            check(["capabilities", "list", "--all"], root,
                  f"{name}: capabilities list")

            gradle = os.path.join(root, "android", "app", "build.gradle.kts")
            if os.path.isfile(gradle):
                bundled = "androidx.camera" in read(gradle)
                print(f"   camera bundled by default: {bundled}")
                if bundled:
                    failures += 1
                    print("   FAIL: the camera stack should be opt-in")

                check(["permissions", "add", "camera"], root,
                      f"{name}: permissions add camera")
                check(["sync"], root, f"{name}: sync (camera)")
                if "androidx.camera" not in read(gradle):
                    failures += 1
                    print("   FAIL: declaring CAMERA should bundle the stack")
                else:
                    print("   camera bundled after `permissions add camera`: True")
            print(f"   OK {name}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if failures:
        print(f"\n{failures} smoke check(s) failed")
        return 1
    print("\nsmoke: every command exited 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
