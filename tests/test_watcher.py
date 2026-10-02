"""Hot-reload watcher: edits, new files and atomic (rename) saves."""

import os
import tempfile
import time
import unittest

from pydrud.core.watcher import FileWatcher, _ReloadHandler


class _Event:
    def __init__(self, src, dest="", is_dir=False):
        self.src_path = src
        self.dest_path = dest
        self.is_directory = is_dir


class TestReloadHandler(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self.handler = _ReloadHandler(self.seen.append, debounce=0.0)

    def test_modified(self):
        self.handler.on_modified(_Event("/p/app.py"))
        self.assertEqual(self.seen, ["/p/app.py"])

    def test_created(self):
        self.handler.on_created(_Event("/p/new.py"))
        self.assertEqual(self.seen, ["/p/new.py"])

    def test_atomic_save_uses_the_destination(self):
        """Editors rename a temp file over the real one."""
        self.handler.on_moved(_Event("/p/.app.py.swp", "/p/app.py"))
        self.assertEqual(self.seen, ["/p/app.py"])

    def test_non_python_and_directories_are_ignored(self):
        self.handler.on_modified(_Event("/p/notes.txt"))
        self.handler.on_modified(_Event("/p/pkg", is_dir=True))
        self.handler.on_created(_Event("/p/__pycache__/app.py"))
        self.assertEqual(self.seen, [])


class TestPollingFallback(unittest.TestCase):
    def test_new_file_after_the_first_scan_fires(self):
        root = tempfile.mkdtemp()
        existing = os.path.join(root, "app.py")
        with open(existing, "w", encoding="utf-8") as handle:
            handle.write("x = 1\n")

        seen = []
        watcher = FileWatcher([root], seen.append, debounce=0.0)
        watcher._walk_and_check(root)      # initial scan
        watcher._scanned = True
        self.assertEqual(seen, [])

        created = os.path.join(root, "late.py")
        with open(created, "w", encoding="utf-8") as handle:
            handle.write("y = 2\n")
        watcher._walk_and_check(root)
        self.assertEqual(seen, [created])

    def test_edit_fires(self):
        root = tempfile.mkdtemp()
        target = os.path.join(root, "app.py")
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("x = 1\n")

        seen = []
        watcher = FileWatcher([root], seen.append, debounce=0.0)
        watcher._walk_and_check(root)
        os.utime(target, (time.time() + 5, time.time() + 5))
        watcher._walk_and_check(root)
        self.assertEqual(seen, [target])


if __name__ == "__main__":
    unittest.main()
