"""v1.3 data layer: SQLite, the ORM, migrations and the file cache."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest

from pydrud.data import Cache, Database, Migration, Model, cached, column


class Note(Model):
    __table__ = "notes"
    body = column(str, index=True)
    done = column(bool, default=False)
    score = column(float, default=0.0)
    tags = column(list, default=list)


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_raw_crud_round_trip(self):
        self.db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        row_id = self.db.insert("t", {"name": "Ada"})
        self.assertEqual(row_id, 1)
        self.assertEqual(self.db.query("SELECT * FROM t")[0]["name"], "Ada")

        self.db.update("t", {"name": "Grace"}, {"id": row_id})
        self.assertEqual(self.db.scalar("SELECT name FROM t"), "Grace")
        self.assertEqual(self.db.count("t"), 1)
        self.db.delete("t", {"id": row_id})
        self.assertEqual(self.db.count("t"), 0)

    def test_tables_and_columns(self):
        self.db.execute("CREATE TABLE a (id INTEGER PRIMARY KEY, x TEXT)")
        self.assertEqual(self.db.tables(), ["a"])
        self.assertEqual(self.db.columns("a"), ["id", "x"])

    def test_transaction_rolls_back_on_error(self):
        self.db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        with self.assertRaises(ValueError):
            with self.db.transaction() as db:
                db.connection.execute("INSERT INTO t (name) VALUES ('x')")
                raise ValueError("boom")
        self.assertEqual(self.db.count("t"), 0)

    def test_migrations_apply_once_and_track_version(self):
        self.assertEqual(self.db.version, 0)
        applied = self.db.migrate(
            Migration(1, "CREATE TABLE m (id INTEGER PRIMARY KEY)"),
            Migration(2, lambda db: db.execute(
                "ALTER TABLE m ADD COLUMN pinned INTEGER")),
        )
        self.assertEqual(applied, [1, 2])
        self.assertEqual(self.db.version, 2)
        self.assertIn("pinned", self.db.columns("m"))
        # Re-running is a no-op.
        self.assertEqual(self.db.migrate(
            Migration(1, "SELECT 1"), Migration(2, "SELECT 1")), [])

    def test_file_database_creates_parent_directories(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "nested", "app.db")
            db = Database(path)
            db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            db.close()
            self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_closed_database_refuses_queries(self):
        self.db.close()
        with self.assertRaises(RuntimeError):
            self.db.query("SELECT 1")


class TestOrm(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.db.bind(Note)

    def tearDown(self):
        Note.__database__ = None
        self.db.close()

    def test_table_and_columns_are_derived(self):
        self.assertEqual(Note.__table__, "notes")
        self.assertEqual(set(self.db.columns("notes")),
                         {"id", "body", "done", "score", "tags"})

    def test_save_insert_then_update(self):
        note = Note(body="Buy milk")
        note.save()
        self.assertEqual(note.id, 1)
        note.body = "Buy oat milk"
        note.save()
        self.assertEqual(Note.count(), 1)
        self.assertEqual(Note.get(1).body, "Buy oat milk")

    def test_types_round_trip(self):
        Note.create(body="x", done=True, score=4.5, tags=["a", "b"])
        found = Note.get(1)
        self.assertIs(found.done, True)
        self.assertEqual(found.score, 4.5)
        self.assertEqual(found.tags, ["a", "b"])

    def test_query_builder(self):
        for index in range(5):
            Note.create(body=f"note {index}", score=float(index),
                        done=index % 2 == 0)
        self.assertEqual(Note.where(done=True).count(), 3)
        self.assertEqual(len(Note.where(score__gte=3).all()), 2)
        self.assertEqual(Note.where(body__contains="note 4").first().score, 4.0)
        ordered = Note.query().order_by("-score").limit(2).all()
        self.assertEqual([n.score for n in ordered], [4.0, 3.0])
        self.assertEqual(Note.where(score__in=[0.0, 1.0]).count(), 2)
        self.assertTrue(Note.where(body__startswith="note").exists())

    def test_pagination_and_slicing(self):
        Note.bulk_create([{"body": f"b{i}"} for i in range(10)])
        self.assertEqual(len(Note.query().page(2, 4).all()), 4)
        self.assertEqual(len(Note.query()[0:3]), 3)
        self.assertEqual(len(Note.query()), 10)

    def test_bulk_update_and_delete(self):
        Note.bulk_create([{"body": "a"}, {"body": "b"}, {"body": "c"}])
        self.assertEqual(Note.query().update(done=True), 3)
        self.assertEqual(Note.where(done=True).count(), 3)
        self.assertEqual(Note.where(body="a").delete(), 1)
        self.assertEqual(Note.count(), 2)

    def test_get_or_create(self):
        note, created = Note.get_or_create(body="unique", defaults={"score": 9})
        self.assertTrue(created)
        again, created = Note.get_or_create(body="unique")
        self.assertFalse(created)
        self.assertEqual(again.id, note.id)

    def test_instance_update_delete_refresh(self):
        note = Note.create(body="x")
        note.update(body="y", done=True)
        self.assertEqual(Note.get(note.id).body, "y")
        copy = Note.get(note.id)
        note.update(score=3.0)
        copy.refresh()
        self.assertEqual(copy.score, 3.0)
        self.assertTrue(note.delete())
        self.assertIsNone(Note.get(1))

    def test_unknown_column_raises(self):
        with self.assertRaises(TypeError):
            Note(nope=1)
        with self.assertRaises(TypeError):
            Note.create(body="x").update(nope=1)

    def test_unbound_model_has_a_helpful_error(self):
        class Orphan(Model):
            name = column(str)

        with self.assertRaises(RuntimeError) as ctx:
            Orphan.all()
        self.assertIn("db.bind", str(ctx.exception))

    def test_new_column_is_added_to_an_existing_table(self):
        self.db.execute('DROP TABLE notes')
        self.db.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)')
        Note.create_table()
        self.assertIn("score", self.db.columns("notes"))

    def test_to_dict_and_equality(self):
        first = Note.create(body="a")
        same = Note.get(first.id)
        self.assertEqual(first, same)
        self.assertEqual(set(first.to_dict()),
                         {"id", "body", "done", "score", "tags"})


class TestCache(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pydrud-cache-")
        self.cache = Cache(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_set_get_delete(self):
        self.cache.set("user", {"name": "Ada"})
        self.assertEqual(self.cache.get("user")["name"], "Ada")
        self.assertIn("user", self.cache)
        self.assertTrue(self.cache.delete("user"))
        self.assertIsNone(self.cache.get("user"))
        self.assertFalse(self.cache.delete("user"))

    def test_bytes_round_trip(self):
        self.cache.set("blob", b"\x00\x01binary")
        self.assertEqual(self.cache.get("blob"), b"\x00\x01binary")

    def test_expiry(self):
        self.cache.set("short", 1, ttl=0.05)
        self.assertEqual(self.cache.get("short"), 1)
        time.sleep(0.08)
        self.assertIsNone(self.cache.get("short"))
        self.assertNotIn("short", self.cache.keys())

    def test_purge_removes_only_expired(self):
        self.cache.set("keep", 1)
        self.cache.set("drop", 2, ttl=0.01)
        time.sleep(0.05)
        self.assertEqual(self.cache.purge(), 1)
        self.assertEqual(self.cache.keys(), ["keep"])

    def test_survives_a_new_instance(self):
        self.cache.set("persist", [1, 2, 3])
        reopened = Cache(self.dir)
        self.assertEqual(reopened.get("persist"), [1, 2, 3])

    def test_lru_eviction_respects_the_budget(self):
        small = Cache(self.dir, max_bytes=300)
        for index in range(20):
            small.set(f"k{index}", "x" * 50)
        self.assertLessEqual(small.size, 300)
        self.assertLess(len(small), 20)

    def test_get_or_set_calls_the_factory_once(self):
        calls = []

        def factory():
            calls.append(1)
            return "value"

        self.assertEqual(self.cache.get_or_set("k", factory), "value")
        self.assertEqual(self.cache.get_or_set("k", factory), "value")
        self.assertEqual(len(calls), 1)

    def test_cached_decorator(self):
        calls = []

        @cached(self.cache, "profile:{0}", ttl=60)
        def load(user_id):
            calls.append(user_id)
            return {"id": user_id}

        self.assertEqual(load(7)["id"], 7)
        self.assertEqual(load(7)["id"], 7)
        self.assertEqual(calls, [7])
        load.invalidate(7)
        self.assertEqual(load(7)["id"], 7)
        self.assertEqual(calls, [7, 7])

    def test_stats(self):
        self.cache.set("a", 1)
        self.cache.get("a")
        self.cache.get("missing")
        stats = self.cache.stats()
        self.assertEqual((stats["hits"], stats["misses"]), (1, 1))


class TestPageDataHelpers(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pydrud-app-")
        os.environ["PYDRUD_APP_DIR"] = self.dir

    def tearDown(self):
        os.environ.pop("PYDRUD_APP_DIR", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_page_database_and_cache_use_the_app_directory(self):
        from pydrud import App

        page = App().page
        db = page.database("notes.db")
        self.assertTrue(db.path.startswith(self.dir))
        # The same name returns the same handle.
        self.assertIs(page.database("notes.db"), db)
        self.assertTrue(page.cache.directory.startswith(self.dir))
        db.close()


if __name__ == "__main__":
    unittest.main()
