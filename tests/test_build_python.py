"""
``buildPython`` selection.

Chaquopy only pre-compiles to ``.pyc`` when ``buildPython`` is the same
minor version as the Python the APK ships. When it is not, the raw Gradle
warning ("is not a valid Python 3.11 command: it is version 3.12") is the
only thing the user sees — Pydrud should explain it instead.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout

from pydrud.commands import project


class TestDetectBuildPython(unittest.TestCase):

    def current(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def test_prefers_an_interpreter_matching_the_app_version(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exe = project._detect_build_python(self.current())
        self.assertTrue(exe)
        self.assertEqual("", output.getvalue(),
                         "a matching interpreter must not warn")
        self.assertEqual(self.current(), project._python_version_of(exe))

    def test_mismatch_is_explained(self):
        unreachable = "3.9" if self.current() != "3.9" else "3.10"
        output = io.StringIO()
        with redirect_stdout(output):
            exe = project._detect_build_python(unreachable)
        self.assertTrue(exe)
        text = output.getvalue()
        if text:  # a non-matching interpreter was selected
            self.assertIn("buildPython", text)
            self.assertIn(unreachable, text)
            self.assertIn("PYDRUD_PYTHON", text)

    def test_version_probe_handles_a_missing_interpreter(self):
        self.assertEqual("", project._python_version_of(
            "definitely-not-a-python-interpreter"))

    def test_app_python_is_a_supported_build_python(self):
        self.assertIn(project.APP_PYTHON_VERSION,
                      project.BUILD_PYTHON_VERSIONS)


if __name__ == "__main__":
    unittest.main()
