# Contributing to Pydrud

## Setting up

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Before you open a PR

```bash
.venv/bin/python -m pytest -q        # the whole suite, no emulator needed
.venv/bin/python tools/check_java.py # parse + symbol-check every Java template
.venv/bin/pip install ruff           # once; it is not part of the dev extra
.venv/bin/ruff check --select F,E9 pydrud tools tests   # exactly what CI lints
```

The lint job only enforces errors and undefined names (`F`, `E9`), so use
that selection: ruff's default rule set is much wider and reports a large
backlog that CI does not.

A new project must also be green out of the box:

```bash
cd /tmp && pydrud init smoke --org com.example && cd smoke && pytest -q
```

## Where things go

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short: runtime code in
`pydrud/runtime/`, platform-neutral machinery (including PSS and protocol) in
`pydrud/core/`, platform adapters in `pydrud/platforms/`, widgets in
`pydrud/widgets/`, service APIs in `pydrud/services/`, CLI in
`pydrud/commands/`, and generated Android templates in
`pydrud/android/templates/` (Chaquopy only).

## House rules

* **Both sides or neither.** A new native command needs the Python API, the
  Java handler, the permission wiring *and* a test in
  `tests/test_native_coverage.py`. A command that can fail must answer the
  request on every path — a `Result` that never resolves is a hang.
* **Keep the public namespace stable.** Move modules if it makes the tree
  clearer, but leave a deprecation shim and say in the docstring which
  release removes it.
* **Tests describe behaviour, not implementation.** Drive the app through
  `AppTester` by key and visible text where you can.
* **Templates are code.** Changes under `pydrud/android/templates/android/`
  must pass `tools/check_java.py`; changes under `.../python/` must leave
  `pydrud init` + `pytest` green.
* **Pydash and Chaquopy packaging are different.** Only the opt-in
  Chaquopy scaffold vendors the runtime into `src/pydrud/`; the default
  Pydash scaffold runs the installed package on the host. For the APK, CLI
  code, terminal UI and templates (`BUNDLE_EXCLUDES` re-exported by
  `pydrud.commands.project`) stay out, and the bundle must import and render
  with only generated `src/` on `sys.path`. Android adapters needed in the
  APK belong under `pydrud/platforms/android/`; do not re-bundle the CLI to
  reach a helper.
* **Line endings are LF.** `.gitattributes` enforces it; on Windows,
  `git config core.autocrlf` should not override it, or every source file
  gains a byte per line and the APK size budget drifts.
* **Version numbers are release-manager owned.** Do not invent `2.0.2`,
  `2.5.0`, `3.0.0` or any other SDK version in a feature PR. The v2 line
  advances deliberately (`2.0.1`, `2.0.2`, `2.1.0`, …) only when the
  maintainer/release issue says so. No v3 naming, protocol reset or breaking
  version jump belongs in routine contributions.
* **If a PR is explicitly part of a release bump, update every versioned
  surface together:** `pydrud/__init__.py`, `pydrud/compatibility.py`,
  `pyproject.toml`, generated-template defaults, `README.md` examples and
  `CHANGELOG.md`. Never bump one file to silence a test.
* **Update `CHANGELOG.md`** in the same commit for every user-visible change,
  even when the SDK version itself is not changing.
