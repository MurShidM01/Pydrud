"""
Runtime selection for Pydrud projects.

Pydrud builds an Android app through a pluggable *runtime backend*:

* ``pydash`` (default) — host-side development for a cross-platform preview
  client. It requires no Android build toolchain.
* ``chaquopy`` — a standalone APK with an embedded CPython interpreter
  (Chaquopy, MIT-licensed). The default when the Android target is present.
* ``host`` — a standalone APK with no interpreter: the native renderer dials
  a Python process running on the developer's machine (``pydrud dev``).
* ``none`` — a standalone APK that renders whatever tree it is handed and
  holds no runtime of its own.

A project's runtime is declared in ``pydrud.toml`` under ``runtime:``.
New and otherwise unconfigured projects resolve to ``pydash``. For compatibility,
a project that already has a generated Android Gradle target but no runtime
key is treated as legacy Chaquopy until it is synchronized; successful sync
persists that inferred selection so subsequent reads are explicit.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from enum import Enum


class Runtime(Enum):
    """The active runtime for a Pydrud project."""

    PYDASH = "pydash"
    CHAQUOPY = "chaquopy"
    HOST = "host"
    NONE = "none"

    @classmethod
    def resolve(cls, raw: object | None) -> "Runtime":
        """Normalise a user-provided value to a :class:`Runtime`.

        * ``None`` / missing → :attr:`PYDASH` (toolchain-free default).
        * Known strings → the matching enum member.
        * Anything else → raises :class:`RuntimeError` with a helpful
          message listing the valid values.
        """
        if raw is None:
            return cls.PYDASH
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
        if self.runtime is not Runtime.PYDASH:
            object.__setattr__(self, "produces_binary", True)
            object.__setattr__(
                self, "requires_android_toolchain", True
            )

    @property
    def backend(self) -> str:
        """The generated Java backend id for this runtime.

        Every non-pydash runtime produces the same native renderer and only
        differs in which ``PythonRuntime`` implementation is compiled in, so
        this is the single value the templates key off.
        """
        return {
            Runtime.PYDASH: "pydash",
            Runtime.CHAQUOPY: "chaquopy",
            Runtime.HOST: "host",
            Runtime.NONE: "none",
        }[self.runtime]

    def assert_not_pydash(self, command: str) -> None:
        """Raise when *command* is not supported in pydash mode."""
        if self.runtime is Runtime.PYDASH:
            raise RuntimeError(
                f"'pydrud {command}' builds an Android app binary, but this "
                f"project runs in pydash mode (no binary is produced). "
                f"Use 'pydrud dev' for live preview, or add the Android "
                f"platform with 'pydrud init android'."
            )

    def assert_chaquopy(self) -> None:
        """Raise when the caller expected chaquopy but got pydash."""
        if self.runtime is Runtime.PYDASH:
            raise RuntimeError(
                "This operation requires runtime: chaquopy. The current "
                "project runs in pydash mode and produces no app binary."
            )


def resolve_runtime(project_dir: str = ".") -> RuntimeDescriptor:
    """Resolve the runtime for *project_dir*.

    ``pydrud.yaml`` is authoritative: it is the manifest ``pydrud init
    android`` and ``pydrud sync`` maintain. ``pydrud.toml`` is consulted only
    for projects generated before that manifest existed, so the two files can
    no longer disagree about which backend a project builds.
    """
    root = os.path.abspath(project_dir)
    raw: object | None = _read_scalar(os.path.join(root, "pydrud.yaml"), "runtime")
    if raw is None:
        raw = _read_scalar(os.path.join(root, "pydrud.toml"), "runtime")
    if raw is None and _has_legacy_android_target(root):
        # Preserve existing generated APK projects that predate the runtime
        # field. New projects without an explicit runtime still choose Pydash.
        runtime = Runtime.CHAQUOPY
    else:
        runtime = Runtime.resolve(raw)
    return RuntimeDescriptor(runtime=runtime)


def _has_legacy_android_target(project_dir: str) -> bool:
    """Whether *project_dir* contains a generated Android/Gradle target."""
    android_dir = os.path.join(project_dir, "android")
    return any(os.path.isfile(os.path.join(android_dir, *parts)) for parts in (
        ("app", "build.gradle.kts"),
        ("app", "build.gradle"),
        ("build.gradle.kts",),
    ))


def _read_scalar(path: str, key: str) -> object | None:
    """Read one top-level ``key: value`` scalar from YAML or TOML.

    Deliberately tiny and dependency-free: this module ships inside the APK,
    so it must not pull the command-line config reader into the bundle.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or line[:1].isspace() or stripped[0] in "#[":
                    continue
                name, separator, value = line.partition("=")
                if not separator:
                    name, separator, value = line.partition(":")
                if not separator or name.strip() != key:
                    continue
                for marker in (" #", "\t#"):
                    if marker in value:
                        value = value.split(marker, 1)[0]
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                return value or None
    except OSError:
        pass
    return None


def persist_runtime(project_dir: str, runtime: Runtime) -> None:
    """Record *runtime* in ``pydrud.yaml``, falling back to ``pydrud.toml``.

    The YAML manifest wins when both exist, so that is where the value is
    kept; the TOML file stays readable but is no longer the source of truth.
    """
    root = os.path.abspath(project_dir)
    for filename in ("pydrud.yaml", "pydrud.toml"):
        path = os.path.join(root, filename)
        if os.path.isfile(path):
            _set_scalar(path, "runtime", runtime.value)
            return
    with open(os.path.join(root, "pydrud.toml"), "w", encoding="utf-8") as handle:
        handle.write(f'runtime = "{runtime.value}"\n')


def _set_scalar(path: str, key: str, value: str) -> None:
    """Set a top-level scalar, preserving comments and the file's syntax."""
    separator = "=" if path.endswith(".toml") else ":"
    rendered = (f'{key} = "{value}"' if separator == "="
                else f'{key}: "{value}"')
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return

    for index, line in enumerate(lines):
        if line[:1].isspace():
            continue
        name = line.split("=", 1)[0].split(":", 1)[0].strip()
        if name == key:
            if line.strip() == rendered:
                return
            lines[index] = rendered
            break
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(rendered)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
