from __future__ import annotations

from pydrud.runtime.app import App
from pydrud.testing import AppTester, FakeDevice, FakeRenderer
from pydrud.widgets import NativeView, Text


def test_fake_device_is_backwards_compatible_renderer_alias():
    assert FakeDevice is FakeRenderer


def test_renderer_missing_capabilities_uses_visible_widget_fallback_and_fails_result():
    def main(page):
        page.add(NativeView("example.controls.Gauge", key="native-gauge"))

    capabilities = {
        "services": [],
        "widget_types": ["Stack", "Column", "Text"],
        "native_view": False,
    }
    with AppTester(main, capabilities=capabilities) as app:
        rendered = app.device.root.find("native-gauge")
        assert rendered is not None
        assert rendered.type == "Text"
        assert rendered.props["value"] == "Unsupported widget: NativeView"
        assert app.device.root.texts().count("Unsupported widget: NativeView") == 1

        result = app.app.invoke("camera_scan", key="native-gauge")
        assert result.done
        assert "camera" in result.error
        assert "camera_scan" in result.error
        assert app.device.commands_named("camera_scan") == []
        assert result.request_id not in app.app._pending


def test_service_capability_map_and_command_list_are_accepted():
    app = App()
    app._connected = True
    app._native_capabilities = {"services": {"camera": True}}
    sent = []
    app._send = sent.append

    result = app.invoke("camera_scan", key="camera")
    assert not result.done
    assert len(sent) == 1
    assert '"cmd": "camera_scan"' in sent[0]
    app._resolve_result({
        "request_id": result.request_id,
        "ok": True,
        "value": {"value": "decoded"},
    })
    assert result.result(timeout=0) == {"value": "decoded"}

    app._native_capabilities = {"commands": ["custom_lookup"]}
    custom = app.invoke("custom_lookup", key="item")
    assert not custom.done
    assert len(sent) == 2


def test_missing_declared_widget_type_becomes_text_and_warns_once(caplog):
    from pydrud.runtime._capabilities import replace_unsupported_widgets
    from pydrud.widgets.base import Widget

    class UnsupportedForCapabilityTest(Widget):
        _widget_type = "UnsupportedForCapabilityTest"

    capabilities = {"widget_types": ["Text"]}
    root = UnsupportedForCapabilityTest(key="unsupported")
    root = replace_unsupported_widgets(root, capabilities)
    assert isinstance(root, Text)
    assert root.key == "unsupported"
    assert root.value == "Unsupported widget: UnsupportedForCapabilityTest"

    replace_unsupported_widgets(
        UnsupportedForCapabilityTest(key="unsupported-again"), capabilities)
    warnings = [record for record in caplog.records
                if "UnsupportedForCapabilityTest" in record.getMessage()]
    assert len(warnings) == 1
    assert "widget_types" in warnings[0].getMessage()


def test_native_view_requires_explicit_capability_even_with_widget_catalogue():
    from pydrud.runtime._capabilities import widget_supported

    assert not widget_supported(
        {"widget_types": ["NativeView", "Text"], "native_view": False},
        "NativeView",
    )
    assert widget_supported({"native_view": True}, "NativeView")
    assert widget_supported({}, "Text")


def test_composite_widgets_are_checked_by_their_rendered_type():
    """Scaffold/AppBar/FAB serialise as Stack/Row/Container.

    Regression: the capability check used the Python ``_widget_type``, so a
    supported ``Scaffold`` was mistaken for an unsupported widget and the
    whole screen collapsed to a single ``Text`` placeholder.
    """
    from pydrud import AppBar, Column, FloatingActionButton, Scaffold
    from pydrud.runtime._capabilities import replace_unsupported_widgets

    capabilities = {
        "widget_types": ["Stack", "Column", "Row", "Container", "Text", "Icon"],
    }
    tree = Scaffold(
        key="screen",
        app_bar=AppBar(title="Demo", key="bar"),
        body=Column(key="body", children=[Text("hello", key="greeting")]),
        floating_action_button=FloatingActionButton(key="add", icon="plus"),
    )

    assert tree.render_type() == "Stack"
    result = replace_unsupported_widgets(tree, capabilities)
    assert result is tree
    assert result.find_by_key("greeting") is not None
    assert result.find_by_key("add").render_type() == "Container"
    assert "Unsupported widget" not in result.to_json()


def test_unsupported_widget_inside_composite_is_replaced_and_survives_serialisation():
    from pydrud import Column, Scaffold, WebView
    from pydrud.runtime._capabilities import replace_unsupported_widgets

    capabilities = {"widget_types": ["Stack", "Column", "Container", "Text"]}
    tree = Scaffold(
        key="screen",
        body=Column(key="body", children=[
            Text("ok", key="keep"),
            WebView("https://example.com", key="web"),
        ]),
    )
    replace_unsupported_widgets(tree, capabilities)

    def collect(node, out):
        out.append((node["type"], node["key"]))
        for child in node.get("children", []):
            collect(child, out)

    wire: list[tuple[str, str]] = []
    collect(tree.to_dict(), wire)
    assert ("Text", "web") in wire
    assert ("WebView", "web") not in wire
    assert ("Text", "keep") in wire
