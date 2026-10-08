<p align="center">
  <img src="https://img.shields.io/pypi/v/pydrud?color=6366F1&style=flat-square" alt="PyPI" />
  <img src="https://img.shields.io/pypi/pyversions/pydrud?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/runtimes-Pydash%20%7C%20Chaquopy-6366F1?style=flat-square" alt="Pydash and Chaquopy runtimes" />
  <img src="https://img.shields.io/github/license/MurShidM01/Pydrud?style=flat-square" alt="License" />
  <img src="https://img.shields.io/pypi/dm/pydrud?style=flat-square" alt="Downloads" />
</p>

<h1 align="center">Pydrud</h1>

<p align="center">
  <strong>Build Python UIs with a Flutter-inspired widget API.</strong><br>
  Run host-side with the toolchain-free <em>Pydash</em> preview, or compile a real Android APK with <em>Chaquopy</em>.
</p>

---

Pydrud is a declarative UI framework for Python with a platform-neutral widget
tree, a keyed diff engine, and a versioned render protocol. The same screen
code drives a host preview or native Android Views — there is no XML and no
Java to write.

## Quick start

```bash
pip install pydrud                       # install the framework
pydrud create my_app --org com.example   # scaffold a project (Pydash runtime)
cd my_app
pydrud dev                               # run host Python, print a preview QR/URI
```

For an installable Android app, add the native platform and run it:

```bash
pydrud init android        # standalone app with embedded Python (Chaquopy)
pydrud run                 # build, install and launch on a device/emulator
```

The generated APK boots your Python on device and runs fully offline. Pass
`--runtime chaquopy` to `pydrud create` to scaffold the Android project
directly.

## Runtimes

| Runtime | What runs where | Build requirements | Select with |
|---------|-----------------|--------------------|-------------|
| **Pydash** (default) | Python and state stay on the host; a preview renderer receives widget snapshots/patches and returns events. No APK. | Host Python only — no Android SDK, NDK, Gradle or ADB. | `pydrud create <name>` or `--runtime pydash` |
| **Android standalone** (Chaquopy) | CPython is bundled in the generated project; widgets render as native Android Views, fully offline. | Android SDK/NDK, JDK, Gradle; a device/emulator to install. | `pydrud init android`, or `pydrud create <name> --runtime chaquopy` |

An Android target can also be built with **no embedded interpreter**:

| Backend | On the device | Use it when |
|---------|---------------|-------------|
| `chaquopy` (default) | CPython bundled; runs fully offline | You want a self-contained, publishable APK |
| `host` | No interpreter — the app dials *out* to Python on your machine | You want your real Python app without embedding a runtime |
| `none` | A pure renderer with no runtime | You only need the native shell / protocol |

```bash
pydrud init android --backend host|none|chaquopy
pydrud dev --bridge            # serve the host bridge (runs `adb reverse` for you)
```

All three share the same widget tree, keyed diff and protocol-v2 render
transactions; only the transport differs.

## Installation

```bash
pip install pydrud                       # from PyPI
```

```bash
git clone https://github.com/MurShidM01/Pydrud.git
cd Pydrud && pip install -e ".[dev]"     # from source
```

Behind a proxy, export `http_proxy` / `https_proxy` before `pydrud build`;
the values are forwarded to Gradle automatically.

## What you get

| Area | Description |
|------|-------------|
| Declarative UI | 130+ widgets and presets: layout, Material 3 components, form fields, chips, charts, media, gestures and animations |
| Reactive state | `State<T>` re-renders the tree on change; `Store` / `Computed` / `ReactiveList` for app-level state |
| Styling | Inline styles plus platform-neutral `.pss` stylesheets with the full CSS authoring surface (see below) |
| Design system | `Theme` + `Tokens` — colours, radii, sizes, depth, motion and type in Python; light/dark and Material You |
| Responsive | Live window metrics (size, insets, text scale, orientation) drive breakpoints, percent units and adaptive widgets |
| Rendering | A transport-neutral widget tree and protocol-v2 transactions; Chaquopy renders native Android Views |
| CLI toolchain | Runtime-aware `create` / `init` / `dev` / `sync` / `analyze` / `doctor` / `pip`, plus Android `run` / `build` / `watch` / `icons` / `keygen` / `permissions` / `capabilities` |
| Data layer | SQLite `Database`, `Model` ORM with migrations, and a TTL `Cache` |
| Native services | Dialogs, storage, files, share, notifications, location, haptics, camera, sensors, biometrics and more |
| Async by default | Thread pool, timers and a non-blocking HTTP client, so the UI never freezes |
| Testable | `pydrud.testing.AppTester` runs your whole app in CI without a device or emulator |

## Examples

Two complete apps live in [`examples/`](examples):

| Example | Demonstrates |
|---------|--------------|
| [`todo_app.py`](examples/todo_app.py) | `Store` state, keyed lists, swipe-to-delete, search + segmented filtering, persistence, a confirm dialog |
| [`weather_app.py`](examples/weather_app.py) | The non-blocking HTTP client, pull-to-refresh, permissions + GPS, a `Chart`, skeleton loading states, bottom navigation |

Run either headless with `python examples/todo_app.py --tree`, or drop it into
a project as `src/app/main.py`.

## PSS stylesheets

Pydrud Style Sheets (PSS) keep presentation out of Python while using the same
platform-neutral vocabulary. Files named `*.pss` under `src/` are discovered
automatically and re-resolved without re-running Python modules.

```pss
:root { --brand: #FF4F46E5; }

.card {
    background: var(--brand);
    border-radius: 16;
    padding: 24;                       /* all four sides */
    shadow: { color: #40000000; offsetY: 8; blur: 24 };
    font: { size: 16, weight: 600 };
}

@media (max-width: 360px) {
    .card { padding: 16; }
}

@keyframes pulse {
    from { transform: scale(1); opacity: 1; }
    to   { transform: scale(1.4); opacity: .4; }
}
.badge { animation: pulse 1.2s ease-in-out infinite; }
.badge:active { transform: scale(.92); }
```

Supported today: custom properties (`--x` / `var()` with fallback, inherited),
the universal selector `*`, structural and state pseudo-classes
(`:first-child`, `:nth-child()`, `:not()`, `:active`, `:hover`, `:focus`, …),
`@media` queries, `@keyframes` + the `animation` shorthand, `transition`, and
the CSS value language — `clamp()`, `calc()`, `min()`/`max()`,
`env(safe-area-inset-*)` and the viewport units, resolved against the live
window. CSS long-hands fold into Pydrud composites (`font-size` → `font.size`,
`padding-top` → `padding.top`, `background` → `bg`, `transform: scale()` →
`scale`), and web-only declarations are accepted then ignored with one
warning, so a stylesheet copied from the web drops in nearly verbatim.

`$token` references resolve against the active palette — `bg: $surface`,
`color: $text`, `border-radius: $radius_card` — so one stylesheet follows
light/dark mode and re-tints after `Theme.seed()`.

See [docs/PSS_STYLESHEETS.md](docs/PSS_STYLESHEETS.md) for the selector,
cascade, value, diagnostics and reload contract, and
[docs/examples/heartbeat-css-parity.pss](docs/examples/heartbeat-css-parity.pss)
for a full stylesheet translated from a web prototype.

## Widget catalogue

The API is Flutter-shaped. Every widget serialises to a platform-neutral node;
the renderer decides how to draw it.

### Layout

| Widget | Description |
|--------|-------------|
| `Container`, `Padding`, `SizedBox`, `Center`, `Spacer` | Boxes, padding and fixed/centred space |
| `Row`, `Column`, `Flex` | Linear layouts (`Flex` is either axis by `direction`) |
| `Stack`, `Positioned` | Overlapping and absolutely-placed children |
| `Scaffold`, `AppBar`, `FloatingActionButton` | Page chrome and the Material action button |
| `ListView`, `GridView`, `PageView`, `Carousel`, `SingleChildScrollView`, `Wrap` | Scrolling and paging |
| `Card`, `Divider`, `Drawer`, `Tabs`, `BottomNavigationBar`, `NavigationRail` | Surfaces and navigation |
| `AdaptiveLayout`, `LayoutBuilder`, `ResponsiveBuilder`, `ResponsiveGrid`, `SafeArea`, `ShowWhen` | Responsive composition |

### Controls

| Widget | Description |
|--------|-------------|
| `Text`, `Heading`, `Title`, `Subtitle`, `Label`, `Caption`, `Link`, `RichText` | Typography |
| `Button`, `TextButton`, `ElevatedButton`, `IconButton`, `SegmentedButton` | Actions |
| `TextField`, `NumberField`, `PasswordField`, `SearchBar`, `Form`, `FormField` | Input and validation |
| `Checkbox`, `Switch`, `Radio`, `Slider`, `RangeSlider`, `Dropdown`, `Stepper`, `Rating` | Selection |
| `Chip`, `Badge`, `Avatar`, `Banner`, `Tooltip`, `PopupMenu`, `ListTile`, `ExpansionTile` | Material 3 components |
| `ProgressBar`, `CircularProgress`, `Skeleton`, `EmptyState`, `ErrorState`, `LoadingState` | Feedback and placeholders |
| `AlertDialog`, `ModalBottomSheet` | Declarative modals — add to the tree to show, drop to dismiss |
| `Chart`, `Canvas`, `Image`, `SvgPicture`, `WebView`, `VideoPlayer`, `MapView`, `NativeView` | Media, painting and escape hatches |

`pydrud docs --serve` generates a searchable HTML reference for every widget,
prop and service.

### Events, state and async

```python
widget.on_click(callback)          # any widget — callback(data)
widget.on_change(callback)         # inputs, sliders, page views
widget.on("select", callback)      # any named event

from pydrud import State, Store, Computed
count = State(0)
Text(lambda: f"{count.value}")     # rebuilds when count changes
page.run_task(heavy_work)          # thread pool; `async def` also works
page.every(1.0, tick)              # repeating timer
page.http.get("/posts").then(render).catch(show_error)
```

## CLI reference

Every command uses the same branded terminal UI (auto-disabled when output is
redirected; override with `NO_COLOR` / `PYDRUD_COLOR`). `pydrud analyze --json`
stays plain JSON.

| Command | Description |
|---------|-------------|
| `pydrud create <name>` | Scaffold a Pydash project (no Android toolchain) |
| `pydrud create <name> --runtime chaquopy` | Scaffold the standalone Android APK project |
| `pydrud init android [--backend …]` | Add the Android platform to an existing project |
| `pydrud dev [--bridge] [--host] [--port]` | Run host Python and serve the preview / device bridge |
| `pydrud build [--debug\|--release]` | Build an APK (Android platform only) |
| `pydrud run [--debug\|--release]` | Build, install and launch on a device |
| `pydrud watch` | Android Hot Reload runner |
| `pydrud devices` | List connected Android devices |
| `pydrud analyze [--path src] [--json]` | Static analysis of Python UI code and PSS stylesheets |
| `pydrud sync` | Refresh the generated Android layer |
| `pydrud clean` | Clean Android build artifacts |
| `pydrud doctor` | Check host and Android toolchain requirements |
| `pydrud pip add\|remove\|list\|search\|sync` | Manage project packages |
| `pydrud permissions add\|remove <name>` | Update YAML and the Android manifest |
| `pydrud capabilities add\|remove <name>` | Enable Android feature bundles |
| `pydrud icons [--source logo.png]` | Generate launcher icons |
| `pydrud keygen` | Create the Play Store upload keystore |
| `pydrud docs [--serve]` | Offline HTML API reference |
| `pydrud inspect [--tree] [--watch]` | Inspect the widget tree or Android bridge traffic |

## Android project configuration

Applies once a project has the Android platform. `pydrud.yaml` is the
source of truth for generated Android files — change it and run
`pydrud sync`.

```yaml
app_name: "Taskflow"
package: "com.example.taskflow"
runtime: "chaquopy"
version_code: 2
version_name: "1.1.0"
min_sdk: 24
target_sdk: 36
compile_sdk: 36
scheme: "taskflow"
permissions: ["CAMERA"]
capabilities: ["haptics", "notifications"]
camera: false
python_version: "3.11"
protocol_version: 2
```

| Key | Purpose |
|-----|---------|
| `runtime` | `chaquopy`, `host` or `none` |
| `capabilities` | Feature bundles (camera, microphone, location, contacts, notifications, haptics, …). `pydrud capabilities list --all` describes each |
| `permissions` | Individual Android permissions (dangerous ones still need a runtime request) |
| `camera` | Bundle the CameraX + ML Kit stack (~10 MB). Off by default; `pydrud permissions add camera` enables it. Without it, `CameraPreview` renders its fallback and camera calls explain the fix |

Runtime dangerous permissions always require `page.permissions.request(...)`
and explicit user consent — Pydrud never fakes or bypasses the Android prompt.

## Architecture

Both runtimes share the transport-neutral widget tree, keyed diff engine and
protocol-v2 transactions:

```text
Pydash (pydrud dev)
  host Python App  ── token-authenticated preview handshake ──► renderer
        source, state and handlers stay on the host

Chaquopy (pydrud run / APK)
  embedded Python App ── local NDJSON bridge ──► generated BridgeService
                                                 └─ native Android Views
```

1. `App(target=main)` builds a widget tree; PSS rules resolve on the Python side.
2. `page.update()` computes keyed patches from the last renderer-confirmed tree.
3. Python sends one `RenderTransaction` (full snapshot or patch batch) with a
   strictly increasing revision.
4. The renderer applies it atomically and ACKs; a NACK triggers a full resync.
5. Events travel back through the same bridge to Python callbacks.

### Source layout

No file in the repository exceeds 1,000 lines.

| Package | Contents |
|---------|----------|
| `pydrud/widgets/` | Widget library: `basic`, `layout`, `forms`, `advanced`, `canvas`, `gestures`, `animation`, `conditional`, `responsive`, `presets`, plus `material/` and `theme/` |
| `pydrud/runtime/` | `App`, `Page` and the bridge event loop, split into focused mixins |
| `pydrud/core/` | Platform-neutral engine: `diff`/`RenderTransaction`, state, bridge/protocol, responsive, watcher, and `styles/` (the PSS engine) |
| `pydrud/services/` | `http` and `native/` platform services |
| `pydrud/commands/` | The CLI (`project/`, builder, analyzer, doctor, docs, …) |
| `pydrud/android/templates/` | Jinja2 templates for the generated Android project |

### Native renderer (Chaquopy)

A thin `ViewFactory` orchestrator plus cohesive collaborators:

| Class | Responsibility |
|-------|----------------|
| `ViewFactory` | Orchestrator — view/node maps, public API, collaborator wiring |
| `BuiltinViews` | `createView` dispatch and built-in widget factories |
| `ViewStyler` | `applyStyle`, borders, gradients, typography, dimensions |
| `LayoutEngine` | Linear/grid layout params, spacing, child attach/removal |
| `TreePatcher` | `applyPatch` / `updateProps` |
| `EventBinder` | Click/change binding, popup menus, touch feedback |
| `ViewAnimator` | Entrance animations, keyframes, transitions |
| `ImageLoader` · `NativeViewFactory` | Image pipeline · user `NativeView` classes |
| `MaterialViews` + `MaterialNavigationViews` | Material 3 components |
| `BridgeService` · `PydrudTheme` | TCP/NDJSON server · generated design system |

## Requirements

### Host workflow (default)

Python 3.10+ and the Pydrud package. `pydrud dev` needs no Java, Android SDK,
NDK, Gradle or ADB.

### Android APK workflow

| Tool | Default | Notes |
|------|---------|-------|
| Python | 3.11 | Used by the Chaquopy build/runtime configuration |
| Java (JDK) | 17+ | Checked by `pydrud doctor` |
| Android SDK | API 36 compile/target | Set `ANDROID_HOME` or `ANDROID_SDK_ROOT` |
| Android NDK | `28.2.13676358` | Generated project default |
| Android Gradle Plugin | `8.13.2` | Generated project default |
| Gradle | `8.14.4` | Wrapper generated with the project |
| Chaquopy | `17.0.0` | Embedded Python runtime (MIT since 12.0.1) |

Projects target Android API 24+ and default to `arm64-v8a`, `armeabi-v7a` and
`x86_64`. ADB is needed for `pydrud run`, not for `pydrud dev` or the tests.

<details>
<summary><b>Setting up the Android SDK</b></summary>

Windows (PowerShell):

```powershell
[System.Environment]::SetEnvironmentVariable('ANDROID_HOME', 'C:\Android\Sdk', 'User')
[System.Environment]::SetEnvironmentVariable('ANDROID_SDK_ROOT', 'C:\Android\Sdk', 'User')
```

Linux / macOS:

```bash
export ANDROID_HOME=$HOME/Android/Sdk
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
```

Restart your terminal and run `pydrud doctor` to verify.
</details>

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
ruff check .                 # the same lint CI runs
```

The suite covers widget/state/protocol unit tests, keyed-diff and PSS
parsing/resolution, scaffold generation for both project shapes, generated
Java template parsing, and end-to-end runtime tests via `pydrud.testing` —
all without a device or emulator.

## Roadmap

| Version | Focus |
|---------|-------|
| **v2.1.0** | `create`/`init android` CLI, pluggable runtime backends, PSS engine, Heartbeat starter, runtime-aware tooling |
| **Next** | PSS as a full CSS-style language, declarative `@keyframes`/`transition`/`:active`, declarative overlays, content blur, animated theming |
| **Later** | iOS (SwiftUI), Web (WASM) and macOS desktop backends |

See [CHANGELOG.md](CHANGELOG.md) for the complete itemised history.

## Contributing

1. Fork the repository.
2. Create a branch: `git checkout -b feature/amazing-feature`.
3. Commit your changes and push the branch.
4. Open a Pull Request.

## License

MIT © Pydrud Contributors. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Pydrud</strong> — <em>Pythonic. Portable. Simple.</em>
</p>
