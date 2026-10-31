"""Ownership rules: what pydrud sync may rewrite, and what it must keep.

Every generated Android file is a starting point. The tests below pin the
three strategies in pydrud.commands.project.managed:

* hash-stamped files are rewritten only while nobody edited them;
* files with a managed region are merged, so hand-written entries survive;
* gradle.properties is ensure-only.
"""

from __future__ import annotations



from pydrud.commands.project.managed import (
    ChangeLog, merge_gradle, merge_manifest, merge_properties, merge_proguard,
    split_stamp, write_generated,
)

MANIFEST_HEAD = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- pydrud:permissions:begin -->
    <uses-permission android:name="android.permission.INTERNET" />
    <!-- pydrud:permissions:end -->

    <application
        android:label="Demo">
        <!-- pydrud:activity:begin -->
        <activity android:name=".DemoActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
            </intent-filter>
        </activity>
        <!-- pydrud:activity:end -->

        <!-- pydrud:services:begin -->
        <!-- pydrud:services:end -->
    </application>

</manifest>
"""

GRADLE = """// build script
android {
    namespace = "com.example.demo"

    defaultConfig {
        minSdk = 24
        versionName = "1.0.0"
    }
}

dependencies {
    // pydrud:deps:begin
    implementation("androidx.core:core:1.13.1")
    // pydrud:deps:end
    // Add your own dependencies below this line.
}
"""


# ── Hash stamps ──────────────────────────────────────────────────────────

def test_a_new_file_is_created_with_a_stamp(tmp_path):
    path = tmp_path / "Demo.java"
    outcome = write_generated(str(path), "class Demo {}\n", "java")
    assert outcome.status == "created"
    body, digest = split_stamp(path.read_text(encoding="utf-8"))
    assert digest is not None
    assert body == "class Demo {}\n"


def test_an_untouched_file_is_rewritten_when_the_template_changes(tmp_path):
    path = tmp_path / "Demo.java"
    write_generated(str(path), "class Demo {}\n", "java")
    outcome = write_generated(str(path), "class Demo { int x; }\n", "java")
    assert outcome.status == "updated"
    assert "int x" in path.read_text(encoding="utf-8")


def test_an_identical_write_is_a_no_op(tmp_path):
    path = tmp_path / "Demo.java"
    write_generated(str(path), "class Demo {}\n", "java")
    before = path.stat().st_mtime_ns
    assert write_generated(str(path), "class Demo {}\n", "java").status == "unchanged"
    assert path.stat().st_mtime_ns == before


def test_an_edited_file_is_kept_and_the_new_version_is_written_beside_it(tmp_path):
    path = tmp_path / "Demo.java"
    write_generated(str(path), "class Demo {}\n", "java")
    path.write_text(path.read_text(encoding="utf-8") + "// mine\n",
                    encoding="utf-8")
    outcome = write_generated(str(path), "class Demo { int x; }\n", "java")
    assert outcome.status == "conflict"
    assert "// mine" in path.read_text(encoding="utf-8")
    fresh = tmp_path / ("Demo.java" + ".pydrud-new")
    assert "int x" in fresh.read_text(encoding="utf-8")


def test_a_file_without_provenance_is_upgraded(tmp_path):
    """Files from an older Pydrud have no stamp; sync adopts them."""
    path = tmp_path / "Demo.java"
    path.write_text("class Demo {}\n", encoding="utf-8")
    assert write_generated(str(path), "class Demo { int x; }\n",
                           "java").status == "updated"
    assert "pydrud-hash" in path.read_text(encoding="utf-8")


def test_the_shebang_stays_on_the_first_line(tmp_path):
    path = tmp_path / "gradlew"
    write_generated(str(path), "#!/bin/sh\necho hi\n", "hash")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "#!/bin/sh"
    assert "pydrud-hash" in lines[1]


def test_an_xml_declaration_stays_on_the_first_line(tmp_path):
    path = tmp_path / "themes.xml"
    write_generated(str(path), '<?xml version="1.0"?>\n<resources />\n', "xml")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("<?xml")
    assert "pydrud-hash" in lines[1]


# ── Manifest ─────────────────────────────────────────────────────────────

def test_manifest_keeps_a_hand_added_permission():
    rendered = MANIFEST_HEAD.replace(
        'android.permission.INTERNET" />',
        'android.permission.INTERNET" />\n'
        '    <uses-permission android:name="android.permission.CAMERA" />')
    existing = MANIFEST_HEAD.replace(
        "    <!-- pydrud:permissions:end -->",
        "    <!-- pydrud:permissions:end -->\n"
        '    <uses-permission android:name="android.permission.NFC" />')
    merged, notes = merge_manifest(existing, rendered)
    assert "android.permission.NFC" in merged
    assert "android.permission.CAMERA" in merged
    assert "permissions" in notes


def test_manifest_drops_a_permission_that_left_the_yaml():
    existing = MANIFEST_HEAD.replace(
        '    <uses-permission android:name="android.permission.INTERNET" />',
        '    <uses-permission android:name="android.permission.CAMERA" />')
    merged, _notes = merge_manifest(existing, MANIFEST_HEAD)
    assert "android.permission.CAMERA" not in merged
    assert "android.permission.INTERNET" in merged


def test_manifest_keeps_a_hand_added_activity():
    existing = MANIFEST_HEAD.replace(
        "    <!-- pydrud:services:begin -->",
        '        <activity android:name=".SettingsActivity" />\n'
        "        <!-- pydrud:services:begin -->")
    rendered = MANIFEST_HEAD.replace(".DemoActivity", ".RenamedActivity")
    merged, _notes = merge_manifest(existing, rendered)
    assert ".SettingsActivity" in merged
    assert ".RenamedActivity" in merged
    assert ".DemoActivity" not in merged


def test_manifest_updates_application_attributes():
    existing = MANIFEST_HEAD.replace(
        'android:label="Demo"',
        'android:label="Demo"\n        android:allowBackup="true"')
    rendered = MANIFEST_HEAD.replace(
        'android:label="Demo"',
        'android:label="Renamed"\n        android:allowBackup="false"')
    merged, notes = merge_manifest(existing, rendered)
    assert 'android:label="Renamed"' in merged
    assert 'android:allowBackup="false"' in merged
    assert "application attributes" in notes


def test_manifest_does_not_invent_an_attribute_the_developer_removed():
    rendered = MANIFEST_HEAD.replace(
        'android:label="Demo"',
        'android:label="Demo"\n        android:allowBackup="false"')
    merged, _notes = merge_manifest(MANIFEST_HEAD, rendered)
    assert "android:allowBackup" not in merged


def test_manifest_merging_is_idempotent():
    rendered = MANIFEST_HEAD.replace(".DemoActivity", ".OtherActivity")
    once, _ = merge_manifest(MANIFEST_HEAD, rendered)
    twice, notes = merge_manifest(once, rendered)
    assert twice == once
    assert notes == []


def test_a_legacy_manifest_gets_regions_without_duplicating_the_activity():
    legacy = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:label="Demo">
        <activity android:name=".OldActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""
    merged, notes = merge_manifest(legacy, MANIFEST_HEAD)
    assert ".OldActivity" not in merged
    assert merged.count(".DemoActivity") == 1
    assert "pydrud:activity:begin" in merged
    assert "activity" in notes


# ── Gradle ───────────────────────────────────────────────────────────────

def test_gradle_values_follow_the_yaml():
    rendered = GRADLE.replace("minSdk = 24", "minSdk = 26").replace(
        'versionName = "1.0.0"', 'versionName = "2.5.0"').replace(
        "androidx.core:core:1.13.1", "androidx.core:core:1.15.0")
    merged, notes = merge_gradle(GRADLE, rendered)
    assert "minSdk = 26" in merged
    assert 'versionName = "2.5.0"' in merged
    assert "androidx.core:core:1.15.0" in merged
    assert "values" in notes


def test_gradle_keeps_a_dependency_added_below_the_region():
    existing = GRADLE.replace(
        "    // Add your own dependencies below this line.",
        '    implementation("com.squareup.okhttp3:okhttp:4.12.0")\n'
        "    // Add your own dependencies below this line.")
    merged, _notes = merge_gradle(existing, GRADLE)
    assert "com.squareup.okhttp3:okhttp" in merged
    assert "androidx.core:core:1.13.1" in merged


def test_gradle_flags_a_change_it_cannot_patch():
    rendered = GRADLE.replace(
        "// build script",
        '// build script\nplugins {\n    id("com.chaquo.python")\n}')
    _merged, notes = merge_gradle(GRADLE, rendered)
    assert "needs review" in notes


# ── Properties and ProGuard ──────────────────────────────────────────────

def test_properties_never_override_a_value_the_developer_set():
    existing = "org.gradle.jvmargs=-Xmx4096m\n"
    rendered = "org.gradle.jvmargs=-Xmx2048m\nandroid.useAndroidX=true\n"
    merged, notes = merge_properties(existing, rendered)
    assert "-Xmx4096m" in merged
    assert "android.useAndroidX=true" in merged
    assert "gradle properties" in notes


def test_proguard_replaces_only_its_region():
    rendered = "# pydrud:rules:begin\n-keep class A { *; }\n# pydrud:rules:end\n"
    existing = ("-keep class Mine { *; }\n"
                "# pydrud:rules:begin\n-keep class Old { *; }\n"
                "# pydrud:rules:end\n")
    merged, notes = merge_proguard(existing, rendered)
    assert "-keep class Mine" in merged
    assert "-keep class A { *; }" in merged
    assert "Old" not in merged
    assert "proguard rules" in notes


# ── End to end ───────────────────────────────────────────────────────────

def test_sync_keeps_edits_and_rewrites_nothing_else(tmp_path, monkeypatch):
    from pydrud.commands.project import create_project, sync_project

    monkeypatch.chdir(tmp_path)
    create_project("stable", org="com.example", runtime="chaquopy")
    project = tmp_path / "stable"
    assert sync_project(str(project), update_runtime=False)

    manifest = project / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    gradle = project / "android" / "app" / "build.gradle.kts"
    properties = project / "android" / "gradle.properties"

    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "    <!-- pydrud:permissions:end -->",
            "    <!-- pydrud:permissions:end -->\n"
            '    <uses-permission android:name="android.permission.NFC" />'),
        encoding="utf-8")
    gradle.write_text(
        gradle.read_text(encoding="utf-8").replace(
            "    // Add your own dependencies below this line.",
            '    implementation("com.squareup.okhttp3:okhttp:4.12.0")\n'
            "    // Add your own dependencies below this line."),
        encoding="utf-8")
    properties.write_text(
        properties.read_text(encoding="utf-8") + "org.gradle.jvmargs=-Xmx4096m\n",
        encoding="utf-8")

    assert sync_project(str(project), update_runtime=False)

    assert "android.permission.NFC" in manifest.read_text(encoding="utf-8")
    assert "com.squareup.okhttp3:okhttp" in gradle.read_text(encoding="utf-8")
    assert "-Xmx4096m" in properties.read_text(encoding="utf-8")
    assert not list((project / "android").rglob("*.pydrud-new"))


def test_a_second_sync_writes_no_file(tmp_path, monkeypatch):
    from pydrud.commands.project import create_project, sync_project

    monkeypatch.chdir(tmp_path)
    create_project("quiet", org="com.example", runtime="chaquopy")
    project = tmp_path / "quiet"
    assert sync_project(str(project), update_runtime=False)

    android = project / "android"
    before = {
        path.relative_to(android): path.stat().st_mtime_ns
        for path in android.rglob("*") if path.is_file()
    }
    assert sync_project(str(project), update_runtime=False)
    after = {
        path.relative_to(android): path.stat().st_mtime_ns
        for path in android.rglob("*") if path.is_file()
    }
    changed = sorted(str(name) for name, mtime in after.items()
                     if before.get(name) != mtime)
    assert changed == []


def test_changelog_counts_every_outcome():
    log = ChangeLog()
    assert log.summary() == "nothing to do"
    assert log.written == 0
    assert log.conflicts == 0
