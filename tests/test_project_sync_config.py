"""System-level Android configuration applied by ``pydrud sync``."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from pydrud.commands.project import create_project, sync_project
from pydrud.commands.project_config import load_project_config
from pydrud.commands.release import update_capabilities, update_permissions


class TestYamlControlledAndroidSync(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-config-sync-")
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        create_project("gone", org="com.pydrud", runtime="chaquopy")
        self.project = os.path.join(self.tmp, "gone")

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, relative: str) -> str:
        with open(os.path.join(self.project, *relative.split("/")),
                  encoding="utf-8") as handle:
            return handle.read()

    def write(self, relative: str, text: str) -> None:
        with open(os.path.join(self.project, *relative.split("/")), "w",
                  encoding="utf-8") as handle:
            handle.write(text)

    def test_new_counter_projects_request_no_starter_service_permissions(self):
        config = load_project_config(self.project)
        self.assertNotIn("haptics", config["capabilities"])
        self.assertNotIn("notifications", config["capabilities"])
        manifest = self.read("android/app/src/main/AndroidManifest.xml")
        self.assertNotIn("android.permission.VIBRATE", manifest)
        self.assertNotIn("android.permission.POST_NOTIFICATIONS", manifest)

        # The generated runtime still supports services when an app opts in;
        # the minimal counter starter simply doesn't request them by default.
        bridge = self.read(
            "android/app/src/main/java/com/pydrud/gone/BridgeService.java")
        self.assertIn("VIBRATOR_MANAGER_SERVICE", bridge)
        self.assertIn("getDefaultVibrator", bridge)
        self.assertIn("createPredefined", bridge)
        self.assertIn("USAGE_ASSISTANCE_SONIFICATION", bridge)

    def test_sync_applies_identity_sdk_toolchain_and_manifest_settings(self):
        # This intentionally replaces the generated file: sync must use YAML,
        # not infer stale identity from the old Java source tree.
        self.write("pydrud.yaml", """\
app_name: "Taskflow"
package: "com.pydrud.taskflow"
version_code: 42
version_name: "2.5.0"
min_sdk: 26
target_sdk: 35
compile_sdk: 36
ndk: "27.2.12479018"
abi_filters: ["arm64-v8a", "x86_64"]
assets_dir: "static"
scheme: "taskflow"
app_links_host: "taskflow.example.com"
permissions:
  - CAMERA
  - "RECORD_AUDIO"
capabilities:
  - notifications
firebase: false
shrink: true
python_version: "3.12"
framework_version: "9.8.7"
protocol_version: 7
chaquopy_version: "17.1.0"
agp_version: "8.12.0"
gradle_version: "8.13"
pydrud_version: "1.0.0"
""")
        os.mkdir(os.path.join(self.project, "static"))
        with open(os.path.join(self.project, "src", "app", "main.py"), "a",
                  encoding="utf-8") as handle:
            handle.write("\n# user-owned-marker\n")
        toml = self.read("pydrud.toml").replace(
            "[python.packages]", '[python.packages]\nrequests = ">=2.31"')
        self.write("pydrud.toml", toml)

        self.assertTrue(sync_project(self.project, update_runtime=False))

        old_java = "android/app/src/main/java/com/pydrud/gone/BridgeService.java"
        new_root = "android/app/src/main/java/com/pydrud/taskflow"
        self.assertFalse(os.path.exists(os.path.join(self.project, old_java)))
        self.assertTrue(os.path.isfile(os.path.join(
            self.project, new_root, "TaskflowActivity.java")))
        bridge = self.read(new_root + "/BridgeService.java")
        self.assertIn("package com.pydrud.taskflow;", bridge)
        self.assertIn("PROTOCOL_VERSION = 7", bridge)
        self.assertIn('renderer_version", "9.8.7"', bridge)

        gradle = self.read("android/app/build.gradle.kts")
        for expected in (
            'namespace = "com.pydrud.taskflow"',
            'applicationId = "com.pydrud.taskflow"',
            "compileSdk = 36", "minSdk = 26", "targetSdk = 35",
            "versionCode = 42", 'versionName = "2.5.0"',
            'version = "3.12"',
            'System.getenv("PYDRUD_COMPILE_PYC")',
            'listOf("arm64-v8a", "x86_64")',
            'assets.srcDirs("../../static")',
            'pydrudShrink") ?: "true"',
            'install("requests>=2.31")',
        ):
            self.assertIn(expected, gradle)
        self.assertIn('version "8.12.0"', self.read("android/build.gradle.kts"))
        self.assertIn('version "17.1.0"', self.read("android/build.gradle.kts"))
        self.assertIn(
            "gradle-8.13-bin.zip",
            self.read("android/gradle/wrapper/gradle-wrapper.properties"))
        self.assertIn('rootProject.name = "Taskflow"',
                      self.read("android/settings.gradle.kts"))

        manifest = self.read("android/app/src/main/AndroidManifest.xml")
        for expected in (
            'android:label="Taskflow"',
            'android:name=".TaskflowActivity"',
            'android:scheme="taskflow"',
            'android:host="taskflow.example.com"',
            'android.permission.CAMERA',
            'android.permission.RECORD_AUDIO',
            'android.permission.POST_NOTIFICATIONS',
        ):
            self.assertIn(expected, manifest)

        metadata = self.read("src/pydrud_config.py")
        self.assertIn('APP_NAME = "Taskflow"', metadata)
        self.assertIn('PACKAGE = "com.pydrud.taskflow"', metadata)
        self.assertIn('VERSION = "2.5.0"', metadata)
        self.assertIn('ASSETS_DIR = "static"', metadata)
        self.assertIn("# user-owned-marker", self.read("src/app/main.py"))

        # TOML remains dependency/theme storage, while its old identity mirror
        # is kept consistent to avoid two contradictory package names.
        toml = self.read("pydrud.toml")
        self.assertIn('name = "Taskflow"', toml)
        self.assertIn('package = "com.pydrud.taskflow"', toml)
        self.assertIn('requests = ">=2.31"', toml)

    def test_abi_splits_emit_per_abi_flavors_instead_of_abi_filters(self):
        # `abi_splits: true` switches from a single universal APK to one APK
        # per ABI plus a universal APK. Chaquopy requires `ndk.abiFilters`
        # and AGP rejects it alongside `splits.abi`, so a product flavor
        # dimension is used instead.
        yaml = self.read("pydrud.yaml").replace(
            "abi_splits: false", "abi_splits: true")
        self.write("pydrud.yaml", yaml)
        self.assertTrue(sync_project(self.project, update_runtime=False))
        gradle = self.read("android/app/build.gradle.kts")
        self.assertIn('flavorDimensions += "abi"', gradle)
        self.assertIn("productFlavors {", gradle)
        # One flavor per ABI plus a universal flavor.
        self.assertIn('create("arm64")', gradle)
        self.assertIn('create("armv7")', gradle)
        self.assertIn('create("x86_64")', gradle)
        self.assertIn('create("universal")', gradle)
        self.assertIn('abiFilters += listOf("arm64-v8a")', gradle)
        self.assertIn(
            'abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")',
            gradle)
        # `splits.abi` is never used (AGP forbids it with `ndk.abiFilters`),
        # and the defaultConfig `ndk` block is replaced by the flavors: one
        # `ndk { … }` per flavor, none in defaultConfig.
        self.assertNotIn("splits {", gradle)
        self.assertEqual(gradle.count("ndk {"), 4)

    def test_old_manifest_shape_uses_toml_scheme_and_yaml_identity(self):
        # Matches projects generated before the expanded YAML schema.
        self.write("pydrud.yaml", """\
app_name: "Taskflow"
pydrud_version: "2.0.0"
package: "com.pydrud.taskflow"
min_sdk: 24
target_sdk: 36
compile_sdk: 36
ndk: 28.2.13676358
python_version: "3.11"
framework_version: "2.0.0"
protocol_version: 2
chaquopy_version: "17.0.0"
agp_version: "8.13.2"
gradle_version: "8.14.4"
assets_dir: "assets"
""")
        self.write("pydrud.toml", self.read("pydrud.toml").replace(
            'scheme = "gone"', 'scheme = "taskflow"'))
        self.assertTrue(sync_project(self.project, update_runtime=False))
        manifest = self.read("android/app/src/main/AndroidManifest.xml")
        self.assertIn('android:label="Taskflow"', manifest)
        self.assertIn('android:scheme="taskflow"', manifest)
        self.assertIn('applicationId = "com.pydrud.taskflow"',
                      self.read("android/app/build.gradle.kts"))

    def test_invalid_config_fails_before_removing_the_old_native_layer(self):
        yaml = self.read("pydrud.yaml").replace(
            'package: "com.pydrud.gone"', 'package: "not a package!"')
        self.write("pydrud.yaml", yaml)
        bridge = os.path.join(
            self.project, "android", "app", "src", "main", "java", "com",
            "pydrud", "gone", "BridgeService.java")
        self.assertFalse(sync_project(self.project, update_runtime=False))
        self.assertTrue(os.path.isfile(bridge))

    def test_permission_cli_updates_yaml_and_survives_sync(self):
        update_permissions(self.project, add=["camera"])
        config = load_project_config(self.project)
        self.assertIn("CAMERA", config["permissions"])
        self.assertTrue(sync_project(self.project, update_runtime=False))
        self.assertIn("android.permission.CAMERA",
                      self.read("android/app/src/main/AndroidManifest.xml"))

    def test_capability_cli_updates_yaml_manifest_and_survives_sync(self):
        update_capabilities(self.project, remove=["haptics"])
        config = load_project_config(self.project)
        self.assertNotIn("haptics", config["capabilities"])
        self.assertNotIn("android.permission.VIBRATE",
                         self.read("android/app/src/main/AndroidManifest.xml"))

        update_capabilities(self.project, add=["haptic"])
        config = load_project_config(self.project)
        self.assertIn("haptics", config["capabilities"])
        self.assertIn("android.permission.VIBRATE",
                      self.read("android/app/src/main/AndroidManifest.xml"))
        self.assertTrue(sync_project(self.project, update_runtime=False))
        self.assertIn("android.permission.VIBRATE",
                      self.read("android/app/src/main/AndroidManifest.xml"))


class TestProjectConfigParser(unittest.TestCase):

    def test_scalars_inline_lists_and_block_lists(self):
        root = tempfile.mkdtemp(prefix="pydrud-yaml-")
        try:
            with open(os.path.join(root, "pydrud.yaml"), "w",
                      encoding="utf-8") as handle:
                handle.write("""\
app_name: "Hash # stays" # comment
abi_filters: [arm64-v8a, "x86_64"]
permissions:
  - CAMERA
  - 'RECORD_AUDIO'
nested:
  ignored: value
app_links_host:
package: com.example.demo
""")
            config = load_project_config(root)
            self.assertEqual(config["app_name"], "Hash # stays")
            self.assertEqual(config["abi_filters"], ["arm64-v8a", "x86_64"])
            self.assertEqual(config["permissions"], ["CAMERA", "RECORD_AUDIO"])
            self.assertEqual(config["nested"], "")
            self.assertEqual(config["app_links_host"], "")
            self.assertNotIn("ignored", config)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
