"""Discovery and reload management for project PSS stylesheets.

This module only deals with paths, text, and the neutral PSS syntax tree; it
has no renderer or platform dependencies. A stylesheet edit is transactional:
a file with syntax errors contributes diagnostics but its most recent valid
version remains active.
"""

from __future__ import annotations

import os
from os import PathLike
from typing import Iterable

from pydrud.core.styles.parser import Diagnostic, StyleSheet, parse_pss


_IGNORED_DIRECTORIES = {
    "__pycache__", ".git", ".venv", "venv", "build", "dist", ".idea",
}


class StyleSheetManager:
    """Load, combine, and reload PSS sources for a project.

    By default, every ``*.pss`` file under ``<project_root>/src`` is loaded
    in deterministic path order. Additional paths can be passed to the
    constructor or registered with :meth:`add`. In-memory ``StyleSheet``
    objects are useful to renderer integrations that receive source over a
    development channel rather than from the original project filesystem.
    """

    def __init__(
        self,
        project_root: str | PathLike[str],
        *,
        search_dirs: Iterable[str | PathLike[str]] = ("src",),
        stylesheets=None,
    ) -> None:
        self.project_root = os.path.abspath(os.fspath(project_root))
        self.search_dirs: list[str] = []
        self._explicit_paths: set[str] = set()
        self._loaded: dict[str, StyleSheet] = {}
        self._contents: dict[str, str] = {}
        self._file_errors: dict[str, list[Diagnostic]] = {}
        self._memory: dict[str, StyleSheet] = {}
        self._memory_seq = 0
        self._diagnostics: list[Diagnostic] = []
        self._stylesheet = StyleSheet(filename="<project>")

        for directory in search_dirs:
            self.add_search_directory(directory)
        if stylesheets is not None:
            if isinstance(stylesheets, (str, os.PathLike, StyleSheet)):
                specs = [stylesheets]
            else:
                specs = list(stylesheets)
            for stylesheet in specs:
                self.add(stylesheet)

    @property
    def stylesheet(self) -> StyleSheet:
        """The combined last-known-good stylesheet tree."""
        return self._stylesheet

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """Current parser and file diagnostics, in deterministic order."""
        return list(self._diagnostics)

    def add_search_directory(self, directory: str | PathLike[str]) -> None:
        path = os.fspath(directory)
        if not os.path.isabs(path):
            path = os.path.join(self.project_root, path)
        absolute = os.path.abspath(path)
        if absolute not in self.search_dirs:
            self.search_dirs.append(absolute)

    def add(self, stylesheet: str | PathLike[str] | StyleSheet) -> None:
        """Register a path or in-memory parsed sheet; refresh occurs on build."""
        if isinstance(stylesheet, StyleSheet):
            self._memory_seq += 1
            name = stylesheet.filename or f"<memory:{self._memory_seq:04d}>"
            self._memory[name] = stylesheet
            return
        path = os.fspath(stylesheet)
        if not os.path.isabs(path):
            path = os.path.join(self.project_root, path)
        self._explicit_paths.add(os.path.abspath(path))

    def add_source(self, source: str, *, filename: str = "<memory>") -> StyleSheet:
        """Parse and register PSS text, replacing a prior source of that name."""
        sheet = parse_pss(source, filename=filename)
        self._memory[filename] = sheet
        self._stylesheet = self._combine()
        return sheet

    def remove_source(self, filename: str | PathLike[str]) -> bool:
        """Remove a registered in-memory source and return whether it existed."""
        name = os.fspath(filename)
        if name not in self._memory:
            return False
        self._memory.pop(name)
        self._stylesheet = self._combine()
        return True

    def refresh(self) -> StyleSheet:
        """Rescan sources and atomically replace valid changed files."""
        paths = self._discover_paths()
        present = set(paths)

        # A deleted stylesheet must stop contributing declarations. Missing
        # explicit paths are retained as diagnostics, but their old rules are
        # removed just as they are for a deleted auto-discovered file.
        for stale in set(self._loaded) - present:
            self._loaded.pop(stale, None)
            self._contents.pop(stale, None)
            self._file_errors.pop(stale, None)

        for path in paths:
            if not os.path.isfile(path):
                self._loaded.pop(path, None)
                self._contents.pop(path, None)
                self._file_errors[path] = [Diagnostic(
                    filename=self._display_path(path),
                    line=1,
                    col=1,
                    message="Stylesheet file does not exist",
                )]
                continue
            try:
                with open(path, "r", encoding="utf-8") as source_file:
                    content = source_file.read()
            except (OSError, UnicodeError) as exc:
                self._file_errors[path] = [Diagnostic(
                    filename=self._display_path(path),
                    line=1,
                    col=1,
                    message=f"Could not read stylesheet: {exc}",
                )]
                continue

            if self._contents.get(path) == content:
                continue
            sheet = parse_pss(content, filename=self._display_path(path))
            errors = [d for d in sheet.diagnostics if d.kind == "error"]
            self._contents[path] = content
            if errors:
                # Keep the previous valid version if there is one. A new
                # invalid file contributes no partial set of rules.
                self._file_errors[path] = errors
                continue
            self._loaded[path] = sheet
            self._file_errors.pop(path, None)

        self._stylesheet = self._combine()
        return self._stylesheet

    def _discover_paths(self) -> list[str]:
        paths = set(self._explicit_paths)
        for directory in self.search_dirs:
            if os.path.isfile(directory) and directory.endswith(".pss"):
                paths.add(os.path.abspath(directory))
                continue
            if not os.path.isdir(directory):
                continue
            for root, dirs, files in os.walk(directory):
                dirs[:] = sorted(
                    name for name in dirs if name not in _IGNORED_DIRECTORIES
                )
                for filename in files:
                    if filename.endswith(".pss"):
                        paths.add(os.path.abspath(os.path.join(root, filename)))
        return sorted(paths)

    def _display_path(self, path: str) -> str:
        try:
            relative = os.path.relpath(path, self.project_root)
        except ValueError:  # pragma: no cover - different Windows drives
            return path
        return relative if not relative.startswith("..") else path

    def _combine(self) -> StyleSheet:
        rules = []
        diagnostics: list[Diagnostic] = []
        variables: dict[str, str] = {}
        keyframes: dict = {}
        for path in sorted(self._loaded):
            sheet = self._loaded[path]
            rules.extend(sheet.rules)
            variables.update(sheet.variables)
            keyframes.update(sheet.keyframes)
            diagnostics.extend(d for d in sheet.diagnostics if d.kind == "warning")
        # In-memory overlays are ordered after disk files so development
        # payloads deterministically take precedence over stale device copies.
        for name in sorted(self._memory):
            sheet = self._memory[name]
            if any(d.kind == "error" for d in sheet.diagnostics):
                diagnostics.extend(sheet.diagnostics)
                continue
            rules.extend(sheet.rules)
            variables.update(sheet.variables)
            keyframes.update(sheet.keyframes)
            diagnostics.extend(sheet.diagnostics)
        for path in sorted(self._file_errors):
            diagnostics.extend(self._file_errors[path])
        self._diagnostics = diagnostics
        return StyleSheet(
            rules=rules,
            diagnostics=diagnostics,
            filename="<project>",
            variables=variables,
            keyframes=keyframes,
        )
