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
    framework_version="2.0.2",
    protocol_version=2,
    android_runtime_version="2.0.2",
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


#: Widget properties the Python API accepts but the native renderer does not
#: read yet. They are inert — not errors — so they are listed here rather
#: than removed: an app that sets them still renders, it just does not get
#: that refinement. ``tests/test_widget_props.py`` asserts this ledger
#: matches the generated Java exactly, in both directions, so the list can
#: only shrink deliberately.
NATIVE_IGNORED_PROPS: dict[str, tuple[str, ...]] = {
    "Banner": ("severity",),
    "Chart": ("labels", "showValues"),
    "CircularProgress": ("stroke",),
    "Form": ("fields", "submitted", "valid"),
    "InfiniteList": ("total", "window"),
    "MapView": ("interactive", "mapType", "provider"),
    "Markdown": ("linkColor",),
    "Rating": ("half",),
    "ReorderableList": ("handle", "longPress"),
    "VideoPlayer": ("aspectRatio",),
}
