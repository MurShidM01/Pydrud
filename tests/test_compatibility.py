from pydrud.compatibility import COMPATIBILITY


def test_generated_toolchain_matrix_is_current_baseline():
    assert COMPATIBILITY.protocol_version == 2
    assert COMPATIBILITY.chaquopy_version == "17.0.0"
    assert COMPATIBILITY.agp_version == "8.13.2"
    assert COMPATIBILITY.gradle_version == "8.14.4"
    assert COMPATIBILITY.compile_sdk >= 36
    assert COMPATIBILITY.target_sdk >= 36
    assert COMPATIBILITY.min_sdk >= 24
    assert COMPATIBILITY.jdk_version == 17
