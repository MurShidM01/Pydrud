"""The generated project is a real, navigable Python project.

``pydrud create`` must produce a package a team can grow: one module per
concern, a README, and tests that pass out of the box.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from pydrud.commands.project import create_project

EXPECTED_FILES = (
    "README.md",
    "run.py",
    "setup.py",
    "pydrud.yaml",
    "pydrud.toml",
    "tests/test_app.py",
    "src/pydrud_config.py",
    "src/app/__init__.py",
    "src/app/main.py",
    "src/app/config.py",
    "src/app/theme.py",
    "src/app/state.py",
    "src/app/runtime.py",
    "src/app/jobs.py",
    "src/app/ui.py",
    "src/app/components/__init__.py",
    "src/app/components/common.py",
    "src/app/screens/__init__.py",
    "src/app/screens/heartbeat.py",
    "src/app/theme.pss",
)


class TestScaffoldLayout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-layout-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("layout_app", org="com.example", runtime="chaquopy")
        cls.root = os.path.join(cls.tmp, "layout_app")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def path(self, relative: str) -> str:
        return os.path.join(self.root, *relative.split("/"))

    def test_every_expected_file_exists(self):
        for relative in EXPECTED_FILES:
            with self.subTest(file=relative):
                self.assertTrue(os.path.isfile(self.path(relative)),
                                f"missing {relative}")

    def test_no_monolithic_main(self):
        """main.py wires the app together; it does not *contain* the app."""
        with open(self.path("src/app/main.py"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertLess(len(lines), 70)

    def test_every_module_compiles(self):
        for relative in EXPECTED_FILES:
            if not relative.endswith(".py"):
                continue
            with self.subTest(file=relative), \
                    open(self.path(relative), encoding="utf-8") as fh:
                compile(fh.read(), relative, "exec")

    def test_readme_documents_the_layout(self):
        with open(self.path("README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        for fragment in ("layout_app", "pydrud run", "src/app/screens",
                         "components/", "Add a screen"):
            self.assertIn(fragment, readme)

    def test_generated_tests_pass(self):
        """The starter test suite is green in a fresh project."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests"],
            cwd=self.root, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)


class TestGeneratedAppStructure(unittest.TestCase):
    """Importing the generated package gives you the pieces it promises."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-structure-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("struct_app", org="com.example", runtime="chaquopy")
        cls.src = os.path.join(cls.tmp, "struct_app", "src")
        sys.path.insert(0, cls.src)
        for mod in [m for m in list(sys.modules)
                    if m == "app" or m.startswith("app.")]:
            del sys.modules[mod]

    @classmethod
    def tearDownClass(cls):
        if cls.src in sys.path:
            sys.path.remove(cls.src)
        for mod in [m for m in list(sys.modules)
                    if m == "app" or m.startswith("app.")]:
            del sys.modules[mod]
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_routes_match_the_registered_screens(self):
        from app.main import router

        for route in ("heartbeat",):
            with self.subTest(route=route):
                self.assertIn(route, router.routes)
        # Heartbeat is the start destination.
        self.assertEqual(router.current_route, "heartbeat")

    def test_runtime_exposes_the_app_handle(self):
        from app import runtime

        self.assertIsNone(runtime._app)
        sentinel = object()
        self.assertIs(runtime.bind(sentinel), sentinel)
        self.assertIs(runtime.current(), sentinel)
        runtime.bind(None)

    def test_jobs_are_registered_and_runnable(self):
        import json

        from app.jobs import JOBS, run_background_job

        self.assertIn("refresh", JOBS)
        out = json.loads(run_background_job("refresh", '{"a": 1}'))
        self.assertEqual(out, {"refreshed": True, "inputs": {"a": 1}})
        self.assertIn("no such job", run_background_job("nope"))

    def test_main_reexports_the_java_entry_points(self):
        import app.main as main

        for name in ("main", "start_app", "run_background_job", "router"):
            self.assertTrue(hasattr(main, name), name)


if __name__ == "__main__":
    unittest.main()
