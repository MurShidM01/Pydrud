"""
File-backed caching with TTL and an LRU size budget.

Mobile apps spend most of their life on a flaky network. :class:`Cache`
stores JSON or bytes in the app's private files directory, so a screen can
render instantly from disk and refresh in the background::

    cache = page.cache                       # Cache in <app_dir>/cache
    posts = cache.get("posts")               # None when missing or expired
    if posts is None:
        posts = fetch_posts()
        cache.set("posts", posts, ttl=300)   # five minutes

    @cached(cache, "profile:{0}", ttl=3600)
    def load_profile(user_id):
        return page.http.get(f"/users/{user_id}").wait().json

Entries are plain files plus a small JSON index, so nothing is lost when the
process is killed. Reads and writes are thread-safe; use ``page.run_task``
for anything bigger than a few hundred kilobytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from typing import Any, Callable, Optional

_MISSING = object()


class Cache:
    """A persistent key/value cache with expiry and an LRU byte budget."""

    def __init__(self, directory: str, *, max_bytes: int = 32 * 1024 * 1024,
                 default_ttl: Optional[float] = None):
        self.directory = os.path.abspath(directory)
        self.max_bytes = int(max_bytes)
        self.default_ttl = default_ttl
        self._lock = threading.RLock()
        self._index_path = os.path.join(self.directory, "index.json")
        os.makedirs(self.directory, exist_ok=True)
        self._index: dict[str, dict] = self._load_index()
        self.hits = 0
        self.misses = 0

    # ── core API ─────────────────────────────────────────────────────────

    def set(self, key: str, value: Any, *, ttl: Optional[float] = None) -> Any:
        """Store *value* (JSON-serialisable or bytes). Returns the value."""
        ttl = self.default_ttl if ttl is None else ttl
        # ``ttl=0`` means "expire immediately", not "never expire", so the
        # expiry is computed whenever a ttl was given at all.
        expires = None if ttl is None else time.time() + float(ttl)
        is_bytes = isinstance(value, (bytes, bytearray))
        payload = bytes(value) if is_bytes else json.dumps(value).encode()
        with self._lock:
            path = self._path_for(key)
            with open(path, "wb") as handle:
                handle.write(payload)
            self._index[key] = {
                "file": os.path.basename(path),
                "size": len(payload),
                "bytes": is_bytes,
                "stored": time.time(),
                "used": time.time(),
                "expires": expires,
            }
            self._save_index()
            self._evict_if_needed()
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value, or *default* when missing or expired."""
        with self._lock:
            entry = self._index.get(key)
            if entry is None:
                self.misses += 1
                return default
            if (entry.get("expires") is not None
                    and entry["expires"] <= time.time()):
                self._remove(key)
                self.misses += 1
                return default
            path = os.path.join(self.directory, entry["file"])
            try:
                with open(path, "rb") as handle:
                    raw = handle.read()
            except OSError:
                self._remove(key)
                self.misses += 1
                return default
            entry["used"] = time.time()
            self.hits += 1
            self._save_index()
        if entry.get("bytes"):
            return raw
        try:
            return json.loads(raw.decode())
        except (ValueError, UnicodeDecodeError):
            return default

    def get_or_set(self, key: str, factory: Callable[[], Any], *,
                   ttl: Optional[float] = None) -> Any:
        """Return the cached value, computing and storing it when absent."""
        found = self.get(key, _MISSING)
        if found is not _MISSING:
            return found
        return self.set(key, factory(), ttl=ttl)

    def has(self, key: str) -> bool:
        return self.get(key, _MISSING) is not _MISSING

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._index:
                return False
            self._remove(key)
            self._save_index()
            return True

    def clear(self) -> None:
        """Drop every entry (the directory itself is kept)."""
        with self._lock:
            shutil.rmtree(self.directory, ignore_errors=True)
            os.makedirs(self.directory, exist_ok=True)
            self._index = {}
            self._save_index()

    def purge(self) -> int:
        """Delete expired entries. Returns how many were removed."""
        now = time.time()
        with self._lock:
            stale = [k for k, e in self._index.items()
                     if e.get("expires") is not None and e["expires"] <= now]
            for key in stale:
                self._remove(key)
            if stale:
                self._save_index()
            return len(stale)

    # ── introspection ────────────────────────────────────────────────────

    def keys(self) -> list[str]:
        with self._lock:
            return sorted(self._index)

    @property
    def size(self) -> int:
        """Total bytes currently stored."""
        with self._lock:
            return sum(int(e.get("size") or 0) for e in self._index.values())

    def age(self, key: str) -> Optional[float]:
        """Seconds since *key* was written, or ``None`` when absent."""
        with self._lock:
            entry = self._index.get(key)
            if entry is None:
                return None
            return time.time() - float(entry.get("stored") or 0.0)

    def stats(self) -> dict:
        return {"entries": len(self._index), "bytes": self.size,
                "hits": self.hits, "misses": self.misses,
                "directory": self.directory}

    # ── internals ────────────────────────────────────────────────────────

    def _path_for(self, key: str) -> str:
        digest = hashlib.sha1(key.encode()).hexdigest()[:20]
        return os.path.join(self.directory, f"{digest}.bin")

    def _remove(self, key: str) -> None:
        entry = self._index.pop(key, None)
        if entry:
            try:
                os.remove(os.path.join(self.directory, entry["file"]))
            except OSError:
                pass

    def _evict_if_needed(self) -> None:
        if self.size <= self.max_bytes:
            return
        # Least-recently-used first.
        for key, _ in sorted(self._index.items(),
                             key=lambda kv: kv[1].get("used") or 0):
            self._remove(key)
            if self.size <= self.max_bytes:
                break
        self._save_index()

    def _load_index(self) -> dict:
        try:
            with open(self._index_path) as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_index(self) -> None:
        tmp = self._index_path + ".tmp"
        try:
            with open(tmp, "w") as handle:
                json.dump(self._index, handle)
            os.replace(tmp, self._index_path)
        except OSError:
            pass

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __len__(self) -> int:
        return len(self._index)

    def __repr__(self) -> str:
        return (f"Cache({self.directory!r}, entries={len(self._index)}, "
                f"bytes={self.size})")


def cached(cache: Cache, key_template: str, *, ttl: Optional[float] = None):
    """Memoise a function's result in *cache*.

    ``key_template`` is formatted with the call arguments, so
    ``"profile:{0}"`` or ``"search:{query}"`` both work.
    """
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                key = key_template.format(*args, **kwargs)
            except (IndexError, KeyError):
                key = f"{key_template}:{args!r}:{sorted(kwargs.items())!r}"
            found = cache.get(key, _MISSING)
            if found is not _MISSING:
                return found
            return cache.set(key, fn(*args, **kwargs), ttl=ttl)

        wrapper.__name__ = getattr(fn, "__name__", "cached")
        wrapper.__doc__ = fn.__doc__
        wrapper.cache_key = key_template
        wrapper.invalidate = lambda *a, **k: cache.delete(
            key_template.format(*a, **k))
        return wrapper
    return decorator
