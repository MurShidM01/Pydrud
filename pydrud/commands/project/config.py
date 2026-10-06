"""
Reading and validating the user-editable ``pydrud.yaml`` / ``pydrud.toml``.
"""

from __future__ import annotations

import os
import re

from pydrud.commands.project.paths import _JAVA_KEYWORDS

def _toml_section(project_dir: str, wanted: str) -> dict[str, str]:
    """Read a small scalar section from ``pydrud.toml``.

    TOML remains the home of Python dependencies and the theme seed. Android
    identity and build settings are authoritative in ``pydrud.yaml``; the
    legacy ``[app]`` table is only used as a fallback for older projects.
    """
    path = os.path.join(project_dir, "pydrud.toml")
    if not os.path.isfile(path):
        return {}
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            section = False
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("[") and stripped.endswith("]"):
                    section = stripped == f"[{wanted}]"
                    continue
                if section and "=" in stripped:
                    key, value = stripped.split("=", 1)
                    values[key.strip()] = value.split(" #", 1)[0].strip().strip('"\'')
    except OSError:
        return {}
    return values


def _project_seed(project_dir: str) -> str | None:
    """Read ``[theme] seed`` from pydrud.toml, if the user set one."""
    return _toml_section(project_dir, "theme").get("seed") or None


class ProjectConfigError(ValueError):
    """A user-editable project setting is invalid."""


def _config_string(config: dict, key: str, default: str = "") -> str:
    value = config.get(key, default)
    if isinstance(value, list):
        raise ProjectConfigError(f"'{key}' must be a scalar value")
    return str(value).strip()


def _config_int(config: dict, key: str, default: int, *, minimum: int = 0) -> int:
    value = _config_string(config, key, str(default))
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ProjectConfigError(f"'{key}' must be an integer, got {value!r}") from exc
    if parsed < minimum:
        raise ProjectConfigError(f"'{key}' must be at least {minimum}")
    return parsed


def _config_bool(config: dict, key: str, default: bool = False) -> bool:
    value = _config_string(config, key, "true" if default else "false").lower()
    if value in {"true", "yes", "on", "1"}:
        return True
    if value in {"false", "no", "off", "0", ""}:
        return False
    raise ProjectConfigError(
        f"'{key}' must be true or false, got {value!r}")


def _config_list(config: dict, key: str, default=()) -> list[str]:
    if key not in config:
        return list(default)
    value = config[key]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    # A comma-separated scalar is accepted for compatibility with the old
    # flat parser, though generated manifests always use a real YAML list.
    return [item.strip().strip('"\'') for item in text.split(",") if item.strip()]


def _validate_package(package: str) -> str:
    parts = package.split(".")
    if len(parts) < 2 or any(
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
            or part in _JAVA_KEYWORDS for part in parts):
        raise ProjectConfigError(
            f"'package' must be a Java package such as com.example.my_app, got {package!r}")
    return package


def _gradle_value(project_dir: str, pattern: str, default: str) -> str:
    """Read a generated Gradle value so old projects retain it on migration."""
    path = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(path, encoding="utf-8") as handle:
            match = re.search(pattern, handle.read())
    except OSError:
        match = None
    return match.group(1) if match else default


def _manifest_permissions(project_dir: str) -> list[str]:
    """Recover explicit permissions from a pre-manifest-config project."""
    import xml.etree.ElementTree as ET

    path = os.path.join(project_dir, "android", "app", "src", "main",
                        "AndroidManifest.xml")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    attribute = "{http://schemas.android.com/apk/res/android}name"
    built_in = {"INTERNET", "ACCESS_NETWORK_STATE"}
    return [
        name.rsplit(".", 1)[-1]
        for node in root.findall("uses-permission")
        if (name := node.get(attribute, "")) and name.rsplit(".", 1)[-1] not in built_in
    ]
