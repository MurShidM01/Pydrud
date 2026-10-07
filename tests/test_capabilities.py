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
