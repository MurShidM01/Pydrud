"""v1.3 tooling: pip package management, release helpers, docs, inspector."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest import mock

from click.testing import CliRunner

from pydrud.commands import release
from pydrud.commands.cli import main as cli
from pydrud.commands.project import create_project
from pydrud.packages import (
    BLOCKED, REGISTRY, PackageError, Requirements, by_category, info,
    installed_summary, is_supported, normalise, render_pip_block, search,
    split_requirement, sync_gradle,
)


class TestRegistry(unittest.TestCase):

    def test_registry_is_well_formed(self):
        self.assertGreater(len(REGISTRY), 100)
        for name, entry in REGISTRY.items():
            self.assertEqual(name, normalise(name), f"{name} is not normalised")
            self.assertEqual(len(entry), 4, name)
            version, category, native, description = entry
            self.assertIsInstance(native, bool)
            self.assertTrue(description, f"{name} has no description")
            self.assertIn(category,
                          ("network", "media", "parsing", "documents",
                           "science", "ai", "security", "database", "utility"))

    def test_blocked_and_registry_never_overlap(self):
        self.assertFalse(set(BLOCKED) & set(REGISTRY))

    def test_popular_packages_are_available(self):
        for name in ("yt-dlp", "requests", "numpy", "pillow", "openai",
                     "beautifulsoup4", "qrcode", "cryptography", "sqlalchemy"):
            self.assertTrue(is_supported(name), name)

    def test_name_normalisation(self):
        self.assertEqual(normalise("Python_Dateutil"), "python-dateutil")
        self.assertTrue(is_supported("Beautifulsoup4"))

    def test_info_explains_blocked_packages(self):
        with self.assertRaises(PackageError) as ctx:
            info("flask")
        self.assertIn("server framework", str(ctx.exception))

    def test_info_suggests_alternatives(self):
        with self.assertRaises(PackageError) as ctx:
            info("request")
        self.assertIn("Did you mean", str(ctx.exception))

    def test_split_requirement(self):
        self.assertEqual(split_requirement("requests>=2.31"),
                         ("requests", ">=2.31"))
        self.assertEqual(split_requirement("  yt_dlp "), ("yt-dlp", ""))
        with self.assertRaises(PackageError):
            split_requirement("requests 2.31")

    def test_search_ranks_exact_matches_first(self):
        results = search("qrcode")
        self.assertEqual(results[0]["name"], "qrcode")
        self.assertTrue(search("video"))
        self.assertEqual(search("zzzzzz"), [])

    def test_by_category_covers_the_registry(self):
        grouped = by_category()
        total = sum(len(entries) for entries in grouped.values())
        self.assertEqual(total, len(REGISTRY))

    def test_render_pip_block_is_marked(self):
        block = render_pip_block(["requests", "yt-dlp"])
        self.assertIn("pydrud:pip:begin", block)
        self.assertIn('install("yt-dlp")', block)
        self.assertIn("pydrud:pip:end", block)


class TestRequirementsFile(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pydrud-req-")
        self.reqs = Requirements(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_add_creates_the_file(self):
        entry = self.reqs.add("requests")
        self.assertEqual(entry["name"], "requests")
        self.assertTrue(os.path.exists(self.reqs.path))
        self.assertIn("requests", self.reqs)

    def test_add_keeps_a_version_spec(self):
        self.reqs.add("requests>=2.31")
        self.assertEqual(self.reqs.load()["requests"], ">=2.31")
        self.assertEqual(self.reqs.requirement_strings(), ["requests>=2.31"])

    def test_pinned_registry_version_is_applied(self):
        entry = self.reqs.add("googletrans")
        self.assertEqual(entry["spec"], "==4.0.0rc1")

    def test_unsupported_package_is_refused_but_force_works(self):
        with self.assertRaises(PackageError):
            self.reqs.add("totally-not-real")
        entry = self.reqs.add("totally-not-real", force=True)
        self.assertEqual(entry["category"], "unverified")
        self.assertIn("totally-not-real", self.reqs)

    def test_remove(self):
        self.reqs.add("requests")
        self.assertTrue(self.reqs.remove("Requests"))
        self.assertFalse(self.reqs.remove("requests"))
        self.assertEqual(len(self.reqs), 0)

    def test_other_sections_survive_a_rewrite(self):
        with open(self.reqs.path, "w", encoding="utf-8") as handle:
            handle.write('[app]\nname = "demo"\n\n[python.packages]\n'
                         'requests = ""\n\n[other]\nkeep = true\n')
        self.reqs.add("yt-dlp")
        text = open(self.reqs.path, encoding="utf-8").read()
        self.assertIn('[app]', text)
        self.assertIn('keep = true', text)
        self.assertIn('yt-dlp', text)
        self.assertIn('requests', text)

    def test_summary_flags_unverified_entries(self):
        self.reqs.add("mystery", force=True)
        rows = installed_summary(self.dir)
        self.assertEqual(rows[0]["category"], "unverified")


class TestProjectIntegration(unittest.TestCase):
    """The pip workflow against a real scaffolded project."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-pip-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("pipdemo", org="com.example")
        cls.project = os.path.join(cls.tmp, "pipdemo")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gradle(self) -> str:
        path = os.path.join(self.project, "android", "app", "build.gradle.kts")
        return open(path, encoding="utf-8").read()

    def test_scaffold_ships_a_toml_and_an_empty_pip_block(self):
        self.assertTrue(os.path.exists(
            os.path.join(self.project, "pydrud.toml")))
        self.assertIn("pydrud:pip:begin", self.gradle())

    def test_sync_injects_and_prunes_installs(self):
        reqs = Requirements(self.project)
        reqs.add("requests")
        reqs.add("yt-dlp")
        sync_gradle(self.project)
        text = self.gradle()
        self.assertIn('install("requests")', text)
        self.assertIn('install("yt-dlp")', text)

        reqs.remove("requests")
        sync_gradle(self.project)
        text = self.gradle()
        self.assertNotIn('install("requests")', text)
        self.assertIn('install("yt-dlp")', text)
        # Syncing repeatedly must not duplicate the block.
        sync_gradle(self.project)
        self.assertEqual(self.gradle().count("pydrud:pip:begin"), 1)

    def test_sync_outside_a_project_fails_clearly(self):
        with self.assertRaises(PackageError):
            sync_gradle(self.tmp)

    def test_release_signing_status_defaults_to_the_debug_key(self):
        status = release.signing_status(self.project)
        self.assertFalse(status["configured"])
        self.assertEqual(status["signed_with"], "debug key")

    def test_permissions_can_be_added_and_removed(self):
        added = release.update_permissions(self.project,
                                           add=["camera", "location"])
        self.assertEqual(added, ["CAMERA", "ACCESS_FINE_LOCATION"])
        self.assertIn("CAMERA", release.list_permissions(self.project))

        # Adding the same permission twice is a no-op.
        self.assertEqual(release.update_permissions(self.project,
                                                    add=["camera"]), [])
        release.update_permissions(self.project, remove=["camera"])
        self.assertNotIn("CAMERA", release.list_permissions(self.project))

    def test_permission_aliases(self):
        self.assertEqual(release.resolve_permission("microphone"),
                         "RECORD_AUDIO")
        self.assertEqual(release.resolve_permission("CUSTOM_THING"),
                         "CUSTOM_THING")

    def test_icon_generation_writes_every_density(self):
        written = release.generate_icons(self.project)
        self.assertTrue(written)
        res = os.path.join(self.project, "android", "app", "src", "main", "res")
        for bucket in release.ICON_SIZES:
            self.assertTrue(os.path.exists(os.path.join(
                res, f"mipmap-{bucket}", "ic_launcher.png")))
        self.assertTrue(os.path.exists(os.path.join(
            res, "mipmap-anydpi-v26", "ic_launcher.xml")))
        self.assertTrue(os.path.exists(os.path.join(
            res, "drawable", "splash.xml")))

    def test_keygen_refuses_short_passwords(self):
        self.assertFalse(release.create_keystore(self.project, password="abc"))

    def test_proguard_rules_are_generated(self):
        rules = os.path.join(self.project, "android", "app",
                             "proguard-rules.pro")
        self.assertTrue(os.path.exists(rules))
        text = open(rules, encoding="utf-8").read()
        self.assertIn("com.chaquo.python", text)
        self.assertIn("BridgeService", text)

    def test_generated_gradle_supports_signing_and_shrinking(self):
        text = self.gradle()
        self.assertIn("keystore.properties", text)
        self.assertIn("pydrudShrink", text)
        self.assertIn("isShrinkResources", text)

    def test_docs_are_generated(self):
        from pydrud.commands.docs import build_docs

        out = build_docs(self.project, "docs")
        index = os.path.join(out, "index.html")
        self.assertTrue(os.path.exists(index))
        html = open(index, encoding="utf-8").read()
        self.assertIn("Pydrud", html)
        self.assertTrue(os.path.exists(os.path.join(out, "pydrud.html")))


class TestInspector(unittest.TestCase):

    def tree(self) -> dict:
        from pydrud import App, Button, Column, Text

        def build(page):
            page.add(Column(children=[Text("Hello"),
                                      Button("Tap", on_click=lambda e: None)]))

        return App(target=build).build().to_dict()

    def test_summarise_counts_nodes_and_handlers(self):
        from pydrud.commands.inspector import count_nodes, summarise

        tree = self.tree()
        stats = summarise(tree)
        self.assertEqual(stats["nodes"], count_nodes(tree))
        self.assertGreaterEqual(stats["interactive"], 1)
        self.assertIn("Text", stats["widgets"])

    def test_render_tree_is_readable(self):
        from pydrud.commands.inspector import render_tree

        text = render_tree(self.tree())
        self.assertIn("Text", text)
        self.assertIn("'Hello'", text)

    def test_connecting_to_nothing_fails_gracefully(self):
        from pydrud.commands.inspector import run_inspector

        tmp = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            self.assertEqual(run_inspector(port=1, timeout=0.2), 1)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)


class TestCliCommands(unittest.TestCase):
    """The click commands themselves, run end-to-end in a temp project."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-cli-")
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        create_project("clidemo", org="com.example")
        os.chdir(os.path.join(self.tmp, "clidemo"))
        self.runner = CliRunner()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pip_add_list_remove(self):
        result = self.runner.invoke(cli, ["pip", "add", "yt-dlp"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("yt-dlp", result.output)

        listed = self.runner.invoke(cli, ["pip", "list"])
        self.assertIn("yt-dlp", listed.output)

        removed = self.runner.invoke(cli, ["pip", "remove", "yt-dlp"])
        self.assertIn("[-] yt-dlp", removed.output)
        self.assertIn("No extra packages",
                      self.runner.invoke(cli, ["pip", "list"]).output)

    def test_pip_add_rejects_blocked_packages(self):
        result = self.runner.invoke(cli, ["pip", "add", "flask"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("server framework", result.output)

    def test_pip_list_all_and_search(self):
        listed = self.runner.invoke(cli, ["pip", "list", "--all"])
        self.assertIn("verified packages", listed.output)
        self.assertIn("NETWORK", listed.output)

        filtered = self.runner.invoke(cli, ["pip", "list", "--all",
                                            "--category", "ai"])
        self.assertIn("openai", filtered.output)
        self.assertNotIn("NETWORK", filtered.output)

        found = self.runner.invoke(cli, ["pip", "search", "pdf"])
        self.assertIn("pypdf", found.output)

    def test_pip_sync(self):
        self.runner.invoke(cli, ["pip", "add", "requests", "--no-sync"])
        result = self.runner.invoke(cli, ["pip", "sync"])
        self.assertIn("Synced 1 package", result.output)

    def test_permissions_commands(self):
        added = self.runner.invoke(cli, ["permissions", "add", "camera"])
        self.assertIn("[+] CAMERA", added.output)
        removed = self.runner.invoke(cli, ["permissions", "remove", "camera"])
        self.assertIn("[-] CAMERA", removed.output)

    def test_icons_command(self):
        result = self.runner.invoke(cli, ["icons"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("resource file(s) written", result.output)

    def test_inspect_without_a_device_reports_statically(self):
        result = self.runner.invoke(cli, ["inspect", "--port", "1"])
        self.assertIn("Nodes:", result.output)


class TestBuildPython(unittest.TestCase):
    """``buildPython`` must match the app's Python so Chaquopy can
    pre-compile to .pyc (Gradle otherwise warns the version is
    "incompatible" and ships plain source)."""

    def test_detection_prefers_the_apps_python_version(self):
        from pydrud.commands import project as project_mod

        tried = []

        def fake_which(name):
            tried.append(name)
            return f"/usr/bin/{name}"

        class FakeRun:
            returncode = 0
            stdout = "/usr/bin/pythonX\n"

        with mock.patch.object(project_mod.shutil, "which", fake_which), \
                mock.patch("subprocess.run", return_value=FakeRun()):
            project_mod._detect_build_python("3.11")
        self.assertTrue(tried[0].endswith("3.11"), tried[:3])

        tried.clear()
        with mock.patch.object(project_mod.shutil, "which", fake_which), \
                mock.patch("subprocess.run", return_value=FakeRun()):
            project_mod._detect_build_python("3.9")
        self.assertTrue(tried[0].endswith("3.9"), tried[:3])

    def test_builder_does_not_force_the_default_interpreter(self):
        """Regression: the builder used to export whatever ``python``
        resolved to, defeating the version-aware detection."""
        from pydrud.commands.builder import Builder

        tmp = tempfile.mkdtemp(prefix="pydrud-buildenv-")
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            create_project("envdemo", org="com.example")
            builder = Builder(os.path.join(tmp, "envdemo"))
            with mock.patch("pydrud.commands.project._detect_build_python",
                            return_value="/opt/py311") as detect:
                env = builder._build_env()
            detect.assert_called_once_with("3.11")
            self.assertEqual(env["PYDRUD_PYTHON"], "/opt/py311")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_explicit_pydrud_python_is_respected(self):
        from pydrud.commands.builder import Builder

        tmp = tempfile.mkdtemp(prefix="pydrud-buildenv-")
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            create_project("envdemo2", org="com.example")
            builder = Builder(os.path.join(tmp, "envdemo2"))
            with mock.patch.dict(os.environ,
                                 {"PYDRUD_PYTHON": "/custom/python"}):
                env = builder._build_env()
            self.assertEqual(env["PYDRUD_PYTHON"], "/custom/python")
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
