<p align="center">
  <img src="https://img.shields.io/pypi/v/pydrud?color=6366F1&style=flat-square" alt="PyPI" />
  <img src="https://img.shields.io/pypi/pyversions/pydrud?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/runtimes-Pydash%20%7C%20Chaquopy-6366F1?style=flat-square" alt="Pydash and Chaquopy runtimes" />
  <img src="https://img.shields.io/github/license/MurShidM01/Pydrud?style=flat-square" alt="License" />
  <img src="https://img.shields.io/pypi/dm/pydrud?style=flat-square" alt="Downloads" />
</p>

<h1 align="center">Pydrud</h1>

<p align="center">
  <strong>Build Python UIs with Pydrud.<br>
  Use Pydash for toolchain-free cross-platform preview, or opt into Chaquopy for Android APKs.</strong>
</p>

<p align="center">
  A Flutter-inspired framework with a platform-neutral widget and renderer protocol.<br>
  The default Pydash workflow runs Python on the host; the optional Chaquopy target renders real Android Views.
</p>

---

## Table of Contents

| # | Section | # | Section |
|---|---------|---|---------|
| 1 | [Quick Start](#quick-start) | 8 | [Responsive](#responsive-v15) |
| 2 | [Runtime Modes](#runtime-modes) | 9 | [Bottom Navigation & Tabs](#bottom-navigation-and-tabs-v15) |
| 3 | [What You Get](#what-you-get) | 10 | [System UI](#set_system_ui-v101) |
| 4 | [What's New in v2.1.0](#whats-new-in-v210) | 11 | [Architecture](#architecture) |
| 5 | [Examples](#examples) | 12 | [Android Project Configuration](#android-project-configuration) |
| 6 | [Installation](#installation) | 13 | [CLI Reference](#cli-reference) |
| 7 | [Widget Reference](#widget-reference) | 14 | [PSS Stylesheets](#pss-stylesheets) |
|   |                                 | 15 | [Requirements](#requirements) · [Development](#development) |
|   |                                 | 16 | [Roadmap](#roadmap) · [Contributing](#contributing) · [License](#license) |

---

## Quick Start

The default project is Pydash: Python runs on your development machine and
connects to a compatible preview renderer over the authenticated LAN protocol.
It does not require an Android SDK or produce an APK.

```bash
pip install pydrud                      # Install the framework
pydrud create my_app --org com.example  # Defaults to the pydash runtime
cd my_app
pydrud dev                              # Start the host app and print a QR/URI
```

For an installable Android app, add the platform inside the project:

```bash
pydrud init android               # Preview shell: no Chaquopy, NDK or CMake needed
pydrud run                        # Build, install and launch on Android
```

Need a fully offline APK with embedded Python? Use
`pydrud init android --standalone` instead (or pass
`--runtime chaquopy` to `pydrud create` to scaffold it directly).

## Runtime Modes

| Runtime | What runs where | Build requirements | How to select |
|---------|-----------------|--------------------|---------------|
| **Pydash (default)** | Python and app state stay on the host; a separately provided renderer receives widget snapshots/patches and returns events. No APK is produced. | Host Python. No Android SDK, NDK, Gradle, or ADB for `pydrud dev`. | `pydrud create <name>` or `--runtime pydash` |
| **Android preview shell** | Python stays on the host; the generated APK renders `pydrud dev` over the authenticated LAN protocol. | JDK, Android SDK, Gradle; a device or emulator for install/run. No Chaquopy, NDK or CMake. | `pydrud init android` inside the project |
| **Android standalone (opt-in Chaquopy)** | CPython is bundled in the generated Android project and widgets are rendered as native Android Views, fully offline. | Android SDK/NDK, JDK/Gradle; a connected device or emulator for install/run. | `pydrud init android --standalone`, or `pydrud create <name> --runtime chaquopy` |

The Pydash companion client is a separate project and is not built, bundled, or
validated by this repository. Pydrud supplies its authenticated host-side
preview endpoint only; this change does not add a client or a standalone
Pydash export target. The two runtimes share the transport-neutral widget,
diff, and protocol-v2 render transaction contracts.

New projects without a runtime setting default to Pydash. For compatibility,
a pre-existing generated Android project with no `runtime` key is detected as
Chaquopy and keeps that behavior; `pydrud sync` writes the inferred choice
back to `pydrud.toml`. The Android target shape is recorded separately as
`standalone:` in `pydrud.yaml` (`true` embeds Python with Chaquopy, `false`
builds the preview shell); older projects without the key keep whatever
their Gradle files already do, so `sync` never silently changes an APK
project into a preview shell or vice versa.


---

## Host-driven live preview (`pydrud dev`)

The preview workflow keeps Python and project source on the development
machine. It watches `src/`, computes the existing keyed widget-tree diffs and
revisioned render transactions, and sends only rendering commands to an
authenticated lightweight client:

```bash
pydrud dev
pydrud dev --host 0.0.0.0 --port 8597
pydrud dev --connect-host 192.168.1.24   # advertise a specific LAN/VPN address
pydrud dev --no-qr                       # URI-only output for scripts
```

The terminal shows the project/session identity, listening and connect
addresses, a QR code and the exact one-run connection URI. On connection it
sends a full snapshot; acknowledged edits use patches. Disconnects leave the
host runtime and watcher alive, and reconnects force a safe full resync from
the client's reported revision. Syntax/reload errors are shown in the terminal
while the last good UI remains visible.

The preview listener defaults to the local network and uses a random 256-bit
bearer token embedded in the QR. It is a trusted-LAN development protocol, not
an internet service: traffic is not encrypted, so do not port-forward it or
share the connection URI. See [Preview Protocol v1](docs/PREVIEW_PROTOCOL.md)
for handshake, capabilities, framing, ACK/NACK and reconnect semantics.

`pydrud run`, APK generation and the embedded Android bridge are separate
Chaquopy-only workflows; `pydrud dev` does not route through ADB or that APK
bridge.


## What You Get

| Feature | Description |
|---------|-------------|
| Declarative UI | 130+ widgets and presets: layout, Material 3 components, form fields, chips, charts, media, gestures, animations and Flutter-style compositions |
| Reactive State | `State<T>` auto-triggers UI re-renders on value change |
| Full Styling | Inline styles plus platform-neutral `.pss` stylesheets; colors, spacing, borders, fonts, elevation and alignment |
| Runtime choices | Pydash is the toolchain-free host-preview default; Chaquopy is the opt-in Android APK target |
| Rendering | A transport-neutral widget tree and protocol v2 render transactions; Chaquopy renders native Android Views |
| CLI Toolchain | Runtime-aware `init` / `dev` / `sync` / `analyze` / `doctor` / `pip`; Android-only `run` / `build` / `watch` / `clean` / `devices` / `icons` / `keygen` / `permissions` / `capabilities`; shared `docs` / `inspect` |
| No XML, no Java | The Python UI API is shared; Android resources and Java are generated only for Chaquopy projects |
| Data Layer | SQLite `Database`, `Model` ORM with migrations, and a TTL `Cache` |
| Runtime-aware packages | Chaquopy keeps its verified Android package registry; Pydash records host dependencies without installing them |
| Android platform services | Chaquopy provides WorkManager, foreground services, push, camera, sensors, biometrics and audio; Pydash service calls depend on the connected client's advertised capabilities |
| Design system | `Theme` + `Tokens` — colours, radii, sizes, depth, motion and type live in Python; each renderer applies the shared style vocabulary |
| Responsive | Live renderer window metrics (size, insets, text scale and orientation) drive breakpoints, percent units and adaptive widgets |
| Customisable navigation | Bottom navigation and tabs Pydrud draws itself — indicator, labels, colours, motion, shape, badges |
| Optional Services | Dialogs, storage, permissions, files, share, notifications, location, haptics and device info when the connected renderer advertises them |
| Async by Default | Thread pool + timers + a non-blocking HTTP client, so the UI never freezes |
| Testable | `pydrud.testing.AppTester` runs your whole app in CI without a device or emulator |
| Transport | Pydash uses the token-authenticated LAN preview handshake; Chaquopy keeps the existing local NDJSON bridge and renderer protocol v2 |

---

## What's New in v2.1.0

The platform release: apps are created with `pydrud create`, the Android
shell is added afterwards with `pydrud init android`, and stylesheets ship
in every starter. The complete, itemised history (v1.0.1 → v2.1.0) lives in
[CHANGELOG.md](CHANGELOG.md).

| Area | Highlights |
|------|------------|
| CLI | `pydrud create` replaces `pydrud init <name>` for new apps; `pydrud init android` adds the native platform to an existing project (ios/linux/windows/web/macos reserved for later) |
| Android without Chaquopy | The default `android/` shell renders `pydrud dev` over the authenticated LAN protocol — JDK + SDK + Gradle only, no Chaquopy, NDK or CMake; `--standalone` embeds CPython for offline APKs |
| PSS stylesheets | Every new app ships `src/app/theme.pss` wired to its screens via `class_`; `pydrud analyze` now validates stylesheets alongside Python |
| Reliability | Hot-reload file paths are POSIX on every OS (Windows fix); state updates during app startup queue instead of racing the first frame |


## Examples

Runnable example apps ship in [`examples/`](examples/):

| Example | Demonstrates |
|---------|--------------|
| [`todo_app.py`](examples/todo_app.py) | `Store` reactive state, list CRUD, filters, `SearchField` |
| [`weather_app.py`](examples/weather_app.py) | Async HTTP, responsive layout, cards and charts |

The `pydrud create` starter is a focused, responsive counter app showcasing
Scaffold, AppBar, a floating action button and PSS theming. `pydrud docs --serve`
generates a searchable HTML reference for every widget, prop and service.

---
## Installation

### From PyPI (recommended)

```bash
pip install pydrud
```

### From source

```bash
git clone https://github.com/MurShidM01/Pydrud.git
cd Pydrud
pip install -e .
```

### Corporate / proxy networks

```bash
export http_proxy=http://proxy:port
export https_proxy=https://proxy:port
pydrud build    # Chaquopy only; proxy forwarded to Gradle automatically
```

---

## Widget Reference

### Layout

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Container` | Box with padding, margin, bg, border-radius | `child`, `padding`, `margin`, `bg`, `border_radius`, `width`, `height`, `alignment`, `expand` |
| `Column` | Vertical flex layout | `children`, `spacing`, `horizontal_alignment`, `vertical_alignment` (main axis: `top`/`center`/`bottom`), `main_axis_size`, `cross_axis_size`, `scroll`, `expand` |
| `Row` | Horizontal flex layout | `children`, `spacing`, `vertical_alignment`, `horizontal_alignment` (main axis: `start`/`center`/`end`), `main_axis_size`, `cross_axis_size`, `expand` |
| **`Flex`** (v2.0.3) | One widget, either axis — `Row` or `Column` by `direction` | `direction` (`row`/`column`/`horizontal`/`vertical`/`x`/`y`), `children`, `spacing`, `main_alignment`, `cross_alignment`, `main_axis_size`, `cross_axis_size` |
| `Center` | Centres its child | `child`, `expand` |
| `Spacer` | Flexible empty space | `expand` (default 1) |
| `Divider` | Horizontal / vertical line | `color`, `thickness` |
| **`Scaffold`** | Page layout: app bar + body + bottom bar + FAB | `app_bar`, `body`, `bottom_bar`, `floating_action_button`, `bg_color` |
| **`AppBar`** | Top app bar | `title`, `leading`, `actions`, `bg_color`, `color`, `elevation`, `center_title` |
| **`Stack`** (v1.1) | Overlays children | `children`, `alignment` |
| **`Positioned`** (v1.1) | Absolute placement inside a Stack | `child`, `left`, `top`, `right`, `bottom` |
| **`Card`** (v1.1) | Rounded elevated surface | `child`, `bg`, `elevation`, `border_radius`, `padding`, `margin` |
| **`ListView`** (v1.1) | Scrollable list | `children`, `spacing`, `horizontal`, `padding` |
| **`GridView`** (v1.1) | Fixed-column grid | `children`, `columns`, `spacing` |
| **`PageView`** (v2.0.3) | Swipeable, snapping pages | `children`, `initial_page`, `orientation`, `peek`, `on_change` |
| **`Carousel`** (v2.0.3) | `PageView` with a peek (neighbours visible) | `children`, `peek`, `orientation` |
| **`SizedBox`** (v1.1) | Fixed-size gap / box | `width`, `height`, `child` |
| **`Padding`** (v1.1) | Pads a single child | `padding`, `child` |
| **`Drawer`** (v1.2) | Slide-in navigation panel | `children`, `header`, `width`, `side`, opened with `page.open_drawer()` |
| **`Tabs`** / `Tab` (v1.2) | Tab bar + the selected tab's body | `tabs`, `selected`, `scrollable`, `on_change` |
| **`BottomNavigationBar`** / `NavItem` (v1.2) | 2-5 bottom destinations | `items`, `selected`, `show_labels`, `on_change` |
| **`NavigationRail`** (v1.2) | Vertical rail for tablets | `items`, `selected`, `extended` |
| **`RefreshIndicator`** (v1.2) | Pull-to-refresh | `child`, `on_refresh`, `refreshing` |

#### Layout model — the one default to know

A `Row`/`Column` **fills the width by default** (Android `MATCH_PARENT`),
unlike Flutter's `mainAxisSize.min`. Inside a horizontal `Row`, several
fill-width children that are not weighted fight for the same space, so the
native renderer hugs their content instead of letting them collapse — and
`pydrud analyze` warns when you pin two of them to `"match"` explicitly.

The three idiomatic recipes:

```python
# 1. A row of columns (stat strip, card row, toolbar) — each hugs its content.
Row(children=[stat("Score"), stat("Combo"), stat("Level")])

# 2. Share the width equally — weight every child.
Row(children=[stat("Score", expand=1), stat("Combo", expand=1)])

# 3. Opt into the Flutter mental model explicitly.
Row(main_axis_size="min", children=[...])   # hug the main axis
Column(cross_axis_size="min", children=[...])  # hug the cross axis
```

`main_axis_size` / `cross_axis_size` accept `"min"`/`"max"` (Flutter), the
Pydrud spellings `"wrap"`/`"match"`, or a number. A bare `Spacer()` expands to
fill, exactly like Flutter — put it between weighted children only when you
*want* it to take a share.

### Basic

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Text` | Readable text | `value`, `size`, `color`, `weight` (100-900), `italic`, `text_align` |
| `Button` | Clickable button | `text`, `variant` (filled / outlined / text), `icon`, `bg_color`, `color`, `disabled` |
| `TextField` | Text input | `value`, `hint`, `multiline`, `password` |
| `Image` | Display image | `src` (asset or URL), `fit` |
| `Icon` | Material icon, or any 24x24 path via `Icon.svg(...)` | `name` (see `pydrud.icons.available()`), `size`, `color` |
| `Checkbox` | Checkable box | `label`, `checked` |
| `Switch` | Toggle switch; labelled switches put text left and control right | `label`, `active`, `full_width` |
| **`ProgressBar`** (v1.1) | Determinate or spinning progress | `value` (0-1), `indeterminate`, `circular`, `color` |
| **`Slider`** (v1.1) | Draggable value slider | `value`, `min`, `max`, `divisions`, `color` |
| **`RangeSlider`** (v2.0.3) | Two-thumb range slider | `start`, `end` (or `values=`), `min`, `max`, `step_size`, `divisions`, `color` |
| **`Dropdown`** (v1.1) | Option picker (spinner) | `options`, `value`, `hint` |
| **`Radio`** (v1.1) | Radio button | `label`, `value`, `group`, `selected` |
| **`ListTile`** (v1.2) | List row: leading / title / subtitle / trailing | `title`, `subtitle`, `leading`, `trailing`, `dense`, `selected` |
| **`ExpansionTile`** (v1.2) | Accordion row | `title`, `children`, `expanded`, `on_expand` |
| **`ExpansionPanelList`** (v2.0.3) | Accordion set built from `ExpansionPanel`s | `panels`, `accordion`, `open_index`, `on_change`, `spacing` |
| **`Chip`** (v1.2) | Tag / filter / choice | `label`, `variant`, `selected`, `deletable`, `on_change` |
| **`Badge`** (v1.2) | Count bubble over a child | `label` (int auto-caps at `max_count`), `child`, `color` |
| **`Avatar`** (v1.2) | Circular image / icon / initials | `source`, `initials`, `icon`, `size`, `bg` |
| **`Banner`** (v1.2) | Inline status message | `message`, `severity`, `action`, `dismissible` |
| **`SearchBar`** (v1.2) | Rounded search field | `value`, `hint`, `on_change`, `on_submit`, `on_clear` |
| **`SegmentedButton`** (v1.2) | Connected choice group | `options`, `selected`, `multi` |
| **`Rating`** (v1.2) | Star rating | `value`, `count`, `half`, `on_change` (omit → read-only) |
| **`CircularProgress`** (v1.2) | Spinner or progress ring | `value` (None = indeterminate), `size`, `stroke` |
| **`Skeleton`** (v1.2) | Shimmering loading placeholder | `lines`, `height`, `radius` |
| **`Stepper`** (v1.2) | Wizard progress | `steps`, `current`, `orientation` |
| **`Chart`** (v1.2) | Canvas line / area / bar / pie chart | `series`, `kind`, `labels`, `colors` |
| **`WebView`** (v1.2) | Embedded browser, 2-way `postMessage` | `url`, `html`, `on_load`, `on_message` |
| **`VideoPlayer`** (v1.2) | Native video surface | `source`, `autoplay`, `loop`, `controls` |
| **`Tooltip`** (v1.2) | Long-press hint | `message`, `child` |
| **`PopupMenu`** / `MenuItem` (v2.0.3) | Overflow menu anchored to its trigger (real native `PopupMenu`) | `items`, `trigger`, `icon`, `label`, `item_icons`, `on_select`; aliases `DropdownMenu`, `PopupMenuButton` |
| **`NativeView`** (v2.0.3) | Mount any Android `View` subclass by class name | `view_class`, `props`, `style` |

### Escape hatch — `NativeView`

`NativeView` is an Android-only escape hatch for the Chaquopy target. Any
native control an app needs but Pydrud does not ship — a third-party chart, a
game surface, an OEM widget — mounts by class name. No fork, no regenerated
Java. A Pydash renderer may reject it or show a fallback unless it explicitly
advertises `native_view` support:

```python
from pydrud import NativeView

NativeView("com.example.MyGauge",
           props={"value": 0.42, "unit": "%"},
           style={"width": 240, "height": 240})
```

The renderer constructs the class from `(Context)` with the app's own class
loader, then applies props either through a
`public void applyProps(org.json.JSONObject)` method (preferred) or by
mapping each prop onto a `setXxx` setter (`"value"` → `setValue`), coercing
the JSON value to the parameter type. A prop with no matching setter logs
the setter it looked for; a class that cannot be loaded logs the reason and
renders an empty box rather than taking the frame down. The view instance is
reused across updates, so a custom view keeps its state — a changed class
name is the one case that rebuilds it.

### Accessibility (v2.0.3)

Three things make an app usable by everyone, and Pydrud now checks all three.

**Screen-reader labels.** Any widget takes `semantics=`, which becomes the
Android view's `contentDescription`. TalkBack reads it in place of the
widget's own text, so an icon-only control is announced instead of
"unlabelled button" — and it works on every supported API level:

```python
IconButton(icon=Icons.SAVE, semantics="Save the document")
Image("chart.png", semantics="Revenue, up 12% quarter on quarter")
```

The label updates live: change it and the next `page.update()` re-announces
it, including when the label is removed.

**Contrast.** `Colors.contrast(fg, bg)` returns the WCAG 2.1 ratio and
`Colors.meets_contrast(fg, bg)` the AA verdict — 4.5:1 for normal text, 3:1
for large text (≥ 18 pt, or ≥ 14 pt bold). `pydrud analyze` applies the same
check to every literal text/background pair in your source, resolving
`Colors.X` tokens as well as hex strings, and names the fix:

```
src/app/home.py:42  Low contrast: #FFFFFFFF on #FFEFEFEF is 1.1:1 —
WCAG AA needs 4.5:1 for normal text. Try Colors.on('#FFEFEFEF') for a
readable foreground.
```

**Touch targets.** `pydrud analyze` also warns when an interactive widget is
pinned below the 48 dp minimum (WCAG 2.5.5 / Material):

```python
IconButton(icon=Icons.CLOSE, style={"width": 24, "height": 24})  # flagged
```

The stock buttons already pad themselves to 48 dp; the check only fires when
an explicit `width`/`height` overrides that padding.

### Paging and ranges (v2.0.3)

**`RangeSlider`** selects a pair. `values=(lo, hi)` is clamped to `[min,
max]` and ordered, so `RangeSlider(80, 20)` is the same as
`RangeSlider(20, 80)`. `on_change` receives `{"values": [lo, hi]}`:

```python
price = RangeSlider(20, 80, min=0, max=200, step_size=5, key="price",
                    on_change=lambda e: page.update())
```

**`PageView`** swipes between full-size pages, one child per page, snapping
to each. `on_change` receives `{"index": page}`. It fills both axes, so give
it a bounded parent:

```python
PageView([
    OnboardingSlide(title="Welcome"),
    OnboardingSlide(title="Fast"),
], initial_page=0, on_change=lambda e: goto(e["index"]))
```

**`Carousel`** is the same widget with carousel defaults — a 24 dp `peek`
that leaves the neighbouring pages visible:

```python
Carousel([PosterCard(p) for p in posters], peek=24)
```

### Menus (v2.0.3)

**`PopupMenu`** is an overflow menu anchored to its trigger — a real
`android.widget.PopupMenu`, not a WebView or a hand-drawn overlay. Tapping
the trigger opens it; choosing an entry fires `on_select` with the entry's
`index` and `value`:

```python
PopupMenu(
    [MenuItem("Rename", icon=Icons.EDIT),
     MenuItem("Duplicate", icon=Icons.COPY),
     MenuDivider(),
     MenuItem("Delete", icon=Icons.DELETE, danger=True)],
    on_select=lambda e: delete() if e["value"] == "Delete" else None,
)
```

Entries accept a bare label, a `(label, icon)` tuple, a dict, or a full
`MenuItem`. A `MenuItem` can carry an `icon`, a `value` (what the event
reports — the label by default), `enabled`, `checkable`/`checked`, `danger`
(an error-tinted icon) and a nested `submenu`. `MenuDivider()` separates two
groups.

The trigger defaults to a 48 dp overflow (⋮) button; pass `label=` for a text
button or `trigger=` to anchor the menu to your own widget. `DropdownMenu`
and `PopupMenuButton` are aliases.

### Flutter-style presets and compositions

These constructors reuse the native primitives above, so they add ergonomics
without adding protocol-only or WebView-backed controls.

| Area | Widgets |
|------|---------|
| Flex and constraints | `Expanded`, `Flexible`, `Align`, `ConstrainedBox`, `LimitedBox`, `Gap` |
| Box and scrolling | `ColoredBox`, `DecoratedBox`, `VerticalDivider`, `SingleChildScrollView`, `Wrap`, `ButtonBar` |
| Typography | `Heading`, `Title`, `Subtitle`, `Label`, `Caption`, `Link` |
| Images | `NetworkImage`, `AssetImage`, `CircleImage`, `Placeholder` |
| Selection | `SwitchListTile`, `CheckboxListTile`, `RadioListTile`, `ActionChip`, `ChoiceChip` |
| Common controls | `CircleAvatar`, `BackButton`, `CloseButton`, `MenuButton`, `SectionHeader` |
| App states and cards | `EmptyState`, `ErrorState`, `LoadingState`, `InfoCard`, `StatCard` |
| Settings and forms | `SettingsTile`, `NavigationTile`, `FormSection` |

### Events

All interactive widgets support callback chaining:

```python
widget.on_click(callback)      # Any widget — callback(data) where data is a dict
widget.on_long_press(callback) # Any widget
widget.on_change(callback)     # TextField, Checkbox, Switch, Slider, RangeSlider, Dropdown, PageView
widget.on_submit(callback)     # TextField (IME action)
widget.on_focus(callback)      # Focus gain / loss
widget.on("select", callback)  # PopupMenu / DropdownMenu ({"index", "value"})
widget.on("scroll", callback)  # Any event name
```

### Gestures (v1.2)

```python
from pydrud import GestureDetector, InkWell, Dismissible

GestureDetector(
    child=photo,
    on_double_tap=lambda e: zoom_in(),
    on_swipe_left=lambda e: next_photo(),
    on_scale=lambda e: set_zoom(e.data["scale"]),
)

InkWell(child=card, on_click=open_item)            # Material ripple
Dismissible(child=row, direction="end",            # swipe to delete
            background=Colors.ERROR, on_dismiss=delete_row)
```

Only the gestures you subscribe to are detected and transmitted, so scrolling
a long list stays silent on the wire.

### Animations (v1.2)

```python
from pydrud import Animation, AnimatedContainer, FadeIn, Hero

AnimatedContainer(child=body, height=expanded and 240 or 80,
                  bg=Colors.SURFACE, animation=Animation.springy())

FadeIn(child=Text("Welcome"), animation=250)
Hero("cover", child=Image(url))          # shared element across routes
Text("Pulse").animate(Animation.fast(), opacity=0.4)
```

Animated widgets tween towards their new values on the device
(`ValueAnimator` / `ViewPropertyAnimator`) instead of snapping.

### Custom painting (Canvas)

`Canvas` records drawing commands in Python and replays them in a real
`View.onDraw`, so gauges, sparklines, signatures and game boards are
drawn by Skia — no bitmap transfer, no WebView.

```python
from pydrud import Canvas, Colors

def gauge(value):
    canvas = Canvas(height=160)
    canvas.circle(0.5, 0.5, 0.45, color=Colors.SURFACE_VARIANT)
    canvas.arc(0.5, 0.5, 0.45, start=135, sweep=270 * value,
               color=Colors.PRIMARY, width=14, cap="round")
    canvas.text(f"{value:.0%}", 0.5, 0.55, size=28, align="center",
                weight="bold")        # "bold"/"medium"/… or 400/700
    return canvas
```

Pass `on_draw` to repaint on every rebuild. It is called with as many
arguments as it declares, so pick whichever shape suits the drawing:

```python
Canvas(on_draw=lambda c: c.circle(0.5, 0.5, 0.4))             # fractions
Canvas(on_draw=lambda c, size: c.rect(0, 0, size.width, 20))  # a Size
Canvas(units="px", on_draw=lambda c, w, h: c.line(0, 0, w, h))  # dp
```

`canvas.size` (`.width` / `.height`, dp) is available outside `on_draw`
too; it resolves `"match"` and percentage styles against the live device
metrics, and `canvas.measure(w, h)` pins exact values. A painter that
raises is logged, keeps whatever it drew and leaves the exception on
`canvas.last_draw_error` — one bad frame cannot take down the rebuild.

### Forms & validation (v1.2)

```python
from pydrud import Form, FormField, TextField, required, email, min_length

form = Form(
    FormField("email", TextField(""), label="Email",
              validators=[required(), email()]),
    FormField("password", TextField("", password=True), label="Password",
              validators=[required(), min_length(8)]),
    on_submit=lambda values: sign_in(**values),
)

Button("Sign in", on_click=lambda e: form.submit())   # validates first
form.set_error("email", "Already registered")         # server-side errors
```

Validators: `required`, `min_length`, `max_length`, `email`, `phone`, `url`,
`numeric`, `between`, `pattern`, `matches` (cross-field), `custom`.

### Native services and runtime permissions (v2.0.2)

The generated Chaquopy Android target implements the native-service examples
below. In Pydash preview, service requests are sent only when the connected
renderer explicitly advertises the required capability; otherwise Pydrud
returns a completed `Result` failure and does not put the request on the wire.

On Android, Pydrud separates **manifest declaration**, **user consent**, and **native use**:

1. Enable the smallest capability bundle your feature needs.
2. Run `pydrud sync` so Android receives the matching manifest entries.
3. Ask the user at the moment the feature is needed.
4. Check the result before opening the camera, contacts, microphone, etc.

Do not request every permission at startup. Android and Google Play expect a
clear, user-visible reason for each dangerous permission. `pydrud capabilities
list --all` shows the supported production-safe bundles.

```bash
# Build-time declaration (run from the project directory)
pydrud capabilities add microphone contacts
pydrud capabilities add notifications files
pydrud permissions add camera        # dangerous permissions stay explicit
pydrud sync

# Inspect enabled and available bundles
pydrud capabilities list
pydrud capabilities list --all
```

`files`, `downloads`, and `share` use Android's user-mediated system intents;
they do not request broad storage access. Avoid copying old internet permission
lists into a manifest: `BIND_*`, `MANAGE_*`, `INTERNAL_*`, `DUMP`, `INSTALL_*`
and similar permissions are reserved for the Android system or device-owner
apps and will not work for a normal Play Store application.

#### Allow / Don't allow permission popups

`page.permissions.request(...)` opens the native Android permission dialog. The
user sees Android's own **Allow** / **Don't allow** controls; Pydrud does not
fake or bypass that security prompt. The result is a mapping from the full
Android permission name to a boolean:

```python
from pydrud import Button, Text, Column, CameraPreview


def request_camera(page):
    # This is the real Android Allow / Don't allow popup.
    page.permissions.request("camera").then(
        lambda grants: start_camera(page, grants)
    ).catch(lambda error: page.dialog.alert(
        f"Camera permission failed: {error}"
    ))


def start_camera(page, grants):
    if grants.get("android.permission.CAMERA", False):
        page.add(CameraPreview(key="camera"))
    else:
        # The user selected Don't allow. Explain the feature and offer retry.
        page.dialog.confirm(
            "Camera access is needed to scan QR codes. Open app settings?",
            title="Permission needed",
            ok="Open settings",
            cancel="Not now",
        ).then(lambda open_settings: (
            page.permissions.open_settings() if open_settings else None
        ))

page.add(Button("Scan QR code", on_click=lambda event: request_camera(page)))
```

For multiple permissions, request them together only when the feature needs
them:

```python
page.permissions.request("camera", "microphone").then(
    lambda grants: print(grants)
)
```

You can inspect permission state without opening a popup. The state is
`granted`, `denied`, or `permanently_denied`:

```python
page.permissions.status("contacts").then(print)
page.permissions.check("contacts").then(print)  # True / False

# Safe synchronous check from a worker/guard; never opens a dialog.
if page.permissions.is_granted("camera"):
    open_scanner()
```

If Android reports `permanently_denied`, show an explanation and let the user
open the app's system settings. Never repeatedly prompt after a permanent
denial:

```python
page.permissions.status("notifications").then(
    lambda state: page.permissions.open_settings()
    if state == "permanently_denied" else None
)
```

Android 13+ requires `notifications` to be declared before posting runtime
notifications. The notification itself is separate from the permission
popup:

```python
page.notifications.create_channel(
    "updates", "App updates", importance="high"
).then(lambda _: page.notifications.show(
    "Sync complete", "Your files are ready", id=42,
    channel="updates", route="/files"
))
```

The system permission popup is controlled by Android. Use `dialog.confirm`
only for an explanatory pre-permission screen; the final Allow / Don't allow
decision must always come from `page.permissions.request`.

```python
page.dialog.confirm(
    "Allow notifications so we can tell you when downloads finish?",
    title="Enable notifications",
    ok="Continue",
    cancel="Not now",
).then(lambda proceed: (
    page.permissions.request("notifications") if proceed else None
))
```

#### Available native services

```python
page.dialog.confirm("Delete?").then(lambda yes: delete() if yes else None)
page.dialog.prompt("New name", value=current).then(rename)

# Date / time pickers. min/max bound the selectable range; all arguments are
# validated in Python, so a typo raises instead of silently doing nothing.
page.dialog.date().then(set_due_date)
page.dialog.date(min="1900-01-01", max="2026-12-31").then(set_birthday)
page.dialog.time(initial="09:30", use_24h=False).then(set_alarm)

# Modal bottom sheet — resolves the chosen index, or -1 when cancelled.
page.dialog.bottom_sheet(["Camera", "Gallery"],
                         icons=["camera", "image"]).then(pick_source)

page.storage.set("profile", {"name": "Ada"})
page.storage.get("profile", default={}).then(render_profile)

# Declare first: `pydrud permissions add camera` then `pydrud sync`.
page.permissions.request("camera").then(lambda granted: ...)
page.permissions.status("camera").then(print)  # granted / denied / permanently_denied
page.files.pick_image(camera=True).then(upload)

# Native Results are also awaitable in async UI callbacks.
async def ask_camera(event):
    grants = await page.permissions.request("camera")
    if grants["android.permission.CAMERA"]:
        page.add(QRScanner(on_scan=lambda code: print(code.value)))
```

Use `CameraPreview(fallback=..., auto_request_permission=True)` when you want
a custom no-camera state. `Image("assets/mark.svg")` and `SvgPicture("assets/mark.svg")`
render vector SVGs directly. On Android 12+, call `Theme.system()` before the
first frame (or follow it with `app.apply_theme()`) to use the wallpaper-derived
Material You palette.

```python
page.clipboard.copy("pydrud.dev")
page.share.text("Built with Pydrud!")
page.notifications.show("Done", "Your export is ready", route="/exports")
page.location.current().then(lambda pos: print(pos["lat"], pos["lon"]))
page.device.info().then(print)
page.haptics.impact("medium")
```

Every call returns a `Result`: use `.then()` / `.catch()` on the UI thread, or
`.wait()` inside a `page.run_task()` worker. Results always settle — a missing
bridge or a cancelled dialog fails fast instead of hanging.

### HTTP & background work (v1.2)

```python
page.http.configure(base_url="https://api.example.com").bearer(token)
page.http.get("/posts", params={"page": 2}).then(render).catch(show_error)
page.http.post("/posts", json_body={"title": "Hi"}, retries=2).then(done)

page.run_task(heavy_sync)              # thread pool; async def also works
page.run_on_ui(lambda: page.update())  # hop back before touching widgets
timer = page.every(1.0, tick)          # repeating timer; timer.cancel()
```

### App-level state (v1.2)

```python
from pydrud import Store, Computed, ReactiveList

store = Store({"todos": [], "filter": "all"})

@store.action
def add_todo(state, text):
    return {"todos": state["todos"] + [text]}

visible = Computed(lambda: [t for t in store["todos"] if matches(t)],
                   sources=[store])
store.select("todos").listen(lambda todos: print(len(todos)))

app.bind(store)        # any change re-renders
store.undo()           # time travel, for free
```

### Theme, colours and icons (v1.1)

```python
from pydrud import Colors, Icons, Theme, Text, Icon

Text("Hello", color=Colors.PRIMARY)
Text("Dim",   color=Colors.with_opacity(Colors.TEXT, 0.5))
Icon(Icons.SETTINGS)

Theme.dark()            # switch the default palette
Theme.apply(primary="#FF0EA5E9")
```

### Scoped theming, text roles and extensions (v2.0.3)

Pydrud resolves theme values at build time, so `Theme.scope()` restyles the
widgets you construct inside it and restores the previous values on exit —
including on exception, and when nested. This is Flutter's
`Theme(data: …)` without a per-frame theme lookup.

```python
from pydrud import Text, TextTheme, Theme, ThemeExtension, Tokens

# Per-subtree overrides — colour roles and design tokens both work.
with Theme.scope(primary="#FFEC4899", radius_card=4):
    Card(child=Text("Scoped", color=Theme.primary))
# Theme.primary and Tokens.radius_card are back to normal here.

# The Material 3 type scale — 15 roles, any spelling.
Text("Title", style=TextTheme.title_large)
Text("Body",  style=TextTheme.BODY_MEDIUM)
Text("Tinted", style=TextTheme.body_medium.with_(color="#FFEF4444"))

# App-specific tokens that travel with the theme.
Theme.extend(ThemeExtension("brand", accent="#FF22D3EE", hero_radius=28))
brand = Theme.extension("brand")
Container(border_radius=brand.hero_radius, bg=brand.accent)
```

Runtime light/dark switching is a single call and repaints native styles
*and* Python-resolved colours together:

```python
page.set_theme_mode("dark")      # light / dark / system
```

The icon vocabulary is available to code, tests and tooling:

```python
from pydrud import icons

icons.has("rocket_launch")       # True  (a shipped alias)
icons.available()                # every supported name
icons.suggest("rocket_lunch")    # ['rocket_launch', 'rocket', …]
icons.canonical("rocket_launch") # 'rocket'
```

### Composite widgets — `pydrud.components` (v2.0.3)

`pydrud.components` is a pure-Python library built only from the primitives,
so it diffs, keys and animates like any built-in and needs no native code.
Copy the pattern to grow your own catalogue.

```python
from pydrud.components import (SectionLabel, StatBlock, StatRow,
                               Toolbar, GlassPanel, InfoRow, FormRow,
                               ProgressRow, PillButton, EmptyPlaceholder)

Column(children=[
    SectionLabel("Today", action=Button("See all", variant="text")),
    StatRow([
        StatBlock("Steps", "8,412", icon="trending_up"),
        StatBlock("Goal",  "78%",   icon="verified"),
    ]),
    ProgressRow("Sync", 0.42),
    EmptyPlaceholder("No results", message="Try another search",
                     action="Retry", on_action=retry),
])
```

### Page commands (v1.1)

```python
page.toast("Saved!")
page.snack_bar("Deleted", action="UNDO")
page.set_title("Inbox")
page.vibrate(30)                       # enable with `pydrud capabilities add haptics`
page.set_system_ui(status_bar_color="#FF6366F1", icon_brightness="light")
page.close()                           # finish the activity
```

### Page commands (v1.2)

```python
page.update(widget)                    # push one mutated subtree
page.open_drawer(); page.close_drawer()
page.scroll_to("row_42"); page.focus("email")
page.hide_keyboard(); page.keep_awake(True)
page.set_orientation("portrait"); page.fullscreen(True)
page.set_theme_mode("system")          # light / dark / system
page.end_refresh()                     # stop a RefreshIndicator spinner
```

### Theming with Material You (v1.2, extended in v1.4)

```python
from pydrud import ColorScheme, Colors, Theme, Typography

Theme.seed(Colors.INDIGO)               # rebuild everything from one colour
Theme.dark()                            # same brand, dark surfaces
Theme.use(ColorScheme.from_seed(Colors.INDIGO, dark=True))   # explicit scheme
Theme.scheme.primary_container          # 13 M3 roles
Theme.outline, Theme.text_secondary     # the roles widgets use most
Typography.scale(1.2)                   # accessibility-scaled type ramp

page.set_theme(Colors.TEAL, dark=True)  # re-theme a running app
app.apply_theme()                       # after changing Theme directly
```

The palette is mirrored to the native renderer, so Android's own ripples,
switches, text-selection handles, dialogs and system bars follow it too.

### Testing your app (v1.2)

```python
from pydrud.testing import AppTester

def test_login():
    with AppTester(main) as app:
        app.answer("dialog", True)              # stub the native dialog
        app.type_in("email", "ada@example.com")
        app.tap("Sign in")                      # by key *or* visible text
        app.wait_for("Welcome back")            # ride out a late rebuild
        assert app.shows("Welcome back")
        assert app.exists("sign_out")           # no waiting, just a check
        assert app.requested("prefs_set")["key"] == "token"
```

Interactions settle before they return, and lookups retry for a moment,
so a tap that triggers navigation, a timer or an async handler does not
have to be followed by a hand-written sleep.

### Styling

```python
Style().bg("#FFFFFF").padding(EdgeInsets.all(16)).border_radius(8).elevation(4).build()
```

**All style properties:**

| Prop | Type | Example |
|------|------|---------|
| `bg` | Hex color | `"#FF6366F1"` |
| `opacity` | float 0-1 | `0.5` |
| `width` / `height` | int or `"match"` | `200` or `"match"` |
| `padding` / `margin` | `EdgeInsets` | `EdgeInsets.all(16)` |
| `borderRadius` | int | `12` |
| `font.size` | int (sp) | `16` |
| `font.color` | Hex color | `"#FF1F2937"` |
| `font.weight` | int 100-900 | `700` |
| `font.italic` | bool | `true` |
| `alignment` | `Alignment` constant | `Alignment.center` |
| `elevation` | int (dp) | `4` |
| `visible` | bool | `true` / `false` |
| `tooltip` | string | `"Save changes"` |

### PSS Stylesheets

Pydrud Style Sheets (PSS) let you keep presentation rules out of Python while
using the same platform-neutral style vocabulary. Files named `*.pss` under
`src/` are discovered automatically; stylesheet edits rebuild styles without
re-executing Python modules.

```python
Button("Save", key="save", class_="primary")
```

```pss
Button { padding: { all: 12 }; }
.primary { color: white; bg: #4F46E5; }
#save { font: { size: 16, weight: 600 }; }
```

PSS supports widget-type, `.class`, explicit-key `#id`, compound, comma-list,
descendant and direct-child selectors. Class names are supplied with the
Python-only `class_=` argument (a string or a sequence); generated keys do not
match `#id` selectors. Matching declarations cascade by CSS-like specificity
and source order, and a widget's inline `style=` values override stylesheet
values. The `class_` metadata and legacy `class_*` markers are never serialized
to the renderer or added to native-ignored-property metadata.

Property names are normalized to Pydrud's shared schema (`text-align` becomes
`textAlign`); use Pydrud keys such as `bg`, not browser CSS properties such as
`background-color`. Scalar values, CSS-style bare names, and nested object/list
values are supported. Malformed edits report source-located diagnostics and
keep that file's last known-good rules active. Creating, editing, moving, or
deleting a `.pss` file triggers a style rebuild without re-executing Python
modules.
See [PSS Stylesheets](docs/PSS_STYLESHEETS.md) for the selector, cascade,
value, diagnostics, and reload contract.

---

## Responsive (v1.5)

Pydrud reads the **window metrics** advertised by the connected renderer and
re-reads them whenever they change — rotation, resize, split screen, font
scale, keyboard and insets. Each change refreshes `MediaQuery`, runs your
listeners and re-renders the tree. Android supplies its live device metrics;
a Pydash preview renderer supplies its own metrics through the same neutral
runtime API.

### MediaQuery — every window metric the renderer reports

```python
from pydrud import MediaQuery

MediaQuery.width            # window width in dp
MediaQuery.height
MediaQuery.width_px         # physical resolution
MediaQuery.density          # px per dp          MediaQuery.dpi
MediaQuery.orientation      # "portrait" | "landscape"
MediaQuery.device_type      # "phone" | "tablet" | "desktop" | "tv" | "watch"
MediaQuery.breakpoint       # "compact" | "medium" | "expanded" | "large" | "xlarge"
MediaQuery.shortest_side    # the sw600dp test, stable across rotation
MediaQuery.diagonal         # inches        MediaQuery.refresh_rate
MediaQuery.text_scale       # the user's font-size preference
MediaQuery.dark             # system dark mode

MediaQuery.safe_area()      # {"top": 48, "bottom": 24, "left": 0, "right": 0}
MediaQuery.viewport()       # usable size after insets and the keyboard
MediaQuery.resolution()     # (1080, 2400)
MediaQuery.info()           # immutable snapshot (attribute access)
MediaQuery.of()             # the same as a plain dict

MediaQuery.matches(min_width=600, orientation="landscape", device="tablet")
MediaQuery.at_least("expanded")   # this size class or wider
MediaQuery.keyboard_visible()
```

React to changes:

```python
stop = MediaQuery.listen(lambda info: print(info.width, info.breakpoint))
stop()                                  # unsubscribe

@app.on_metrics_change                  # the same thing, on the App
def _(info): ...
```

### Breakpoints — customisable size classes

```python
from pydrud import Breakpoints

# Defaults (dp): compact <600, medium ≥600, expanded ≥840, large ≥1200, xlarge ≥1600
Breakpoints.configure(medium=620, expanded=900)
Breakpoints.reset()
```

### Responsive — sizing helpers

```python
from pydrud import Responsive

Responsive.text(16)      # font size      Responsive.sp(16)   # + system font scale
Responsive.w(48)         # width          Responsive.h(48)    # height
Responsive.padding(24)   # padding        Responsive.spacing(12)
Responsive.radius(12)    # corners        Responsive.icon(24)

Responsive.wp(50)        # 50% of the screen width, in dp
Responsive.hp(33)        # 33% of the height
Responsive.vw(50), Responsive.vh(50)      # viewport units (insets excluded)
Responsive.sw(80)        # % of the shortest side
Responsive.to_px(16), Responsive.px(48)   # dp ⇄ physical pixels
```

Scaling is **clamped to 0.9–1.2x** of the 360dp baseline and is based on
the *shortest* side, so rotating a phone does not inflate every font.
Tune it once at startup:

```python
Responsive.configure(min_factor=0.95, max_factor=1.4, basis="diagonal")
Responsive.configure_reset()
```

Layout decisions come from breakpoints, not from scaling:

```python
Responsive.breakpoint()                             # current size class
Responsive.is_phone(), Responsive.is_tablet(), Responsive.is_landscape()
Responsive.value(compact=1, medium=2, expanded=3)   # pick per size class
Responsive.value(phone=16, tablet=32, desktop=48)   # device aliases
Responsive.value(compact=8, landscape=16)           # orientation override
Responsive.columns(min_width=180, max_columns=4)    # how many cards fit
Responsive.grid(min_width=180)                      # (columns, item_width)
Responsive.gutter()                                 # page padding per size
Responsive.content_width(560)                       # cap long line lengths
```

### Responsive widgets

```python
from pydrud import (AdaptiveLayout, LayoutBuilder, ResponsiveBuilder,
                    ResponsiveGrid, SafeArea, ShowWhen)

ResponsiveBuilder(lambda s: Text(f"{s.width}x{s.height} · {s.breakpoint}"))

LayoutBuilder(lambda c:                  # Flutter's builder, real constraints
    Row(children=cards) if c.max_width >= 600 else Column(children=cards))
LayoutBuilder(lambda c: GridView(columns=c.columns(180), children=cards))
# c.max_width / c.max_height / c.is_tablet / c.breakpoint / c.matches(...)

AdaptiveLayout(                       # a different layout per size class
    compact=Column(children=cards),
    medium=Row(children=cards),
    expanded=Row(children=[rail, body]),
    landscape=WideLayout,             # callables are built lazily
)

ResponsiveGrid(children=cards, min_item_width=180)   # columns follow the screen
ShowWhen(Sidebar(), min_width=600, otherwise=MenuButton())
SafeArea(child=body, top=False)       # real cutout / gesture-bar insets
```

### Conditional rendering

`ShowWhen` asks whether the *window* is big enough; `Visible` and `Hidden`
ask whether the *app* is in the right state. The condition is re-read
every time the tree is serialised, so the usual `app.bind(...)` /
`page.update()` flow is all it takes:

```python
from pydrud import Visible, Hidden, State

logged_in = State(False)

Visible(Dashboard(), when=logged_in)                  # State
Visible(Spinner(), when=is_loading, otherwise=Results())
Visible(Badge("3"), when=lambda: cart.count > 0)      # callable
Hidden(CheckoutButton(), when=cart_is_empty)          # the inverse
ShowWhen(Tips(), min_width=600, condition=show_tips)  # size *and* state
```

A bool, `State`, `Computed`, `Selector`, `ReactiveList` (truthy when
non-empty) or a callable all work, and `when=`, `condition=` and
`visible=` are the same parameter under three names. When the condition
is false the `otherwise` widget renders — or a zero-sized placeholder, so
the diff engine can swap the real widget back in without rebuilding the
page.

### Responsive units in styles

Any width or height accepts responsive units, resolved natively against
the current window:

```python
Container(style={"width": "50%"})     # half the window on this axis
Container(style={"width": "80%w", "height": "30%h"})
Container(style={"width": "60%s"})    # % of the shortest side
Container(style={"height": "40vh", "width": "120px", "minWidth": "16dp"})
Column(style={"maxWidth": 640})       # capped and centred on big screens
```

**How it works**

1. Android sends `ready` on connect and a `metrics` event on every window
   change (`onConfigurationChanged` + the insets listener, debounced).
2. `MediaQuery.update()` re-derives orientation, size class, device type
   and safe area, syncs `Responsive` and notifies listeners.
3. The app re-renders, so `ResponsiveBuilder`, `AdaptiveLayout`,
   `Responsive.value()` and percent units all produce fresh values and
   the diff engine patches only what moved.

> With no device connected (tests, CI) the metrics default to a 360x640
> phone and nothing scales.

---

## Bottom navigation and tabs (v1.5)

Pydrud draws both surfaces itself, so every property really changes the
pixels — nothing is locked behind a Material theme attribute.

```python
from pydrud import BottomNavigationBar, NavItem, Icons

BottomNavigationBar(
    [NavItem("Home",   icon=Icons.HOME),
     NavItem("Search", icon=Icons.SEARCH),
     NavItem("Cart",   icon=Icons.CART, badge=3, badge_color="#FFEF4444"),
     NavItem("Me",     icon=Icons.PERSON, active_icon=Icons.SETTINGS)],
    selected=0, on_change=lambda e: go(e.value),

    height=68, bg="#FFFFFFFF", elevation=12, radius=24,       # surface
    floating=True, margin=12, border_color="#14000000",
    top_divider=False,

    indicator="pill",                                          # pill | circle
    indicator_color="#1A6366F1",                               # line | dot | none
    indicator_width=64, indicator_height=34,

    selected_color="#FF6366F1", unselected_color="#FF9CA3AF",  # icons + labels
    icon_size=24, selected_icon_size=26,
    label_behavior="selected",            # always | selected | never
    label_size=11, selected_label_size=12, bold_selected=True,

    type="fixed",                         # fixed | shifting
    ripple=True, ripple_color="#1A6366F1",
    animate=True, duration=180, haptic=True,
)
```

Helpers: `bar.select(2)`, `bar.select_route("/cart")`, `bar.badge(2, 7)`,
`bar.current`. `NavigationBar` is an alias, and `native=True` falls back
to Android's stock `BottomNavigationView`.

The bar draws its own gesture inset and floating margin, so it looks the
same on gesture-navigation and three-button devices, and selecting a
destination is a one-property patch instead of a rebuild.

```python
from pydrud import Tabs, Tab      # TabBar is an alias

Tabs(
    [Tab("Today", icon=Icons.HOME, content=today),
     Tab("Week",  icon=Icons.CALENDAR, content=week, badge=2)],
    mode="scrollable",                    # fixed | scrollable
    indicator="pill", indicator_color="#FF6366F1",
    indicator_height=32, indicator_radius=999,
    indicator_size="label",               # label | tab | full
    label_color="#FF111827", unselected_label_color="#FF6B7280",
    label_size=14, selected_label_size=14, bold_selected=True,
    icon_position="start", icon_size=18,
    bg="#FFFFFFFF", tab_height=52, tab_min_width=96, align="fill",
    divider=True, ripple=True, animate=True, duration=220,
)
```

---

## set_system_ui (v1.0.1)

Dynamically control the Android status bar from Python:

```python
# Light status bar (dark icons on white background)
page.set_system_ui(status_bar_color="#FFFFFFFF", icon_brightness="dark")

# Dark status bar (white icons on colored background)
page.set_system_ui(status_bar_color="#FF6366F1", icon_brightness="light")
```

---

## Architecture

Pydash preview and the Chaquopy APK use different connection setup, but share
the transport-neutral widget tree, keyed diff engine, desired/confirmed render
identity, and protocol-v2 transactions:

```text
Pydash default (`pydrud dev`)
  host Python App  <-- token-authenticated preview handshake --> renderer
        source, state, event handlers stay on the host
        render_transaction / ACK-NACK use renderer protocol v2

Chaquopy opt-in (`pydrud run` / APK)
  embedded Python App ──existing local NDJSON bridge──► generated Android BridgeService
                                                         └─ native Android Views
```

The Pydash handshake is a separate preview-protocol layer; after pairing it
carries the existing `render_transaction` v2 contract. The Android bridge's
existing commands and transaction behavior remain the Android path. Neither
transport changes the meaning of `TreeDiff`, keyed patches, or render
revisions. See [Preview Protocol v1](docs/PREVIEW_PROTOCOL.md) for the
host-preview handshake and reconnect behavior.

### Data Flow

1. **`App(target=main)`** calls the builder and creates a widget tree; PSS rules
   are resolved on the Python side before serialization.
2. **`page.update()`** builds the desired tree and computes keyed patches from
   the last renderer-confirmed tree, not merely the last tree sent.
3. Python sends one **`RenderTransaction`**: a full snapshot or a keyed patch
   batch with a strictly increasing revision and confirmed base revision.
4. The renderer applies the transaction atomically and ACKs that revision.
   Only then does Python advance its confirmed snapshot; a NACK triggers a
   full resynchronizing snapshot.
5. User events travel back through the same renderer bridge to Python
   callbacks; state changes request the next render transaction.

Renderer capabilities are explicit, optional data. In Pydash mode, a service
request is not sent unless the connected client advertises it; unsupported
widgets are replaced by a visible `Text` fallback when the client explicitly
provides a widget catalogue. These checks do not change the core protocol or
assume a particular client platform.

### Source layout

The Python side is organised into small, single-purpose modules — no file in
the repository exceeds 1,000 lines.

| Package | Contents |
|---------|----------|
| `pydrud/widgets/` | The widget library: `basic`, `layout`, `forms`, `advanced`, `canvas`, `gestures`, `animation`, `conditional`, `responsive`, `presets` — plus `material/` (Material 3 components split into focused modules) and `theme/` (colour maths, `Theme`, `Typography`, `Icons`, `Tokens`) |
| `pydrud/runtime/` | `App`, `Page` and the bridge event loop, split into focused mixins (`app`, `page`, `navigation`, `_render`, `_bridge`, `_lifecycle`, `_modules`, `_hotreload`) |
| `pydrud/core/` | Platform-neutral engine: `diff`/`RenderTransaction`, `state`/`store`/`controllers`, `bridge`/`protocol`, `preview`, `responsive`, `watcher`, and `styles/` (PSS schema, lexer, parser, selectors and resolver) |
| `pydrud/platforms/android/` | Android-only renderer profile, on-device development server and logcat adapter; not imported by the neutral PSS or protocol core |
| `pydrud/services/` | `http` (async client) and `native/` — `Dialogs`, `Storage`/`FilePicker`, `Clipboard`, `Share`, `Permissions`, `Notifications`, `Location`, `DeviceInfo`, `Haptics`, `Push`, `Shortcuts`, `Secure`, `Background`, `Camera`, `Sensors`, `Bluetooth`, `Nfc`, `Biometrics`, `Audio` |
| `pydrud/commands/` | The CLI: `project/` (scaffold, sync, bundle, templates, config), `builder`, `analyzer`, `devrunner`, `doctor`, `docs`, `release`, `inspector` |
| `pydrud/android/templates/` | Jinja2 build-time templates for the optional Chaquopy Android project (`*.java.j2`, Gradle, manifest, resources) |

### Native renderer (Chaquopy)

The optional generated Java renderer follows the same discipline — a thin
orchestrator plus cohesive collaborator classes:

| Generated class | Responsibility |
|-----------------|----------------|
| `ViewFactory` | Orchestrator — shared view/node maps, public API, collaborator wiring |
| `BuiltinViews` | `createView` dispatch and every built-in widget factory |
| `ViewStyler` | `applyStyle`, borders, gradients, typography, dimension helpers |
| `LayoutEngine` | Linear/grid layout params, spacing, child attach/removal |
| `TreePatcher` | `applyPatch` / `updateProps`, parent indexing |
| `EventBinder` | Click/change/submit binding, popup menus, touch feedback |
| `ImageLoader` | Managed image pipeline — decode pool + LRU bitmap cache |
| `NativeViewFactory` | User-supplied `NativeView` classes — load, create, apply props |
| `ViewAnimator` | Entrance animations and animated prop changes |
| `MaterialViews` + `MaterialNavigationViews` | Material 3 components (dispatch point + navigation family) |
| `BridgeService` | TCP server — NDJSON protocol, transactional renders (port 8595) |
| `PydrudTheme` | The generated design system on the Java side |

---

## Android project configuration

This section applies once a project has the Android platform — added with
`pydrud init android` (preview shell by default, `--standalone` for embedded
Python) or scaffolded directly with `pydrud create <name> --runtime
chaquopy`. Pure Pydash projects do not have an Android project or use the
Android fields in `pydrud.yaml`.

For Chaquopy projects, `pydrud.yaml` is the system-level source of truth for
generated Android files. Change it and run `pydrud sync`; the command updates
the Java package, activity, manifest, Gradle build files, wrapper, native
theme and generated Python metadata together. Changing `app_name` or
`package` migrates the generated Java sources rather than retaining the old
identity discovered under `android/`.

```yaml
app_name: "Taskflow"
package: "com.example.taskflow"
runtime: "chaquopy"
standalone: true
version_code: 2
version_name: "1.1.0"
min_sdk: 24
target_sdk: 36
compile_sdk: 36
ndk: "28.2.13676358"
abi_filters: ["arm64-v8a", "armeabi-v7a", "x86_64"]
assets_dir: "assets"
scheme: "taskflow"
app_links_host: ""
permissions:
  - "CAMERA"
capabilities:
  - "haptics"
  - "notifications"
firebase: false
shrink: false
python_version: "3.11"
framework_version: "2.1.0"
protocol_version: 2
chaquopy_version: "17.0.0"
agp_version: "8.13.2"
gradle_version: "8.14.4"
```

`capabilities:` is for generated feature bundles. Supported bundles include
`camera`, `microphone`, `location`, `contacts`, `calendar`, `phone`, `sms`,
`media`, `bluetooth`, `nfc`, `biometrics`, `activity_recognition`,
`exact_alarms`, `battery_optimization`, `files`, `downloads`, `share`, `audio`,
`sensors`, `foreground_service`, `boot_receiver`, `wake_lock`, `haptics` and
`notifications`. Use `pydrud capabilities list --all` for descriptions.
`permissions:` remains available for an individual Android permission. The CLI
updates YAML and the generated manifest: `pydrud capabilities add contacts` or
`pydrud permissions add camera`, then `pydrud sync`. (`capabilities add camera`
answers with that same suggestion — the camera permission is always a
deliberate declaration.) Runtime dangerous
permissions still require `page.permissions.request(...)` and user consent.

`pydrud.toml` stores the top-level `runtime` choice plus `[python.packages]`
and `[theme]`. Its legacy `[app]` identity fields are kept in sync with YAML
for compatibility; when both files contain an app name or package, YAML wins.
App source under `src/app/`, local SDK paths, signing keys and custom Java
files are not removed by Chaquopy `sync`.

---

## CLI Reference

Every command uses the same responsive terminal UI as the Hot Reload runner:
branded command cards, phase dividers, status badges, aligned tables, final
summaries and actionable next steps. It works in PowerShell and standard
Unix terminals without adding a UI dependency. Colours automatically switch
off when output is redirected; `NO_COLOR=1` / `PYDRUD_COLOR=never` disables
them explicitly, and `PYDRUD_COLOR=always` forces them. Machine output such
as `pydrud analyze --json` remains plain JSON.

| Command | Description |
|---------|-------------|
| `pydrud create <name>` | Create a Pydash project by default; no Android toolchain or APK |
| `pydrud create <name> --runtime chaquopy` | Opt into the standalone Android APK project |
| `pydrud create <name> --org com.example` | Set the project/package prefix |
| `pydrud init android` | Add the Android preview shell to this project (no Chaquopy/NDK/CMake) |
| `pydrud init android --standalone` | Add the Android platform with embedded Python (offline APK) |
| `pydrud dev [project_dir]` | Run host Python, start authenticated LAN preview, print QR/URI; no ADB |
| `pydrud dev --host <ip> --port <port>` | Configure preview listener (`--connect-host` overrides the QR address) |
| `pydrud build` / `pydrud build --release` | Build a debug/release APK (Android platform only) |
| `pydrud run` | Build + install + launch on Android (Android platform only) |
| `pydrud watch` | Standalone-only Android Hot Reload runner; use `pydrud dev` otherwise |
| `pydrud devices` | List connected Android devices (`adb devices -l`) |
| `pydrud analyze` | Static analysis of Python UI code and PSS stylesheets (runtime-aware) |
| `pydrud analyze --path src` | Custom source directory |
| `pydrud analyze --json` | Machine-readable JSON output |
| `pydrud clean` | Clean Android build artifacts |
| `pydrud sync` | Refresh the generated Android layer (Android platform only; Pydash is a no-op) |
| `pydrud doctor` | Check host requirements and, when relevant, Android toolchain requirements |
| `pydrud pip add <pkg>...` | Pydash records host dependencies; Chaquopy validates packages and syncs Gradle |
| `pydrud pip remove <pkg>...` | Remove declarations; Chaquopy also updates Gradle |
| `pydrud pip list [--all] [--category ai]` | List project declarations or the Android package catalogue |
| `pydrud pip search <term>` | Search the Android catalogue; Pydash also accepts unlisted host packages |
| `pydrud pip sync` | Apply package declarations to Gradle (standalone only) |
| `pydrud permissions add\|remove <name>...` | Update YAML and the Android manifest (Android platform only) |
| `pydrud capabilities add\|remove <name>...` | Enable Android feature bundles (Android platform only) |
| `pydrud icons [--source logo.png]` | Generate Android launcher icons (Android platform only) |
| `pydrud keygen` | Create the Play Store upload keystore (Android platform only) |
| `pydrud docs [--serve]` | Offline HTML API reference |
| `pydrud inspect [--tree] [--watch]` | Build a local static tree or inspect Android bridge traffic; `--watch` follows the Chaquopy bridge |

### Environment

```bash
pydrud doctor

# Pydash host workflow: Python and framework checks only
# Chaquopy project: JDK, Android SDK/NDK, Gradle and ADB are checked as applicable
# ADB is only needed for Android install/run, never for `pydrud dev`
```

---

## Requirements

### Pydash host workflow (default)

Python 3.10 or newer and the Pydrud package are sufficient to run host-side
`pydrud dev`. The host preview server does not require Java, the Android SDK,
NDK, Gradle, or ADB. The independent Pydash companion renderer is not shipped
or built by this repository.

### Android APK workflows (added with `pydrud init android`)

The default preview shell needs only the JDK, Android SDK and Gradle. The
standalone target additionally needs the NDK, CMake and the Chaquopy plugin
(applied automatically — there is nothing to install by hand):

| Tool | Current project default | Notes |
|------|-------------------------|-------|
| Python | 3.11 | Used by the Chaquopy build/runtime configuration |
| Java (JDK) | 17+ | `pydrud doctor` checks the Android build environment |
| Android SDK | API 36 compile/target | Configurable in `pydrud.yaml`; set `ANDROID_HOME` or `ANDROID_SDK_ROOT` |
| Android NDK | `28.2.13676358` | Generated project default |
| Android Gradle Plugin | `8.13.2` | Generated project default |
| Gradle | `8.14.4` | Wrapper is generated with the project |
| Chaquopy | `17.0.0` | Android-only embedded Python runtime |

A generated Android project currently targets Android API 24+ and defaults to
`arm64-v8a`, `armeabi-v7a`, and `x86_64`. ADB or a connected device/emulator is
needed for `pydrud run`, but not for host-side `pydrud dev` or the unit tests.

### Setting up Android SDK

These steps are needed only for projects with the Android platform
(`pydrud init android`); pure Pydash projects never touch the SDK:

<details>
<summary><b>Windows</b></summary>

```powershell
[System.Environment]::SetEnvironmentVariable('ANDROID_HOME', 'C:\Android\Sdk', 'User')
[System.Environment]::SetEnvironmentVariable('ANDROID_SDK_ROOT', 'C:\Android\Sdk', 'User')
```

Restart your terminal and verify:
```powershell
pydrud doctor
```
</details>

<details>
<summary><b>Linux / macOS</b></summary>

```bash
export ANDROID_HOME=$HOME/Android/Sdk
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
```

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export ANDROID_HOME=$HOME/Android/Sdk' >> ~/.bashrc
echo 'export ANDROID_SDK_ROOT=$HOME/Android/Sdk' >> ~/.bashrc
```
</details>

---

## Development

```bash
git clone https://github.com/MurShidM01/Pydrud.git
cd Pydrud
pip install -e ".[dev]"
python -m pytest tests/ -v
```

The suite covers:

* unit/runtime tests for widgets, state, protocol-v2 rendering, keyed diffs,
  responsive behavior, the analyzer, package backends and PSS parsing/resolution;
* project-generation tests for both the default Pydash scaffold and the
  Chaquopy Android scaffold, including packaging and import-boundary checks;
* generated Java template parsing/symbol checks and Python compile checks;
* **end-to-end runtime tests** using `pydrud.testing` and a local protocol
  renderer, with no device or emulator required. These tests do not constitute
  an Android Gradle/APK build or validation of the separate Pydash client.

```bash
python -m pytest tests/ -v            # everything
python -m pytest tests/test_integration.py       # app ⇄ bridge ⇄ renderer
python -m pytest tests/test_starter_app_e2e.py   # the scaffolded starter app
```

### Project Structure

```
Pydrud/
+-- pydrud/
|   +-- widgets/            # 130+ widgets (basic, layout, forms, material/, theme/, ...)
|   +-- runtime/            # App, Page, bridge event loop, hot reload
|   +-- core/               # keyed diff, RenderTransaction, PSS engine, state, preview protocol
|   +-- platforms/android/  # Android-only renderer profile, diagnostics and logcat adapters
|   +-- services/           # async HTTP client + native/ platform services
|   +-- commands/           # CLI (project/ scaffold+sync, builder, analyzer, ...)
|   +-- components/         # higher-level compositions
|   +-- data/               # bundled registries (PyPI catalogue, icon paths)
|   +-- navigation.py       # Router, NavigationStack
|   +-- testing.py          # AppTester - run the whole app in CI
|   +-- android/templates/  # Jinja2 build-time templates for optional Chaquopy APK projects
+-- examples/               # todo_app.py, weather_app.py
+-- docs/                   # ARCHITECTURE.md, PREVIEW_PROTOCOL.md
+-- tests/                  # runtime, parser, analyzer, scaffold and protocol tests
+-- pyproject.toml
```

---


## Roadmap

| Version | Focus |
|---------|-------|
| **v2.1.0** | `create`/`init android` CLI, Chaquopy-free Android preview shell, starter PSS theme, Pydash default/Chaquopy opt-in, runtime-aware tooling, platform-neutral PSS engine |
| **v1.0.0** | Core widgets, state, diffing, CLI, APK generation, responsive scaling |
| **v1.0.1** | Router, Scaffold, AppBar, FAB, MediaQuery, Hot Reload, incremental patches, WidgetRegistry, analyze CLI |
| **v1.1.0** | Stable keys + keyed diffing, 10 new widgets, Colors/Icons/Theme, working back button, FAB overlays, toast/snackbar/vibrate, lifecycle hooks, self-bootstrapping Gradle, FakeDevice test harness |
| **v1.2.0** | 21 Material 3 components, gestures, implicit animations + Hero, forms & validation, native services (dialogs/storage/permissions/files/notifications/location/haptics), HTTP client, task runner & timers, Store/Computed/ReactiveList, Material You theming, `pydrud.testing.AppTester` |
| **v1.3.0** | SQLite + ORM + cache, pattern routes/deep links/nested navigators, 119 PyPI packages via `pydrud pip`, WorkManager jobs & foreground services, FCM push, camera/sensors/biometrics/BLE/NFC/audio, secure storage, Canvas & explicit animations, stateful hot reload, inspector, docs generator, signing & icon tooling |
| **v1.4** | Independent Pydash renderer/client and any standalone export targets remain separate future work; richer Material 3 motion and Compose interop |
| **v2.0** | iOS backend (SwiftUI), Web (WASM), macOS desktop |

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -am 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT (c) Pydrud Contributors. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Pydrud</strong> -- <em>Pythonic. Portable. Simple.</em><br>
  Host-driven preview by default; native Android APKs are an explicit Chaquopy option.
</p>