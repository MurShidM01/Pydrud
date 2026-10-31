"""Resolve the framework version instead of declaring it.

The version is declared exactly once, in pyproject.toml, and every other
consumer derives it from that declaration:

1. the generated _build_info module (written into an APK bundle by sync)
2. pyproject.toml next to the package (running from a source checkout)
3. installed distribution metadata (a wheel, or an editable install)

A release therefore edits one line of project metadata and nothing else;
no Python module carries a copy that can drift out of step.
"""

from __future__ import annotations

import os
import re
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

#: Reported when nothing can be resolved (a bare source tree with no
#: metadata). Deliberately not a release number.
_UNRESOLVED = "0.0.0+unknown"

_PROJECT_VERSION = re.compile(
    r"^version\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def _from_bundle() -> str:
    """Version stamped into the APK bundle by pydrud sync."""
    try:
        module = import_module("pydrud._build_info")
    except ImportError:
        return ""
    return str(getattr(module, "__version__", "") or "")


def _from_pyproject() -> str:
    """The declaration in pyproject.toml, when running from a checkout."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "pyproject.toml")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            try:
                import tomllib
            except ImportError:  # Python 3.10
                match = _PROJECT_VERSION.search(
                    handle.read().decode("utf-8", "replace"))
                return match.group(1) if match else ""
            data = tomllib.load(handle)
    except (OSError, ValueError):
        return ""
    value = data.get("project", {}).get("version")
    return str(value) if isinstance(value, str) else ""


def _from_metadata() -> str:
    """What the installed distribution says (wheels ship no pyproject)."""
    try:
        return _distribution_version("pydrud")
    except PackageNotFoundError:
        return ""


def resolve_version() -> str:
    """First non-empty source, in order of specificity."""
    for candidate in (_from_bundle(), _from_pyproject(), _from_metadata()):
        if candidate:
            return candidate
    return _UNRESOLVED


__version__ = resolve_version()
