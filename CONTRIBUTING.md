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
* **Update `CHANGELOG.md`** in the same commit, and bump the version in
  `pydrud/__init__.py`, `pydrud/compatibility.py` and `pyproject.toml`
  together — a test checks they agree.
