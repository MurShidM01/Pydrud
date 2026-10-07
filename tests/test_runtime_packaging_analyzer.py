"""Runtime-specific package policy and analyzer diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pydrud.commands.analyzer import run_analysis
from pydrud.commands.cli import main as cli
from pydrud.commands.packages import get_backend


def _write_project(root: Path, runtime: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pydrud.yaml").write_text(
        f'app_name: "demo"\nruntime: "{runtime}"\n', encoding="utf-8")
    (root / "pydrud.toml").write_text(
        f'runtime = "{runtime}"\n\n[python.packages]\n', encoding="utf-8")
    source = root / "src" / "app"
    source.mkdir(parents=True)
    (source / "imports.py").write_text(
        "from pydrud.commands.packages import Requirements\n"
        "from pydrud.android import templates\n"
        "from pydrud.platforms import android\n",
        encoding="utf-8",
    )
    return source


def test_pydash_packages_are_not_limited_by_android_registry(tmp_path):
    backend = get_backend("pydash")

    blocked_on_android = backend.add(str(tmp_path), "flask")
    unlisted = backend.add(str(tmp_path), "my-private-package>=1.4")

    assert blocked_on_android.success
    assert blocked_on_android.details["android_support_category"] == "blocked"
    assert unlisted.success
    assert unlisted.details["spec"] == ">=1.4"
    assert "recorded" in unlisted.message.lower()
    assert "install it there" in unlisted.message
    assert not (tmp_path / "android").exists()
    assert not list(tmp_path.rglob("build.gradle.kts"))

    manifest = (tmp_path / "pydrud.toml").read_text(encoding="utf-8")
    assert "flask = \"\"" in manifest
    assert 'my-private-package = ">=1.4"' in manifest
    assert "installed into the APK" not in manifest

    listed = {row["name"]: row for row in backend.list_packages(str(tmp_path))}
    assert listed["flask"]["support_category"] == "host"
    assert listed["my-private-package"]["android_support_category"] == "unverified"
    assert backend.search("qrcode")[0]["support_category"] == "host"


def test_chaquopy_package_policy_stays_registry_and_apk_specific(tmp_path):
    backend = get_backend("chaquopy")
    _write_project(tmp_path, "chaquopy")

    host_only = backend.add(str(tmp_path), "psutil")
    supported = backend.add(str(tmp_path), "requests>=2.31")

    assert not host_only.success
    assert "host-only" in host_only.message
    assert supported.success
    assert (tmp_path / "pydrud.toml").read_text(encoding="utf-8").find(
        'requests = ">=2.31"') >= 0
    assert "psutil" not in (tmp_path / "pydrud.toml").read_text(encoding="utf-8")


def test_pydash_cli_records_host_dependencies_without_creating_android_files(
        tmp_path, monkeypatch):
    _write_project(tmp_path, "pydash")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    added = runner.invoke(
        cli, ["pip", "add", "flask", "new-host-lib"], catch_exceptions=False)
    assert added.exit_code == 0, added.output
    assert "Runtime      pydash" in added.output
    assert "recorded only; install in the host Python environment" in added.output
    assert not (tmp_path / "android").exists()
    assert "flask = \"\"" in (tmp_path / "pydrud.toml").read_text()

    listed = runner.invoke(cli, ["pip", "list"], catch_exceptions=False)
    assert listed.exit_code == 0, listed.output
    assert "Runtime   pydash" in listed.output
    assert "flask" in listed.output


def test_analyzer_uses_project_runtime_for_platform_specific_imports(tmp_path):
    pydash_src = _write_project(tmp_path / "pydash", "pydash")
    chaquopy_src = _write_project(tmp_path / "chaquopy", "chaquopy")

    pydash_issues = run_analysis(str(pydash_src))
    chaquopy_issues = run_analysis(str(chaquopy_src))

    pydash_messages = [issue["message"] for issue in pydash_issues]
    assert not any("pydrud.commands" in message for message in pydash_messages)
    assert any("Android-specific" in message for message in pydash_messages)
    assert not any("bundler strips" in message for message in pydash_messages)

    chaquopy_messages = [issue["message"] for issue in chaquopy_issues]
    assert any("pydrud.commands" in message for message in chaquopy_messages)
    assert any("bundler strips" in message for message in chaquopy_messages)
    assert not any("Android-specific" in message for message in chaquopy_messages)


def test_analyze_cli_applies_runtime_but_preserves_json_output(
        tmp_path, monkeypatch):
    _write_project(tmp_path, "pydash")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["analyze", "--json"], catch_exceptions=False)

    assert result.exit_code == 0
    issues = json.loads(result.output)
    assert any("Android-specific" in issue["message"] for issue in issues)
    assert not any("bundler strips" in issue["message"] for issue in issues)
