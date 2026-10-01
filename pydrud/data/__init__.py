"""
Pydrud data layer — SQLite + ORM, file-backed caching and secure storage.

* :mod:`pydrud.data.database` runs entirely in Python (``sqlite3`` ships with
  Chaquopy), so queries work identically on a laptop and on the device.
* :mod:`pydrud.data.cache` is a TTL + LRU cache on top of the app's private
  files directory.
* Encrypted key/value storage lives in :class:`pydrud.services.native.Secure`
  because it must go through Android's Keystore.
"""

from pydrud.data.cache import Cache, cached
from pydrud.data.database import (
    Database, Field, Migration, Model, Query, column, open_database,
)

__all__ = [
    "Cache", "cached",
    "Database", "Field", "Migration", "Model", "Query", "column",
    "open_database",
]
