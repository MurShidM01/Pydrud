# Changelog

All notable changes to Pydrud are documented here.

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
