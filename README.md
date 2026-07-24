<p align="center">
  <img src="https://img.shields.io/pypi/v/pydrud?color=6366F1&style=flat-square" alt="PyPI" />
  <img src="https://img.shields.io/pypi/pyversions/pydrud?style=flat-square" alt="Python" />
  <img src="https://img.shields.io/badge/android-native-brightgreen?style=flat-square" alt="Android Native" />
  <img src="https://img.shields.io/github/license/MurShidM01/Pydrud?style=flat-square" alt="License" />
  <img src="https://img.shields.io/pypi/dm/pydrud?style=flat-square" alt="Downloads" />
</p>

<h1 align="center">⚡ Pydrud</h1>

<p align="center">
  <strong>Build native Android apps with Python.<br>
  No XML layouts. No Kotlin UI code. Just Python.</strong>
</p>

<p align="center">
  A Flutter-inspired framework that converts declarative Python widget trees<br>
  into <strong>real native Android Views</strong> at runtime — via Chaquopy + a lightweight TCP bridge.
</p>

<br>

---

## ✨ Quick Start

```bash
pip install pydrud                    # Install the framework
pydrud init my_app --org com.example  # Scaffold a new project
cd my_app
pydrud run                            # Build → install → launch
```

**First APK in ~2 minutes.** Connect your Android device via USB (or ADB over TCP), and `pydrud run` does the rest.

<br>

---

## 📱 What You Get

| | |
|---|---|
| **🧱 Declarative UI** | Compose screens with Python — `Container`, `Column`, `Row`, `Text`, `Button`, and more |
| **⚡ Reactive State** | `State<T>` auto-triggers UI re-renders on value change |
| **🎨 Full Styling** | Colors, padding, margin, borders, fonts, elevation, alignment |
| **📲 Native Rendering** | Every widget becomes a real Android `View` — not a WebView or canvas |
| **🛠 CLI Toolchain** | `init` / `build` / `run` / `clean` / `doctor` — one command to ship |
| **📏 Responsive** | `Responsive.text()` auto-scales UI to any screen size |
| **🌉 TCP Bridge** | Clean NDJSON protocol over port 8595 — debuggable with any JSON tool |

<br>

---

## 📝 Example App

```python
from pydrud import App, Text, Container, Column, Row, Button, Center
from pydrud import State, EdgeInsets, Alignment

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

            Spacer(expand=2),
            Center(child=Text(str(counter.value), size=72, weight=200, color="#FF6366F1")),
            Center(child=Text("Tap the button", size=14, color="#FF9CA3AF")),
            Spacer(expand=3),

            Center(
                child=Button(
                    "+", bg_color="#FF6366F1", color="#FFFFFFFF",
                    style={"borderRadius": 28, "width": 56, "height": 56},
                ).on_click(on_pressed),
            ),
            Spacer(expand=1),

        ]),
    )

app = App(target=main)
app.run()
```

> 💡 **State lives outside `main()`** so it persists across re-renders.  
> Update → `page.update()` → tree rebuilds → Android re-renders.

<br>

---

## 🔧 Installation

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
export https_proxy=http://proxy:port
pydrud build    # proxy forwarded to Gradle automatically
```

<br>

---

## 🧱 Widget Reference

### Layout

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Container` | Box with padding, margin, bg, border-radius | `child`, `padding`, `margin`, `bg`, `border_radius`, `width`, `height`, `alignment`, `expand` |
| `Column` | Vertical flex layout | `children`, `spacing`, `horizontal_alignment`, `scroll`, `expand` |
| `Row` | Horizontal flex layout | `children`, `spacing`, `vertical_alignment`, `expand` |
| `Center` | Centres its child | `child`, `expand` |
| `Spacer` | Flexible empty space | `expand` (default 1) |
| `Divider` | Horizontal / vertical line | `color`, `thickness` |

### Basic

| Widget | Description | Key Props |
|--------|-------------|-----------|
| `Text` | Readable text | `value`, `size`, `color`, `weight` (100–900), `italic`, `text_align` |
| `Button` | Clickable button | `text`, `variant` (filled / outlined / text), `icon`, `bg_color`, `color`, `disabled` |
| `TextField` | Text input | `value`, `hint`, `multiline`, `password` |
| `Image` | Display image | `src` (asset or URL), `fit` |
| `Icon` | Material icon | `name` (star, home, search, …), `size`, `color` |
| `Checkbox` | Checkable box | `label`, `checked` |
| `Switch` | Toggle switch | `label`, `active` |

### Events

All interactive widgets support callback chaining:

```python
widget.on_click(callback)      # callback(data) → data is a dict
widget.on_change(callback)     # TextField, Checkbox, Switch
widget.on_submit(callback)     # TextField (IME action)
widget.on_focus(callback)      # Focus gain / loss
```

### Styling

Use the `Style` builder or pass dicts inline:

```python
Style().bg("#FFFFFF").padding(EdgeInsets.all(16)).border_radius(8).elevation(4).build()
```

**All style properties:**

| Prop | Type | Example |
|------|------|---------|
| `bg` | Hex color | `"#FF6366F1"` |
| `opacity` | float 0–1 | `0.5` |
| `width` / `height` | int or `"match"` | `200` or `"match"` |
| `padding` / `margin` | `EdgeInsets` | `EdgeInsets.all(16)` |
| `borderRadius` | int | `12` |
| `font.size` | int (sp) | `16` |
| `font.color` | Hex color | `"#FF1F2937"` |
| `font.weight` | int 100–900 | `700` |
| `font.italic` | bool | `true` |
| `alignment` | `Alignment` constant | `Alignment.center` |
| `elevation` | int (dp) | `4` |
| `visible` | bool | `true` / `false` |
| `tooltip` | string | `"Save changes"` |

<br>

---

## 📏 Responsive Scaling

Pydrud includes a built-in responsive system that **auto-scales** your UI to the device screen width.

```python
from pydrud import Responsive

Responsive.text(16)      # Font size — scales proportionally
Responsive.w(48)         # Width — scales proportionally
Responsive.h(48)         # Height
Responsive.padding(24)   # Padding / margin
Responsive.spacing(12)   # Gaps between widgets
Responsive.radius(12)    # Border radius
Responsive.icon(24)      # Icon size
```

**How it works:**

1. Android sends the screen dimensions (width, height, density) to Python via the bridge `"ready"` event
2. Python's `Responsive` class computes a scale factor: `screen_width_dp / 360`
3. All sizes are multiplied by this factor — on a 720dp tablet, everything is **2× larger**
4. Baseline `360dp` matches the typical phone width

> ✅ No device info available? Defaults to factor `1.0` (no scaling) — safe fallback.

<br>

---

## 🏗 Architecture

```
┌──────────────────────────────────────────┐
│  Python Layer                             │
│  ┌────────┐  ┌──────────────────────┐    │
│  │Widgets │  │ EventDispatcher      │    │
│  │  Tree  ├──┤  (user callbacks)    │    │
│  └───┬────┘  └──────────┬───────────┘    │
│      │                  │                │
│  ┌───▼──────────────────▼────────────┐   │
│  │  TreeDiff → Patches → Bridge.encode│   │
│  └────────────────┬──────────────────┘   │
└───────────────────┼──────────────────────┘
                    │ TCP / NDJSON :8595
┌───────────────────┼──────────────────────┐
│  Android Layer    │                      │
│  ┌────────────────▼──────────────────┐   │
│  │  BridgeService  (TCP server)      │   │
│  └────────────────┬──────────────────┘   │
│  ┌────────────────▼──────────────────┐   │
│  │  ViewFactory   → native Views     │   │
│  └───────────────────────────────────┘   │
│  ┌───────────────────────────────────┐   │
│  │  EventDispatcher → Python         │   │
│  └───────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

### Data Flow

1. **`App(target=main)`** — calls your builder → produces a Widget tree
2. **`page.update()`** — rebuilds the tree → sends full render command to Android
3. **`BridgeService`** — receives the JSON tree → `ViewFactory` creates native Views
4. **User taps a Button** — Java sends `{"type":"click","key":"..."}` over the socket
5. **Python EventDispatcher** — routes the event to your callback
6. **Callback mutates `State`** — triggers `page.update()` → goto step 2

> 🔄 For V1, every state change sends a **full tree re-render**. Incremental patch support is planned for V2.

<br>

---

## 🛠 CLI Reference

| Command | Description |
|---------|-------------|
| `pydrud init <name>` | Create a new project |
| `pydrud init <name> --org com.example` | With custom package |
| `pydrud build` | Build debug APK |
| `pydrud build --release` | Build release APK |
| `pydrud run` | Build + install + launch + live logcat |
| `pydrud run --device <id>` | Target specific device |
| `pydrud clean` | Clean build artifacts |
| `pydrud doctor` | Check environment requirements |

### Environment

```bash
pydrud doctor

# Expected output:
# ✔ Python ≥ 3.10       — 3.12.3
# ✔ Java 17+            — OpenJDK 17
# ✔ Android SDK         — /path/to/sdk (API 35)
# ✔ Gradle              — gradlew wrapper found
# ✔ ADB                 — Android Debug Bridge 2.x
```

<br>

---

## ⚙️ Requirements

### Development machine

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.10, ≤ 3.12 | 3.12 recommended for Chaquopy compatibility |
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

<br>

---

## 🧪 Development

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
├── pydrud/
│   ├── main.py                   # App + Page + bridge event loop
│   ├── widgets/
│   │   ├── base.py               # Widget base class
│   │   ├── layout.py             # Container, Column, Row, Center, Spacer, Divider
│   │   ├── basic.py              # Text, Button, TextField, Image, Icon, Checkbox, Switch
│   │   └── styling.py            # Style, EdgeInsets, Alignment, FontStyle
│   ├── core/
│   │   ├── state.py              # State[T], ReactiveDict
│   │   ├── diff.py               # TreeDiff → Patch list
│   │   ├── events.py             # Event dispatcher
│   │   ├── bridge.py             # Protocol encoding / decoding
│   │   └── responsive.py         # Responsive scaling
│   ├── commands/
│   │   ├── cli.py                # Click CLI
│   │   ├── project.py            # Jinja2 project scaffold
│   │   ├── builder.py            # Gradle + ADB
│   │   └── doctor.py             # Environment check
│   └── android/templates/        # Jinja2 → Android project
├── tests/                        # pytest test suite
├── pyproject.toml
└── README.md
```

### Adding a New Widget

1. Create Python class in `pydrud/widgets/` (extend `Widget`, set `_widget_type`, implement `_serialise_props()`)
2. Export in `pydrud/widgets/__init__.py` and `pydrud/__init__.py`
3. Add a creator method in `pydrud/android/templates/android/ViewFactory.java.j2`
4. Add style handling in `applyStyle()`
5. Write tests in `tests/`
6. Run `python -m pytest tests/ -v`

<br>

---

## 📦 Publishing to PyPI

```bash
# Install build tools
pip install build twine

# Build source distribution and wheel
python -m build

# Upload to PyPI
twine upload dist/*
```

> 💡 Update the version number in `pyproject.toml` before publishing.

<br>

---

## 🗺 Roadmap

| Version | Focus |
|---------|-------|
| **V1** ✅ | Core widgets, state, diffing, CLI, APK generation, responsive scaling |
| **V2** 🔜 | Hot reload, Material theme, ListView / GridView, Navigation, Animations, Snackbar / Dialog |
| **V3** 🚀 | Canvas / CustomPaint, Camera / GPS, Plugins, Database (SQLite), i18n |
| **V4** 🌍 | iOS backend (SwiftUI), Web (WASM), macOS desktop |

<br>

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -am 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Open a Pull Request

<br>

---

## 📄 License

MIT © Pydrud Contributors. See [LICENSE](LICENSE) for details.

<br>

---

<p align="center">
  <strong>Pydrud</strong> — <em>Pythonic. Native. Simple.</em><br>
  Built with ❤️ for Python developers who love native mobile.
</p>
