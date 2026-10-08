"""Pydrud's generated compatibility contracts.

Two matrices live here because they have different scoping rules:

* ``HOST_COMPATIBILITY`` — framework protocol and version numbers that
  matter on every platform (host and device). Used by the runtime layer
  and core services that are bundled into an APK.
* ``COMPATIBILITY`` — Android toolchain pins used only when generating
  or syncing a Chaquopy project (build-time). Never imported from the
  runtime path.

Keeping them separate lets the pydash-only code path stay clean of
Android-specific constants.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HostCompatibility:
    """Cross-platform framework compatibility snapshot.

    These fields matter both on the developer host and inside an APK.
    Importing this class does not pull in any Android-specific constants.
    """

    framework_version: str
    protocol_version: int
    python_version: str


@dataclass(frozen=True, slots=True)
class Compatibility:
    """Android-only build-toolchain matrix.

    Fields here should never be referenced from runtime or core code
    that runs inside an APK.
    """

    #: Framework version (mirrors HOST_COMPATIBILITY.framework_version).
    android_runtime_version: str
    #: Protocol version used by the BridgeService on Android (mirrors
    #: HOST_COMPATIBILITY.protocol_version; kept here so the scaffold
    #: can pass it into generated Java without importing HOST_COMPATIBILITY).
    protocol_version: int
    agp_version: str
    gradle_version: str
    chaquopy_version: str
    python_version: str
    min_sdk: int
    target_sdk: int
    compile_sdk: int
    jdk_version: int
    ndk_version: str


#: Cross-platform — valid on both host and device. The runtime reads this
#: to verify that the host and APK agree on the protocol.
HOST_COMPATIBILITY = HostCompatibility(
    framework_version="2.1.4",
    protocol_version=2,
    python_version="3.11",
)

#: Android toolchain pins — only consumed during scaffolding / sync.
COMPATIBILITY = Compatibility(
    android_runtime_version="2.1.4",
    protocol_version=2,
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
}
