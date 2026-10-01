<p align="center">
  <img src="https://img.shields.io/pypi/v/pydrud?color=6366F1&style=flat-square" alt="PyPI" />
  <img src="https://img.shields.io/pypi/pyversions/pydrud?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/android-native-brightgreen?style=flat-square" alt="Android Native" />
  <img src="https://img.shields.io/github/license/MurShidM01/Pydrud?style=flat-square" alt="License" />
  <img src="https://img.shields.io/pypi/dm/pydrud?style=flat-square" alt="Downloads" />
</p>

<h1 align="center">Pydrud</h1>

<p align="center">
  <strong>Build native Android apps with Python.<br>
  No XML layouts. No Kotlin UI code. Just Python.</strong>
</p>

<p align="center">
  A Flutter-inspired framework that converts declarative Python widget trees<br>
  into <strong>real native Android Views</strong> at runtime via Chaquopy + a lightweight TCP bridge.
</p>

---

## Quick Start

```bash
pip install pydrud                    # Install the framework
pydrud init my_app --org com.example  # Scaffold a new project
cd my_app
pydrud run                            # Build, install, launch
```

**First APK in ~2 minutes.** Connect your Android device via USB (or ADB over TCP).

---

## What You Get

| Feature | Description |
|---------|-------------|
| Declarative UI | Compose screens with Python — Container, Column, Row, Text, Button, and more |
| Reactive State | `State<T>` auto-triggers UI re-renders on value change |
| Full Styling | Colors, padding, margin, borders, fonts, elevation, alignment |
| Native Rendering | Every widget becomes a real Android View — not a WebView or canvas |
| CLI Toolchain | `init` / `build` / `run` / `watch` / `analyze` / `doctor` / `clean` |
| Responsive | `Responsive.text()` auto-scales UI to any screen size |
| TCP Bridge | Clean NDJSON protocol over port 8595 |

---

## New in v1.0.1

| Feature | Description |
|---------|-------------|
| **Router + NavigationStack** | Multi-screen navigation with push/pop/replace and Android hardware back-button sync |
| **Scaffold, AppBar, FAB** | Material-style page layout widgets — Scaffold, AppBar with leading/title/actions |
| **MediaQuery** | Auto-cached screen metrics: width, height, density, scale factor, phone/tablet detection |
| **set_system_ui** | Dynamic status bar color and icon brightness control via bridge command |
| **Hot Reload** | File-watcher pushes updated widget trees instantly — no APK recompilation needed |
| **Hot Restart** | Reset app state and reload UI from scratch without rebuilding |
| **Incremental Patches** | TreeDiff now sends only changed widgets via parent_key, not full re-renders |
| **Async Event Loop** | Non-blocking socket reader with thread-safe event queue — no UI freezes |
| **WidgetRegistry** | Modular ViewCreator lambdas on Android side — 10x faster rendering pipeline |
| **pydrud analyze** | Static analysis CLI — checks missing widget keys, invalid styles, unhandled async |

---

## Example App

```python
from pydrud import App, Text, Container, Column, Row, Button, Center
from pydrud import State, EdgeInsets, Alignment, Responsive

counter = State(0)

def main(page):
    page.title = "Pydrud Demo"
    page.bgcolor = "#FFF9FAFB"

    def on_pressed(data):
        counter.value += 1
        page.update()

    page.add(
        Column(scroll=True, children=[

            Container(
                bg="#FF6366F1", padding=EdgeInsets.symmetric(horizontal=20, vertical=16),
                child=Text("Pydrud", size=20, weight=700, color="#FFFFFFFF"),
            ),

            Center(child=Text(str(counter.value), size=72, weight=200, color="#FF6366F1")),
            Center(child=Text("Tap the button", size=14, color="#FF9CA3AF")),

            Center(
                child=Button(
                    "+", bg_color="#FF6366F1", color="#FFFFFFFF",
                    style={"borderRadius": 28, "width": 56, "height": 56},
                ).on_click(on_pressed),
            ),

        ]),
    )

app = App(target=main)
app.run()
```

> State lives outside `main()` so it persists across re-renders.  
> Update -> `page.update()` -> tree rebuilds -> Android re-renders.

---

## v1.0.1 Example: Router + Scaffold + MediaQuery

```python
from pydrud import (
    App, Router, Scaffold, AppBar,
    Container, Column, Center, Text, Button,
    Responsive, MediaQuery,
)

def home(page):
    page.title = "Pydrud v1.0.1"
    page.set_system_ui(status_bar_color="#FF6366F1", icon_brightness="light")
    mq = MediaQuery.of()

    scaffold = Scaffold(
        app_bar=AppBar(
            title=Text("Pydrud", size=20, weight=700, color="#FFFFFF"),
            bg_color="#FF6366F1",
        ),
        body=Center(
            child=Text(f"Screen: {mq['width']}x{mq['height']} dp",
                       size=18, weight=600, color="#FF1F2937"),
        ),
    )
    page.add(scaffold)

router = Router()
router.define("home", home).initial("home")

app = App(target=router.build_root(), title="Pydrud")
app.attach_router(router)
app.enable_hot_reload()
app.run()
```

---

## Breakthrough: Incremental Patches

v1.0.0 sent the **entire widget tree** on every state change. v1.0.1 uses an enhanced `TreeDiff` engine that:

- Compares old and new widget trees
- Generates only the changed operations (create, update, delete, replace)
- Each patch carries a `parent_key` so the Android ViewFactory can attach new views to the correct parent
- Falls back to full re-render when >50 patches are needed (e.g., screen transitions)

This means state changes like button taps, text input, toggles, and slider moves now send **kilobytes instead of megabytes** over the bridge.

---

## Router & Navigation

```python
from pydrud import Router

router = Router()
router.define("home", home_screen)
router.define("settings", settings_screen)
router.initial("home")

# In an event handler:
# router.push("settings")    -- push screen, back returns to home
# router.pop()               -- go back
# router.replace("home")     -- replace current screen
```

The Android hardware back button sends a `"back"` event to Python's event loop. The Router handles it by popping the navigation stack. When the stack reaches the root, Android finishes the activity.

---

## Hot Reload

```python
app = App(target=main)
app.enable_hot_reload()  # Watch src/ for .py changes
app.run()
```

Or via CLI:
```bash
pydrud run --watch
```

When a Python file changes:
1. The affected module is reloaded via `importlib.reload()`
2. The widget tree is rebuilt
3. Incremental patches are sent to the device

**No APK recompilation needed.** Chaquopy serves Python files from the source directory at runtime.

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
pydrud build    # proxy forwarded to Gradle automatically
```

---

## Widget Reference

### Layout

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Container` | Box with padding, margin, bg, border-radius | `child`, `padding`, `margin`, `bg`, `border_radius`, `width`, `height`, `alignment`, `expand` |
| `Column` | Vertical flex layout | `children`, `spacing`, `horizontal_alignment`, `scroll`, `expand` |
| `Row` | Horizontal flex layout | `children`, `spacing`, `vertical_alignment`, `expand` |
| `Center` | Centres its child | `child`, `expand` |
| `Spacer` | Flexible empty space | `expand` (default 1) |
| `Divider` | Horizontal / vertical line | `color`, `thickness` |
| **`Scaffold`** (v1.0.1) | Page layout with AppBar + body | `app_bar`, `body`, `bg_color` |
| **`AppBar`** (v1.0.1) | Top app bar | `title`, `leading`, `actions`, `bg_color`, `elevation` |

### Basic

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Text` | Readable text | `value`, `size`, `color`, `weight` (100-900), `italic`, `text_align` |
| `Button` | Clickable button | `text`, `variant` (filled / outlined / text), `icon`, `bg_color`, `color`, `disabled` |
| `TextField` | Text input | `value`, `hint`, `multiline`, `password` |
| `Image` | Display image | `src` (asset or URL), `fit` |
| `Icon` | Material icon | `name` (star, home, search, ...), `size`, `color` |
| `Checkbox` | Checkable box | `label`, `checked` |
| `Switch` | Toggle switch | `label`, `active` |

### Events

All interactive widgets support callback chaining:

```python
widget.on_click(callback)      # callback(data) -> data is a dict
widget.on_change(callback)     # TextField, Checkbox, Switch
widget.on_submit(callback)     # TextField (IME action)
widget.on_focus(callback)      # Focus gain / loss
```

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

---

## Responsive Scaling

```python
from pydrud import Responsive

Responsive.text(16)      # Font size -- scales proportionally
Responsive.w(48)         # Width
Responsive.h(48)         # Height
Responsive.padding(24)   # Padding / margin
Responsive.spacing(12)   # Gaps between widgets
Responsive.radius(12)    # Border radius
Responsive.icon(24)      # Icon size
```

### MediaQuery (v1.0.1)

```python
from pydrud import MediaQuery

mq = MediaQuery.of()
width = mq["width"]          # Screen width in dp
height = mq["height"]        # Screen height in dp
density = mq["density"]      # Pixel density
scale = mq["scale_factor"]   # width / 360

if MediaQuery.is_phone():    # width <= 428
    # Compact layout
elif MediaQuery.is_tablet(): # width > 600
    # Expanded layout
```

**How it works:**

1. Android sends screen dimensions via the bridge `"ready"` event
2. Python's `Responsive` and `MediaQuery` classes cache the metrics
3. Layout values auto-scale based on the device width vs 360dp baseline

> No device info available? Defaults to factor 1.0 (no scaling).

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

```
+------------------------------------------+
|  Python Layer                             |
|  +--------+  +----------------------+     |
|  |Widgets |  | EventDispatcher      |     |
|  |  Tree  +--+  (user callbacks)    |     |
|  +----+---+  +----------+-----------+     |
|       |                  |                |
|  +----+------------------+-----------+    |
|  |  TreeDiff -> Patches -> Bridge      |  |
|  +----------------+-------------------+    |
+-------------------+-----------------------+
                    | TCP / NDJSON :8595
+-------------------+-----------------------+
|  Android Layer    |                       |
|  +----------------+-------------------+   |
|  |  BridgeService  (TCP server)       |   |
|  +----------------+-------------------+   |
|  +----------------+-------------------+   |
|  |  WidgetRegistry -> ViewFactory     |   |
|  |  (modular ViewCreator lambdas)     |   |
|  +----------------+-------------------+   |
|  +----------------+-------------------+   |
|  |  EventDispatcher -> Python         |   |
|  +-----------------------------------+   |
+------------------------------------------+
```

### Data Flow

1. **`App(target=main)`** -- calls your builder -> produces a Widget tree
2. **`page.update()`** -- rebuilds the tree -> TreeDiff computes patches -> sends only changed widgets
3. **`BridgeService`** -- receives patches -> `ViewFactory` creates/updates native Views
4. **User taps a Button** -- Java sends `{"type":"click","key":"..."}` over the socket
5. **Python EventDispatcher** -- routes the event to your callback
6. **Callback mutates `State`** -- triggers `page.update()` -> goto step 2

### Bridge Protocol

**Android -> Python events:**
```
{"type": "click",   "key": "btn_abc", "data": {}}
{"type": "change",  "key": "tf_xyz",  "data": {"value": "hello"}}
{"type": "submit",  "key": "tf_xyz",  "data": {"value": "hello"}}
{"type": "ready",   "key": "",        "data": {"width": 360, "height": 640, "density": 2.0}}
{"type": "back",    "key": "",        "data": {}}            # Hardware back button
```

**Python -> Android commands:**
```
{"cmd": "full_render",      "tree": {...}}                    # Initial render
{"cmd": "render",           "patches": [...]}                 # Incremental update
{"cmd": "toast",            "message": "Saved"}
{"cmd": "set_title",        "title": "My App"}
{"cmd": "set_system_ui",    "status_bar_color": "#...", "icon_brightness": "light"}
{"cmd": "finish_activity"}                                     # Exit app
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `pydrud init <name>` | Create a new project |
| `pydrud init <name> --org com.example` | With custom package |
| `pydrud build` | Build debug APK |
| `pydrud build --release` | Build release APK |
| `pydrud run` | Build + install + launch + live logcat |
| `pydrud run --device <id>` | Target specific device |
| `pydrud run --watch` | Enable hot-reload (file watcher) |
| `pydrud analyze` | Static analysis (missing keys, invalid styles) |
| `pydrud analyze --path src` | Custom source directory |
| `pydrud analyze --json` | Machine-readable JSON output |
| `pydrud clean` | Clean build artifacts |
| `pydrud doctor` | Check environment requirements |

### Environment

```bash
pydrud doctor

# Expected output:
# Python >= 3.10       -- 3.12.3
# Java 17+             -- OpenJDK 17
# Android SDK          -- /path/to/sdk (API 35)
# Gradle               -- gradlew wrapper found
# ADB                  -- Android Debug Bridge 2.x
```

---

## Requirements

### Development machine

| Tool | Version | Notes |
|------|---------|-------|
| Python | >= 3.10, <= 3.12 | 3.12 recommended for Chaquopy compatibility |
| Java (JDK) | 17+ | OpenJDK 17 LTS recommended |
| Android SDK | API 33+ | Set `ANDROID_HOME` or `ANDROID_SDK_ROOT` |
| Android NDK | r29+ | Required for Chaquopy native libraries |
| Gradle | 8.x | Bundled via wrapper in generated projects |

### Android device

| Requirement | Notes |
|-------------|-------|
| API 24+ (Android 7.0+) | Minimum supported |
| ARM64 / x86_64 | Both supported |
| USB Debugging enabled | Or ADB over TCP |

### Setting up Android SDK

<details>
<summary><b>Windows</b></summary>

```powershell
# Set environment variables
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

Current test count: **96 tests** (widgets, state, diffing, events, styling, bridge, responsive).

### Project Structure

```
pydrud/
+-- pydrud/
|   +-- main.py                   # App + Page + bridge event loop
|   +-- navigation.py             # Router, NavigationStack, Route (new)
|   +-- widgets/
|   |   +-- base.py               # Widget base class
|   |   +-- layout.py             # Container, Column, Row, Center, Spacer, Divider
|   |   +-- basic.py              # Text, Button, TextField, Image, Icon, Checkbox, Switch
|   |   +-- styling.py            # Style, EdgeInsets, Alignment, FontStyle
|   |   +-- app_bar.py            # AppBar (new)
|   |   +-- scaffold.py           # Scaffold (new)
|   |   +-- fab.py                # FloatingActionButton (new)
|   +-- core/
|   |   +-- state.py              # State[T], ReactiveDict
|   |   +-- diff.py               # TreeDiff -> Patch list with parent_key
|   |   +-- events.py             # Event dispatcher
|   |   +-- bridge.py             # Protocol encoding / decoding
|   |   +-- responsive.py         # Responsive scaling + MediaQuery
|   |   +-- watcher.py            # FileWatcher for hot reload (new)
|   +-- commands/
|   |   +-- cli.py                # Click CLI
|   |   +-- project.py            # Jinja2 project scaffold
|   |   +-- builder.py            # Gradle + ADB
|   |   +-- doctor.py             # Environment check
|   |   +-- analyzer.py           # Static analysis (new)
|   +-- utils/
|       +-- colors.py             # ANSI CLI colours
|   +-- android/templates/        # Jinja2 -> Android project
|       +-- android/
|           +-- ViewFactory.java.j2       # WidgetRegistry-based rendering
|           +-- BridgeService.java.j2     # set_system_ui, finish_activity
|           +-- MainActivity.java.j2      # onBackPressed for Router
|           +-- ViewCreator.java.j2       # Functional interface (new)
|           +-- WidgetRegistry.java.j2    # Map-based registry (new)
+-- tests/                        # pytest test suite
+-- pyproject.toml
+-- README.md
```

---

## Migrating from v1.0.0 to v1.0.1

1. **Update the framework:**
   ```bash
   pip install --upgrade pydrud
   ```

2. **Optional: adopt Router-based navigation**
   Replace manual `app_state["screen"]` routing with `Router`:
   ```python
   router = Router()
   router.define("home", home_screen).initial("home")
   app = App(target=router.build_root())
   app.attach_router(router)
   ```

3. **Optional: migrate to Scaffold + AppBar**
   Replace custom `app_bar()` wrappers with the framework `AppBar` widget:
   ```python
   Scaffold(
       app_bar=AppBar(title=Text("Home"), bg_color="#6366F1"),
       body=...,
   )
   ```

4. **Run the analyzer** to check for issues:
   ```bash
   pydrud analyze
   ```

---

## Roadmap

| Version | Focus |
|---------|-------|
| **v1.0.0** | Core widgets, state, diffing, CLI, APK generation, responsive scaling |
| **v1.0.1** | Router, Scaffold, AppBar, FAB, MediaQuery, Hot Reload, incremental patches, WidgetRegistry, analyze CLI |
| **v1.1** | Material theme, ListView / GridView, Animations, Snackbar / Dialog |
| **v1.2** | Canvas / CustomPaint, Camera / GPS, Plugins, Database (SQLite) |
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
  <strong>Pydrud</strong> -- <em>Pythonic. Native. Simple.</em><br>
  Built for Python developers who love native mobile.
</p>
