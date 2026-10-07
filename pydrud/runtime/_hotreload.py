"""
Hot reload and hot restart: file watching, module reloading, state capture.

Split out of ``app.py`` so the reload machinery is self-contained; the methods
run on ``App`` through :class:`HotReloadMixin`.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
import time
import traceback
from typing import TYPE_CHECKING, Any

from pydrud.runtime._modules import (
    _find_user_modules,
    _module_name_for,
    _module_name_from_path,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pydrud.runtime.app import App


def _unlink_synced_file(sync_dir: str, relative_path: str) -> None:
    """Remove a synchronized source only when it stays inside *sync_dir*."""
    root = os.path.abspath(sync_dir)
    candidate = os.path.abspath(os.path.join(root, relative_path))
    try:
        if os.path.commonpath((root, candidate)) == root:
            os.remove(candidate)
    except (OSError, ValueError):
        pass


class HotReloadMixin:
    """File watching, module reloading and State/Store preservation."""


    # ── Hot Reload ─────────────────────────────────────────────────────────

    def enable_hot_reload(self, watch_dirs: list[str] | None = None) -> None:
        """Watch source files and rebuild the UI when they change.

        Args:
            watch_dirs: Directories to watch (relative to the project root).
                Defaults to ``["src"]``.
        """
        from pydrud.core.watcher import FileWatcher

        if self._watcher is not None:
            return
        names = watch_dirs or self._watch_dirs
        dirs = [
            d if os.path.isabs(d) else os.path.join(self._project_root, d)
            for d in names
        ]
        dirs = [d for d in dirs if os.path.isdir(d)]
        if not dirs:
            print(f"[Pydrud] Hot Reload: no directories to watch ({names})")
            return
        self._watcher = FileWatcher(dirs, self._on_hot_reload)
        self._watcher.start()
        print(f"[Pydrud] Hot Reload watching: {', '.join(dirs)}")

    def disable_hot_reload(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    # ── stateful hot reload ──────────────────────────────────────────────

    def capture_state(self) -> dict:
        """Snapshot every bound State/Store value before a reload."""
        snapshot: dict = {"states": [], "stores": [], "route": None,
                          "params": {}}
        for state in self._bound_states:
            try:
                snapshot["states"].append(
                    (getattr(state, "name", "") or "", state.value))
            except Exception:
                snapshot["states"].append(("", None))
        for store in self._bound_stores:
            try:
                snapshot["stores"].append(
                    dict(store.state) if hasattr(store, "state") else None)
            except Exception:
                snapshot["stores"].append(None)
        if self._router is not None:
            # Store the *pattern* (e.g. "/items/:id"), which is what the
            # rebuilt router will know about, plus the resolved params.
            snapshot["route"] = self._router.current_route
            snapshot["params"] = dict(self._router.current_params)
            snapshot["path"] = self._router.path()
        return snapshot

    def restore_state(self, snapshot: dict) -> None:
        """Push a snapshot back into the reloaded module's objects.

        Hot reload rebuilds module-level ``State`` objects, so values are
        matched positionally (and by name when one was given) — the same
        trade-off Flutter makes, and it keeps a counter or a half-typed form
        intact while you edit the screen around it.
        """
        states = snapshot.get("states") or []
        for index, state in enumerate(self._bound_states):
            if index >= len(states):
                break
            name, value = states[index]
            if name and getattr(state, "name", "") and name != state.name:
                continue
            try:
                state.value = value
            except Exception:
                pass
        stores = snapshot.get("stores") or []
        for index, store in enumerate(self._bound_stores):
            if index >= len(stores) or stores[index] is None:
                continue
            try:
                store.replace(stores[index])
            except AttributeError:
                try:
                    store.state.update(stores[index])
                except Exception:
                    pass
        route = snapshot.get("route")
        if not route or self._router is None:
            return
        try:
            if self._router.has_route(route):
                self._router.replace(route, **(snapshot.get("params") or {}))
            elif snapshot.get("path"):
                # The route pattern was renamed or removed; fall back to
                # resolving the concrete URL path again.
                self._router.go(snapshot["path"])
        except Exception:
            pass

    def preserve_state(self, enabled: bool = True) -> "App":
        """Keep State/Store values across hot reloads (default: on)."""
        self._preserve_state = bool(enabled)
        return self

    def apply_hot_reload(
        self,
        files: list[dict],
        *,
        deleted: list[str] | None = None,
    ) -> dict:
        """Apply Python/PSS edits and PSS deletions, preserve state, and render.

        Python modules are re-executed; stylesheet files are parsed and
        replaced transactionally without being treated as Python source.
        Deleted stylesheet paths are removed from the synchronized overlay.

        Args:
            files: List of dicts with ``{"path": str, "content": str}``.
            deleted: Host-relative paths of deleted PSS files.
        """
        import types
        from pydrud.core.styles.parser import parse_pss

        t0 = time.perf_counter()
        reloaded_modules = []

        # 1. Sync directory on device
        sync_dir = self._get_sync_dir()
        if sync_dir and sync_dir not in sys.path:
            sys.path.insert(0, sync_dir)

        # 2. Validate every changed unit before mutating files or modules.
        compiled_files = []
        deleted_stylesheets: set[str] = set()
        for raw_path in deleted or []:
            clean_path = os.path.normpath(
                str(raw_path).replace("\\", "/")).replace(os.sep, "/")
            if clean_path.startswith("src/"):
                clean_path = clean_path[4:]
            if (clean_path not in ("", ".", "..")
                    and not clean_path.startswith("../")
                    and not os.path.isabs(clean_path)
                    and clean_path.lower().endswith(".pss")):
                deleted_stylesheets.add(clean_path)

        for file in files:
            rel_path = file.get("path", "")
            content = file.get("content", "")
            clean_path = rel_path.replace("\\", "/")
            if clean_path.startswith("src/"):
                clean_path = clean_path[4:]

            if clean_path.lower().endswith(".pss"):
                sheet = parse_pss(content, filename=clean_path)
                errors = [d for d in sheet.diagnostics if d.kind == "error"]
                if errors:
                    first = errors[0]
                    message = (
                        f"{first.filename}:{first.line}:{first.col}: {first.message}"
                    )
                    return {
                        "status": "error",
                        "error_type": "StylesheetError",
                        "message": message,
                        "filename": first.filename,
                        "lineno": first.line,
                        "offset": first.col,
                        "diagnostics": [
                            {"filename": d.filename, "line": d.line, "col": d.col,
                             "message": d.message, "kind": d.kind}
                            for d in errors
                        ],
                    }
                compiled_files.append(("stylesheet", clean_path, content, sheet))
                continue

            try:
                code_obj = compile(content, clean_path, "exec")
                compiled_files.append(("python", clean_path, content, code_obj))
            except SyntaxError as err:
                tb = traceback.format_exc()
                if self._dev_server:
                    self._dev_server.broadcast_error(
                        err, tb=tb, title="Hot Reload Syntax Error",
                        filename=clean_path, lineno=err.lineno
                    )
                return {
                    "status": "error",
                    "error_type": "SyntaxError",
                    "message": getattr(err, "msg", str(err)),
                    "filename": clean_path,
                    "lineno": err.lineno or 1,
                    "offset": err.offset or 1,
                    "text": (err.text or "").strip(),
                    "traceback": tb,
                }
            except Exception as err:
                tb = traceback.format_exc()
                if self._dev_server:
                    self._dev_server.broadcast_error(err, tb=tb, title="Hot Reload Compilation Error")
                return {
                    "status": "error",
                    "error_type": err.__class__.__name__,
                    "message": str(err),
                    "filename": clean_path,
                    "traceback": tb,
                }

        updated_stylesheet_paths = {
            clean_path for kind, clean_path, _content, _compiled in compiled_files
            if kind == "stylesheet"
        }
        # An update in the same batch takes precedence over a stale delete event.
        deleted_stylesheets.difference_update(updated_stylesheet_paths)

        # 3. Snapshot state before modifying modules
        snapshot = self.capture_state() if self._preserve_state else None

        # 4. Write sources and execute Python modules. PSS overlays are
        # installed only after Python execution succeeds, so a failed mixed
        # reload cannot partially switch the active stylesheet.
        updated_stylesheets = []
        for kind, clean_path, content, code_obj in compiled_files:
            if sync_dir:
                full_dest = os.path.join(sync_dir, clean_path)
                try:
                    os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                    with open(full_dest, "w", encoding="utf-8") as fp:
                        fp.write(content)
                except Exception:
                    pass

            if kind == "stylesheet":
                updated_stylesheets.append(code_obj)
                continue

            mod_name = _module_name_from_path(clean_path)
            if not mod_name:
                continue

            try:
                if mod_name in sys.modules:
                    mod = sys.modules[mod_name]
                    mod.__file__ = os.path.join(sync_dir, clean_path) if sync_dir else clean_path
                    exec(code_obj, mod.__dict__)
                else:
                    mod = types.ModuleType(mod_name)
                    mod.__file__ = os.path.join(sync_dir, clean_path) if sync_dir else clean_path
                    mod.__name__ = mod_name
                    sys.modules[mod_name] = mod
                    exec(code_obj, mod.__dict__)
                reloaded_modules.append(mod_name)
            except Exception as exc:
                tb = traceback.format_exc()
                self._report_error(exc)
                return {
                    "status": "error",
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "filename": clean_path,
                    "traceback": tb,
                }

        remote_sources = set(getattr(
            self, "_hot_reload_stylesheet_sources", set()))
        for sheet in updated_stylesheets:
            self._stylesheet_manager.add(sheet)
            remote_sources.add(sheet.filename)
        for clean_path in deleted_stylesheets:
            self._stylesheet_manager.remove_source(clean_path)
            remote_sources.discard(clean_path)
            if sync_dir:
                _unlink_synced_file(sync_dir, clean_path)
        self._hot_reload_stylesheet_sources = remote_sources

        # 5. Re-bind router / target if main module or screens were reloaded
        if "app.main" in sys.modules:
            try:
                main_mod = sys.modules["app.main"]
                if hasattr(main_mod, "main") and callable(main_mod.main):
                    self.target = main_mod.main
            except Exception:
                pass
        elif "main" in sys.modules:
            try:
                main_mod = sys.modules["main"]
                if hasattr(main_mod, "main") and callable(main_mod.main):
                    self.target = main_mod.main
            except Exception:
                pass

        # 6. Restore state
        if snapshot is not None:
            self.restore_state(snapshot)

        # 7. Update UI
        self.update()

        duration_ms = (time.perf_counter() - t0) * 1000
        kept = len(snapshot["states"]) + len(snapshot["stores"]) if snapshot else 0

        return {
            "status": "ok",
            "duration_ms": round(duration_ms, 1),
            "reloaded": reloaded_modules,
            "states_preserved": kept,
        }

    def apply_hot_restart(self, files: list[dict] | None = None) -> dict:
        """Reset all app state, reload user modules, and re-render."""
        from pydrud.core.styles.parser import parse_pss

        t0 = time.perf_counter()
        parsed_stylesheets = []
        for file in files or []:
            rel_path = file.get("path", "")
            if not rel_path.lower().endswith(".pss"):
                continue
            clean_path = rel_path.replace("\\", "/")
            if clean_path.startswith("src/"):
                clean_path = clean_path[4:]
            sheet = parse_pss(file.get("content", ""), filename=clean_path)
            errors = [d for d in sheet.diagnostics if d.kind == "error"]
            if errors:
                first = errors[0]
                return {
                    "status": "error",
                    "error_type": "StylesheetError",
                    "message": (
                        f"{first.filename}:{first.line}:{first.col}: "
                        f"{first.message}"
                    ),
                    "filename": first.filename,
                    "lineno": first.line,
                    "offset": first.col,
                }
            parsed_stylesheets.append(sheet)

        # ``files`` is a full source snapshot from DevRunner. Reconcile the
        # remote stylesheet overlay, including files absent from this batch.
        if files is not None:
            sync_dir = self._get_sync_dir()
            if sync_dir and sync_dir not in sys.path:
                sys.path.insert(0, sync_dir)
            for f in files:
                rel_path = f.get("path", "")
                content = f.get("content", "")
                clean_path = rel_path.replace("\\", "/")
                if clean_path.startswith("src/"):
                    clean_path = clean_path[4:]
                if sync_dir:
                    dest = os.path.join(sync_dir, clean_path)
                    try:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "w", encoding="utf-8") as fp:
                            fp.write(content)
                    except Exception:
                        pass

            current_sources = {sheet.filename for sheet in parsed_stylesheets}
            previous_sources = set(getattr(
                self, "_hot_reload_stylesheet_sources", set()))
            for stale in previous_sources - current_sources:
                self._stylesheet_manager.remove_source(stale)
                if sync_dir:
                    _unlink_synced_file(sync_dir, stale)
            for sheet in parsed_stylesheets:
                self._stylesheet_manager.add(sheet)
            self._hot_reload_stylesheet_sources = current_sources

        # Reset router
        if self._router is not None:
            self._router.reset()

        # Clear event dispatcher and cached tree
        self._event_dispatcher.unregister_all()
        self._current_tree = None
        self._desired_tree = None
        self._snapshot = None
        self._confirmed_revision = 0
        self._desired_revision = 0
        self._inflight.clear()
        self._inflight_trees.clear()
        self._outbox.clear()
        self._outbox_final_tree = None

        # Re-import user modules (parents before children)
        user_modules = [m for m in list(sys.modules.keys()) if m.startswith("app.") or m == "app" or m == "main"]
        user_modules.sort(key=lambda x: (x.count("."), len(x)))
        for mod_name in user_modules:
            if mod_name in sys.modules and sys.modules[mod_name] is not None:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception:
                    pass

        if "app.main" in sys.modules:
            main_mod = sys.modules["app.main"]
            if hasattr(main_mod, "main"):
                self.target = main_mod.main

        # Render fresh
        self.render()

        duration_ms = (time.perf_counter() - t0) * 1000
        return {
            "status": "ok",
            "duration_ms": round(duration_ms, 1),
            "restarted": True,
        }

    def _get_sync_dir(self) -> str:
        """Get or create the local hot reload synchronization directory."""
        import tempfile
        candidates = [
            os.path.join(os.path.expanduser("~"), ".pydrud_sync"),
            os.path.join(tempfile.gettempdir(), ".pydrud_sync"),
            os.path.join(os.getcwd(), ".pydrud_sync"),
        ]
        for c in candidates:
            try:
                os.makedirs(c, exist_ok=True)
                return c
            except Exception:
                continue
        return tempfile.gettempdir()

    def _on_hot_reload(self, filepath: str) -> None:
        """Called by the file watcher when a source file changes."""
        # Watchdog invokes callbacks on its own thread. Once a renderer is
        # attached, serialize module replacement and rebuilding with native
        # events on the normal UI actor.
        if (self._ui_thread_id is not None
                and self._ui_thread_id != threading.get_ident()):
            self.run_on_ui(self._on_hot_reload, filepath)
            return

        # Stylesheet changes are parsed and reapplied without re-importing any
        # Python modules. The manager keeps its last valid sheet if this edit
        # contains a syntax error.
        if filepath.lower().endswith(".pss"):
            try:
                self._stylesheet_manager.refresh()
                self.update()
                print(f"[Pydrud] PSS Reload: {os.path.basename(filepath)}")
                for diagnostic in self._stylesheet_manager.diagnostics:
                    if diagnostic.kind == "error":
                        print(
                            f"[Pydrud] {diagnostic.filename}:{diagnostic.line}:"
                            f"{diagnostic.col}: {diagnostic.message}"
                        )
            except Exception as exc:
                print(f"[Pydrud] PSS reload error for {filepath}: {exc}")
                traceback.print_exc()
                print("[Pydrud] Keeping the last good preview; waiting for the next edit.")
            return

        snapshot = self.capture_state() if self._preserve_state else None
        try:
            # Validate the edited unit before mutating any loaded module. A
            # syntax error must leave the last good preview tree and handlers
            # in place while the developer fixes the file.
            if filepath.endswith(".py") and os.path.isfile(filepath):
                with open(filepath, "r", encoding="utf-8") as source_file:
                    source = source_file.read()
                compile(source, filepath, "exec")

            mod_name = _module_name_for(filepath, self._project_root)
            reloaded: dict[str, Any] = {}

            # Reload leaf modules before package re-exports, and the entry
            # module last, so a rebuilt router captures the newest screens.
            user_modules = _find_user_modules(self._project_root)
            if mod_name and mod_name not in user_modules:
                user_modules.append(mod_name)
            user_modules.sort(key=lambda name: (
                name in {"app.main", "main"}, -name.count("."), name,
            ))

            reload_failed = False
            for name in user_modules:
                if name in sys.modules:
                    try:
                        reloaded[name] = importlib.reload(sys.modules[name])
                    except Exception as err:
                        print(f"[Pydrud] Failed to reload module {name}: {err}")
                        traceback.print_exc()
                        reload_failed = True
                        break

            if (not reload_failed and mod_name and mod_name in sys.modules
                    and mod_name not in reloaded):
                try:
                    reloaded[mod_name] = importlib.reload(sys.modules[mod_name])
                except Exception as err:
                    print(f"[Pydrud] Failed to reload module {mod_name}: {err}")
                    traceback.print_exc()
                    reload_failed = True

            if reload_failed:
                print("[Pydrud] Keeping the last good preview; waiting for the next edit.")
                return

            # Re-bind the target if it came from a reloaded module.
            target_name = getattr(self.target, "__name__", None)
            target_mod = getattr(self.target, "__module__", None)
            if target_mod in reloaded:
                new_target = getattr(reloaded[target_mod], target_name, None)
                if callable(new_target):
                    self.target = new_target
            elif "app.main" in reloaded:
                new_main = getattr(reloaded["app.main"], "main", None)
                if callable(new_main) and (self.target is None or target_name == "main"):
                    self.target = new_main
            elif "main" in reloaded:
                new_main = getattr(reloaded["main"], "main", None)
                if callable(new_main) and (self.target is None or target_name == "main"):
                    self.target = new_main

            # Generated projects keep the router and app binding in
            # app.runtime. Reloading that module creates a new router, so
            # attach it before restoring the previous route.
            runtime_mod = reloaded.get("app.runtime") or sys.modules.get("app.runtime")
            main_mod = reloaded.get("app.main") or sys.modules.get("app.main")
            new_router = getattr(main_mod, "router", None)
            if new_router is None and runtime_mod is not None:
                new_router = getattr(runtime_mod, "router", None)
            if new_router is not None and new_router is not self._router:
                self.attach_router(new_router)
            bind = getattr(runtime_mod, "bind", None) if runtime_mod else None
            if callable(bind):
                bind(self)

            if snapshot is not None:
                self.restore_state(snapshot)
            kept = len(snapshot["states"]) + len(snapshot["stores"]) \
                if snapshot else 0
            print(f"[Pydrud] Hot Reload: {os.path.basename(filepath)}"
                  + (f" (kept {kept} state object(s))" if kept else ""))
            self.update()
        except Exception as exc:
            print(f"[Pydrud] Hot Reload error for {filepath}: {exc}")
            traceback.print_exc()
            print("[Pydrud] Keeping the last good preview; waiting for the next edit.")

    def hot_restart(self) -> None:
        """Reset all app state and re-render from scratch."""
        if self._router is not None:
            self._router.reset()

        self._event_dispatcher.unregister_all()
        self._current_tree = None

        for mod_name in _find_user_modules(self._project_root):
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception as exc:
                    print(f"[Pydrud] Hot Restart reload error {mod_name}: {exc}")

        self.render()