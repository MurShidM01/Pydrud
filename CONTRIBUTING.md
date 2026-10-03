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
.venv/bin/ruff check pydrud tests
```

A new project must also be green out of the box:

```bash
cd /tmp && pydrud init smoke --org com.example && cd smoke && pytest -q
```

## Where things go

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short: runtime code in
`pydrud/runtime/`, machinery in `pydrud/core/`, widgets in
`pydrud/widgets/`, device APIs in `pydrud/services/`, CLI in
`pydrud/commands/`, everything that ends up in a generated app in
`pydrud/android/templates/`.

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
* **Nothing build-time ships in the APK.** `pydrud init` vendors the runtime
  into `src/pydrud/`; the CLI, its terminal UI and the templates
  (`BUNDLE_EXCLUDES` in `pydrud/commands/project.py`) stay out, and the
  bundle has to import and render with only `src/` on `sys.path`. If a
  runtime module needs a helper from `pydrud/utils/`, move the helper —
  do not re-bundle the CLI.
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
