"""Module-name helpers for the device's ``src/`` import root.

The generated app ships its Python under ``src/`` (the import root on the
device), so a file path has to be turned back into a dotted module name for
hot reload to re-import the right module. Kept in its own module so the hot
reload machinery can use it without importing :mod:`pydrud.runtime.app`.
"""

from __future__ import annotations

import os


def _module_name_from_path(filepath: str) -> str:
    """Convert relative filepath like 'app/screens/home.py' to 'app.screens.home'."""
    clean = filepath.replace("\\", "/")
    if clean.startswith("src/"):
        clean = clean[4:]
    if clean.endswith(".py"):
        clean = clean[:-3]
    parts = [p for p in clean.split("/") if p]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_name_for(filepath: str, project_root: str) -> str:
    """Map ``<root>/src/app/main.py`` to the module name ``app.main``."""
    try:
        rel = os.path.relpath(os.path.abspath(filepath), os.path.abspath(project_root))
    except ValueError:  # pragma: no cover — different drives on Windows
        return ""
    if rel.startswith(".."):
        return ""
    # Sources live under src/, which is the import root on the device.
    rel = rel.replace(os.sep, "/")
    if rel.startswith("src/"):
        rel = rel[len("src/"):]
    rel = rel[:-3] if rel.endswith(".py") else rel
    parts = [p for p in rel.split("/") if p]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _find_user_modules(project_root: str) -> list[str]:
    """Find all importable module names under the project's src/ directory."""
    src_dir = os.path.join(project_root, "src")
    modules: list[str] = []
    if not os.path.isdir(src_dir):
        return modules
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "pydrud")]
        for fname in files:
            if fname.endswith(".py"):
                mod = _module_name_for(os.path.join(root, fname), project_root)
                if mod:
                    modules.append(mod)
    return modules
