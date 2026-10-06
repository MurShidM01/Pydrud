"""Regression tests for the runtime hardening batch.

Covers: versioned HTTP User-Agent, synchronous permission checks,
TextField ime_action plumbing, tap-outside keyboard dismissal, manifest
cleartext default, and ListView virtualization scaffolding in templates.
"""

import re
from pathlib import Path

from jinja2 import BaseLoader, Environment

from pydrud import __version__
from pydrud.core.results import Result
from pydrud.services import http
from pydrud.services.native import Permissions
from pydrud.widgets.basic import SearchField, TextField

TEMPLATES = (
    Path(__file__).resolve().parent.parent
    / "pydrud" / "android" / "templates" / "android"
)


def test_http_user_agent_tracks_package_version():
    ua = http.user_agent()
    assert __version__ in ua
    assert ua.startswith("Pydrud/")
    assert ua.endswith("(Android)")
    assert "1.2" not in ua


def test_permissions_is_granted_sync_check():
    calls = []

    def invoke(cmd, **kwargs):
        calls.append(cmd)
        result = Result("req-1", cmd)
        result.complete(True)
        return result

    perms = Permissions(invoke)
    assert perms.is_granted("camera") is True
    assert perms.is_granted("android.permission.NFC") is True
    assert calls == ["permission_check", "permission_check"]


def test_permissions_is_granted_denied_and_timeout():
    def denied(cmd, **kwargs):
        result = Result("req-2", cmd)
        result.complete(False)
        return result

    assert Permissions(denied).is_granted("microphone") is False

    def never(cmd, **kwargs):
        return Result("req-3", cmd)  # never completes

    assert Permissions(never).is_granted("camera", timeout=0.01) is False


def test_textfield_ime_action_serialised():
    field = TextField(hint="Search", ime_action="search")
    assert field.style["ime"] == "search"
    default = TextField(hint="Name")
    assert "ime" not in default.style


def test_searchfield_defaults_to_search_ime():
    assert SearchField().style["ime"] == "search"


def test_textfield_submit_event_binding():
    handled = []
    field = TextField(on_submit=lambda event: handled.append(event))
    assert "submit" in field.event_handlers
    assert field.event_handlers["submit"] is not None


def _render_manifest(**ctx):
    env = Environment(loader=BaseLoader())
    tpl = env.from_string(
        (TEMPLATES / "AndroidManifest.xml.j2").read_text(encoding="utf-8"))
    base = dict(project_name="Demo", app_name="Demo", pydrud_app_name="demo")
    base.update(ctx)
    return tpl.render(**base)


def test_manifest_allows_cleartext_by_default():
    out = _render_manifest()
    assert 'android:usesCleartextTraffic="true"' in out


def test_manifest_cleartext_opt_out():
    out = _render_manifest(cleartext_traffic=False)
    assert 'android:usesCleartextTraffic="false"' in out


def test_main_activity_has_no_deprecated_back_override():
    text = (TEMPLATES / "MainActivity.java.j2").read_text(encoding="utf-8")
    assert "OnBackPressedDispatcher" in text or "OnBackPressedCallback" in text
    assert not re.search(r"public void onBackPressed\(\)", text)


def test_main_activity_dismisses_keyboard_on_outside_tap():
    text = (TEMPLATES / "MainActivity.java.j2").read_text(encoding="utf-8")
    assert "dispatchTouchEvent" in text
    assert "hideSoftInputFromWindow" in text


def test_viewfactory_lists_virtualize_beyond_threshold():
    from tests import all_java_templates
    text = all_java_templates()
    assert "VIRTUALIZE_THRESHOLD" in text
    assert "RecyclerView" in text
    assert "rebuildListRows" in text


def test_viewfactory_image_pipeline_is_managed():
    from tests import read_template
    # The image pipeline lives in its own ImageLoader collaborator class;
    # scope the raw-thread ban to it (worker/bridge threads elsewhere are
    # unrelated to image decoding).
    text = read_template("ImageLoader.java.j2")
    assert "IMAGE_EXECUTOR" in text and "newFixedThreadPool" in text
    assert "IMAGE_CACHE" in text and "LruCache" in text
    assert "inSampleSize" in text           # downsampling
    assert "pydrud_tag_image" in text       # cancellation token
    # No raw fire-and-forget image threads; the only Thread construction
    # allowed is inside the named pool factory.
    raw = [l for l in text.splitlines()
           if "new Thread(() ->" in l or 'new Thread("' in l]
    assert not raw
