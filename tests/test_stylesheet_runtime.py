"""PSS loading, App rendering, and stylesheet hot-reload integration tests."""

from __future__ import annotations

from pathlib import Path

from pydrud import App, Button, Scaffold, Text
from pydrud.core.styles.manager import StyleSheetManager


def _button_tree(app: App) -> dict:
    return app.build().to_dict()


def _find_node(tree: dict, key: str) -> dict:
    stack = [tree]
    while stack:
        node = stack.pop()
        if node.get("key") == key:
            return node
        stack.extend(reversed(node.get("children", [])))
    raise AssertionError(f"widget key {key!r} missing from tree")


def _app_with_button(*, stylesheet=None, stylesheets=None) -> App:
    return App(
        target=lambda page: page.add(Button(
            "Save", key="save", class_=["primary"], style={"color": "orange"})),
        stylesheet=stylesheet,
        stylesheets=stylesheets,
        dev_server=False,
    )


def test_app_applies_pss_before_serialization_and_keeps_inline_precedence():
    app = _app_with_button()
    app.add_stylesheet_source(
        "Button { color: red; bg: #112233; }\n"
        ".primary { color: blue; padding: {\"all\": 8}; }"
    )

    tree = _button_tree(app)
    button = _find_node(tree, "save")
    assert button["style"]["color"] == "orange"  # inline wins over class/type
    assert button["style"]["bg"] == "#112233"
    assert button["style"]["padding"] == {"all": 8}
    assert not any(name.startswith("class_") for name in button["style"])
    assert "class_" not in button


def test_pss_style_for_composite_wrapper_reaches_its_rendered_node():
    app = App(
        target=lambda page: page.add(Scaffold(
            body=Text("Body"), key="layout", class_=["screen"])),
        dev_server=False,
    )
    app.add_stylesheet_source(".screen { bg: #445566; }")

    tree = _button_tree(app)
    rendered_scaffold = _find_node(tree, "layout._stack")
    assert rendered_scaffold["style"]["bg"] == "#445566"
    assert not any(key.startswith("class_")
                   for key in rendered_scaffold["style"])


def test_app_loads_explicit_stylesheet_path(tmp_path: Path):
    styles = tmp_path / "theme.pss"
    styles.write_text("Button { bg: #AABBCC; }", encoding="utf-8")
    app = _app_with_button(stylesheet=styles)

    assert _find_node(_button_tree(app), "save")["style"]["bg"] == "#AABBCC"


def test_app_auto_discovers_stylesheets_in_src(tmp_path: Path):
    source = tmp_path / "src" / "app"
    source.mkdir(parents=True)
    (source / "theme.pss").write_text(
        ".primary { bg: #ABCDEF; }", encoding="utf-8")
    manager = StyleSheetManager(tmp_path)
    app = _app_with_button()
    app._project_root = str(tmp_path)
    app._stylesheet_manager = manager

    assert _find_node(_button_tree(app), "save")["style"]["bg"] == "#ABCDEF"


def test_stylesheet_manager_retains_last_good_sheet_after_parse_error(tmp_path: Path):
    source = tmp_path / "src" / "theme.pss"
    source.parent.mkdir(parents=True)
    source.write_text("Button { bg: #112233; }", encoding="utf-8")
    manager = StyleSheetManager(tmp_path)
    assert manager.refresh().rules[0].body.declarations == [("bg", "#112233")]

    source.write_text("Button { bg #FF0000; }", encoding="utf-8")
    sheet = manager.refresh()
    assert sheet.rules[0].body.declarations == [("bg", "#112233")]
    assert manager.diagnostics
    assert manager.diagnostics[0].kind == "error"


def test_stylesheet_manager_removes_deleted_auto_discovered_file(tmp_path: Path):
    source = tmp_path / "src" / "theme.pss"
    source.parent.mkdir(parents=True)
    source.write_text("Button { bg: red; }", encoding="utf-8")
    manager = StyleSheetManager(tmp_path)
    assert len(manager.refresh().rules) == 1

    source.unlink()
    assert manager.refresh().rules == []


def test_pss_file_hot_reload_reapplies_styles_without_reloading_target(
    tmp_path: Path,
):
    source = tmp_path / "theme.pss"
    source.write_text("Button { bg: red; }", encoding="utf-8")
    app = _app_with_button(stylesheet=source)
    target = app.target
    app.build()
    assert app._desired_tree.find_by_key("save")._effective_style()["bg"] == "red"

    source.write_text("Button { bg: blue; }", encoding="utf-8")
    app._on_hot_reload(str(source))

    assert app.target is target
    assert app._desired_tree.find_by_key("save")._effective_style()["bg"] == "blue"


def test_devserver_hot_reload_deletes_remote_stylesheet_source(tmp_path: Path):
    app = _app_with_button()
    sync_dir = tmp_path / "sync"
    app._get_sync_dir = lambda: str(sync_dir)

    created = app.apply_hot_reload([{
        "path": "src/app/theme.pss",
        "content": "Button { bg: red; }",
    }])
    assert created["status"] == "ok"
    assert _find_node(app._desired_tree.to_dict(), "save")["style"]["bg"] == "red"
    synchronized = sync_dir / "app" / "theme.pss"
    assert synchronized.exists()

    deleted = app.apply_hot_reload([], deleted=["src/app/theme.pss"])

    assert deleted["status"] == "ok"
    assert "bg" not in _find_node(app._desired_tree.to_dict(), "save")["style"]
    assert not synchronized.exists()


def test_hot_restart_reconciles_deleted_remote_stylesheets(tmp_path: Path):
    app = _app_with_button()
    sync_dir = tmp_path / "sync"
    app._get_sync_dir = lambda: str(sync_dir)

    app.apply_hot_restart([{
        "path": "src/app/theme.pss",
        "content": "Button { bg: purple; }",
    }])
    assert app._desired_tree.find_by_key("save")._effective_style()["bg"] == "purple"
    synchronized = sync_dir / "app" / "theme.pss"
    assert synchronized.exists()

    app.apply_hot_restart([])

    assert "bg" not in app._desired_tree.find_by_key("save")._effective_style()
    assert not synchronized.exists()


def test_invalid_pss_hot_reload_keeps_last_good_styles_and_reports_diagnostic(
    tmp_path: Path,
):
    source = tmp_path / "theme.pss"
    source.write_text("Button { bg: green; }", encoding="utf-8")
    app = _app_with_button(stylesheet=source)
    app.build()

    source.write_text("Button { bg #000000; }", encoding="utf-8")
    app._on_hot_reload(str(source))

    assert app._desired_tree.find_by_key("save")._effective_style()["bg"] == "green"
    assert any(d.kind == "error" for d in app.stylesheet_diagnostics)


def test_devserver_hot_reload_accepts_pss_content_without_python_compilation(
    tmp_path: Path,
):
    app = _app_with_button()
    app._get_sync_dir = lambda: str(tmp_path / "sync")

    response = app.apply_hot_reload([{
        "path": "src/app/theme.pss",
        "content": "Button { bg: #123456; }",
    }])

    assert response["status"] == "ok"
    assert response["reloaded"] == []
    assert _find_node(app._desired_tree.to_dict(), "save")["style"]["bg"] == "#123456"
    assert (tmp_path / "sync" / "app" / "theme.pss").read_text(encoding="utf-8") \
        == "Button { bg: #123456; }"


def test_devserver_rejects_invalid_pss_before_applying_any_file(tmp_path: Path):
    app = _app_with_button()
    sync_dir = tmp_path / "sync"
    app._get_sync_dir = lambda: str(sync_dir)
    updates = []
    app.update = lambda: updates.append(True)

    response = app.apply_hot_reload([{
        "path": "src/app/theme.pss",
        "content": "Button { bg #123456; }",
    }])

    assert response["status"] == "error"
    assert response["error_type"] == "StylesheetError"
    assert not updates
    assert not sync_dir.exists()
