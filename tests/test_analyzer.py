"""Static analyzer: findings, de-duplication and registry drift."""

import contextlib
import inspect
import io
import os
import shutil
import tempfile
import unittest

import pydrud
from pydrud.commands.analyzer import _WIDGET_CLASSES, _analyze_file, run_analysis
from pydrud.commands.project import create_project
from pydrud.commands.project_config import set_scalar
from pydrud.widgets.base import Widget

NESTED = """
from pydrud import Text
def f(page, rows):
    for r in rows:
        for c in r:
            page.add(Text(c))
            page.update()
"""

CLEAN = """
from pydrud import Text
def f(page, rows):
    for r in rows:
        page.add(Text(r, key=f"row-{r}"))
    page.update()
"""


def messages(source):
    return [(i["line"], i["message"]) for i in _analyze_file(source, "x.py")]


class TestAnalyzer(unittest.TestCase):
    def test_nested_loops_report_once(self):
        found = messages(NESTED)
        self.assertEqual(len(found), 2, found)
        self.assertIn("without an explicit key=", found[0][1])
        self.assertIn("page.update() inside a loop", found[1][1])

    def test_keyed_widgets_are_clean(self):
        self.assertEqual(messages(CLEAN), [])

    def test_issues_are_sorted_by_line(self):
        lines = [line for line, _ in messages(NESTED)]
        self.assertEqual(lines, sorted(lines))

    def test_syntax_errors_are_reported(self):
        issues = _analyze_file("def (:\n", "bad.py")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "error")

    def test_unknown_style_key(self):
        source = 'from pydrud import Text\nText("hi", style={"nope": 1})\n'
        self.assertTrue(any("Unknown style key" in m for _, m in
                            messages(source)))


class TestHostOnlyImports(unittest.TestCase):
    """DX-003: build-time-only pydrud modules must not be imported by an app."""

    def test_a_build_time_only_import_is_an_error(self):
        for source, part in (
            ("import pydrud.commands\n", "commands"),
            ("from pydrud.android import templates\n", "android"),
            ("from pydrud.utils import tui\n", "utils"),
            ("from pydrud.commands.packages import Requirements\n", "commands"),
            ("import pydrud.preview\n", "preview"),
        ):
            with self.subTest(source=source.strip()):
                found = [i for i in _analyze_file(
                    source, "x.py", runtime="chaquopy")
                         if i["severity"] == "error"]
                self.assertTrue(
                    any(f"pydrud.{part}" in i["message"] for i in found), found)

    def test_pydash_skips_apk_bundler_checks_but_rejects_android_adapters(self):
        host_only = "from pydrud.commands.packages import Requirements\n"
        self.assertEqual(
            _analyze_file(host_only, "x.py", runtime="pydash"), [])

        for source in (
            "from pydrud.android import templates\n",
            "from pydrud.platforms import android\n",
            "import pydrud.platforms.android.logging\n",
        ):
            with self.subTest(source=source.strip()):
                issues = _analyze_file(source, "x.py", runtime="pydash")
                self.assertEqual(len(issues), 1)
                self.assertIn("Android-specific", issues[0]["message"])
                self.assertNotIn("APK", issues[0]["message"])

    def test_runtime_imports_are_clean(self):
        source = ("from pydrud import App, Text, Colors\n"
                  "import pydrud.icons\n"
                  "from pydrud.core.diff import TreeDiff\n")
        self.assertEqual(_analyze_file(source, "x.py"), [])


class TestCameraOptInAnalysis(unittest.TestCase):
    """``pydrud analyze`` catches camera use the APK cannot serve."""

    SCREEN = ("from pydrud import CameraPreview, Column\n\n"
              "def home_screen(page):\n"
              "    return Column(children=[CameraPreview(key=\"cam\")])\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-analyze-camera-")
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        create_project("camapp", org="com.example", runtime="chaquopy")
        self.project = os.path.join(self.tmp, "camapp")
        self.src = os.path.join(self.project, "src")
        with open(os.path.join(self.src, "app", "screens", "home.py"), "w",
                  encoding="utf-8") as handle:
            handle.write(self.SCREEN)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def camera_issues(self):
        return [issue for issue in run_analysis(self.src, runtime="chaquopy")
                if "camera stack" in issue["message"]]

    def test_camera_use_without_the_stack_is_reported(self):
        issues = self.camera_issues()
        self.assertEqual(len(issues), 1, issues)
        self.assertEqual(issues[0]["file"], os.path.join("app", "screens",
                                                         "home.py"))
        self.assertEqual(issues[0]["severity"], "warning")
        self.assertIn("camera: true", issues[0]["message"])

    def test_enabling_the_stack_clears_the_warning(self):
        set_scalar(self.project, "camera", True)
        self.assertEqual(self.camera_issues(), [])

    def test_the_bundled_runtime_is_not_reported(self):
        """``src/pydrud`` *defines* CameraPreview; it does not use it."""
        with open(os.path.join(self.src, "app", "screens", "home.py"), "w",
                  encoding="utf-8") as handle:
            handle.write("from pydrud import Text\n")
        self.assertEqual(self.camera_issues(), [])

    def test_pydash_projects_are_never_reported(self):
        """Pydash renders through the client app, which ships a camera."""
        pydash = os.path.join(self.tmp, "preview")
        with contextlib.redirect_stdout(io.StringIO()):
            create_project("preview", org="com.example")
        src = os.path.join(pydash, "src")
        with open(os.path.join(src, "app", "screens", "home.py"), "w",
                  encoding="utf-8") as handle:
            handle.write(self.SCREEN)
        issues = [issue for issue in run_analysis(src, runtime="pydash")
                  if "camera stack" in issue["message"]]
        self.assertEqual(issues, [])


class TestWidgetRegistryDrift(unittest.TestCase):
    def test_analyzer_knows_every_exported_widget(self):
        """A new widget must be added to ``_WIDGET_CLASSES`` as well."""
        exported = {
            name for name in dir(pydrud)
            if inspect.isclass(getattr(pydrud, name))
            and issubclass(getattr(pydrud, name), Widget)
            and getattr(pydrud, name) is not Widget
        }
        self.assertEqual(exported - _WIDGET_CLASSES, set())
        self.assertEqual(_WIDGET_CLASSES - exported, set())


if __name__ == "__main__":
    unittest.main()
