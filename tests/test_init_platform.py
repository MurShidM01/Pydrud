"""Tests for 2.1.0 platform workflows: ``create`` + ``init android``.

``pydrud init android`` always generates the standalone (Chaquopy) target
with embedded Python, so the generated APK runs the app offline. This also
covers ``sync`` shape generation, the starter PSS theme, the Windows
hot-reload path fix and the UI-queue startup race fix.
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


def test_init_android_builds_a_standalone_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli, ["init", "android"],
                                catch_exceptions=False)
    assert result.exit_code == 0, result.output

    gradle = _read(project / "android" / "app" / "build.gradle.kts")
    assert "com.chaquo.python" in gradle
    assert "chaquopy {" in gradle
    assert "ndkVersion" in gradle
    root_gradle = _read(project / "android" / "build.gradle.kts")
    assert "com.chaquo.python" in root_gradle
    assert "chaquo.com" in _read(
        project / "android" / "settings.gradle.kts")

    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    # No preview client / connect screen in the standalone target.
    assert not (java_dir / "PreviewClient.java").exists()
    activity = _read(java_dir / "TasksActivity.java")
    assert "showPreviewConnect" not in activity
    # The activity is backend-agnostic: the runtime is chosen by the factory
    # and the Chaquopy JNI calls live only in ChaquopyRuntime.
    assert "PydrudRuntimeFactory.create()" in activity
    assert "com.chaquo.python" not in activity
    assert 'runtime.startApp("app.android_main")' in activity
    assert "Python.start" in _read(java_dir / "ChaquopyRuntime.java")
    assert (java_dir / "PythonRuntime.java").is_file()
    assert (java_dir / "PydrudRuntimeFactory.java").is_file()
    assert "PydrudWorker" in _read(java_dir / "PydrudWorker.java")

    assert 'runtime = "chaquopy"' in _read(project / "pydrud.toml")
    assert resolve_runtime(str(project)).runtime is Runtime.CHAQUOPY
    assert android_is_standalone(str(project)) is True
    # Embedded interpreter: bundled runtime, setup.py and adapters exist.
    assert (project / "src" / "pydrud" / "__init__.py").is_file()
    assert (project / "setup.py").is_file()
    assert (project / "src" / "app" / "android_main.py").is_file()
    assert (project / "src" / "app" / "jobs.py").is_file()


def test_init_android_embeds_python(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android")

    gradle = _read(project / "android" / "app" / "build.gradle.kts")
    assert "com.chaquo.python" in gradle
    assert "chaquopy {" in gradle
    assert "ndkVersion" in gradle
    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    activity = _read(java_dir / "TasksActivity.java")
    assert "PydrudRuntimeFactory.create()" in activity
    assert "showPreviewConnect" not in activity
    assert 'runtime.startApp("app.android_main")' in activity
    assert "Python.start" in _read(java_dir / "ChaquopyRuntime.java")
    assert (project / "src" / "app" / "android_main.py").is_file()
    assert (project / "src" / "app" / "jobs.py").is_file()
    assert (project / "setup.py").is_file()
    assert (project / "src" / "pydrud" / "__init__.py").is_file()
    assert android_is_standalone(str(project)) is True


def test_init_android_host_backend_has_no_chaquopy(tmp_path, monkeypatch):
    """`init android --backend host` builds a target with no Chaquopy."""
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android", backend="host")

    gradle = _read(project / "android" / "app" / "build.gradle.kts")
    assert "com.chaquo.python" not in gradle
    assert "chaquopy {" not in gradle
    assert "com.chaquo.python" not in _read(
        project / "android" / "build.gradle.kts")
    assert "chaquo.com" not in _read(
        project / "android" / "settings.gradle.kts")

    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    # Only the host backend is generated; the Chaquopy runtime is absent.
    assert (java_dir / "HostRuntime.java").is_file()
    assert not (java_dir / "ChaquopyRuntime.java").exists()
    assert "return new HostRuntime();" in _read(
        java_dir / "PydrudRuntimeFactory.java")
    assert "com.chaquo.python" not in _read(java_dir / "TasksActivity.java")

    assert 'runtime = "host"' in _read(project / "pydrud.toml")
    assert resolve_runtime(str(project)).runtime is Runtime.HOST
    assert android_is_standalone(str(project)) is True

    # The bridge dials the host instead of listening on loopback.
    bridge = _read(java_dir / "BridgeService.java")
    assert "clientMode" in bridge
    assert "PydrudRuntimeConfig.REMOTE_HOST" in bridge
    assert "PydrudRuntimeConfig.REMOTE_PORT" in bridge
    assert "runClient" in bridge
    # The host/port the device dials come from the generated config.
    config = _read(java_dir / "PydrudRuntimeConfig.java")
    assert 'BACKEND = "host"' in config
    assert 'REMOTE_HOST = "127.0.0.1"' in config
    assert "REMOTE_PORT = 8597" in config


def test_host_backend_remote_address_is_configurable(tmp_path, monkeypatch):
    """`preview_host` / `preview_port` in pydrud.yaml drive the dial address."""
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"
    yaml_path = project / "pydrud.yaml"
    yaml_path.write_text(
        _read(yaml_path) + "preview_host: 10.0.2.2\npreview_port: 9100\n",
        encoding="utf-8")

    assert init_platform(str(project), "android", backend="host")

    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    config = _read(java_dir / "PydrudRuntimeConfig.java")
    assert 'REMOTE_HOST = "10.0.2.2"' in config
    assert "REMOTE_PORT = 9100" in config


def test_init_android_none_backend_renders_without_runtime(tmp_path,
                                                           monkeypatch):
    """`init android --backend none` builds a renderer with no runtime."""
    monkeypatch.chdir(tmp_path)
    create_project("tasks", org="com.example")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android", backend="none")

    java_dir = (project / "android" / "app" / "src" / "main" / "java"
                / "com" / "example" / "tasks")
    assert (java_dir / "NoRuntime.java").is_file()
    assert not (java_dir / "ChaquopyRuntime.java").exists()
    assert "return new NoRuntime();" in _read(
        java_dir / "PydrudRuntimeFactory.java")
    assert resolve_runtime(str(project)).runtime is Runtime.NONE
    assert android_is_standalone(str(project)) is True


def test_init_android_rerun_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("tasks")
    project = tmp_path / "tasks"

    assert init_platform(str(project), "android")
    # Re-running is a no-op success.
    assert init_platform(str(project), "android")
    assert android_is_standalone(str(project)) is True
    assert (project / "src" / "app" / "android_main.py").is_file()


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


def test_sync_upgrades_a_chaquopy_free_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("preview_app")
    preview = tmp_path / "preview_app"
    assert init_platform(str(preview), "android")

    # Simulate a target generated by an older release: the Chaquopy-free
    # preview shell had neither the plugin nor the runtime factory.
    gradle = preview / "android" / "app" / "build.gradle.kts"
    gradle.write_text(
        _read(gradle).replace('id("com.chaquo.python")', ""),
        encoding="utf-8")
    for stale in (preview / "android").rglob("PydrudRuntimeFactory.java"):
        stale.unlink()
    assert android_is_standalone(str(preview)) is False

    assert sync_project(str(preview), update_runtime=False)
    assert "com.chaquo.python" in _read(gradle)
    assert android_is_standalone(str(preview)) is True
    assert (preview / "src" / "app" / "android_main.py").is_file()


def test_sync_keeps_a_legacy_chaquopy_entry_point(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_project("legacy_app", runtime="chaquopy")
    legacy = tmp_path / "legacy_app"
    assert sync_project(str(legacy), update_runtime=False)
    assert ("com.chaquo.python" in
            _read(legacy / "android" / "app" / "build.gradle.kts"))
    assert android_is_standalone(str(legacy)) is True
    # Legacy entry point keeps booting app.main; no managed adapter appears.
    assert 'runtime.startApp("app.main")' in _read(
        legacy / "android" / "app" / "src" / "main" / "java" / "com"
        / "example" / "legacy_app" / "LegacyAppActivity.java")
    assert not (legacy / "src" / "app" / "android_main.py").exists()


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
    heading = None
    while stack:
        node = stack.pop()
        if node.get("key") == "hb_number":
            heading = node
            break
        stack.extend(node.get("children", []))
    assert heading is not None
    # The reading is sized to the window with clamp(78px, 24vw, 108px) in
    # app/screens/heartbeat.py (PSS has no viewport units), so with no device
    # connected it sits inside the design's band.
    assert 78 <= heading["style"]["font"]["size"] <= 108
    # Its colour comes from the theme role, so it tracks light/dark.
    from pydrud import Theme
    assert heading["style"]["font"]["color"] == Theme.text


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


def test_doctor_checks_the_standalone_toolchain(tmp_path, monkeypatch):
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

    calls = []
    for name in ("_check_ndk", "_check_cmake"):
        monkeypatch.setattr(
            doctor_module, name,
            lambda _n=name: calls.append(_n) or True)
    monkeypatch.setattr(doctor_module, "_check_chaquopy",
                        lambda _p: calls.append("_check_chaquopy") or True)

    assert doctor_module.run_doctor() is True
    # The standalone target needs the NDK, CMake and Chaquopy checks.
    assert calls == ["_check_ndk", "_check_cmake", "_check_chaquopy"]


@pytest.mark.skipif(not HAS_JAVALANG, reason="javalang not installed")
def test_generated_java_parses_and_resolves():
    from jinja2 import Environment, PackageLoader

    from pydrud.android.javacheck import check_sources

    env = Environment(loader=PackageLoader("pydrud", "android/templates"),
                      trim_blocks=True, lstrip_blocks=True)
    ctx = {"project_name": "demo_app", "app_name": "DemoApp",
           "pydrud_app_name": "demo_app",
           "package": "com.example.demo_app",
           "python_entry": "app.android_main"}
    rendered = {
        name: env.get_template("android/" + name).render(**ctx)
        for name in ("MainActivity.java.j2", "BridgeService.java.j2",
                     "PydrudWorker.java.j2")
    }
    for source in rendered.values():
        javalang.parse.parse(source)
    assert check_sources(rendered) == []
