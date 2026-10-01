# Changelog

All notable changes to Pydrud are documented here.

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
