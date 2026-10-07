"""
Runtime selection for Pydrud projects.

Pydrud supports two runtimes:

* ``pydash`` (default) — live development inside the Pydash client app.
  No Android build toolchain required. Cross-platform (Android + iOS).
* ``chaquopy`` (opt-in, legacy default) — standalone APK with embedded
  CPython via Chaquopy. Android-only.

A project's runtime is declared in ``pydrud.toml`` under ``runtime:``.
When absent (legacy projects), the project resolves to ``chaquopy`` so
it never silently changes behaviour. ``pydrud sync`` persists the
explicit value so future reads are stable.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum


class Runtime(Enum):
    """The active runtime for a Pydrud project."""

    PYDASH = "pydash"
    CHAQUOPY = "chaquopy"

    @classmethod
    def resolve(cls, raw: object | None) -> "Runtime":
        """Normalise a user-provided value to a :class:`Runtime`.

        * ``None`` / missing → :attr:`CHAQUOPY` (legacy default).
        * Known strings → the matching enum member.
        * Anything else → raises :class:`RuntimeError` with a helpful
          message listing the valid values.
        """
        if raw is None:
            return cls.CHAQUOPY
        text = str(raw).strip().lower()
        try:
            return cls(text)
        except ValueError:
            valid = ", ".join(r.value for r in cls)
            raise RuntimeError(
                f"Unknown runtime {raw!r}. Valid values are: {valid}."
            ) from None


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    """Immutable snapshot of a project's chosen runtime."""

    runtime: Runtime

    #: Whether this project produces a distributable app binary.
    produces_binary: bool = False

    #: Whether Android-specific tooling is required.
    requires_android_toolchain: bool = False

    def __post_init__(self) -> None:
        if self.runtime is Runtime.CHAQUOPY:
            object.__setattr__(self, "produces_binary", True)
            object.__setattr__(
                self, "requires_android_toolchain", True
            )

    def assert_not_pydash(self, command: str) -> None:
        """Raise when *command* is not supported in pydash mode."""
        if self.runtime is Runtime.PYDASH:
            raise RuntimeError(
                f"'pydrud {command}' builds an Android app binary, but this "
                f"project runs in pydash mode (no binary is produced). "
                f"Use 'pydrud dev' for live preview, or set "
                f"runtime: chaquopy in pydrud.toml for a standalone APK."
            )

    def assert_chaquopy(self) -> None:
        """Raise when the caller expected chaquopy but got pydash."""
        if self.runtime is Runtime.PYDASH:
            raise RuntimeError(
                "This operation requires runtime: chaquopy. The current "
                "project runs in pydash mode and produces no app binary."
            )


def resolve_runtime(project_dir: str = ".") -> RuntimeDescriptor:
    """Read the runtime from *project_dir*/pydrud.toml and return it."""
    toml_path = os.path.join(os.path.abspath(project_dir), "pydrud.toml")
    raw: object | None = None
    if os.path.isfile(toml_path):
        raw = _read_toml_runtime(toml_path)
    runtime = Runtime.resolve(raw)
    return RuntimeDescriptor(runtime=runtime)


def _read_toml_runtime(path: str) -> object | None:
    """Parse just the ``runtime`` key from a TOML file.

    Uses a tiny hand-rolled scanner so we do not add a TOML parser
    dependency to the core path. Falls back to ``None`` (chaquopy) on
    any error.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("runtime") and "=" in stripped:
                    _, _, value = stripped.partition("=")
                    value = value.strip().strip('"').strip("'")
                    return value if value else None
    except OSError:
        pass
    return None


def persist_runtime(project_dir: str, runtime: Runtime) -> None:
    """Write (or update) the ``runtime`` key in pydrud.toml.

    If the key already exists its value is overwritten; otherwise it is
    appended below the ``[app]`` section header. Comments and unknown
    sections are preserved verbatim.
    """
    path = os.path.join(os.path.abspath(project_dir), "pydrud.toml")
    if not os.path.isfile(path):
        # New project: write a minimal TOML.
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f'runtime = "{runtime.value}"\n')
        return

    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    # Find the existing runtime= line (if any).
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("runtime") and "=" in stripped:
            lines[idx] = f'runtime = "{runtime.value}"\n'
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
            return

    # No existing line — insert after the [app] section header.
    inserted = False
    for idx, line in enumerate(lines):
        if line.strip() == "[app]":
            lines.insert(idx + 1, f'runtime = "{runtime.value}"\n')
            inserted = True
            break
    if not inserted:
        # Fallback: prepend at top.
        lines.insert(0, f'runtime = "{runtime.value}"\n')

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
