from __future__ import annotations

from pydrud.commands import doctor


_ANDROID_CHECKS = (
    "_check_java",
    "_check_android_sdk",
    "_check_ndk",
    "_check_cmake",
    "_check_gradle",
    "_check_adb",
)


def _write_runtime_project(root, runtime: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pydrud.yaml").write_text(
        f'app_name: "demo"\nruntime: "{runtime}"\n', encoding="utf-8")
    (root / "pydrud.toml").write_text(
        f'runtime = "{runtime}"\n', encoding="utf-8")


def test_pydash_doctor_skips_android_toolchain_and_android_project_checks(
        tmp_path, monkeypatch, capsys):
    _write_runtime_project(tmp_path, "pydash")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "_check_python", lambda: True)
    monkeypatch.setattr(doctor, "_check_package", lambda *_args: True)
    monkeypatch.setattr(doctor, "_check_project_shadowing", lambda _path: True)

    for name in (*_ANDROID_CHECKS, "_check_chaquopy", "_check_manifest_permissions"):
        monkeypatch.setattr(
            doctor, name,
            lambda *args, _name=name: (_ for _ in ()).throw(
                AssertionError(f"{_name} must be skipped for Pydash")),
        )

    assert doctor.run_doctor() is True
    output = capsys.readouterr().out
    assert "Runtime" in output and "pydash" in output
    assert "Android toolchain not required" in output


def test_chaquopy_doctor_runs_android_toolchain_and_project_checks(
        tmp_path, monkeypatch):
    _write_runtime_project(tmp_path, "chaquopy")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor, "_check_python", lambda: True)
    monkeypatch.setattr(doctor, "_check_package", lambda *_args: True)
    monkeypatch.setattr(doctor, "_check_project_shadowing", lambda _path: True)

    calls = []
    for name in _ANDROID_CHECKS:
        monkeypatch.setattr(
            doctor, name,
            lambda _name=name: calls.append(_name) or True,
        )
    monkeypatch.setattr(
        doctor, "_check_chaquopy",
        lambda _path: calls.append("_check_chaquopy") or True,
    )
    monkeypatch.setattr(
        doctor, "_check_manifest_permissions",
        lambda _path: calls.append("_check_manifest_permissions") or True,
    )

    assert doctor.run_doctor() is True
    assert set(calls) == set(_ANDROID_CHECKS) | {
        "_check_chaquopy", "_check_manifest_permissions"}
