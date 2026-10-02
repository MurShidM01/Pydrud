"""
Tests for ``pydrud init`` — the generated project must be complete,
syntactically valid (Python *and* Java) and runnable.
"""

from __future__ import annotations

import ast
import compileall
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from jinja2 import Environment, PackageLoader, select_autoescape

from pydrud.commands.project import bundled_runtime_size_kb, create_project

# Packages the scaffold deliberately leaves out of the APK. Nothing that
# ships may import them: they are not there at runtime.
BUILD_TIME_ONLY = ("pydrud.android", "pydrud.commands", "pydrud.utils",
                   "pydrud.packages")


def bundle_files(bundle: str) -> list:
    """``(size_in_bytes, relative_path)`` for everything in *bundle*."""
    found = []
    for root, dirs, files in os.walk(bundle):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(root, name)
            found.append((os.path.getsize(path),
                          os.path.relpath(path, bundle)))
    return sorted(found, reverse=True)


def imported_modules(path: str, module: str):
    """Absolute dotted names imported by the Python file at *path*.

    Relative imports are resolved against *module* (the file's own dotted
    name) so ``from ..utils import tui`` is reported as ``pydrud.utils``.
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    package = module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: strip one package per leading dot
                base = package.split(".")
                base = base[:len(base) - node.level + 1]
                prefix = ".".join(base)
            else:
                prefix = ""
            name = ".".join(p for p in (prefix, node.module or "") if p)
            yield node.lineno, name
            for alias in node.names:  # `from pydrud import utils`
                yield node.lineno, f"{name}.{alias.name}"

try:
    import javalang
    HAS_JAVALANG = True
except ImportError:  # pragma: no cover - optional dev dependency
    HAS_JAVALANG = False


JAVA_TEMPLATES = [
    "android/MainActivity.java.j2",
    "android/BridgeService.java.j2",
    "android/ViewFactory.java.j2",
    "android/EventDispatcher.java.j2",
    "android/WidgetRegistry.java.j2",
    "android/ViewCreator.java.j2",
]

def all_java_templates() -> list:
    """Every ``*.java.j2`` shipped under ``android/templates/android``."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(here, "pydrud", "android", "templates", "android")
    return sorted("android/" + f for f in os.listdir(folder)
                  if f.endswith(".java.j2"))


def _declared(node, want_static=None) -> tuple:
    """(method names, field names) declared directly on ``node``."""
    names = {m.name for m in node.methods
             if want_static is None
             or ("static" in m.modifiers) == want_static}
    fields = {d.name for f in node.fields
              if want_static is None
              or ("static" in f.modifiers) == want_static
              for d in f.declarators}
    return names, fields


def outer_instance_uses(outer, template: str) -> list:
    """Bare uses of ``outer``'s instance members inside its static classes."""
    methods, fields = _declared(outer, want_static=False)
    found = []
    nested_classes = [m for m in outer.body
                      if isinstance(m, javalang.tree.ClassDeclaration)
                      and "static" in m.modifiers]
    for nested in nested_classes:
        own_methods, own_fields = _declared(nested)
        for _, call in nested.filter(javalang.tree.MethodInvocation):
            if (not call.qualifier and call.member in methods
                    and call.member not in own_methods):
                found.append(f"{template}: {outer.name}.{nested.name} "
                             f"calls instance method {call.member}()")
        for _, ref in nested.filter(javalang.tree.MemberReference):
            if (not ref.qualifier and ref.member in fields
                    and ref.member not in own_fields):
                found.append(f"{template}: {outer.name}.{nested.name} "
                             f"reads instance field {ref.member}")
    return sorted(set(found))


CTX = {
    "project_name": "demo_app",
    "app_name": "DemoApp",
    "pydrud_app_name": "demo_app",
    "package": "com.example.demo_app",
    "package_path": "com/example/demo_app",
    "min_sdk": 24,
    "target_sdk": 35,
    "compile_sdk": 35,
    "build_tools_version": "36.0.0",
    "gradle_version": "8.7",
    "chaquopy_version": "15.0.1",
    "python_version": "3.11",
    "sdk_dir": "/opt/android-sdk",
    "python_executable": "python3",
    "ndk": "29.0.14206865",
}


class TestGeneratedProject(unittest.TestCase):
    """A freshly scaffolded project is complete and valid."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-scaffold-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("demo_app", org="com.example")
        cls.project = os.path.join(cls.tmp, "demo_app")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def path(self, *parts: str) -> str:
        return os.path.join(self.project, *parts)

    def test_essential_files_exist(self):
        required = [
            "pydrud.yaml",
            "setup.py",
            "run.py",
            ".gitignore",
            "src/app/main.py",
            "src/app/__init__.py",
            "src/pydrud/__init__.py",
            "android/gradlew",
            "android/gradlew.bat",
            "android/settings.gradle.kts",
            "android/build.gradle.kts",
            "android/app/build.gradle.kts",
            "android/gradle/wrapper/gradle-wrapper.properties",
            "android/app/src/main/AndroidManifest.xml",
            "android/app/src/main/res/values/themes.xml",
            "android/app/src/main/res/values/ids.xml",
            "android/app/src/main/java/com/example/demo_app/DemoAppActivity.java",
            "android/app/src/main/java/com/example/demo_app/BridgeService.java",
            "android/app/src/main/java/com/example/demo_app/ViewFactory.java",
        ]
        for rel in required:
            self.assertTrue(os.path.isfile(self.path(rel)), f"missing {rel}")

    def test_launcher_icons_copied(self):
        icon = self.path("android/app/src/main/res/mipmap-hdpi/ic_launcher.png")
        self.assertTrue(os.path.isfile(icon))

    def test_gradlew_is_executable_and_bootstraps(self):
        gradlew = self.path("android/gradlew")
        if sys.platform != "win32":
            self.assertTrue(os.access(gradlew, os.X_OK), "gradlew is not executable")
        content = open(gradlew, encoding="utf-8").read()
        # The wrapper JAR is not shipped, so the script must be able to
        # fetch a Gradle distribution by itself.
        self.assertIn("distributionUrl", content)
        self.assertIn("pydrud-dists", content)

    def test_gradlew_shell_syntax_is_valid(self):
        if shutil.which("sh") is None:  # pragma: no cover
            self.skipTest("no POSIX shell available")
        result = subprocess.run(
            ["sh", "-n", self.path("android/gradlew")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_python_compiles(self):
        ok = compileall.compile_dir(
            self.path("src", "app"), quiet=2, force=True
        )
        self.assertTrue(ok, "generated Python does not compile")
        ok_run = compileall.compile_file(self.path("run.py"), quiet=2, force=True)
        self.assertTrue(ok_run)

    def test_generated_app_builds_a_widget_tree(self):
        """The starter app must actually render without a device attached."""
        sys.path.insert(0, self.path("src"))
        try:
            for mod in [m for m in list(sys.modules) if m.startswith("app")]:
                del sys.modules[mod]
            import app.main as starter  # noqa: WPS433

            from pydrud import App
            tree = App(target=starter.main).build()
            widgets = [w for w, _ in tree.walk()]
            self.assertGreater(len(widgets), 15)
            texts = [
                w._serialise_props().get("value")
                for w in widgets
                if w._widget_type == "Text"
            ]
            self.assertIn("TAPS TODAY", texts)
            self.assertIn("To-do", texts)
        finally:
            sys.path.remove(self.path("src"))
            for mod in [m for m in list(sys.modules) if m.startswith("app")]:
                del sys.modules[mod]

    def test_bundled_runtime_is_slim(self):
        bundle = self.path("src", "pydrud")
        self.assertTrue(os.path.isfile(os.path.join(bundle, "main.py")))
        # Build-time only code must not ship inside the APK.
        for name in ("android", "commands", "utils"):
            self.assertFalse(os.path.isdir(os.path.join(bundle, name)),
                             f"build-time only package '{name}' was bundled")
        self.assertFalse(os.path.isfile(os.path.join(bundle, "packages.py")),
                         "pydrud.packages only aliases the CLI package")

        # Measured with CRLF counted as one byte, so a Windows checkout
        # (core.autocrlf) reports the same size as a Unix one.
        size_kb = bundled_runtime_size_kb(bundle)
        heaviest = "".join(f"\n  {s / 1024:6.1f} KB  {p}"
                           for s, p in bundle_files(bundle)[:5])
        self.assertLess(size_kb, 600,
                        f"bundled runtime is unexpectedly large "
                        f"({size_kb:.1f} KB); heaviest modules:{heaviest}")

    def test_bundled_runtime_runs_on_its_own(self):
        """Inside the APK, ``src/`` is all there is.

        Run the starter app in a subprocess started with ``-S`` — no
        site-packages, so neither the pip-installed Pydrud nor any
        third-party dependency can quietly fill a gap in the bundle.
        """
        src = self.path("src")
        code = textwrap.dedent("""
            import sys

            import pydrud
            from pydrud import App, Column, Router, Text  # noqa: F401
            from pydrud.testing import AppTester
            import pydrud.data, pydrud.runtime.app, pydrud.services.native

            bundle = sys.argv[1]
            strays = sorted(
                m.__name__ for m in list(sys.modules.values())
                if getattr(m, "__name__", "").startswith("pydrud")
                and getattr(m, "__file__", None)
                and not m.__file__.startswith(bundle))
            print("STRAYS:", strays)

            sys.path.insert(0, bundle)
            from app.main import main

            tester = AppTester(main, title="demo_app").start()
            print("RENDERS:", tester.shows("TAPS TODAY"))
            tester.stop()
        """)
        env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-S", "-c", code, src],
            # cwd holds no pydrud/ of its own, so the bundle wins.
            cwd=self.project, env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0,
                         f"bundled runtime does not run alone:\n"
                         f"{result.stderr}")
        self.assertIn("STRAYS: []", result.stdout,
                      "the bundle reached outside itself: " + result.stdout)
        self.assertIn("RENDERS: True", result.stdout,
                      "the starter app did not render from the bundle alone")

    def test_bundled_runtime_never_imports_build_time_code(self):
        """A lazy ``from pydrud.utils import tui`` would crash on a device."""
        bundle = self.path("src", "pydrud")
        offenders = []
        for _size, rel in bundle_files(bundle):
            if not rel.endswith(".py"):
                continue
            dotted = "pydrud." + rel[:-3].replace(os.sep, ".")
            for lineno, name in imported_modules(
                    os.path.join(bundle, rel), dotted):
                if any(name == b or name.startswith(b + ".")
                       for b in BUILD_TIME_ONLY):
                    offenders.append(f"{rel}:{lineno} imports {name}")
        self.assertEqual(sorted(offenders), [],
                         "bundled modules import build-time only code: "
                         + ", ".join(sorted(offenders)))

    def test_package_name_includes_app_name(self):
        gradle = open(self.path("android/app/build.gradle.kts"), encoding="utf-8").read()
        self.assertIn('applicationId = "com.example.demo_app"', gradle)

    def test_tag_ids_are_declared_and_used(self):
        # View.setTag(key, …) crashes with framework ids, so the renderer
        # must only use ids declared in the app's own resources.
        ids = open(self.path("android/app/src/main/res/values/ids.xml"),
                   encoding="utf-8").read()
        factory = open(
            self.path("android/app/src/main/java/com/example/demo_app/ViewFactory.java"),
            encoding="utf-8").read()
        for name in ("pydrud_tag_range", "pydrud_tag_listener",
                     "pydrud_tag_children"):
            self.assertIn(f'name="{name}"', ids, f"{name} missing from ids.xml")
            self.assertIn(f"R.id.{name}", factory,
                          f"ViewFactory does not use R.id.{name}")

    def test_manifest_references_generated_activity(self):
        manifest = open(
            self.path("android/app/src/main/AndroidManifest.xml"), encoding="utf-8"
        ).read()
        self.assertIn('android:name=".DemoAppActivity"', manifest)

    def test_build_gradle_wires_chaquopy_and_sources(self):
        gradle = open(self.path("android/app/build.gradle.kts"), encoding="utf-8").read()
        self.assertIn('id("com.chaquo.python")', gradle)
        self.assertIn('srcDir("../../src")', gradle)
        self.assertIn('namespace = "com.example.demo_app"', gradle)

    def test_analyzer_reports_no_errors_for_starter_app(self):
        from pydrud.commands.analyzer import run_analysis

        issues = run_analysis(self.path("src", "app"))
        errors = [i for i in issues if i["severity"] == "error"]
        self.assertEqual(errors, [], f"analyzer errors: {errors}")

    def test_duplicate_project_is_refused(self):
        with self.assertRaises(SystemExit):
            create_project("demo_app", org="com.example")


class TestJavaTemplates(unittest.TestCase):
    """Every Java template must render and parse as valid Java."""

    @classmethod
    def setUpClass(cls):
        cls.env = Environment(
            loader=PackageLoader("pydrud", "android/templates"),
            autoescape=select_autoescape(["xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, name: str) -> str:
        return self.env.get_template(name).render(**CTX)

    @unittest.skipUnless(HAS_JAVALANG, "javalang not installed")
    def test_java_templates_parse(self):
        for name in JAVA_TEMPLATES:
            with self.subTest(template=name):
                source = self.render(name)
                javalang.parse.parse(source)

    @unittest.skipUnless(HAS_JAVALANG, "javalang not installed")
    def test_static_nested_classes_touch_no_outer_instance_members(self):
        """A ``static`` inner class has no outer instance — javac rejects
        bare calls/references to the enclosing class' instance members
        (``error: non-static method dp(int) cannot be referenced from a
        static context``).  Catch that here instead of at Gradle time."""
        violations = []
        for name in all_java_templates():
            tree = javalang.parse.parse(self.render(name))
            for _, outer in tree.filter(javalang.tree.ClassDeclaration):
                violations += outer_instance_uses(outer, name)
        self.assertEqual(violations, [], "static context violations: "
                         + ", ".join(violations))

    def test_no_unrendered_jinja_placeholders(self):
        for name in JAVA_TEMPLATES + ["android/AndroidManifest.xml.j2",
                                      "android/app/build.gradle.kts.j2",
                                      "python/main.py.j2"]:
            with self.subTest(template=name):
                source = self.render(name)
                self.assertNotIn("{{", source)
                self.assertNotIn("{%", source)

    def test_view_factory_handles_every_widget_type(self):
        """Each Python widget type must have a branch in the renderer."""
        from pydrud import widgets as widget_pkg

        source = self.render("android/ViewFactory.java.j2")
        rendered_types = {
            "Container", "Center", "Padding", "SizedBox", "Positioned", "Card",
            "Stack", "Column", "ListView", "Row", "GridView", "Spacer",
            "Divider", "Text", "Button", "TextField", "Image", "Icon",
            "Checkbox", "Switch", "Radio", "ProgressBar", "Slider", "Dropdown",
        }
        for type_name in rendered_types:
            self.assertIn(f'case "{type_name}"', source)

        # Composite widgets serialise to one of the above primitives.
        composites = {"AppBar": "Container", "Scaffold": "Stack", "FAB": "Container"}
        for name in composites:
            self.assertTrue(hasattr(widget_pkg, name) or name == "FAB")

    def test_bridge_handles_every_python_command(self):
        source = self.render("android/BridgeService.java.j2")
        for cmd in ["full_render", "render", "toast", "snackbar", "set_title",
                    "finish_activity", "set_system_ui", "vibrate", "back_result"]:
            self.assertIn(f'case "{cmd}"', source)

    def test_activity_waits_for_python_before_default_back(self):
        source = self.render("android/MainActivity.java.j2")
        self.assertIn("onBackResult", source)
        self.assertIn("awaitingBackResult", source)
        self.assertIn("sendLifecycle", source)


class TestBundleSizeMetric(unittest.TestCase):
    """The APK size budget must mean the same thing on every platform."""

    def test_line_endings_do_not_change_the_measurement(self):
        tmp = tempfile.mkdtemp(prefix="pydrud-size-")
        self.addCleanup(shutil.rmtree, tmp, True)
        unix, windows = os.path.join(tmp, "lf"), os.path.join(tmp, "crlf")
        os.makedirs(unix)
        os.makedirs(windows)

        body = "".join(f"line {i}\n" for i in range(500))
        with open(os.path.join(unix, "module.py"), "wb") as fh:
            fh.write(body.encode())
        with open(os.path.join(windows, "module.py"), "wb") as fh:
            fh.write(body.replace("\n", "\r\n").encode())

        # A checkout with core.autocrlf is bigger on disk …
        self.assertGreater(os.path.getsize(os.path.join(windows, "module.py")),
                           os.path.getsize(os.path.join(unix, "module.py")))
        # … but that is not weight the APK carries, so the budget ignores it.
        self.assertEqual(bundled_runtime_size_kb(unix),
                         bundled_runtime_size_kb(windows))


if __name__ == "__main__":
    unittest.main()
