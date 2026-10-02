"""
Table and column names cannot be bound as SQL parameters, so they are
interpolated into the statement text. Everything that reaches that
interpolation must be a plain identifier — otherwise a column name coming
from user input (a sort key in a deep link, a dynamic filter) is an
injection point.
"""

from __future__ import annotations

import unittest

from pydrud.data.database import Database, Model, column


class TestIdentifierValidation(unittest.TestCase):

    def setUp(self):
        self.db = Database(":memory:")
        self.db.execute(
            'CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)')
        self.db.insert("notes", {"body": "hello"})

    def tearDown(self):
        self.db.close()

    def test_valid_usage_still_works(self):
        self.assertEqual(1, self.db.count("notes"))
        self.assertEqual(1, self.db.update("notes", {"body": "hi"},
                                           {"id": 1}))
        self.assertEqual("hi", self.db.scalar("SELECT body FROM notes"))

    def test_malicious_table_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.count('notes" ; DROP TABLE notes --')
        self.assertIn("notes", self.db.tables())

    def test_malicious_column_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.insert("notes", {'body" , "id': "x"})
        with self.assertRaises(ValueError):
            self.db.delete("notes", {'id" OR "1"="1': 1})
        self.assertEqual(1, self.db.count("notes"))

    def test_malicious_order_by_is_rejected(self):
        class Note(Model):
            __table__ = "notes"
            body = column(str)

        self.db.bind(Note)
        with self.assertRaises(ValueError):
            Note.query().order_by("body; DROP TABLE notes").all()
        self.assertEqual(1, self.db.count("notes"))

    def test_descending_and_plus_prefixes_are_allowed(self):
        class Note(Model):
            __table__ = "notes"
            body = column(str)

        self.db.bind(Note)
        sql, _params = Note.query().order_by("-id", "+body").sql()
        self.assertIn('"id" DESC', sql)
        self.assertIn('"body" ASC', sql)

    def test_bad_model_definition_fails_at_class_creation(self):
        with self.assertRaises(ValueError):
            class Bad(Model):
                __table__ = 'oops"; DROP TABLE notes --'


if __name__ == "__main__":
    unittest.main()
