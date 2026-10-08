from pydrud.compatibility import COMPATIBILITY, HOST_COMPATIBILITY


def test_host_compatibility_is_cross_platform():
    assert HOST_COMPATIBILITY.framework_version == "2.1.4"
    assert HOST_COMPATIBILITY.protocol_version == 2
    assert HOST_COMPATIBILITY.python_version == "3.11"


def test_generated_toolchain_matrix_is_current_baseline():
    # Android-only toolchain pins live on COMPATIBILITY; protocol_version
    # moved to HOST_COMPATIBILITY because it's used by the core runtime too.
    assert COMPATIBILITY.chaquopy_version == "17.0.0"
    assert COMPATIBILITY.agp_version == "8.13.2"
    assert COMPATIBILITY.gradle_version == "8.14.4"
    assert COMPATIBILITY.compile_sdk >= 36
    assert COMPATIBILITY.target_sdk >= 36
    assert COMPATIBILITY.min_sdk >= 24
    assert COMPATIBILITY.jdk_version == 17
