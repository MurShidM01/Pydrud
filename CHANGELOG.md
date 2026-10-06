# Changelog

All notable changes to Pydrud are documented here.

## [2.0.3] — 2026-10-06

The production-readiness release. Every finding in the 2.0.2 adversarial QA
report (`PYDRUD.md`) is addressed: the seven confirmed bugs (PB-001…PB-007),
the developer-experience traps (DX-001…DX-006), the doc/API mismatches
(DOC-001…DOC-004) and the intermittent race (IC-001), plus the UI/UX,
unlimited-widget and unlimited-icon work.

### Fixed — silent render failures
* **PB-002 — an oversized frame no longer wedges rendering forever.**
  `App._send_desired_tree` now encodes the transaction *before* registering
  it as in-flight, rolls the in-flight state back when encoding fails, and
  raises a loud, recoverable error instead of leaving a phantom transaction
  that defers every later render. Oversized snapshots are automatically
  split (windowing) so a large list cannot kill the UI.
* **PB-001 — deep widget trees no longer raise `RecursionError`.**
  `Widget.to_dict`, `walk`, `clone`, `find_by_key`, `validate_tree_keys`,
  `assign_stable_keys` and the whole `TreeDiff` engine now use explicit
  stacks instead of recursion, and a documented maximum depth raises a
  structured `PydrudError` instead of a bare `RecursionError`.
* **PB-003 — `Canvas` repaints on the device.** The native `updateProps`
  path now applies changed `ops` (and `units`) through
  `AdvancedViews.updateCanvas`, so a canvas/game board animates instead of
  freezing after the first frame.
* **PB-004 — `Canvas(on_draw=…)` over shared state now diffs correctly.**
  Each canvas caches its serialised ops at build time, so the diff compares
  two snapshots instead of re-running the old painter against the current
  state and emitting zero patches.
* **PB-006 — `Positioned(left/top/right/bottom)` moves on update.** The
  native style applier now re-applies absolute offsets and gravity, so
  absolute positioning is no longer create-only.
* **PB-005 — unknown icon names are loud, and the vocabulary is complete.**
  The renderer logs an unknown icon once per name under the stable `Pydrud`
  tag (never silently drawing “?”), the Python side gained
  `pydrud.icons.available()` / `has()` / `suggest()` and an analyzer rule,
  and the Material names developers actually copy (`play_arrow`,
  `rocket_launch`, `emoji_events`, `sports_esports`, `bolt`, `speed`,
  `replay`, …) are aliased to renderer-backed icons. The catalogue is now
  **176 paths + 178 aliases**, and `Icon.svg("M…")` renders arbitrary 24×24
  path data so the set is effectively unlimited.
* **PB-007 — layout model parity.** `Row`/`Column` gained
  `main_axis_size`/`cross_axis_size` (`"min"`/`"max"`, Flutter-style) so a
  "row of columns" hugs its content instead of collapsing; the renderer
  already downgrades an unweighted fill-width child inside a horizontal row
  to `WRAP_CONTENT`; and `pydrud analyze` now warns when two unweighted
  children are pinned to fill the main axis. The fill-width default is
  documented with the three idiomatic recipes.

### Added — theming, widgets and icons
* **Runtime theming.** `Theme.scope()` (per-subtree overrides),
  `ThemeExtension` (custom tokens), a named `TextTheme`, and verified
  runtime light/dark switching via `page.set_theme_mode()`.
* **`pydrud.components`** — a pure-Python library of composite widgets
  (stat cards, toolbars, form rows, empty states) so the catalogue grows
  without touching the framework core, plus `NativeView` as an escape hatch
  for arbitrary Android views.
* **`pydrud.icons`** — `available()` / `has()` / `closest()` so apps and
  tests can reason about the shipped icon set.
* Missing Material-3 components: date/time pickers, a persistent bottom
  sheet, `RangeSlider`, a rich `PopupMenu`, `Carousel`/`PageView`,
  `LayoutBuilder`-style breakpoints and `ExpansionPanelList`.

### Changed — developer experience
* **DX-001 / IC-001** — `AppTester.settle()` now awaits render/revision
  convergence, so State-driven navigation and renders are deterministic in
  tests without hand-rolled polling.
* **DX-002** — the analyzer no longer flags an unkeyed child of a keyed
  ancestor inside a loop.
* **DX-004** — framework output uses a stable `Pydrud` log tag.
* **DX-005** — `pydrud analyze` resolves every icon string against the
  shipped set and suggests the closest supported name.
* **DX-006** — dev builds log dropped/unknown native props once per key.
* **DOC-001…DOC-004** — documented the `permissions list` command, the
  `Row`/`Column` fill-width default, the icon vocabulary and the corrected
  Canvas painter contract.

## [Unreleased]

### Added — conditional rendering and canvas painters
* **`Visible` / `Hidden` — conditional rendering by state.** `ShowWhen` only
  ever answered "is the window big enough?", so there was no built-in way to
  show a widget because the *app* is in a particular state. `Visible(child,
  when=…)` (and its inverse `Hidden`) accept a bool, a `State`, a `Computed`,
  a `Selector`, a `ReactiveList` or a callable, re-read on every
  serialisation, and render `otherwise` — or a zero-sized placeholder — when
  false. `ShowWhen` also gained `condition=`, so size and state can be
  required together.
* **`Canvas.on_draw` adapts to the painter's signature.** The framework only
  ever called `on_draw(canvas)`, while the obvious Flutter-shaped
  `def paint(canvas, width, height)` failed at render time. `(canvas)`,
  `(canvas, size)` and `(canvas, width, height)` all work now, and a painter
  that raises is reported, keeps what it drew and leaves the exception on
  `canvas.last_draw_error` instead of taking down the rebuild cycle.
* **Canvas dimensions are available.** `canvas.size` / `.width` / `.height`
  report dp, resolving `"match"` and percentage styles against the live
  `MediaQuery` metrics; `canvas.measure(w, h)` pins exact values when the
  laid-out size is known. Pixel-accurate drawing no longer requires guessing.
* **`AppTester.wait_for()` / `.exists()`.** Lookups now retry for a moment
  before failing, so a tap that triggers navigation, a timer or an async
  handler no longer needs a hand-written sleep to be found.
* **`Timer(..., max_errors=…)`.** A repeating timer still survives a failing
  tick, but identical consecutive failures are collapsed in the log instead
  of printing thousands of lines a minute, `errors` /`consecutive_errors` /
  `last_error` are exposed, and `max_errors` cancels a timer that only ever
  fails.

### Fixed — API gaps found by an adversarial stress test
* **The design-token APIs have the names developers type.** `Elevation` gained
  Material's full `D0`–`D24` dp scale next to its semantic names, `Radius.FULL`
  aliases `PILL`/`CIRCLE`, and the palette gained `AMBER`, `DEEP_ORANGE`,
  `DEEP_PURPLE`, `LIGHT_BLUE`, `LIGHT_GREEN`, `BLUE_GREY`, light/dark greys
  and the American spellings. Lookups are spelling-insensitive
  (`Colors.amber`, `Colors.deepOrange`), every class answers `.names()`, and
  an unknown name now reports the closest matches instead of a bare
  `AttributeError`. `Icons` shares the same machinery, so misspelled icons get
  suggestions too.
* **`Canvas.text(weight="bold")` works.** Weight accepts the CSS/Flutter names
  (`"normal"`, `"medium"`, `"bold"`, …) as well as the renderer's numbers.
* **`column("id", primary_key=True)` no longer reads the name as a type.**
  `column()` accepts a name, a type, or both (`column("score", int)`,
  `column("tags", "list")`, `column(name=…, type_=…)`), infers `int` for
  primary keys and `id`, and rejects a name that contradicts the attribute it
  is assigned to — the attribute is the column name everywhere else in the
  API. `Model`'s docstring now states that the free `id` stays `None` until
  the row is saved.
* **`NavigationItem` and `NavigationDestination` alias `NavItem`**, for code
  ported from Flutter.
* **`ReactiveList(name=…)`** matches `Store`'s API and shows up in `repr()`
  (`Computed(name=…)` too), and `replace_all()` no longer notifies every
  subscriber when the new contents are identical.
* **Concurrent `Store` writes cannot interleave.** `update`, `replace`,
  `mutate`, actions, `undo` and `reset` take a reentrant write lock, so two
  threads running read-modify-write actions can no longer lose an update or
  publish a state nobody computed.
* **The navigation stack is atomic.** `NavigationStack` locks every operation
  and exposes the compound ones as single calls (`pop(keep_root=True)`,
  `collapse_to_root()`), so rapid taps on different threads cannot corrupt
  the stack; `Router.pop()` and `Router.pop_to_root()` use them.
* **`page.set_theme_mode()` repaints immediately** for every mode, including
  `"system"`, instead of waiting for the next unrelated refresh.
* **`pydrud analyze` catches invalid design tokens.** `Colors.purlpe`,
  `Elevation.D44` and friends are reported statically, with suggestions,
  alongside the existing icon check.

### Changed
* **The bundled-runtime size tripwire moves from 600 KB to 640 KB.** The
  budget exists to catch *accidental* bloat (bundling the CLI, templates or
  icons adds megabytes); the runtime features above take the real bundle to
  ~600 KB, so the tripwire keeps roughly the same headroom it had when it was
  set.

### Fixed — CI and drift regressions
* **New widgets are known to the analyzer again.** `FractionallySizedBox`,
  `FittedBox`, `DataTable`, `MetricCard` and `Timeline` are registered in
  `_WIDGET_CLASSES`, so the key-in-loops lint covers them and the registry
  drift test passes. `widthFactor`/`heightFactor` join the valid style keys
  (the renderer reads them).
* **Fresh projects declare their starter permissions.** `pydrud init` now
  renders `capability_permissions` into `AndroidManifest.xml` from the same
  registry `pydrud sync` uses, so a new project declares
  `android.permission.VIBRATE` and `android.permission.POST_NOTIFICATIONS`
  before its first build instead of only after a manual sync.
* **`capabilities add camera` suggests the permissions command again.** The
  expanded capability table made `camera` resolvable as a bundle, which
  silently re-enabled the exact mistake the command guards against. The
  resolver now redirects `camera` to `pydrud permissions add camera` (the
  flow documented by the generated manifest and the README release
  workflow); the `camera` bundle stays registered for
  `capabilities list --all` and the doctor's manifest checks.
* **Icon-pack tests no longer leak into the vector drift check.**
  `Icons.builtins()` separates the constants the framework ships from
  icons registered at runtime via `Icons.load_pack` (`Icons.all()` still
  reports both), the generated-template drift test checks only the shipped
  constants, and the pack test restores the registry afterwards.

### Fixed — runtime hardening batch
* **Legacy Gingerbread-era icons removed.** The ~106-entry
  `android.R.drawable` lookup table in the generated `ViewFactory` (which
  rendered `chevron_right` as a media-rewind button, `qr_code` as a crop
  tool, `sparkle` as a sun and `code` as a wrench) is deleted. Every icon
  now renders through the vector `PydrudIcons` path only — sharp at any
  density and tintable.
* **Managed image pipeline.** Network/asset images no longer spawn a raw
  `Thread` each: they run on a shared 3-thread pool, are cached in a
  heap-aware `LruCache` (scrolling back over a list never re-downloads),
  are downsampled at decode time (`inSampleSize` — a 4K photo can no longer
  OOM the app), and carry a tag-based cancellation token so recycled
  `ImageView`s never show stale bitmaps. `Image(style={"placeholder": …,
  "error_image": …})` assets are honoured and remote bitmaps fade in.
* **Cleartext HTTP works by default.** The generated manifest now includes
  `android:usesCleartextTraffic="true"`, so local dev servers and plain-HTTP
  LAN APIs stop failing with "Cleartext HTTP traffic not permitted" on
  Android 9+. Opt out with `cleartext_traffic: false` in `pydrud.yaml`.
* **Predictive back gesture (Android 13+).** The deprecated
  `onBackPressed()` override is gone; all presses flow through
  `OnBackPressedDispatcher`, restoring swipe-to-go-back animations, and the
  Python-router round trip now falls back to a dispatcher-safe default.
* **ListView virtualization.** A `ListView` with 24+ children (or
  `style={"virtualized": True}`) is backed by a `RecyclerView` with
  view-holder recycling instead of an eager `LinearLayout` — long lists
  scroll without jank or memory spikes. Structural patches
  (insert/delete/move/replace) against virtualized lists are handled
  safely instead of crashing on `RecyclerView.addView`.
* **Versioned HTTP client.** The `User-Agent` is generated from the
  installed package version (`Pydrud/<version> (Android)`) instead of the
  stale hardcoded `Pydrud/1.2`.

### Added — runtime hardening batch
* **TextField IME actions.** `TextField(ime_action="search" | "done" |
  "send" | "go" | "next" | "previous")` sets the keyboard action button;
  pressing it (including SEARCH) fires `on_submit` and dismisses the
  keyboard. `SearchField` defaults to `ime_action="search"`.
* **Tap-outside keyboard dismissal.** Touching anywhere outside a focused
  text field hides the soft keyboard and clears focus — no more hunting
  for the back button.
* **Custom fonts from assets.** Drop `inter.ttf` into `assets/fonts/` and
  use `font_family="inter"`; the native layer resolves and caches
  `.ttf`/`.otf` typefaces from the app assets, falling back to the
  framework typeface when a family is missing.
* **Synchronous permission check.** `page.permissions.is_granted("camera")`
  returns a plain `bool` without ever opening a system prompt — ideal for
  guards; async code can keep using `await page.permissions.check(name)`.

### Changed — runtime hardening batch
* `InfiniteList`'s `virtualized` style prop graduated from the inert ledger
  (`NATIVE_IGNORED_PROPS`) to a natively honoured setting.

### Added
* **Host-driven live preview foundation.** `pydrud dev` now imports and runs
  project Python on the developer machine, binds a configurable LAN preview
  server, watches source files, and prints a QR code plus exact connection URI
  for the future independent Pydash rendering client. This path never builds
  or reinstalls an APK.
* **Stable Preview Protocol v1.** The documented Android-agnostic contract
  defines short-lived bearer-token authentication, project/session identity,
  client and renderer version negotiation, required capabilities, metrics,
  initial snapshots, incremental revisioned patches, ACK/NACK recovery,
  reconnect resynchronization, frame limits, and QR fields.
* Added a transport-neutral `App.serve_transport()` adapter so an authenticated
  accepted renderer socket can reuse Pydrud's existing widget serialization,
  state/event ownership, diffing, revisions and bridge protocol without
  changing the outbound generated-Android bridge used by `pydrud run`.

* **Built-in QR encoder.** `pydrud.core.qr` implements QR symbol generation
  (byte mode, all versions and error-correction levels, Reed-Solomon ECC,
  masking and format/version information) with nothing but the standard
  library, so `pydrud dev` always prints a scannable code.

### Changed
* `qrcode` is no longer a required dependency. `pydrud dev` falls back to the
  bundled encoder when it is absent; install the `qr` extra to keep using the
  third-party encoder. This fixes `ModuleNotFoundError: No module named
  'qrcode'` / "QR support is unavailable" in environments where the optional
  package was missing.
* Host file reloads are serialized on the UI actor while a preview client is
  connected. Generated routers and runtime bindings are refreshed in
  dependency order; a failed reload reports its traceback and keeps the last
  good rendered UI visible.
* Bridge input now applies the same 2 MiB frame limit as the core protocol, and
  NACK recovery snapshots retain their sent-tree bookkeeping so their ACK can
  correctly advance the confirmed snapshot.

## [2.0.2] — Reliable haptics and expanded widget catalogue

### Fixed
* Android 12+ haptics now resolve the default device through
  `VibratorManager`, use hardware-tuned predefined effects for named impacts,
  and apply explicit amplitudes on older devices. Pattern input and durations
  are bounded, and the starter's demo uses a clearly perceptible heavy impact.
* `pydrud run` scopes logcat to the app PID, so unrelated OEM `System.err`
  exceptions (including Transsion push/network services) no longer pollute the
  application's live output.
* A host Python/runtime minor-version mismatch now sets
  `PYDRUD_COMPILE_PYC=false`, avoiding Chaquopy's bytecode warning while
  preserving the supported source-code fallback.
* Labelled `Switch` controls fill their row by default, and the playground's
  dark-mode control is a `SwitchListTile` with left text and a right-aligned
  toggle.

### Added
* Expanded the public catalogue to 130+ widget classes with 40 native-backed
  Flutter-style presets: flex/constraint helpers, typography and image
  presets, list-tile controls, navigation buttons, app states, dashboard
  cards, settings rows and form sections.
* New projects include an `app/components/` package for reusable UI. The old
  `app.ui` module remains as a compatibility re-export.

## [2.0.1] — Starter capability and UI hardening

### Fixed
* **Vibration now works in newly generated starter apps.** `pydrud init`
  enables the `haptics` capability by default, so the generated manifest
  declares `android.permission.VIBRATE`. The Android bridge also replies to
  request/response haptic calls, supports vibration patterns, and reports an
  actionable error when the permission or device vibrator is unavailable
  instead of only logging `Vibrate unavailable (missing permission?)`.
* **The starter permission demo is declared before it is requested.** New
  projects enable the `notifications` capability by default, so
  `page.permissions.request("notifications")` can show Android's runtime
  dialog on Android 13+. Permission requests now fail with a clear message
  when a requested permission is missing from `AndroidManifest.xml`.
* **`page.push.permission()` sends the correct bridge payload.** It now uses
  the same `permissions=["android.permission.POST_NOTIFICATIONS"]` shape as
  `page.permissions.request(...)`.

### Added
* **`pydrud capabilities` CLI.** `pydrud capabilities add/remove/list`
  manages generated feature bundles (`haptics`, `notifications`,
  `foreground_service`, `boot_receiver`, `wake_lock`) in `pydrud.yaml` and
  updates the generated manifest so apps do not need hand edits under
  `android/`.
* **More Python widget presets.** Added `FilledButton`, `TonalButton`,
  `OutlinedButton`, `TextButton`, `ElevatedButton`, `IconButton`,
  `SearchField`, `EmailField`, `PasswordField`, `NumberField`, `PhoneField`,
  `UrlField`, `LinearProgress`, `AssistChip`, `FilterChip`, `InputChip` and
  `SuggestionChip`. They reuse the existing native Android renderers, so they
  are convenience APIs rather than web fallbacks.
* **More icon aliases.** The `Icons` catalogue and native icon resolver now
  cover additional app, commerce, media, security, navigation and developer
  names.

### Changed — the starter app is now the Pydrud Native Playground
* **`pydrud init` generates a focused, single-screen playground** instead of
  the three-destination counter/to-do app. The screen is organised into
  clearly branded cards — a hero header (“Pydrud Native Playground — Native
  Android, powered by Python”), **Native Android** (Toast, Snackbar, dialog,
  vibrate/haptics, clipboard, share sheet, device info and a runtime
  permission request — each one a working, one-tap demo of a real Android
  API), **Components** (TextField with a live greeting, a Switch that
  re-themes the app natively, Checkbox, Slider driving a ProgressBar),
  **State & interaction** (a reactive counter with snackbar undo) and
  **Navigation** (push a details screen; the app-bar arrow, an in-page
  button and the hardware back gesture all pop it). The generated package is
  smaller and simpler — `config.py`, `state.py`, `runtime.py`, `ui.py`,
  `jobs.py` and two screen modules — while keeping the same architecture and
  Java entry points (`app.main.start_app`, `app.main.run_background_job`).
  The layout stays responsive: phones use the full width, tablets centre the
  content at a readable width.

### Fixed
* **Generated apps now get the current branded launcher icon.** `pydrud
  init` copies icons from the package's `android/templates/res/`, which had
  fallen out of sync with the repository's updated `res/` artwork — so new
  projects kept installing with the old icon. Both locations now carry the
  same branded adaptive icon.
* **`pydrud icons` no longer produces a solid-colour tile.** It used to
  force a hard-coded indigo `@color/ic_launcher_background` behind a padded
  foreground. It now writes the same adaptive structure the scaffold uses
  (`ic_launcher_adaptive_back` + `ic_launcher_adaptive_fore`), samples the
  background colour from the edges of your source art when `--background`
  is not given, keeps the art inside the adaptive safe zone, and flattens
  the legacy `ic_launcher.png` onto that background so transparent logos
  never land on a black square. Stale `drawable/splash.xml`,
  `values/ic_launcher_background.xml` and `ic_launcher_foreground.png`
  files from older runs are cleaned up.
* **The splash screen is a customisable screen, not an icon.** `pydrud
  icons` no longer stamps the launcher icon into a splash drawable (the
  `--splash-text` flag is gone), and the generated `themes.xml` now styles
  the Android 12+ system splash: it follows the app theme's background
  colour and hides the centred launcher icon, with a comment showing where
  to customise it.

* **The bundled-runtime size budget failed on Windows checkouts.** With
  `core.autocrlf` on, Git rewrites the ~17 000 lines of vendored runtime with
  CRLF, adding one byte per line: the identical bundle measured 584 KB on
  Linux/macOS and 600.4 KB on Windows, so
  `test_bundled_runtime_is_slim_and_importable` failed there and nowhere
  else. A `.gitattributes` now pins text files to LF in the working tree on
  every platform, and the budget is measured with CRLF counted as one byte so
  the number means the same thing everywhere.

### Changed
* **`pydrud init` no longer ships the CLI's terminal UI inside the APK.**
  `pydrud/utils/` (ANSI colours, banners, tables) and the deprecated
  `pydrud/packages.py` shim — which only aliases the build-time
  `pydrud.commands.packages` and could never import on a device — are
  excluded from the vendored runtime alongside `android/` and `commands/`.
  The bundle drops from 584 KB to 566 KB; `pydrud sync` removes the stale
  directory from existing projects.

### Added
* **The bundle is now tested the way the APK uses it.** `pydrud init`'s
  runtime is imported and the starter app rendered in a subprocess started
  with `-S`, so neither the pip-installed Pydrud nor any third-party package
  can hide a gap in it; a static import scan additionally fails the build if
  anything that ships imports `pydrud.android`, `pydrud.commands`,
  `pydrud.utils` or `pydrud.packages`, including lazily inside a function.

## [2.0.0] — A project you can grow into

Two restructures, one release: the project `pydrud init` gives you, and the
package Pydrud itself is. Nothing about writing an app changes —
`from pydrud import App, Router, Column` is still the only import you need.

### Changed — generated project layout (breaking for the scaffold)

`pydrud init` used to hand you a 702-line `src/app/main.py`. That is a demo,
not a project: the first thing every team did was take it apart. The same
starter app — same widgets, same keys, same behaviour — now arrives as:

```
src/app/
├── main.py        route registration + the start-up entry point (< 60 lines)
├── config.py      routes, navigation destinations, design presets
├── state.py       the State objects every screen shares
├── runtime.py     the router and the live App handle (`refresh()`)
├── jobs.py        background work run by WorkManager
├── ui/            shell.py (the page shell) + components.py
└── screens/       home.py, settings.py, gallery.py — one per destination
```

Existing projects are untouched: `pydrud sync` only regenerates `android/`,
never your Python. To adopt the layout, scaffold a new project and move your
screens across; `from app.runtime import refresh, router` replaces the
module-level globals that used to live in `main.py`.

### Changed — framework package layout (shimmed, not broken)

The top level of the package now names layers instead of files:

| Was | Is |
| --- | --- |
| `pydrud/main.py` (1 602 lines) | `pydrud/runtime/app.py` |
| `pydrud/navigation.py` | `pydrud/runtime/navigation.py` |
| `pydrud/packages.py` | `pydrud/commands/packages.py` (it is build tooling) |

The old paths still import, with a `DeprecationWarning` naming the
replacement; they are removed in 3.0. `pydrud/android/` is now a real
package rather than an implicit namespace one.

### Added
* **One terminal UI across the entire CLI.** `init`, `sync`, `build`, `clean`,
  `doctor`, `analyze`, package/permission commands, release tooling, devices,
  docs and inspector now use the same responsive banners, status badges,
  sections, tables, summaries and next-step prompts as Hot Reload. Root and
  per-command help are branded too, while `analyze --json` remains clean
  machine-readable output.
* **`README.md` in every new project** — how to run it, what each directory
  is for, and how to add a screen.
* **`tests/test_app.py` in every new project** — three `AppTester` tests
  that pass from the first commit, so a project starts out testable.
* **`App.current()`** — the most recently created app, so screen code can
  reach the running app without a module-level global.
* **`docs/ARCHITECTURE.md`** — the layers, the render/ack contract, the
  threading rule and the native-service convention.
* **`CONTRIBUTING.md`** — how to set up, what to run before a PR, and the
  rules a native command has to satisfy.
* **`tests/test_package_layout.py`, `tests/test_scaffold_layout.py`,
  `tests/test_tester_settle.py`** — the layout, the shims and the harness
  are now pinned by tests (733 tests, 2 217 subtests in total).

### Fixed
* **`pydrud sync` ignored Android identity and toolchain edits.** It used the
  stale package/activity discovered in generated Java and refreshed only Java
  plus theme resources. `pydrud.yaml` is now the Android source of truth:
  sync migrates package/name changes and regenerates the manifest, Gradle
  files/wrapper, SDK/NDK settings, version metadata, ABIs, assets, permissions,
  deep links and generated Python metadata. TOML dependencies/theme settings
  and `src/app/` remain untouched.
* **Permission CLI edits disappeared after sync.** `pydrud permissions` now
  records its changes in the YAML manifest as well as applying them
  immediately to `AndroidManifest.xml`.
* **`AppTester.settle()` returned too early.** It only checked that the
  event queue was empty — which is also true while an event is still in
  flight on the socket — so a `tap()` could silently do nothing and the
  next assertion would read stale UI. It now waits for the app to handle
  everything the device has sent *and* for the resulting render to be
  acknowledged. Taps, typing and toggles are deterministic.
* **`FakeDevice` text matching missed list tiles.** `shows()` now sees
  `title`, `subtitle`, `message` and `placeholder` text, not just
  `value`/`text`/`label`/`hint`.
* **README** no longer advertises unimplemented native commands; they all
  shipped in 1.6.0.

## [1.6.0] — Every native command implemented

The Python API always exposed Bluetooth, NFC, camera extras, speech and
friends, but 24 of those commands had no handler on the Android side and
answered `unsupported native command`. **`UNIMPLEMENTED_COMMANDS` is now
empty.**

### Added
* **Bluetooth Low Energy** (`page.bluetooth`) — adapter state, enabling,
  scanning with service filters, GATT connect/disconnect, service discovery,
  characteristic read/write and notifications. Discovered peripherals and
  notification payloads arrive as `bluetooth` events (`App.on_bluetooth`).
  Android 12 `BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT` and the older
  location-based permission model are both handled, and every failure path
  answers the request instead of leaving it pending.
* **NFC** (`page.nfc`) — availability, NDEF read and write (text, URI and
  MIME records) through reader mode, with a timeout and `cancel()`.
  Read-only, too-small and non-NDEF tags each report a clear error.
* **Camera extras** (`page.camera`) — `flash()` (torch), `zoom()` clamped to
  what the lens supports, `record()`/`stop_record()` to MP4 via CameraX
  video, and continuous barcode/QR `scan()` powered by ML Kit, which emits
  `scan` events per code. Recordings finalise with a `recording` event
  (`App.on_recording`).
* **Speech recognition** (`page.speech.listen()`) — the system recogniser,
  with locale and prompt, resolving with the best transcript.
* **Colour picker** (`page.dialog.color()`) — an RGB dialog with a live
  swatch, returning `#AARRGGBB`.
* **Continuous location** (`page.location.watch()`) — GPS/network updates at
  an interval and distance filter, delivered as `location` events
  (`App.on_location`), stopped with `stop_watch()`.
* **Notification channels** (`page.notifications.channel()`) — importance,
  description, vibration, lights and badge, a no-op below Android 8.
* New generated classes `CaptureServices.java` and
  `ConnectivityServices.java`, dispatched from `BridgeService` and disposed
  with the Activity. New Gradle dependencies: `androidx.camera:camera-video`
  and `com.google.mlkit:barcode-scanning`.
* New permission aliases: `bluetooth_scan`, `bluetooth_advertise`,
  `bluetooth_legacy`, `bluetooth_admin`, `background_location`, `activity`.

Existing apps pick all of this up with `pydrud sync`.

## [1.5.2] — Build-time correctness

A full audit of the generated Android layer and the Python↔Java contract.
The theme is *fail fast and loudly*: every failure mode below used to be a
silent hang, a no-op, or a two-minute Gradle error.

### Fixed
* **Keyed children could render in the wrong order.** `TreeDiff` computed
  `move` indices against the *old* child list, but the native applier mutates
  the parent as it walks the patch list, so a surviving child whose index was
  shifted by an earlier insert/delete was never moved. The diff now tracks the
  evolving order, and `tests/test_diff_applier.py` replays every patch through
  a model of `ViewFactory.applyPatch` (named regressions plus a 2000-tree fuzz).
* **`cache.set(key, value, ttl=0)` cached forever.** A zero ttl was treated as
  "no expiry"; it now means "already expired". Expiry comparisons are
  inclusive, and the index is read defensively so a cache written by an older
  version can no longer raise `KeyError`.
* **The newest installed NDK is now picked numerically.** `sorted()` on the
  SDK's `ndk/` directory ranked `9.0.x` above `28.2.x`; the builder also had a
  hardcoded fallback that disagreed with the pinned `COMPATIBILITY.ndk_version`
  and is gone.
* **`pydrud.yaml` parsing no longer reads nested keys.** Indented keys and list
  items could shadow a real top-level setting, and inline `# comments` ended up
  inside values. Unreadable files now warn instead of failing silently.
* **`Store.mutate()` honours deletions.** A draft edited in place now replaces
  the state, so `draft.pop("key")` actually removes the key.
* **`Computed` is lazy again.** Invalidating a source recomputed the value
  immediately even with no subscribers.
* **Selector leak.** `Store.select()` kept every selector forever;
  `Selector.dispose()` (and `Store.unselect()`) detach one.
* **Animations ran for the wrong length of time.** `AnimationController`
  re-derived its clock from the *eased* value each frame, so the curve was
  applied repeatedly: `ease_in`/`bounce` animations never reached the end and
  `ease_out` finished in 8 frames instead of 60. The controller now keeps a
  linear clock and eases once per frame, so every curve takes exactly
  `duration`. `animate_to()` also no longer rewrites `upper`, which used to
  shrink the controller's range permanently.
* **`pydrud analyze` reported nested-loop findings twice** (once per
  enclosing loop). Findings are now de-duplicated and sorted by line, and a
  test pins the analyzer's widget list against the exported widgets.
* **Hot reload missed most saves.** The watchdog handler only listened for
  `on_modified`, but vim/PyCharm (and most editors) save atomically by
  renaming a temp file — those arrived as `on_moved` and were dropped, as were
  newly created modules. The polling fallback ignored new files too.
* **`Responsive.configure()` no longer half-applies a rejected call.**
* **`pydrud run` no longer fails to compile.** `ViewFactory` called
  `AdvancedViews.setEventDispatcher()` and `ViewFactory.isReusableType()`,
  neither of which existed. Added the late-binding setter (matching
  `MaterialViews`/`GestureBinder`) and the view-reuse predicate (`Canvas`,
  `MapView`, `CameraPreview`, `ReorderableList`, `InfiniteList`).
* **Unknown native commands no longer hang the app.** `BridgeService` now
  answers any command no handler claimed with a failed `result`, so a
  pending `Result` settles with `unsupported native command: …` instead of
  never resolving.
* **Three native events had no Python handler.** `push_token`,
  `audio_complete` and `protocol_error` were emitted by the Java layer and
  dropped. Added `App.on_push_token()`, `App.on_audio_complete()`, and
  protocol errors are now routed to the app's error handler.
* Unused imports, empty f-strings, exception chaining (`raise … from`) and
  other lint findings across `pydrud/` and `tools/`.

### Added
* **`pydrud.android.javacheck`** — cross-class symbol resolution for the
  generated Java: unqualified calls, calls on fields/locals of Pydrud types,
  static calls and constructor arities, with no false positives on framework
  types or chained calls.
* **Build pre-flight.** `pydrud run`/`pydrud build` resolve the project's own
  `*.java` before invoking Gradle and abort in under a second with the exact
  missing symbol, suggesting `pydrud sync`.
* **Staleness warning.** Projects now record `pydrud_version:` in
  `pydrud.yaml`; building with a different installed version warns and points
  at `pydrud sync`, which re-stamps it.
* **`UNIMPLEMENTED_COMMANDS`** documents the 24 Python service calls (BLE,
  NFC, camera extras, speech, colour picker, location watch, notification
  channels) the Android runtime does not implement yet; their docstrings say
  so, and a test keeps the list in sync with the Java sources.
* New test suites: `test_java_symbols`, `test_native_coverage`,
  `test_native_events`, `test_build_preflight` — covering symbol resolution,
  command/event/widget parity between Python and Java, and the build guards.

* **Awkward project names generated invalid Java.** `pydrud init 2cool`
  wrote `public class 2coolActivity`; names are now normalised to real Java
  and Python identifiers (`App2cool`, `app_2cool`), including non-ASCII and
  punctuation-only names.
* **The recorded Gradle version was wrong.** `pydrud.yaml` said 8.13 while
  the wrapper downloaded 8.14.4; the wrapper, the properties file and the
  compatibility matrix now share one value.
* **Unbounded bridge buffering.** A stream with no line break could grow the
  reader's buffer without limit; it is now dropped with a reported error
  (mirroring the native 2 MiB frame cap).
* **SQL identifiers are validated.** Table and column names cannot be bound
  as parameters, so `Database`/`Model`/`Query` now reject anything that is
  not a plain identifier instead of splicing it into the statement.

### Changed
* `tools/check_java.py` now runs the symbol check after parsing, so CI fails
  on an unresolved cross-class call.
* `buildPython` selection explains a version mismatch ("the app ships Python
  3.11, you have 3.12 — Chaquopy will skip .pyc") instead of leaving the raw
  Gradle warning unexplained.
* `NATIVE_IGNORED_PROPS` records the widget properties the renderer does not
  read yet, pinned in both directions by `tests/test_widget_props.py`.

## [Unreleased] — Runtime architecture and Android hardening

This development line focuses on making the Python-to-Android runtime more
explicit, transactional and upgradeable. It is the foundation for the next
major runtime iteration; it does not claim full device-matrix certification
yet.

### Added
* **Protocol v2.** Render transactions carry a transaction id, desired revision
  and patch base revision; Android responds with explicit `render_ack` or
  `render_nack` messages.
* **Persistent Elements.** Added `Element` and `ElementTree` primitives to
  give widgets a durable identity layer between declarative Python state and
  native Android Views.
* **Compatibility metadata.** Generated projects record framework, protocol,
  Android runtime, Chaquopy, AGP, Gradle, Python, SDK and NDK compatibility
  defaults.
* **Runtime regression tests.** Added coverage for duplicate keys, protocol
  envelope validation, render revision metadata, state distinct semantics and
  compatibility requirements.
* **CI scaffolding.** Added Python test/compile jobs plus generated-Java static
  validation for pull requests.

### Changed
* **Rendering is acknowledgement-aware.** Python does not treat a render as
  confirmed until the native runtime acknowledges it; pending updates are
  coalesced behind an in-flight transaction.
* **Widget keys are validated.** Duplicate or empty identity keys now fail
  early instead of producing ambiguous keyed diffs.
* **State subscriptions are cancellable.** `State`, `Store` and related
  subscription APIs expose explicit lifetime handles.
* **State scheduling is explicit.** Watchers can marshal callbacks through the
  app scheduler, and `distinct=True` enables equal-value suppression without
  changing the default behavior.
* **Task failures stay observable.** Worker exceptions remain attached to the
  returned future via `exception()`, while legacy `.result()` stays non-raising
  by default; callers can opt into raising with `propagate_exceptions=True`.
* **Android project defaults are modernized.** Generated projects move to SDK
  36, AGP 8.13.2, Gradle 8.13 and Chaquopy 17.0.0, with Python 3.11/JDK 17
  defaults.
* **WebView defaults are safer.** JavaScript is disabled by default and the
  native bridge is no longer exposed automatically.
* **Foreground-service behavior is tightened.** Services use
  `START_NOT_STICKY` and include the newer timeout handling path.
* **Back handling is modernized.** Generated activities use
  `OnBackPressedDispatcher` while preserving the legacy callback entry
  point.
* **Manifest generation is least-privilege by default.** Optional permissions
  and components are capability-gated rather than always emitted.

### Fixed
* **CI protocol parity.** The in-process `FakeDevice` now understands v2
  render transactions and sends render acknowledgements, so AppTester exercises
  the same transaction boundary as the native bridge.
* **Backward-compatible protocol errors.** The low-level decoder now exposes
  structured `ProtocolError` failures, while `BridgeProtocol.decode_message()`
  preserves the legacy invalid-JSON -> `None` behavior.
* **Backward-compatible subscriptions.** Subscription handles are callable,
  preserving existing `off()` / `unsubscribe()` usage while supporting explicit
  `.cancel()` / `.dispose()`.
* **Task error compatibility.** Worker failures remain available from the
  underlying future via `exception()`, while legacy `.result()` behavior stays
  non-raising by default; strict propagation is available with
  `propagate_exceptions=True`.
* Reduced the chance of Python state racing ahead of the last native render
  acknowledgement during rapid successive updates.
* Prevented duplicate widget identity from silently collapsing keyed diff
  indexes.
* Improved cleanup semantics for app-owned subscriptions during shutdown.

### Validation
* Repository-level Python and generated-code checks are included in the PR.
* A real Android build/device matrix, lifecycle/process-death tests, 16 KB
  page-size validation, performance benchmarks and end-to-end native
  reconciliation tests remain follow-up validation before calling the new
  runtime fully production-certified.

## [1.5.1] — Live-update fixes

A bug-hunt release: every defect here made the on-screen UI disagree
with the Python state.

### Fixed
* **Snackbar actions do something.** `page.snack_bar(..., action="Undo")`
  wired the button to an empty listener on Android, so Undo was
  decorative. The button now reports back and runs
  `on_action` (and `on_dismiss` when the bar fades out by itself):

      page.snack_bar("Counter reset", action="Undo", on_action=undo)

  The starter app's Undo restores the counter again.
* **Material widgets render their children on the first frame.** The
  ViewFactory only attached children for its own layouts, so a `Tabs`
  body, a `Drawer`, a `FormField`, an `ExpansionTile` and every gesture
  or animation wrapper came up empty until an unrelated patch happened
  to re-create them — the "tabs are blank until you switch tabs" bug.
  Composite widgets now declare a content host (`Tabs` puts its body
  *below* the strip, `ExpansionTile` under its header) and both the
  first render and later patches target it.
* **Patch indices match the native tree.** Column/Row spacing used to be
  interleaved `Space` views, which shifted every child index: inserting
  or removing a row landed in the wrong position and left orphaned gaps.
  Spacing is now a margin, re-normalised after each structural change.
* **Hidden children keep their slot.** `to_dict()` dropped invisible
  children while the diff still counted them, so indices drifted. They
  are serialised and hidden natively, and toggling `visible` is now a
  one-property update instead of a create/delete.
* **No prop change is silently dropped.** `updateProps` reports whether
  it handled a change; anything it cannot patch (a Chip's selected
  state, a Rating's value, a Banner's message, an ExpansionTile's
  expanded flag…) is rebuilt in place. `Image` reloads on a new `src`.
* **The diff compares against what the device shows.** `App.update()`
  diffed against the last tree *built*, so an update made while
  disconnected froze the UI for every later update.
* **Deletes purge their descendants.** Parent links are now recorded for
  full renders too, instead of only for patch-created views.
* **`children=` works on every widget** rather than disappearing into
  props, and non-widgets raise `TypeError`.
* **`Tabs` accepts plain labels**, `(label, icon)` tuples and dicts, and
  keeps explicit `children` when no tab declares `content`.

### Added
* `FakeDevice.tap_snackbar_action()`, `FakeDevice.dismiss_snackbar()`
  and `AppTester.tap_snackbar_action()` for testing snackbar callbacks.

## [1.5.0] — The responsive release

Layouts now follow the device instead of guessing. Pydrud reads the real
window metrics, re-reads them on every change, and ships navigation
surfaces you can style down to the pixel.

### Added — responsiveness that actually detects the device
* **Live metrics.** Android sends a `metrics` event on every window
  change — rotation, split screen, foldable unfold, font-scale change,
  new insets, keyboard show/hide — and Python refreshes `MediaQuery`,
  notifies listeners and re-renders. Previously the screen size was read
  once at startup, so a rotated phone kept its portrait layout.
* **`MediaQuery` rebuilt.** Resolution in dp *and* pixels, density, dpi,
  orientation, device type (phone/tablet/desktop/tv/watch), window size
  class, shortest/longest side, aspect ratio, diagonal, refresh rate,
  dark mode, safe-area insets and keyboard height. Read them as
  attributes (`MediaQuery.width`), as a dict (`MediaQuery.of()`) or as an
  immutable `ScreenInfo` snapshot (`MediaQuery.info()`).
* `MediaQuery.matches(min_width=…, orientation=…, device=…)` — CSS-style
  media queries, plus `at_least()`, `at_most()`, `viewport()` and
  `safe_area()`.
* `MediaQuery.listen(callback)` and `App.on_metrics_change(callback)` for
  code that needs to react to a resize.
* **`Breakpoints`** — the size-class table (compact / medium / expanded /
  large / xlarge) is now customisable: `Breakpoints.configure(medium=620)`.
* **`Responsive`** gained percent units (`wp` `hp` `vw` `vh` `sw`), pixel
  conversion (`px` `to_px`), accessibility-capped `sp()`, `grid()`,
  `gutter()`, `at_least()`/`at_most()`, and `configure()` to tune the
  scaling clamp and basis (width / shortest side / diagonal). Scaling is
  based on the shortest side by default, so a rotated phone no longer
  inflates every font.
* **New widgets**: `ResponsiveBuilder`, `AdaptiveLayout`, `ResponsiveGrid`,
  `ShowWhen` and `SafeArea` — all resolved against live metrics.
* **Responsive sizes in styles.** The renderer now understands `"50%"`,
  `"50%w"`, `"50%h"`, `"50%s"`, `"40vw"`, `"40vh"`, `"120px"` and `"16dp"`
  anywhere a width/height is accepted, plus `maxWidth`/`maxHeight` caps
  that centre a readable column on big screens.
* Android: `PydrudTheme.refreshMetrics()` re-reads the *window* metrics
  (not the display) via `WindowMetrics` on API 30+, the activity handles
  `density`, `fontScale`, `smallestScreenSize` and `layoutDirection`
  changes without being recreated, and display cutouts are included in
  the safe area.

### Added — bottom navigation and tabs you can really customise
* **Pydrud draws the bottom bar itself** (`PydrudNavBar`), so every
  property changes the pixels: height, background, corner radius,
  elevation, floating margin, border, top divider, indicator shape
  (`pill` / `circle` / `line` / `dot` / `none`) with its own size, colour
  and radius, per-item colours, active icons, badges with custom colours,
  label behaviour (`always` / `selected` / `never`), icon and label sizes,
  ripple, motion duration, haptics and `fixed`/`shifting` behaviour.
  `native=True` falls back to Android's `BottomNavigationView`.
* The bar draws its own gesture inset and floating margin, so it looks
  identical on gesture-navigation and button-navigation devices.
* **`Tabs` / `TabBar`** gained the full Flutter-style knob set: fixed or
  scrollable, indicator style/size/colour/height/radius, label and icon
  colours per state, per-tab overrides and badges, icon position, tab
  height and min width, alignment, divider, ripple and motion.
* `NavigationBar` and `TabBar` aliases, `NavItem(active_icon=…,
  badge_color=…, tooltip=…)`, `Tab(color=…, badge_color=…)`, plus
  `select()`, `select_route()` and `badge()` helpers.
* Selecting a destination is now a small patch: both surfaces implement
  `applyProps()` instead of being rebuilt.

## [1.4.0] — The design release

Everything you see on screen was rebuilt. Pydrud now ships a real design
system instead of per-widget guesses: one palette, one spacing scale, one
set of motion curves, shared by the Python widgets and the native
renderer.

### Added — the UI is 100% Python
* **`Tokens`** — every metric the renderer draws with (corner radii,
  control heights, bar heights, depth, motion, the type ramp, the
  typeface) is a Python value. The full set is serialised into the
  `theme` command, so the Java renderer and `themes.xml` no longer hold
  design decisions of their own; they render what Python sends.
* `Theme.configure(**values)` sets colours *and* tokens in one call and
  rejects typos with a suggestion; `Theme.configure_reset()` restores the
  defaults; `Theme.tokens()` returns the current set.
* `page.configure(**values)` does the same on a running app and repaints
  immediately — `page.configure(radius_card=24, font_scale=1.1)`.
* `pydrud init --accent "#FF0EA5E9"` generates the whole project from one
  brand colour, and `pydrud.toml` gains a `[theme] seed` entry that
  `pydrud sync` re-reads.
* `values/themes.xml` and `values-night/themes.xml` are now **generated
  from the Python colour scheme** instead of containing hand-written hex.
* A regression test asserts that every token Python can set is read by
  `PydrudTheme.applyTokens`, so the two halves cannot drift apart.

### Added — design system
* Design tokens: `Spacing` (4dp grid), `Radius`, `Elevation` and `Motion`,
  exported from `pydrud`.
* `Theme.seed(colour)` rebuilds the whole palette from one brand colour;
  `Theme.dark()` / `Theme.light()` keep that seed and lift the primary so
  it stays readable on dark surfaces. `Theme` now also exposes
  `secondary`, `surface_variant`, `outline`, `error`, `on_primary` and
  `text_secondary`.
* Colour maths on `Colors`: `mix`, `lighten`, `darken`, `on` (readable
  foreground) and `is_light`.
* `ColorScheme.from_seed` derives the secondary by rotating the hue
  instead of swapping channels, so generated palettes stay harmonious.
* `PydrudTheme.java` — the native half of the design system: tokens,
  Material ripples, press feedback, elevation, the type scale and widget
  recipes, all driven by the palette Python sends.
* `PydrudIcons.java` — 172 vector icons (plus ~60 aliases) rendered as
  paths at any size and colour; `Icons` grew to 123 named constants and
  every one of them resolves to a real vector.

### Added — live theming
* The palette is pushed to the device as a `theme` command *before* the
  first frame, so there is no flash of unstyled UI and native widgets
  (ripples, inputs, switches, dialogs, system bars) match the app.
* `page.set_theme(seed, dark=…)` and `app.apply_theme()` re-theme a
  running app; `page.set_theme_mode()` now repaints natively too.
* Generated projects ship `values/themes.xml` **and**
  `values-night/themes.xml` built from the same palette.

### Added — adaptive layout
* `Responsive` scaling is clamped to 0.9–1.2x. A tablet is twice as wide
  as a phone, but doubling every font and button just produced a
  zoomed-in phone app; layouts now adapt through breakpoints instead.
* Material 3 window size classes: `Responsive.breakpoint()`,
  `is_phone()`, `is_tablet()`, `is_landscape()`.
* New helpers: `Responsive.value(compact=…, medium=…, expanded=…)`
  (with `phone=`/`tablet=` aliases), `columns(min_width=…)`,
  `content_width(max)`, `clamp()` and `raw()` for the old behaviour.
* `MediaQuery.breakpoint()`, `is_landscape()` and `safe_area()`.
* True edge-to-edge: the app bar and bottom navigation absorb the
  system-bar insets themselves (`style.safeAreaTop` / `safeAreaBottom`),
  so their surfaces continue behind the bars instead of leaving grey
  strips. Insets are re-applied on rotation and when the keyboard opens.

### Changed — widgets
* `AppBar` follows the theme (surface + 56dp + hairline separator instead
  of a hard-coded purple bar), ellipsises long titles and puts actions on
  48dp circular ripple targets.
* `Card` defaults to the Material 3 flat + outlined look (`elevation=0`,
  `radius=16`); pass `elevation` for the classic raised card, or
  `on_click` to make it tappable.
* `Button` gained `tonal` and `elevated` variants plus `pill` and
  `full_width`; unknown variants now raise instead of silently falling
  back. `sm`/`md`/`lg` map to 38/48/56dp so every button clears the
  touch-target guideline.
* `TextField` gained `variant="filled"|"outlined"`, a leading `icon` and
  `accent`; the native input has a focus-reactive fill, themed caret and
  selection handles.
* `Divider` uses the theme outline and supports `indent`/`end_indent`.
* `FloatingActionButton` follows the theme and clears the gesture bar.
* `Border.only(bottom=True, …)` plus per-side borders in the renderer.
* Rating stars, chips, segmented buttons, tabs, list tiles, search bars
  and skeleton shimmer were all redrawn against the design system.

### Added — tooling
* `pydrud sync` upgrades an existing project to the current Pydrud
  release: it rewrites the generated Java, the theme resources and the
  bundled runtime, and leaves your code in `src/app/` untouched.
* `buildPython` detection prefers a Chaquopy-compatible interpreter
  (3.8–3.12) instead of whatever `python` happens to be, which removes
  the "incompatible buildPython" warning from the build log.
* `tools/preview_ui.py` renders the app to PNG from the same JSON the
  device receives — design review without a three-minute Gradle build.
  `--accent`, `--token radius_card=28`, `--dark` and `--width` included.
* `tools/check_java.py` renders and parses every generated Java template
  in under a second, so a template typo is caught before Gradle sees it.

### Changed — starter app
* The generated app is now a small, properly designed app: a gradient
  hero card, stat tiles, empty states, a to-do list with swipe-to-delete,
  a settings screen with live dark-mode and accent-colour switching, and
  a component gallery. It adapts between a bottom navigation bar on
  phones and a navigation rail on tablets.

### Fixed
* The floating action button no longer sits on top of the bottom
  navigation bar — `Scaffold` lifts it clear of the bar.
* `ListTile` no longer overwrites a key you gave to its `leading` or
  `trailing` widget, so events on those children keep working.
* Markdown, rich text, canvases and charts take their colours from the
  theme, so they stay readable in dark mode.
* Chart series now walk a generated palette instead of repeating one
  colour.
* **A freshly generated project compiles again.** `ChartView` is a
  `static` nested class, so its calls to `MaterialViews`' instance
  helpers (`dp`, `parseColor`) made `javac` fail with *"non-static
  method ... cannot be referenced from a static context"*; it now goes
  through `PydrudTheme` directly. A test walks every Java template and
  fails on any static nested class that touches an outer instance
  member.
* `pydrud run` no longer forces `buildPython` to whatever `python`
  resolves to. It picks an interpreter matching the app's Python
  (3.11) — and honours an explicit `PYDRUD_PYTHON` — so Chaquopy stops
  warning *"buildPython version 3.12.x is incompatible"* and can
  pre-compile to `.pyc`.

## [1.3.0] — The "ship it" release

### Added — data
* `Database`: SQLite with named migrations, transactions, `scalar`/`query`
  helpers, schema introspection and a per-app directory (`page.database()`).
* `Model` + `Field`: a small ORM with `create`, `get`, `get_or_create`,
  `where`, `bulk_create`, `count`, `update`, `delete`, `refresh`, `to_dict`,
  field lookups (`__gte`, `__contains`, `__in`, `__startswith`, …), ordering,
  slicing and `page()` pagination.
* `Cache` + `@cached`: TTL/LRU cache with size accounting, `get_or_set`,
  `purge`, `stats` and decorator-level `invalidate()`; `page.cache`.

### Added — navigation
* Pattern routes (`/items/:id`, `/files/*rest`) with typed path parameters and
  query strings, specific-over-wildcard matching and a `not_found` screen.
* Route guards (block or redirect), nested navigators with correct back-button
  precedence, deep links (`myapp://…` and `https://…`) and seven transitions.
* `push`/`replace`/`reset` now accept a concrete path or full URL as well as a
  route pattern.

### Added — platform
* Ten new services: `secure` (EncryptedSharedPreferences), `background`
  (WorkManager jobs, constraints, foreground services), `push` (FCM tokens and
  topics), `shortcuts` (app shortcuts and home-screen widgets), `sensors`
  (streams plus shake detection), `biometrics`, `bluetooth` (BLE), `nfc`,
  `camera` (capture, flash, switch) and `audio` (record, play, TTS, speech
  recognition).
* Background jobs run headlessly through `PydrudWorker` →
  `app.main.run_background_job(name, inputs_json)`, with a `@job` decorator in
  the generated project.
* Deep links and notification/shortcut intents route via the `pydrud_route`
  extra; links arriving before a handler is attached are replayed.

### Added — UI
* `Canvas` with `Paint`, `Path`, transforms, gradients, `grid`, `sparkline`
  and `pie`, plus an `on_draw` callback redrawn on every render.
* Explicit animations: `AnimationController` (forward, reverse, repeat,
  ping-pong, dispose), `Tween` (numbers, colours, tuples), `Sequence_` and
  `page.animation()`.
* New widgets: `CameraPreview`, `MapView`/`Marker`, `RichText`/`Span`,
  `Markdown` (headings, lists, task lists, quotes, code, rules, inline spans),
  `ReorderableList` and a virtualising `InfiniteList`.

### Added — tooling
* `pydrud pip add/remove/list/search/sync`: 119 verified Android-compatible
  PyPI packages recorded in `pydrud.toml` and injected into Chaquopy's
  `build.gradle.kts`; known-incompatible packages are rejected with a reason.
* `pydrud keygen`, `pydrud icons`, `pydrud permissions add|remove`,
  `pydrud docs` (offline HTML API reference) and `pydrud inspect` (live widget
  inspector with a static fallback).
* Release builds support an upload keystore, R8 shrinking and ProGuard rules.

### Added — developer experience
* Stateful hot reload: bound `State` and `Store` values, and the current
  route, survive a file save. `State(name=…)` makes the match explicit;
  `app.preserve_state(False)` opts out.
* `Store.replace()` swaps a whole state dict and notifies every changed key.
* The package now ships `py.typed`.

### Fixed
* `abi_filters` is supplied by the project context instead of relying on the
  Gradle template default.
* `job_result` acks are no longer logged as unknown bridge commands.

## [1.2.0] — The full Android toolkit

### Added — components
* 21 Material 3 widgets: `ListTile`, `ExpansionTile`, `Chip`, `Badge`,
  `Avatar`, `Banner`, `Tooltip`, `Tabs`/`Tab`, `BottomNavigationBar`/`NavItem`,
  `NavigationRail`, `Drawer`, `SegmentedButton`, `SearchBar`, `Rating`,
  `CircularProgress`, `Skeleton`, `RefreshIndicator`, `Stepper`, `WebView`,
  `VideoPlayer` and a Canvas-drawn `Chart` (line / area / bar / pie).
* `Scaffold` gained `drawer`, `end_drawer`, `bottom_navigation`,
  `navigation_rail`, `banner`, `fab_position`, `safe_area` and
  `resize_to_avoid_keyboard`.

### Added — interaction
* `GestureDetector` (tap, double-tap, long-press, four-way swipe, pan, pinch
  scale), `InkWell`, `Dismissible` and `Draggable`. Only subscribed gestures
  are detected and sent over the bridge.
* Implicit animations: `AnimatedContainer`, `AnimatedOpacity`, `AnimatedScale`,
  `AnimatedRotation`, `AnimatedSwitcher`; entrance effects `FadeIn`, `SlideIn`,
  `ScaleIn`; `Hero` shared elements; `widget.animate(...)` on any widget;
  `Animation` specs with nine curves.
* `Form`, `FormField` and eleven validators with per-field, cross-field and
  server-side errors.

### Added — platform
* Native services behind `page.*`: `dialog`, `storage`, `clipboard`, `share`,
  `permissions`, `notifications`, `location`, `device`, `files`, `haptics`.
  Each returns a `Result` future with `.then()` / `.catch()` / `.wait()`.
* `page.http` — a dependency-free, non-blocking HTTP client (JSON, retries,
  timeouts, base URL, bearer auth, downloads).
* Page commands: `open_drawer`, `close_drawer`, `scroll_to`, `focus`,
  `show_keyboard`/`hide_keyboard`, `keep_awake`, `set_orientation`,
  `fullscreen`, `set_theme_mode`, `end_refresh`.
* New Java sources generated per project: `MaterialViews.java`,
  `GestureBinder.java`, `NativeServices.java` (plus command handling in
  `BridgeService` and result plumbing in the Activity).

### Added — architecture
* `Store` (actions, selectors, middleware, batching, undo), `Computed`,
  `ReactiveList`; `app.bind()` now accepts any of them.
* `TaskRunner`: `page.run_task()` (threads and `async def`),
  `page.run_on_ui()`, `page.after()`, `page.every()`, `@debounce`, `@throttle`.
* `ColorScheme.from_seed()` (Material You, light and dark) and the M3
  `Typography` scale.
* `pydrud.testing` is now public API: `FakeDevice` plus the new `AppTester`
  harness (tap by key *or* visible text, stub native answers, assert on
  rendered text).

### Changed
* Event callbacks receive an `Event` object exposing `.type`, `.key`,
  `.value`, `.data` and `.control`. It subclasses `dict`, so handlers written
  for earlier versions keep working.
* `page.update(widget)` pushes a single mutated subtree without re-running the
  builder; `page.update()` keeps the declarative rebuild semantics.
* The starter app gained a three-tab "Showcase" screen touring the new
  components, and the manifest documents the runtime permissions to opt into.

### Fixed
* `on_<event>=` keyword arguments were silently serialised as props on widgets
  that did not declare them explicitly (e.g. `TextField(on_change=...)`); any
  `on_*` callable is now registered as an event handler, and non-callables
  raise a clear `TypeError`.
* Form inputs lost their value when the real bridge delivered events, because
  the handler expected a raw dict rather than the dispatched payload.

## [1.1.0]

Correctness release: stable widget keys and keyed diffing, 11 new widgets,
Colors/Icons/Theme, a working hardware back button, FAB overlays, lifecycle
hooks, error isolation, self-bootstrapping Gradle, unique package names,
`pydrud watch` / `devices`, and the FakeDevice test harness. See the
"New in v1.1.0" section of the README for the full list.

## [1.0.1]

Router, Scaffold, AppBar, FAB, MediaQuery, hot reload, incremental patches,
WidgetRegistry and `pydrud analyze`.

## [1.0.0]

Initial release: core widgets, state, diffing, CLI, APK generation and
responsive scaling.