# Contributing to Pydrud

## Setting up

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Before you open a PR

CI runs five jobs on Python 3.13 — the single supported interpreter, pinned
as `PYTHON_VERSION` in `.github/workflows/ci.yml`. Every one of them is a
command you can run locally:

```bash
.venv/bin/python -m pytest -ra -q     # the whole suite, no emulator needed
.venv/bin/python tools/check_java.py  # parse + symbol-check every Java template
.venv/bin/python tools/smoke.py       # drive the installed CLI end to end
.venv/bin/pip install ruff            # once; it is not part of the dev extra
.venv/bin/ruff check .                # reads [tool.ruff] from pyproject.toml
```

The lint job only enforces errors and undefined names (`F`, `E9`) — that
selection lives in `pyproject.toml`, so plain `ruff check .` matches CI
exactly. Ruff's default rule set is much wider and reports a large backlog
that CI does not.

`tools/check_java.py` renders each template once per optional feature
(`camera` bundled and not), so a template that only breaks in one variant
still fails here instead of two minutes into a Gradle build.

The packaging job needs a build first, and is only worth running when you
touch `[tool.setuptools]`, package data or the templates:

```bash
.venv/bin/pip install build
.venv/bin/python -m build && .venv/bin/python tools/check_wheel.py
```

It proves the wheel still ships `pydrud/android/templates/**` and that
`pydrud create` works from an installed wheel — something the test suite
cannot catch, because it imports from the source tree.

A new project must also be green out of the box:

```bash
cd /tmp && pydrud create smoke --org com.example && cd smoke && pytest -q
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
  must pass `tools/check_java.py` in every feature variant; changes under
  `.../python/` must leave `pydrud create` + `pytest` green.
* **Heavy native dependencies are opt-in.** CameraX and ML Kit are gated
  behind the `camera:` setting for a reason: they add ~10 MB to every APK.
  A new library that ships native code needs the same treatment — a YAML
  switch, a graceful path when it is off, and a test for both variants.
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
