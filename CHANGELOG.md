# Changelog

All notable changes to Pydrud are documented here.

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
