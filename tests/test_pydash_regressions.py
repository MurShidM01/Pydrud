"""Regression coverage for Pydash integration friction points."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest

from pydrud import (App, AppBar, CameraPreview, Column, Container, Image,
                    QRScanner, SvgPicture, Text, Theme)
from click.testing import CliRunner

from pydrud.commands.cli import main as cli
from pydrud.commands.project import create_project, sync_project
from pydrud.commands.release import resolve_capability
from pydrud.core.diff import TreeDiff
from pydrud.core.results import Result, ResultError
from pydrud.testing import AppTester
from pydrud.widgets.base import assign_stable_keys


class TestManifestAndCliRegressions(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pydrud-regressions-")
        self.previous_cwd = os.getcwd()
        os.chdir(self.root)
        self.project = os.path.join(self.root, "camera_app")
        create_project("camera_app", org="com.example", runtime="chaquopy")

    def tearDown(self):
        os.chdir(self.previous_cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def test_yaml_permissions_are_rendered_and_qualified_input_is_normalised(self):
        yaml = os.path.join(self.project, "pydrud.yaml")
        with open(yaml, "a", encoding="utf-8") as handle:
            handle.write("permissions: [android.permission.CAMERA, RECORD_AUDIO]\n")
        self.assertTrue(sync_project(self.project, update_runtime=False))
        manifest = os.path.join(self.project, "android", "app", "src", "main",
                                "AndroidManifest.xml")
        rendered = open(manifest, encoding="utf-8").read()
        self.assertIn('android.permission.CAMERA', rendered)
        self.assertIn('android.permission.RECORD_AUDIO', rendered)
        self.assertNotIn('android.permission.android.permission', rendered)

    def test_capability_mistake_has_permission_command_suggestion(self):
        with self.assertRaises(ValueError) as caught:
            resolve_capability("camera")
        self.assertEqual(str(caught.exception),
                         "Did you mean 'pydrud permissions add camera'?")

        original = os.getcwd()
        try:
            os.chdir(self.project)
            result = CliRunner().invoke(cli, ["capabilities", "add", "camera"])
        finally:
            os.chdir(original)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Did you mean 'pydrud permissions add camera'?", result.output)
        self.assertNotIn("ValueError", result.output)


class TestAsyncAndPermissionStatus(unittest.TestCase):
    def test_result_is_a_real_awaitable(self):
        result = Result("request", "dialog")

        async def consume():
            return await result

        async def complete():
            task = asyncio.create_task(consume())
            await asyncio.sleep(0)
            result.complete(True)
            return await task

        self.assertTrue(asyncio.run(complete()))

        failed = Result("request", "dialog")

        async def consume_failure():
            return await failed

        async def fail_it():
            task = asyncio.create_task(consume_failure())
            await asyncio.sleep(0)
            failed.fail("cancelled")
            with self.assertRaises(ResultError):
                await task

        asyncio.run(fail_it())

    def test_async_click_handler_can_await_native_service(self):
        seen: list[object] = []

        def main(page):
            async def ask(_event):
                answer = await page.dialog.confirm("Continue?")
                seen.append(answer)
            page.add(Text("Ask", key="ask", on_click=ask))

        with AppTester(main) as app:
            app.answer("dialog", True)
            app.tap("ask")
            self.assertTrue(app.device.wait_for(lambda _device: bool(seen)))
            self.assertEqual(seen, [True])

    def test_status_uses_non_prompting_native_command(self):
        app = App(target=lambda page: page.add(Text("x")))
        app.build()
        result = app.page.permissions.status("camera")
        self.assertEqual(result.cmd, "permission_status")


class TestWidgetQualityOfLife(unittest.TestCase):
    def test_camera_auto_permission_fallback_and_scanner_props(self):
        fallback = Container(key="fallback", child=Text("Enable camera"))
        camera = CameraPreview(key="camera", fallback=fallback)
        data = camera.to_dict()
        self.assertTrue(data["props"]["autoRequestPermission"])
        self.assertEqual(data["props"]["fallbackKey"], "fallback")
        self.assertEqual(data["children"][0]["key"], "fallback")

        scanner = QRScanner(key="scanner", on_scan=lambda event: None)
        props = scanner.to_dict()["props"]
        self.assertTrue(props["scan"])
        self.assertTrue(props["scanOverlay"])
        self.assertEqual(props["scanFormats"], ["QR_CODE"])

    def test_app_bar_density_is_instance_specific_and_safe_by_default(self):
        compact = AppBar("Compact", density="compact").to_dict()["style"]
        comfy = AppBar("Comfy", density="comfortable").to_dict()["style"]
        self.assertLess(compact["minHeight"], comfy["minHeight"])
        self.assertTrue(compact["safeAreaTop"])
        with self.assertRaises(ValueError):
            AppBar("Bad", density="huge")

    def test_compact_density_shrinks_the_action_slot_halo(self):
        """A compact bar's controls must not stretch it back to full height.

        An icon button keeps its own (tall) touch target, so a compact bar has
        to stop adding the 12dp halo a normal bar wraps around each control —
        otherwise the slot, not the density, decides the bar height.
        """
        from pydrud import IconButton, Icons

        def slot_pad(density):
            bar = AppBar("Bar", density=density,
                         actions=[IconButton(Icons.QR_CODE)]).to_dict()
            slots = [child for child in bar["children"][0]["children"]
                     if child["key"].endswith("_action0")]
            return slots[0]["style"]["padding"]

        self.assertEqual(slot_pad("compact")["top"], 2)
        self.assertEqual(slot_pad("normal")["top"], 12)

    def test_svg_api_and_plain_image_share_the_native_image_type(self):
        self.assertEqual(Image("art.svg").to_dict()["type"], "Image")
        self.assertEqual(SvgPicture("art.svg").to_dict()["type"], "Image")
        with self.assertRaises(ValueError):
            SvgPicture("art.png")

    def test_keyless_reorder_preserves_matching_native_views(self):
        old = assign_stable_keys(Column(children=[Text("A"), Text("B")]))
        new = assign_stable_keys(Column(children=[Text("B"), Text("A")]))
        patches = TreeDiff.diff(old, new)
        self.assertEqual([patch.op for patch in patches], ["move"])

    def test_system_theme_marks_the_next_connected_theme_for_dynamic_lookup(self):
        Theme.system()
        self.assertTrue(Theme._uses_system())
        self.assertTrue(Theme._apply_system_palette({
            "available": True, "primary": "#FF123456", "secondary": "#FF654321",
            "background": "#FFFEFEFE", "surface": "#FFFFFFFF",
            "on_surface": "#FF111111", "dark": False,
        }))
        self.assertEqual(Theme.primary, "#FF123456")
        Theme.seed("#FF6366F1")  # Reset global state for the rest of the suite.


if __name__ == "__main__":
    unittest.main()
