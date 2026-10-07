"""The CameraX + ML Kit stack is opt-in for generated Android projects.

Those libraries ship ``libimage_processing_util_jni.so`` and ML Kit's
``libbarhopper_v3.so`` into every APK: roughly 10 MB that the NDK stripper
then complains about ("Unable to strip the following libraries"). Projects
that never touch a camera must not pay for them, and projects that do can
opt in with ``camera: true`` or simply by declaring the CAMERA permission.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from pydrud.commands.project import create_project, sync_project
from pydrud.commands.project_config import load_project_config, set_scalar
from pydrud.commands.project.config import _config_bool
from pydrud.commands.release import update_permissions

CAMERA_DEPENDENCIES = (
    "androidx.camera:camera-core",
    "com.google.mlkit:barcode-scanning",
)


class TestCameraIsOptIn(unittest.TestCase):
    """Generated projects start lean and gain the stack on demand."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-camera-")
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        create_project("lean", org="com.example", runtime="chaquopy")
        self.project = os.path.join(self.tmp, "lean")

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── helpers ──────────────────────────────────────────────────────────

    def read(self, relative: str) -> str:
        with open(os.path.join(self.project, *relative.split("/")),
                  encoding="utf-8") as handle:
            return handle.read()

    def gradle(self) -> str:
        return self.read("android/app/build.gradle.kts")

    def activity(self) -> str:
        return self.read(
            "android/app/src/main/java/com/example/lean/LeanActivity.java")

    def java_sources(self) -> dict[str, str]:
        """Every generated ``.java`` file, keyed by its relative path."""
        root = os.path.join(self.project, "android/app/src/main/java")
        sources: dict[str, str] = {}
        for folder, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith(".java"):
                    path = os.path.join(folder, name)
                    sources[os.path.relpath(path, root)] = self.read(
                        os.path.relpath(path, self.project))
        return sources

    # ── default: no camera ───────────────────────────────────────────────

    def test_new_projects_ship_no_camera_libraries(self):
        gradle = self.gradle()
        for dependency in CAMERA_DEPENDENCIES:
            with self.subTest(dependency=dependency):
                self.assertNotIn(dependency, gradle)
        self.assertNotIn("androidx.camera", self.read(
            "android/app/proguard-rules.pro"))

    def test_new_projects_generate_no_camera_native_code(self):
        activity = self.activity()
        self.assertNotIn("androidx.camera", activity)
        self.assertNotIn("com.google.mlkit", activity)
        self.assertNotIn("bindCameraPreview", activity)

    def test_missing_camera_stack_answers_commands_with_an_actionable_error(self):
        capture = self.read(
            "android/app/src/main/java/com/example/lean/CaptureServices.java")
        bridge = self.read(
            "android/app/src/main/java/com/example/lean/BridgeService.java")
        for source in (capture, bridge):
            with self.subTest(source=source.splitlines()[0]):
                self.assertIn("CAMERA_DISABLED", source)
                self.assertIn("camera: true", source)
        # The placeholder widget explains itself instead of blanking out.
        builtin = self.read(
            "android/app/src/main/java/com/example/lean/BuiltinViews.java")
        self.assertIn("camera_disabled", builtin)

    def test_the_choice_is_recorded_in_pydrud_yaml(self):
        config = load_project_config(self.project)
        self.assertFalse(_config_bool(config, "camera", False))
        # The manifest keeps CAMERA inside its commented-out "dangerous
        # permissions" note only — it is never actually requested.
        manifest = self.read("android/app/src/main/AndroidManifest.xml")
        self.assertNotIn(
            '\n    <uses-permission android:name="android.permission.CAMERA" />',
            manifest)

    def test_generated_java_still_parses_without_the_camera_stack(self):
        from pydrud.android.javacheck import check_sources

        self.assertEqual(check_sources(self.java_sources()), [])

    # ── opt-in through the CAMERA permission ─────────────────────────────

    def test_declaring_the_camera_permission_bundles_the_stack(self):
        update_permissions(self.project, add=["camera"])
        self.assertTrue(sync_project(self.project, update_runtime=False))

        gradle = self.gradle()
        for dependency in CAMERA_DEPENDENCIES:
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, gradle)
        self.assertIn("androidx.camera", self.activity())
        self.assertIn("com.google.mlkit", self.activity())
        self.assertIn("android.permission.CAMERA",
                      self.read("android/app/src/main/AndroidManifest.xml"))
        # The resolved choice is written back so the YAML explains the APK.
        self.assertTrue(_config_bool(
            load_project_config(self.project), "camera", False))

    # ── opt-in through pydrud.yaml ───────────────────────────────────────

    def test_camera_true_in_yaml_bundles_the_stack(self):
        set_scalar(self.project, "camera", True)
        self.assertTrue(sync_project(self.project, update_runtime=False))
        self.assertIn("androidx.camera:camera-core", self.gradle())
        self.assertIn("bindCameraPreview", self.activity())

    def test_camera_false_removes_the_stack_again(self):
        set_scalar(self.project, "camera", True)
        self.assertTrue(sync_project(self.project, update_runtime=False))
        set_scalar(self.project, "camera", False)
        self.assertTrue(sync_project(self.project, update_runtime=False))

        self.assertNotIn("androidx.camera", self.gradle())
        self.assertNotIn("androidx.camera", self.activity())

    def test_generated_java_still_parses_with_the_camera_stack(self):
        from pydrud.android.javacheck import check_sources

        set_scalar(self.project, "camera", True)
        self.assertTrue(sync_project(self.project, update_runtime=False))
        self.assertEqual(check_sources(self.java_sources()), [])

    # ── upgrading an older project ───────────────────────────────────────

    def test_projects_that_already_ship_camera_keep_it(self):
        """A project generated before the knob existed must not lose its
        ``CameraPreview`` widgets on the next ``pydrud sync``."""
        set_scalar(self.project, "camera", True)
        self.assertTrue(sync_project(self.project, update_runtime=False))

        # Simulate the upgrade: the YAML knows nothing about `camera:` yet.
        with open(os.path.join(self.project, "pydrud.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write('app_name: "lean"\npackage: "com.example.lean"\n'
                         'standalone: true\n')
        self.assertTrue(sync_project(self.project, update_runtime=False))

        self.assertIn("androidx.camera:camera-core", self.gradle())
        self.assertIn("bindCameraPreview", self.activity())
