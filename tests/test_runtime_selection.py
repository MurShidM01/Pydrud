from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from pydrud.commands.cli import main as cli
from pydrud.commands.packages import PydashBackend, get_backend
from pydrud.commands.project import create_project, sync_project
from pydrud.runtime.runtime import Runtime, RuntimeDescriptor, resolve_runtime


def test_unconfigured_runtime_defaults_to_pydash_but_preserves_legacy_android(tmp_path):
    assert Runtime.resolve(None) is Runtime.PYDASH
    assert RuntimeDescriptor(Runtime.PYDASH).produces_binary is False
    assert RuntimeDescriptor(Runtime.PYDASH).requires_android_toolchain is False
    assert RuntimeDescriptor(Runtime.CHAQUOPY).produces_binary is True
    assert RuntimeDescriptor(Runtime.CHAQUOPY).requires_android_toolchain is True

    assert resolve_runtime(str(tmp_path)).runtime is Runtime.PYDASH

    legacy = tmp_path / "legacy"
    gradle = legacy / "android" / "app" / "build.gradle.kts"
    gradle.parent.mkdir(parents=True)
    gradle.write_text("// generated before runtime selection\n", encoding="utf-8")
    assert resolve_runtime(str(legacy)).runtime is Runtime.CHAQUOPY


def test_default_scaffold_is_pydash_and_never_probes_android_toolchain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch("pydrud.commands.project.scaffold._detect_sdk",
              side_effect=AssertionError("SDK detection must be skipped")),
        patch("pydrud.commands.project.scaffold._detect_ndk",
              side_effect=AssertionError("NDK detection must be skipped")),
        patch("pydrud.commands.project.scaffold._detect_build_python",
              side_effect=AssertionError("Chaquopy Python detection must be skipped")),
    ):
        create_project("cross_platform_app")

    project = tmp_path / "cross_platform_app"
    assert not (project / "android").exists()
    assert not (project / "setup.py").exists()
    assert get_backend("pydash").__class__ is PydashBackend
    assert resolve_runtime(str(project)).runtime is Runtime.PYDASH

    toml = (project / "pydrud.toml").read_text(encoding="utf-8")
    yaml = (project / "pydrud.yaml").read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    runner = (project / "run.py").read_text(encoding="utf-8")
    entry = (project / "src" / "app" / "main.py").read_text(encoding="utf-8")
    portable_config = (project / "src" / "pydrud_config.py").read_text(encoding="utf-8")

    assert 'runtime = "pydash"' in toml
    assert "scheme =" not in toml
    assert 'runtime: "pydash"' in yaml
    for android_only in ("min_sdk:", "target_sdk:", "compile_sdk:", "ndk:",
                         "abi_filters:", "chaquopy_version:", "gradle_version:"):
        assert android_only not in yaml
    assert "Android SDK, NDK, Gradle" in readme
    assert "android/" not in readme
    assert "pydrud init android" in readme
    assert (project / "src" / "app" / "theme.pss").is_file()
    assert "PreviewRunner" in runner
    assert "start_app" not in entry
    assert "android" not in entry.lower()
    assert "MIN_SDK" not in portable_config
    assert not (project / "src" / "app" / "jobs.py").exists()


def test_pydash_cli_guards_and_sync_do_not_touch_android(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("preview_app")
    project = tmp_path / "preview_app"
    monkeypatch.chdir(project)

    runner = CliRunner()
    for command in (
        ["build"],
        ["run"],
        ["watch"],
        ["icons"],
        ["permissions", "add", "camera"],
        ["capabilities", "add", "haptics"],
    ):
        result = runner.invoke(cli, command, catch_exceptions=False)
        assert result.exit_code == 1, (command, result.output)
        assert "Android" in result.output
        assert "pydash mode" in result.output

    (project / "pydrud.toml").unlink()
    sync_result = runner.invoke(cli, ["sync"], catch_exceptions=False)
    assert sync_result.exit_code == 0, sync_result.output
    assert "no Android project" in sync_result.output
    assert 'runtime = "pydash"' in (project / "pydrud.toml").read_text()
    assert not (project / "android").exists()
    assert sync_project(str(project))


def test_legacy_android_project_sync_persists_inferred_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("legacy_app", runtime="chaquopy")
    project = tmp_path / "legacy_app"
    toml_path = project / "pydrud.toml"
    toml = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        "\n".join(line for line in toml.splitlines()
                   if not line.strip().startswith("runtime =")) + "\n",
        encoding="utf-8",
    )

    assert resolve_runtime(str(project)).runtime is Runtime.CHAQUOPY
    assert sync_project(str(project), update_runtime=False)
    assert 'runtime = "chaquopy"' in toml_path.read_text(encoding="utf-8")


def test_generated_test_suites_run_for_both_runtimes(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (
        str(repo_root), env.get("PYTHONPATH", ""),
    )))
    monkeypatch.chdir(tmp_path)

    for runtime in ("pydash", "chaquopy"):
        name = f"{runtime}_fixture"
        create_project(name, runtime=runtime)
        project = tmp_path / name
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests"],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, (
            f"Generated {runtime} suite failed:\n{result.stdout}\n{result.stderr}"
        )
        # The generated suite must actually exercise the starter (not collect
        # zero tests). The exact count grows as the scaffold gains coverage,
        # so require a healthy floor instead of a frozen number.
        summary = re.search(r"(\d+) passed", result.stdout)
        assert summary, f"no test summary in:\n{result.stdout}"
        assert int(summary.group(1)) >= 3

        tree_result = subprocess.run(
            [sys.executable, "run.py", "--tree"],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        assert tree_result.returncode == 0, (
            f"Generated {runtime} runner failed:\n"
            f"{tree_result.stdout}\n{tree_result.stderr}"
        )
        assert '"type": "Stack"' in tree_result.stdout
