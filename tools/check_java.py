#!/usr/bin/env python3
"""
Render every generated Java template and parse it, without a JDK.

``pydrud create``/``init android`` write a dozen Java sources from Jinja templates. A typo in
one of them only shows up minutes later, as a Gradle compile error on a
line number that does not exist in the template. This script renders each
template with a representative context and parses the result with
``javalang``, so syntax breakage is caught in under a second::

    pip install javalang jinja2
    python tools/check_java.py                       # all templates
    python tools/check_java.py android/ViewFactory.java.j2

It then resolves every call between the generated classes with
``pydrud.android.javacheck``, so a missing method on a sibling class
(``advanced.setEventDispatcher(d)``) is reported here rather than two
minutes into a Gradle build.
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


#: Optional feature switches that change which code is generated. Every
#: template is rendered once per combination so neither variant can rot.
VARIANTS = ({"camera": False}, {"camera": True})


def _environment() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)),
                       keep_trailing_newline=True)


def check(name: str, variant: dict) -> tuple[bool, str]:
    source = _environment().get_template(name).render(
        **CONTEXT, **variant)
    try:
        javalang.parse.parse(source)
    except Exception as exc:  # noqa: BLE001 - report any parse failure
        return False, f"{exc}"
    return True, f"{len(source.splitlines())} lines"


def symbol_check(names: list[str], variant: dict) -> int:
    """Cross-class symbol resolution over the whole generated source set."""
    from pydrud.android.javacheck import check_sources

    env = _environment()
    rendered = {name: env.get_template(name).render(**CONTEXT, **variant)
                for name in names}
    problems = check_sources(rendered)
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"{len(problems)} unresolved symbol(s)")
    return 1 if problems else 0


def main() -> int:
    sys.path.insert(0, str(REPO))
    names = sys.argv[1:]
    if not names:
        names = sorted(
            str(p.relative_to(TEMPLATES))
            for p in TEMPLATES.rglob("*.java.j2"))
    failures = 0
    for variant in VARIANTS:
        label = "camera bundled" if variant["camera"] else "camera opt-in"
        print(f"── {label} ──")
        for name in names:
            ok, detail = check(name, variant)
            print(f"{'OK  ' if ok else 'FAIL'} {name:<44} {detail}")
            failures += not ok
        print(f"\n{len(names) - failures}/{len(names)} templates parse")
        if failures:
            return 1
        print()
        if symbol_check(names, variant):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
