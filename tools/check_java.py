#!/usr/bin/env python3
"""
Render every generated Java template and parse it, without a JDK.

``pydrud init`` writes a dozen Java sources from Jinja templates. A typo in
one of them only shows up minutes later, as a Gradle compile error on a
line number that does not exist in the template. This script renders each
template with a representative context and parses the result with
``javalang``, so syntax breakage is caught in under a second::

    pip install javalang jinja2
    python tools/check_java.py                       # all templates
    python tools/check_java.py android/ViewFactory.java.j2

It checks syntax, not types: cross-class calls still need a real build.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import javalang
    from jinja2 import Environment, FileSystemLoader
except ImportError:  # pragma: no cover - developer tool
    sys.exit("pip install javalang jinja2 first")

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "pydrud" / "android" / "templates"

CONTEXT = {
    "package": "com.example.demo",
    "app_name": "Demo",
    "project_name": "demo_app",
    "scheme": "demoapp",
    "firebase": False,
    "night": False,
    "permissions": [],
    "python_executable": "python3",
    "abi_filters": ["arm64-v8a"],
    "pip_packages": [],
    "version_code": 1,
    "version_name": "1.0.0",
    "min_sdk": 24,
    "target_sdk": 35,
    "compile_sdk": 35,
}


def check(name: str) -> tuple[bool, str]:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      keep_trailing_newline=True)
    source = env.get_template(name).render(**CONTEXT)
    try:
        javalang.parse.parse(source)
    except Exception as exc:  # noqa: BLE001 - report any parse failure
        return False, f"{exc}"
    return True, f"{len(source.splitlines())} lines"


def main() -> int:
    names = sys.argv[1:]
    if not names:
        names = sorted(
            str(p.relative_to(TEMPLATES))
            for p in TEMPLATES.rglob("*.java.j2"))
    failures = 0
    for name in names:
        ok, detail = check(name)
        print(f"{'OK  ' if ok else 'FAIL'} {name:<44} {detail}")
        failures += not ok
    print(f"\n{len(names) - failures}/{len(names)} templates parse")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
