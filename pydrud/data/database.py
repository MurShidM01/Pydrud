"""
SQLite and a small ORM.

Chaquopy bundles CPython's ``sqlite3``, so the *same* code runs on the device
and on a development machine — no bridge round-trip, no Java glue, and no
difference in behaviour between tests and production.

Raw SQL::

    db = page.database("notes.db")
    db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT)")
    db.insert("notes", {"body": "Hello"})
    rows = db.query("SELECT * FROM notes WHERE body LIKE ?", ["He%"])

Models::

    class Note(Model):
        __table__ = "notes"
        body = column(str, index=True)
        done = column(bool, default=False)
        created = column(float, default=time.time)

    db.bind(Note)                       # creates/migrates the table
    Note(body="Buy milk").save()
    Note.where(done=False).order_by("-created").limit(20).all()
    Note.get(1).update(done=True)

Every call is synchronous. SQLite is fast, but file I/O still does not belong
on the UI thread: use ``page.run_task(...)`` for anything bulk, or
``db.transaction()`` to batch writes.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from typing import Any, Iterable, Iterator, Optional, Sequence

_PY_TO_SQL = {
    int: "INTEGER",
    float: "REAL",
    bool: "INTEGER",
    str: "TEXT",
    bytes: "BLOB",
    dict: "TEXT",   # stored as JSON
    list: "TEXT",   # stored as JSON
}

#: Column types may also be named as strings (``column("score", "int")``),
#: which is what a schema loaded from YAML/JSON naturally produces.
_TYPE_ALIASES = {t.__name__: t for t in _PY_TO_SQL}
_TYPE_ALIASES.update({
    "integer": int, "text": str, "string": str, "real": float,
    "double": float, "boolean": bool, "blob": bytes, "json": dict,
})


#: SQLite identifiers (table and column names) cannot be parameterised, so
#: they are interpolated into the SQL text. Everything that reaches that
#: interpolation goes through :func:`_ident` first.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    """Validate a table/column name before it is spliced into SQL.

    Values are always bound as parameters, but identifiers cannot be — a
    column name taken from user input (a sort key in a URL, a dynamic
    filter) would otherwise be an injection point. Anything that is not a
    plain identifier is rejected loudly.
    """
    text = str(name)
    if not _IDENT_RE.match(text):
        raise ValueError(
            f"invalid SQL identifier {name!r} — table and column names must "
            "match [A-Za-z_][A-Za-z0-9_]*")
    return text


def _resolve_type(type_: Any) -> type:
    """Accept ``int``, ``"int"`` or ``"INTEGER"`` and return a Python type."""
    if isinstance(type_, str):
        resolved = _TYPE_ALIASES.get(type_.strip().lower())
        if resolved is None:
            raise TypeError(
                f"Unsupported column type {type_!r}. "
                f"Use one of {sorted(t.__name__ for t in _PY_TO_SQL)}")
        return resolved
    if type_ not in _PY_TO_SQL:
        raise TypeError(
            f"Unsupported column type {type_!r}. "
            f"Use one of {sorted(t.__name__ for t in _PY_TO_SQL)}")
    return type_


class Field:
    """A column definition on a :class:`Model`.

    ``name`` is optional — :class:`ModelMeta` fills it in from the
    attribute the field is assigned to, and an explicit one (what
    ``column("score", int)`` passes) has to agree with it.
    """

    __slots__ = ("name", "type", "primary_key", "null", "unique", "index",
                 "default", "sql_type", "explicit_name")

    def __init__(self, type_: Any = str, *, name: str = "",
                 primary_key: bool = False,
                 null: bool = True, unique: bool = False, index: bool = False,
                 default: Any = None):
        type_ = _resolve_type(type_)
        self.name = str(name)    # filled in by ModelMeta when left empty
        self.explicit_name = bool(name)
        self.type = type_
        self.primary_key = bool(primary_key)
        self.null = bool(null) and not primary_key
        self.unique = bool(unique)
        self.index = bool(index)
        self.default = default
        self.sql_type = _PY_TO_SQL[type_]

    # ── value conversion ─────────────────────────────────────────────────

    def to_db(self, value: Any) -> Any:
        if value is None:
            return None
        if self.type is bool:
            return 1 if value else 0
        if self.type in (dict, list):
            import json
            return json.dumps(value)
        if self.type is bytes:
            return value if isinstance(value, (bytes, bytearray)) else bytes(value)
        return self.type(value)

    def from_db(self, value: Any) -> Any:
        if value is None:
            return None
        if self.type is bool:
            return bool(value)
        if self.type in (dict, list):
            import json
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return value
        return value

    def make_default(self) -> Any:
        return self.default() if callable(self.default) else self.default

    def ddl(self) -> str:
        parts = [f'"{self.name}"', self.sql_type]
        if self.primary_key:
            parts.append("PRIMARY KEY")
            if self.type is int:
                parts.append("AUTOINCREMENT")
        if not self.null and not self.primary_key:
            parts.append("NOT NULL")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"Field({self.name!r}, {self.type.__name__})"


def column(*args: Any, **kwargs: Any) -> Field:
    """Shorthand for :class:`Field` — reads better in model bodies::

        name  = column(str)                      # type only (classic)
        score = column("score", type_=int, index=True)
        tags  = column("tags", "list")           # type named as a string
        id    = column("id", primary_key=True)   # type inferred: int

    An explicit name must match the attribute it is assigned to — the
    attribute *is* the column name in ``where``/``order_by``/``to_dict``,
    so a mismatch is a mistake, not an alias. Without a type, a primary
    key (or ``id``) defaults to ``int``, the rest to ``str``.
    """
    name = kwargs.pop("name", "")
    type_ = kwargs.pop("type_", None)
    strings: list[str] = []
    for arg in args:
        if isinstance(arg, type):
            if type_ is not None:
                raise TypeError("column() got more than one type")
            type_ = arg
        elif isinstance(arg, str):
            strings.append(arg)
        else:
            raise TypeError(
                f"column() takes a name and/or a type, got {arg!r}")

    if len(strings) == 2:
        if name:
            raise TypeError("column() got more than one name")
        name, type_ = strings[0], strings[1] if type_ is None else type_
    elif len(strings) == 1:
        only = strings[0]
        known_type = only.strip().lower() in _TYPE_ALIASES
        if type_ is None and not name and known_type:
            type_ = only            # column("int") — a type named as a string
        elif name:
            raise TypeError("column() got more than one name")
        else:
            name = only             # column("id", primary_key=True)
    elif len(strings) > 2:
        raise TypeError("column() takes at most two positional arguments")

    if type_ is None:
        type_ = int if (kwargs.get("primary_key") or name == "id") else str
    return Field(type_, name=name, **kwargs)


# ──────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────


class Database:
    """A thread-safe handle on one SQLite file (or ``:memory:``)."""

    def __init__(self, path: str = ":memory:", *, timeout: float = 5.0,
                 foreign_keys: bool = True):
        self.path = path
        if path != ":memory:":
            directory = os.path.dirname(os.path.abspath(path))
            if directory:
                os.makedirs(directory, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, timeout=timeout,
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            if foreign_keys:
                self._conn.execute("PRAGMA foreign_keys=ON")

    # ── raw access ───────────────────────────────────────────────────────

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying ``sqlite3.Connection`` for anything exotic."""
        return self._conn

    def execute(self, sql: str, params: Sequence = ()) -> sqlite3.Cursor:
        """Run a statement and commit. Returns the cursor."""
        self._check()
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def execute_many(self, sql: str, rows: Iterable[Sequence]) -> int:
        self._check()
        with self._lock:
            cur = self._conn.executemany(sql, [tuple(r) for r in rows])
            self._conn.commit()
            return cur.rowcount

    def execute_script(self, sql: str) -> None:
        self._check()
        with self._lock:
            self._conn.executescript(sql)
            self._conn.commit()

    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        """Run a SELECT and return a list of plain dicts."""
        self._check()
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return [dict(row) for row in cur.fetchall()]

    def first(self, sql: str, params: Sequence = ()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence = ()) -> Any:
        """Return the first column of the first row (or ``None``)."""
        row = self.first(sql, params)
        return next(iter(row.values())) if row else None

    # ── convenience CRUD ─────────────────────────────────────────────────

    def insert(self, table: str, values: dict) -> int:
        if not values:
            raise ValueError("insert() needs at least one column")
        cols = ", ".join(f'"{_ident(c)}"' for c in values)
        marks = ", ".join("?" for _ in values)
        cur = self.execute(
            f'INSERT INTO "{_ident(table)}" ({cols}) VALUES ({marks})',
                           list(values.values()))
        return int(cur.lastrowid or 0)

    def update(self, table: str, values: dict, where: dict) -> int:
        if not values:
            return 0
        sets = ", ".join(f'"{_ident(c)}" = ?' for c in values)
        clause, params = _where_clause(where)
        cur = self.execute(f'UPDATE "{_ident(table)}" SET {sets}{clause}',
                           list(values.values()) + params)
        return cur.rowcount

    def delete(self, table: str, where: dict) -> int:
        clause, params = _where_clause(where)
        cur = self.execute(f'DELETE FROM "{_ident(table)}"{clause}', params)
        return cur.rowcount

    def count(self, table: str, where: Optional[dict] = None) -> int:
        clause, params = _where_clause(where or {})
        return int(self.scalar(
            f'SELECT COUNT(*) FROM "{_ident(table)}"{clause}',
                               params) or 0)

    def tables(self) -> list[str]:
        rows = self.query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        return [r["name"] for r in rows]

    def columns(self, table: str) -> list[str]:
        return [r["name"]
                for r in self.query(f'PRAGMA table_info("{_ident(table)}")')]

    # ── transactions ─────────────────────────────────────────────────────

    def transaction(self) -> "_Transaction":
        """Context manager: commits on success, rolls back on exception."""
        return _Transaction(self)

    # ── schema versioning ────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return int(self.scalar("PRAGMA user_version") or 0)

    @version.setter
    def version(self, value: int) -> None:
        self.execute(f"PRAGMA user_version = {int(value)}")

    def migrate(self, *migrations: "Migration") -> list[int]:
        """Apply every migration whose version is above ``db.version``."""
        applied: list[int] = []
        for migration in sorted(migrations, key=lambda m: m.version):
            if migration.version <= self.version:
                continue
            with self.transaction():
                migration.apply(self)
            self.version = migration.version
            applied.append(migration.version)
        return applied

    # ── models ───────────────────────────────────────────────────────────

    def bind(self, *models: type) -> "Database":
        """Attach model classes to this database and create their tables."""
        for model in models:
            if not (isinstance(model, type) and issubclass(model, Model)):
                raise TypeError(f"{model!r} is not a Model subclass")
            model.__database__ = self
            model.create_table()
        return self

    # ── lifecycle ────────────────────────────────────────────────────────

    def close(self) -> None:
        if not self._closed:
            with self._lock:
                self._conn.close()
            self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    def _check(self) -> None:
        if self._closed:
            raise RuntimeError("Database is closed")

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Database({self.path!r}, tables={len(self.tables())})"


class _Transaction:
    def __init__(self, db: Database):
        self._db = db

    def __enter__(self) -> Database:
        self._db._lock.acquire()
        self._db._conn.execute("BEGIN")
        return self._db

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self._db._conn.commit()
            else:
                self._db._conn.rollback()
        finally:
            self._db._lock.release()
        return False


class Migration:
    """One numbered schema change.

    ``Migration(2, "ALTER TABLE notes ADD COLUMN pinned INTEGER")`` or
    ``Migration(3, lambda db: db.execute(...))``.
    """

    def __init__(self, version: int, action: Any, *, name: str = ""):
        if int(version) < 1:
            raise ValueError("migration versions start at 1")
        self.version = int(version)
        self.action = action
        self.name = name or f"migration_{version}"

    def apply(self, db: Database) -> None:
        if callable(self.action):
            self.action(db)
        elif isinstance(self.action, str):
            db.connection.executescript(self.action)
        else:
            for statement in self.action:
                db.connection.execute(statement)

    def __repr__(self) -> str:
        return f"Migration({self.version}, {self.name!r})"


def open_database(path: str = ":memory:", **kwargs) -> Database:
    """Open (and create if needed) a database file."""
    return Database(path, **kwargs)


# ──────────────────────────────────────────────────────────────────────────
# ORM
# ──────────────────────────────────────────────────────────────────────────


def _where_clause(where: dict) -> tuple[str, list]:
    """Translate ``{"age__gte": 18}`` into ``" WHERE age >= ?", [18]``."""
    if not where:
        return "", []
    ops = {"eq": "=", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">",
           "gte": ">=", "like": "LIKE", "contains": "LIKE",
           "startswith": "LIKE", "endswith": "LIKE", "in": "IN",
           "not": "!=", "isnull": "IS"}
    parts, params = [], []
    for raw_key, value in where.items():
        key, _, suffix = raw_key.partition("__")
        op = ops.get(suffix, "=") if suffix else "="
        if suffix == "in":
            values = list(value)
            if not values:
                parts.append("0")
                continue
            parts.append(
                f'"{_ident(key)}" IN ({", ".join("?" for _ in values)})')
            params.extend(values)
            continue
        if suffix == "isnull":
            parts.append(
                f'"{_ident(key)}" IS {"NULL" if value else "NOT NULL"}')
            continue
        if suffix == "contains":
            value = f"%{value}%"
        elif suffix == "startswith":
            value = f"{value}%"
        elif suffix == "endswith":
            value = f"%{value}"
        if isinstance(value, bool):
            value = int(value)
        parts.append(f'"{_ident(key)}" {op} ?')
        params.append(value)
    return " WHERE " + " AND ".join(parts), params


class Query:
    """A lazy, chainable SELECT builder bound to a :class:`Model`."""

    def __init__(self, model: type):
        self._model = model
        self._where: dict = {}
        self._order: list[str] = []
        self._limit: Optional[int] = None
        self._offset: int = 0

    # ── chaining ─────────────────────────────────────────────────────────

    def where(self, **conditions) -> "Query":
        clone = self._clone()
        clone._where.update(conditions)
        return clone

    filter = where

    def order_by(self, *columns: str) -> "Query":
        clone = self._clone()
        clone._order.extend(columns)
        return clone

    def limit(self, count: int, offset: int = 0) -> "Query":
        clone = self._clone()
        clone._limit = int(count)
        clone._offset = int(offset)
        return clone

    def page(self, number: int, size: int = 20) -> "Query":
        """1-based pagination helper."""
        return self.limit(size, max(0, (int(number) - 1)) * int(size))

    # ── execution ────────────────────────────────────────────────────────

    def sql(self) -> tuple[str, list]:
        clause, params = _where_clause(self._where)
        sql = f'SELECT * FROM "{self._model.__table__}"{clause}'
        if self._order:
            parts = []
            for col in self._order:
                if col.startswith("-"):
                    parts.append(f'"{_ident(col[1:])}" DESC')
                else:
                    parts.append(f'"{_ident(col.lstrip("+"))}" ASC')
            sql += " ORDER BY " + ", ".join(parts)
        if self._limit is not None:
            sql += f" LIMIT {self._limit} OFFSET {self._offset}"
        return sql, params

    def all(self) -> list:
        sql, params = self.sql()
        rows = self._model._db().query(sql, params)
        return [self._model._from_row(row) for row in rows]

    def first(self):
        results = self.limit(1).all()
        return results[0] if results else None

    def count(self) -> int:
        clause, params = _where_clause(self._where)
        return int(self._model._db().scalar(
            f'SELECT COUNT(*) FROM "{self._model.__table__}"{clause}',
            params) or 0)

    def exists(self) -> bool:
        return self.count() > 0

    def values(self, *columns: str) -> list[dict]:
        """Rows as dicts, optionally limited to *columns*."""
        sql, params = self.sql()
        rows = self._model._db().query(sql, params)
        if not columns:
            return rows
        return [{c: row.get(c) for c in columns} for row in rows]

    def delete(self) -> int:
        clause, params = _where_clause(self._where)
        cur = self._model._db().execute(
            f'DELETE FROM "{self._model.__table__}"{clause}', params)
        return cur.rowcount

    def update(self, **values) -> int:
        fields = self._model.__fields__
        payload = {k: fields[k].to_db(v) if k in fields else v
                   for k, v in values.items()}
        clause, params = _where_clause(self._where)
        sets = ", ".join(f'"{_ident(c)}" = ?' for c in payload)
        cur = self._model._db().execute(
            f'UPDATE "{self._model.__table__}" SET {sets}{clause}',
            list(payload.values()) + params)
        return cur.rowcount

    # ── python protocol ──────────────────────────────────────────────────

    def __iter__(self) -> Iterator:
        return iter(self.all())

    def __len__(self) -> int:
        return self.count()

    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start or 0
            stop = item.stop if item.stop is not None else start + 100
            return self.limit(stop - start, start).all()
        return self.limit(1, int(item)).all()[0]

    def _clone(self) -> "Query":
        clone = Query(self._model)
        clone._where = dict(self._where)
        clone._order = list(self._order)
        clone._limit = self._limit
        clone._offset = self._offset
        return clone

    def __repr__(self) -> str:
        return f"Query({self._model.__name__}, {self.sql()[0]!r})"


class ModelMeta(type):
    """Collects :class:`Field` attributes and gives every model an ``id``."""

    def __new__(mcls, name, bases, namespace):
        fields: dict[str, Field] = {}
        for base in bases:
            fields.update(getattr(base, "__fields__", {}))

        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                if value.explicit_name and value.name != key:
                    raise TypeError(
                        f"{name}.{key}: column named {value.name!r} is "
                        f"assigned to attribute {key!r}. The attribute name "
                        f"is the column name everywhere else in the API — "
                        f"rename one of them (or drop the name argument).")
                value.name = key
                fields[key] = value
                namespace.pop(key)

        cls = super().__new__(mcls, name, bases, namespace)
        if name != "Model" and "id" not in fields:
            pk = Field(int, primary_key=True)
            pk.name = "id"
            fields = {"id": pk, **fields}
        cls.__fields__ = fields
        if name != "Model" and not namespace.get("__table__"):
            cls.__table__ = name.lower() + "s"
        if name != "Model":
            # Fail at class-definition time rather than on the first query.
            _ident(cls.__table__)
            for field_name in fields:
                _ident(field_name)
        return cls


class Model(metaclass=ModelMeta):
    """Base class for ORM models.

    Subclasses declare columns with :func:`column` and are attached to a
    database with ``db.bind(MyModel)``. Every model gets an autoincrement
    ``id`` primary key for free — declaring it is optional, and it stays
    ``None`` until the row is saved, because SQLite is what allocates it::

        entry = Score(player="Ali")   # entry.id is None
        entry.save()                  # entry.id is 1
    """

    __table__: str = ""
    __database__: Optional[Database] = None
    __fields__: dict[str, Field] = {}

    def __init__(self, **values):
        unknown = set(values) - set(self.__fields__)
        if unknown:
            raise TypeError(
                f"{type(self).__name__} has no column(s): {sorted(unknown)}")
        for name, field in self.__fields__.items():
            if name in values:
                setattr(self, name, values[name])
            else:
                setattr(self, name, field.make_default())

    # ── class helpers ────────────────────────────────────────────────────

    @classmethod
    def _db(cls) -> Database:
        if cls.__database__ is None:
            raise RuntimeError(
                f"{cls.__name__} is not bound to a database — call "
                f"db.bind({cls.__name__}) first")
        return cls.__database__

    @classmethod
    def create_table(cls, *, if_not_exists: bool = True) -> None:
        columns = ", ".join(f.ddl() for f in cls.__fields__.values())
        exists = "IF NOT EXISTS " if if_not_exists else ""
        db = cls._db()
        db.execute(f'CREATE TABLE {exists}"{cls.__table__}" ({columns})')
        # Add columns introduced after the table was first created.
        present = set(db.columns(cls.__table__))
        for field in cls.__fields__.values():
            if field.name not in present:
                db.execute(f'ALTER TABLE "{cls.__table__}" '
                           f'ADD COLUMN {field.ddl()}')
        for field in cls.__fields__.values():
            if field.index and not field.primary_key:
                db.execute(
                    f'CREATE INDEX IF NOT EXISTS '
                    f'"ix_{cls.__table__}_{field.name}" '
                    f'ON "{cls.__table__}" ("{field.name}")')

    @classmethod
    def drop_table(cls) -> None:
        cls._db().execute(f'DROP TABLE IF EXISTS "{cls.__table__}"')

    @classmethod
    def query(cls) -> Query:
        return Query(cls)

    @classmethod
    def where(cls, **conditions) -> Query:
        return Query(cls).where(**conditions)

    filter = where

    @classmethod
    def all(cls) -> list:
        return Query(cls).all()

    @classmethod
    def get(cls, pk=None, **conditions):
        """Fetch one row by primary key or by conditions (``None`` if absent)."""
        if pk is not None:
            conditions["id"] = pk
        return Query(cls).where(**conditions).first()

    @classmethod
    def create(cls, **values):
        instance = cls(**values)
        instance.save()
        return instance

    @classmethod
    def get_or_create(cls, defaults: Optional[dict] = None, **conditions):
        """Returns ``(instance, created)``."""
        found = Query(cls).where(**conditions).first()
        if found is not None:
            return found, False
        payload = dict(conditions)
        payload.update(defaults or {})
        return cls.create(**payload), True

    @classmethod
    def bulk_create(cls, rows: Iterable[dict]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        names = [n for n in cls.__fields__ if n != "id"]
        marks = ", ".join("?" for _ in names)
        cols = ", ".join(f'"{n}"' for n in names)
        payload = [
            [cls.__fields__[n].to_db(row.get(n,
                                             cls.__fields__[n].make_default()))
             for n in names]
            for row in rows
        ]
        return cls._db().execute_many(
            f'INSERT INTO "{cls.__table__}" ({cols}) VALUES ({marks})', payload)

    @classmethod
    def count(cls, **conditions) -> int:
        return Query(cls).where(**conditions).count()

    @classmethod
    def _from_row(cls, row: dict):
        instance = cls.__new__(cls)
        for name, field in cls.__fields__.items():
            setattr(instance, name, field.from_db(row.get(name)))
        return instance

    # ── instance API ─────────────────────────────────────────────────────

    def save(self):
        """INSERT when the row is new, UPDATE when it already has an id."""
        db = self._db()
        payload = {name: field.to_db(getattr(self, name, None))
                   for name, field in self.__fields__.items()
                   if name != "id"}
        if getattr(self, "id", None) is None:
            self.id = db.insert(self.__table__, payload)
        else:
            db.update(self.__table__, payload, {"id": self.id})
        return self

    def update(self, **values):
        for key, value in values.items():
            if key not in self.__fields__:
                raise TypeError(f"Unknown column {key!r}")
            setattr(self, key, value)
        return self.save()

    def delete(self) -> bool:
        if getattr(self, "id", None) is None:
            return False
        self._db().delete(self.__table__, {"id": self.id})
        self.id = None
        return True

    def refresh(self):
        fresh = type(self).get(self.id)
        if fresh is not None:
            for name in self.__fields__:
                setattr(self, name, getattr(fresh, name))
        return self

    def to_dict(self) -> dict:
        return {name: getattr(self, name, None) for name in self.__fields__}

    def __eq__(self, other) -> bool:
        return (type(other) is type(self)
                and getattr(other, "id", None) == getattr(self, "id", None)
                and getattr(self, "id", None) is not None)

    def __hash__(self) -> int:
        return hash((type(self).__name__, getattr(self, "id", None)))

    def __repr__(self) -> str:
        shown = ", ".join(
            f"{k}={v!r}" for k, v in list(self.to_dict().items())[:4])
        return f"{type(self).__name__}({shown})"
