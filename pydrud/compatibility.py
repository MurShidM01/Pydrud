"""Pydrud's generated Android compatibility contract.

Keep the framework/runtime/toolchain matrix in one place so scaffolding,
migration diagnostics and tests cannot silently drift.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Compatibility:
    framework_version: str
    protocol_version: int
    android_runtime_version: str
    agp_version: str
    gradle_version: str
    chaquopy_version: str
    python_version: str
    min_sdk: int
    target_sdk: int
    compile_sdk: int
    jdk_version: int
    ndk_version: str


COMPATIBILITY = Compatibility(
    framework_version="1.5.2",
    protocol_version=2,
    android_runtime_version="2.0.0",
    agp_version="8.13.2",
    gradle_version="8.14.4",
    chaquopy_version="17.0.0",
    python_version="3.11",
    min_sdk=24,
    target_sdk=36,
    compile_sdk=36,
    jdk_version=17,
    ndk_version="28.2.13676358",
)
