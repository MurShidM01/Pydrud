"""Tests for 2.1.0 platform workflows: ``create`` + ``init android``.

Covers the preview shell (no Chaquopy), the standalone upgrade, mode
preservation across ``sync``, the starter PSS theme, the Windows hot-reload
path fix and the UI-queue startup race fix.
"""

from __future__ import annotations

import sys

import pytest
from click.testing import CliRunner

from pydrud.commands.cli import main as cli
from pydrud.commands.project import (
    android_is_standalone,
    create_project,
    init_platform,
    sync_project,
)
from pydrud.runtime.runtime import Runtime, resolve_runtime

try:
    import javalang  # noqa: F401
    HAS_JAVALANG = True
except ImportError:  # pragma: no cover - optional dev dependency
    HAS_JAVALANG = False


def _read(path) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_create_command_scaffolds_pydash_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["create", "tasks"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    project = tmp_path / "tasks"
    assert (project / "pydrud.yaml").is_file()
    assert (project / "src" / "app" / "theme.pss").is_file()
    assert not (project / "android").exists()
    assert resolve_runtime(str(project)).runtime is Runtime.PYDASH


def test_init_without_platform_lists_platforms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    monkeypatch.chdir(tmp_path / "tasks")
    result = CliRunner().invoke(cli, ["init"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "android" in result.output
    assert "ios" in result.output


def test_init_android_builds_preview_shell_without_chaquopy(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli, ["init", "android"],
                                catch_exceptions=False)
    assert result.exit_code == 0, result.output

    gradle = _read(project / "android" / "app" / "build.gradle.kts")
    assert "com.chaquo.python" not in gradle
    assert "chaquopy {" not in gradle
    assert "ndkVersion" not in gradle
    root_gradle = _read(project / "android" / "build.gradle.kts")
    assert "chaquopy" not in root_gradle.lower()
    assert "chaquo.com" not in _read(
        project / "android" / "settings.gradle.kts")

    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    assert (java_dir / "PreviewClient.java").is_file()
    activity = _read(java_dir / "TasksActivity.java")
    assert "showPreviewConnect" in activity
    assert "com.chaquo.python" not in activity
    assert "PydrudWorker" in _read(java_dir / "PydrudWorker.java")

    assert "standalone: false" in _read(project / "pydrud.yaml")
    assert 'runtime = "chaquopy"' in _read(project / "pydrud.toml")
    assert resolve_runtime(str(project)).runtime is Runtime.CHAQUOPY
    assert android_is_standalone(str(project)) is False
    # No embedded interpreter means no bundle, no setup.py and no jobs shim.
    assert not (project / "src" / "pydrud").exists()
    assert not (project / "setup.py").exists()
    assert not (project / "src" / "app" / "android_main.py").exists()
    assert not (project / "src" / "app" / "jobs.py").exists()


def test_init_android_standalone_embeds_python(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android", standalone=True)

    gradle = _read(project / "android" / "app" / "build.gradle.kts")
    assert "com.chaquo.python" in gradle
    assert "chaquopy {" in gradle
    assert "ndkVersion" in gradle
    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    activity = _read(java_dir / "TasksActivity.java")
    assert "Python.start" in activity
    assert "showPreviewConnect" not in activity
    assert 'getModule("app.android_main")' in activity
    assert (project / "src" / "app" / "android_main.py").is_file()
    assert (project / "src" / "app" / "jobs.py").is_file()
    assert (project / "setup.py").is_file()
    assert (project / "src" / "pydrud" / "__init__.py").is_file()
    assert "standalone: true" in _read(project / "pydrud.yaml")
    assert android_is_standalone(str(project)) is True


def test_init_android_upgrades_preview_but_never_silently_downgrades(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android")
    # Re-running the same mode is a no-op success.
    assert init_platform(str(project), "android")
    # Preview -> standalone upgrade works in place.
    assert init_platform(str(project), "android", standalone=True)
    assert android_is_standalone(str(project)) is True
    assert (project / "src" / "app" / "android_main.py").is_file()
    # Standalone -> preview is refused: that would drop the runtime.
    assert init_platform(str(project), "android") is False
    assert android_is_standalone(str(project)) is True


def test_init_rejects_unknown_and_future_platforms(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    monkeypatch.chdir(tmp_path / "tasks")
    runner = CliRunner()

    future = runner.invoke(cli, ["init", "ios"], catch_exceptions=False)
    assert future.exit_code == 1
    assert "not available yet" in future.output

    unknown = runner.invoke(cli, ["init", "frobnicate"],
                            catch_exceptions=False)
    assert unknown.exit_code == 1
    assert "pydrud create <name>" in unknown.output


def test_init_outside_a_project_fails_with_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["init", "android"],
                                catch_exceptions=False)
    assert result.exit_code == 1
    assert "Not inside a Pydrud project" in result.output


def test_sync_preserves_preview_and_legacy_standalone_shapes(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("preview_app")
    preview = tmp_path / "preview_app"
    assert init_platform(str(preview), "android")
    assert sync_project(str(preview), update_runtime=False)
    assert ("com.chaquo.python" not in
            _read(preview / "android" / "app" / "build.gradle.kts"))
    assert android_is_standalone(str(preview)) is False

    create_project("legacy_app", runtime="chaquopy")
    legacy = tmp_path / "legacy_app"
    assert sync_project(str(legacy), update_runtime=False)
    assert ("com.chaquo.python" in
            _read(legacy / "android" / "app" / "build.gradle.kts"))
    assert android_is_standalone(str(legacy)) is True
    # Legacy entry point keeps booting app.main; no managed adapter appears.
    assert 'getModule("app.main")' in _read(
        legacy / "android" / "app" / "src" / "main" / "java" / "com"
        / "example" / "legacy_app" / "LegacyAppActivity.java")
    assert not (legacy / "src" / "app" / "android_main.py").exists()


def test_yaml_standalone_flag_drives_sync_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    project = tmp_path / "tasks"
    assert init_platform(str(project), "android")

    yaml_path = project / "pydrud.yaml"
    yaml_path.write_text(
        _read(yaml_path).replace("standalone: false", "standalone: true"),
        encoding="utf-8")
    assert sync_project(str(project), update_runtime=False)
    assert ("com.chaquo.python" in
            _read(project / "android" / "app" / "build.gradle.kts"))
    assert (project / "src" / "app" / "android_main.py").is_file()


def test_starter_stylesheet_parses_clean_and_styles_preview(tmp_path,
                                                            monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    project = tmp_path / "tasks"

    from pydrud.core.styles.parser import parse_pss
    sheet = parse_pss(
        _read(project / "src" / "app" / "theme.pss"), filename="theme.pss")
    assert len(sheet.rules) >= 8
    assert [d for d in sheet.diagnostics if d.kind == "error"] == []

    from pydrud.commands.preview import load_preview_app
    saved_path = list(sys.path)
    saved_modules = dict(sys.modules)
    # Earlier suites may leave foreign `app.*` modules behind (e.g. synced
    # hot-reload fixtures); purge them so the import below reads this tmp
    # project, mirroring the other scaffold-import tests.
    for name in [m for m in sys.modules
                 if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    try:
        app = load_preview_app(str(project))
        tree = app.build().to_dict()
    finally:
        sys.path[:] = saved_path
        for name in [m for m in list(sys.modules)
                     if m not in saved_modules
                     or m == "app" or m.startswith("app.")]:
            sys.modules.pop(name, None)
    stack = [tree]
    title = None
    while stack:
        node = stack.pop()
        if node.get("key") == "pydash_title":
            title = node
            break
        stack.extend(node.get("children", []))
    assert title is not None
    assert title["style"]["color"] == "#0F172A"  # from .app-title


def test_analyze_reports_stylesheet_errors(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "broken.pss").write_text("Button { bg #123456; }",
                                    encoding="utf-8")
    (src / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")

    from pydrud.commands.analyzer import run_analysis
    issues = run_analysis(str(src))
    pss_issues = [i for i in issues if i["file"].endswith(".pss")]
    assert pss_issues, "invalid PSS must surface through analyze"
    assert any(i["severity"] == "error" for i in pss_issues)


def test_devrunner_reports_posix_hot_reload_paths(tmp_path, monkeypatch):
    from pydrud.commands.devrunner import DevRunner

    runner = DevRunner.__new__(DevRunner)
    runner.root = str(tmp_path)
    monkeypatch.setattr("os.path.relpath",
                        lambda *args: "src\\app\\theme.pss")
    assert (runner._relative_project_path("anything")
            == "src/app/theme.pss")


def test_run_on_ui_queues_while_starting_instead_of_racing():
    import threading
    from unittest import mock

    from pydrud.runtime.app import App

    app = App(target=lambda page: None, dev_server=False)
    try:
        called = []
        app._running = True
        app._ui_thread_id = None  # event loop not published yet
        reader = mock.Mock(spec=threading.Thread)
        reader.is_alive.return_value = True  # connected, loop starting
        app._reader_thread = reader
        app.run_on_ui(lambda: called.append(True))
        assert called == [], "must queue while the loop is starting"
        assert app._ui_queue.qsize() == 1
        assert app._event_queue.qsize() == 1

        # Headless (no reader at all): inline, exactly as before.
        app._reader_thread = None
        app.run_on_ui(lambda: called.append(True))
        assert called == [True]
    finally:
        app.stop()


def test_preview_doctor_skips_ndk_cmake_and_checks_shell(
        tmp_path, monkeypatch):
    from pydrud.commands import doctor as doctor_module

    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    project = tmp_path / "tasks"
    assert init_platform(str(project), "android")
    monkeypatch.chdir(project)

    monkeypatch.setattr(doctor_module, "_check_python", lambda: True)
    monkeypatch.setattr(doctor_module, "_check_package", lambda *_a: True)
    monkeypatch.setattr(doctor_module, "_check_project_shadowing",
                        lambda _p: True)
    monkeypatch.setattr(doctor_module, "_check_manifest_permissions",
                        lambda _p: True)
    for name in ("_check_java", "_check_android_sdk", "_check_gradle",
                 "_check_adb"):
        monkeypatch.setattr(doctor_module, name, lambda: True)
    for name in ("_check_ndk", "_check_cmake", "_check_chaquopy"):
        monkeypatch.setattr(
            doctor_module, name,
            lambda *_a, _n=name: (_ for _ in ()).throw(
                AssertionError(f"{_n} must be skipped for preview shells")),
        )
    calls = []
    monkeypatch.setattr(doctor_module, "_check_preview_shell",
                        lambda _p: calls.append(True) or True)

    assert doctor_module.run_doctor() is True
    assert calls == [True]


@pytest.mark.skipif(not HAS_JAVALANG, reason="javalang not installed")
def test_preview_java_parses_and_resolves():
    from jinja2 import Environment, PackageLoader

    from pydrud.android.javacheck import check_sources

    env = Environment(loader=PackageLoader("pydrud", "android/templates"),
                      trim_blocks=True, lstrip_blocks=True)
    ctx = {"project_name": "demo_app", "app_name": "DemoApp",
           "pydrud_app_name": "demo_app",
           "package": "com.example.demo_app", "standalone": False,
           "python_entry": "app.android_main"}
    rendered = {
        name: env.get_template("android/" + name).render(**ctx)
        for name in ("PreviewClient.java.j2", "MainActivity.java.j2",
                     "BridgeService.java.j2", "PydrudWorker.java.j2")
    }
    for source in rendered.values():
        javalang.parse.parse(source)
    assert check_sources(rendered) == []
