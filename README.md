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
| Declarative UI | 50+ widgets: layout, Material 3 components, charts, media, gestures, animations |
| Reactive State | `State<T>` auto-triggers UI re-renders on value change |
| Full Styling | Colors, padding, margin, borders, fonts, elevation, alignment |
| Native Rendering | Every widget becomes a real Android View — not a WebView or canvas |
| CLI Toolchain | `init` / `build` / `run` / `watch` / `analyze` / `doctor` / `clean` |
| Responsive | `Responsive.text()` auto-scales UI to any screen size |
| Native Services | Dialogs, storage, permissions, files, share, notifications, GPS, haptics, device info |
| Async by Default | Thread pool + timers + a non-blocking HTTP client, so the UI never freezes |
| Testable | `pydrud.testing.AppTester` runs your whole app in CI without a device or emulator |
| TCP Bridge | Clean NDJSON protocol over port 8595 |

---

## New in v1.2.0 — the "full Android toolkit" release

v1.1 made the renderer correct. v1.2 makes Pydrud *complete*: the component
library, the platform APIs and the app architecture you need to ship a real
product.

| Area | What you get |
|------|--------------|
| **21 Material 3 components** | `ListTile`, `ExpansionTile`, `Chip`, `Badge`, `Avatar`, `Banner`, `Tooltip`, `Tabs`, `BottomNavigationBar`, `NavigationRail`, `Drawer`, `SegmentedButton`, `SearchBar`, `Rating`, `CircularProgress`, `Skeleton`, `RefreshIndicator`, `Stepper`, `WebView`, `VideoPlayer`, `Chart` |
| **Gestures** | `GestureDetector` (tap, double-tap, long-press, 4-way swipe, pan, pinch-scale), `InkWell` ripples, swipe-to-dismiss, `Draggable` |
| **Animations** | `Animation` specs with 9 curves, implicit `AnimatedContainer` / `AnimatedOpacity` / `AnimatedScale` / `AnimatedRotation` / `AnimatedSwitcher`, entrance effects (`FadeIn`, `SlideIn`, `ScaleIn`), `Hero` shared elements, and `widget.animate(...)` on *any* widget |
| **Forms & validation** | `Form` + `FormField` with 11 validators (`required`, `email`, `min_length`, `between`, `matches`, `pattern`, `custom`, …), per-field errors, server-side errors, cross-field rules |
| **Native services** | `page.dialog` (alert/confirm/prompt/choose/bottom-sheet/date/time/colour/progress), `page.storage`, `page.clipboard`, `page.share`, `page.permissions`, `page.notifications`, `page.location`, `page.device`, `page.files`, `page.haptics` |
| **HTTP client** | `page.http.get/post/put/patch/delete/download` — JSON in/out, retries, timeouts, base URL, never on the UI thread |
| **Concurrency** | `page.run_task()` (threads *and* `async def`), `page.run_on_ui()`, `page.after()` / `page.every()` timers, `@debounce` / `@throttle` |
| **App-level state** | `Store` with actions, selectors, middleware, batching and undo; `Computed` cached derivations; `ReactiveList`; all accepted by `app.bind(...)` |
| **Material You theming** | `ColorScheme.from_seed(...)` (light & dark), the M3 `Typography` scale, `page.set_theme_mode("dark"/"system")` |
| **More page control** | `open_drawer`, `scroll_to`, `focus`, `hide_keyboard`, `keep_awake`, `set_orientation`, `fullscreen`, `end_refresh` |
| **Imperative updates** | `page.update(widget)` diffs just that subtree — mutate a control and push it, Flet-style, without re-running the builder |
| **Richer events** | Handlers now receive an `Event` with `.type`, `.key`, `.value`, `.data`, `.control` (still a dict, so old code works), and `on_<anything>=` works on every widget |
| **`pydrud.testing`** | `AppTester` — boot your app, `tap("Sign in")`, stub native answers, assert on what the screen shows. 300+ tests in this repo use it |

```python
from pydrud import Chart, Chip, ListTile, Tabs, Tab, FadeIn

def dashboard(page):
    page.http.get("https://api.example.com/stats").then(show)
    page.storage.get("theme", "light").then(page.set_theme_mode)

    page.add(Tabs([
        Tab("Overview", content=FadeIn(child=Chart([3, 7, 4, 9], kind="bar"))),
        Tab("Settings", content=ListTile("Account", leading="person",
                                         on_click=open_account)),
    ], on_change=lambda e: print("tab", e.value)))
```

---

## New in v1.1.0

| Feature | Description |
|---------|-------------|
| **Stable widget keys** | Auto-generated keys are now deterministic, so `page.update()` really does send tiny patches instead of silently re-rendering everything |
| **Keyed diffing** | Insert/remove/reorder in a list emits `create` / `delete` / `move` for just that item (with target `index`) |
| **10 new widgets** | `Stack`, `Positioned`, `SizedBox`, `Padding`, `Card`, `ListView`, `GridView`, `ProgressBar`, `Slider`, `Dropdown`, `Radio` |
| **Colors / Icons / Theme** | A Material palette, an icon catalogue, and a switchable light/dark theme |
| **Clicks on any widget** | `on_click` / `on_long_press` now work on Containers, Icons, Images, Cards — not just Buttons |
| **Working back button** | Android waits for Python's `back_result` before closing the activity — `router.pop()` no longer exits the app |
| **Scaffold overlays** | `Scaffold(floating_action_button=...)` renders a real floating FAB via absolute positioning |
| **page.toast / snack_bar / vibrate / close** | Direct access to common Android affordances |
| **Lifecycle hooks** | `app.on_lifecycle("resume"/"pause"/"stop"/"destroy", cb)` |
| **Error isolation** | An exception in one event handler is reported via `app.on_error(...)` instead of killing the app |
| **Self-bootstrapping Gradle** | Generated projects build without a checked-in `gradle-wrapper.jar` — the launcher downloads Gradle once |
| **Unique package names** | `pydrud init app1 --org com.acme` → `com.acme.app1` (apps no longer overwrite each other) |
| **`pydrud watch` / `devices`** | Rebuild-reinstall-relaunch loop and device listing |
| **FakeDevice test harness** | `tests/fake_device.py` emulates the Android bridge so whole apps can be tested in CI |

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

## Examples

Two complete apps live in [`examples/`](examples/) and are covered by the test
suite:

| File | Demonstrates |
|------|--------------|
| `examples/todo_app.py` | `Store` actions, keyed lists, swipe-to-delete, filtering, persistence, confirm dialog |
| `examples/weather_app.py` | HTTP client, pull-to-refresh, permissions + GPS, `Chart`, `Skeleton` loading, bottom navigation |

```bash
python examples/todo_app.py --tree     # render the widget tree, no device needed
```

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

## Watch mode & Hot Reload

```python
app = App(target=main)
app.enable_hot_reload()  # Watch src/ for .py changes
app.run()
```

In-process hot reload (used when Python runs on the host, or inside a
long-lived session) reloads the changed module, rebuilds the tree and sends
incremental patches.

Because Chaquopy embeds your Python *inside the APK*, host-side edits have to
be shipped to the device. That is what watch mode does:

```bash
pydrud run --watch      # build → install → launch, then rebuild on every save
pydrud watch            # the same loop for an already-installed app
```

Each save triggers an incremental Gradle build plus `adb install -r`, which
normally takes a couple of seconds.

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
| **`Scaffold`** | Page layout: app bar + body + bottom bar + FAB | `app_bar`, `body`, `bottom_bar`, `floating_action_button`, `bg_color` |
| **`AppBar`** | Top app bar | `title`, `leading`, `actions`, `bg_color`, `color`, `elevation`, `center_title` |
| **`Stack`** (v1.1) | Overlays children | `children`, `alignment` |
| **`Positioned`** (v1.1) | Absolute placement inside a Stack | `child`, `left`, `top`, `right`, `bottom` |
| **`Card`** (v1.1) | Rounded elevated surface | `child`, `bg`, `elevation`, `border_radius`, `padding`, `margin` |
| **`ListView`** (v1.1) | Scrollable list | `children`, `spacing`, `horizontal`, `padding` |
| **`GridView`** (v1.1) | Fixed-column grid | `children`, `columns`, `spacing` |
| **`SizedBox`** (v1.1) | Fixed-size gap / box | `width`, `height`, `child` |
| **`Padding`** (v1.1) | Pads a single child | `padding`, `child` |
| **`Drawer`** (v1.2) | Slide-in navigation panel | `children`, `header`, `width`, `side`, opened with `page.open_drawer()` |
| **`Tabs`** / `Tab` (v1.2) | Tab bar + the selected tab's body | `tabs`, `selected`, `scrollable`, `on_change` |
| **`BottomNavigationBar`** / `NavItem` (v1.2) | 2-5 bottom destinations | `items`, `selected`, `show_labels`, `on_change` |
| **`NavigationRail`** (v1.2) | Vertical rail for tablets | `items`, `selected`, `extended` |
| **`RefreshIndicator`** (v1.2) | Pull-to-refresh | `child`, `on_refresh`, `refreshing` |

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
| **`ProgressBar`** (v1.1) | Determinate or spinning progress | `value` (0-1), `indeterminate`, `circular`, `color` |
| **`Slider`** (v1.1) | Draggable value slider | `value`, `min`, `max`, `divisions`, `color` |
| **`Dropdown`** (v1.1) | Option picker (spinner) | `options`, `value`, `hint` |
| **`Radio`** (v1.1) | Radio button | `label`, `value`, `group`, `selected` |
| **`ListTile`** (v1.2) | List row: leading / title / subtitle / trailing | `title`, `subtitle`, `leading`, `trailing`, `dense`, `selected` |
| **`ExpansionTile`** (v1.2) | Accordion row | `title`, `children`, `expanded`, `on_expand` |
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

### Events

All interactive widgets support callback chaining:

```python
widget.on_click(callback)      # Any widget — callback(data) where data is a dict
widget.on_long_press(callback) # Any widget
widget.on_change(callback)     # TextField, Checkbox, Switch, Slider, Dropdown
widget.on_submit(callback)     # TextField (IME action)
widget.on_focus(callback)      # Focus gain / loss
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

### Native services (v1.2)

```python
page.dialog.confirm("Delete?").then(lambda yes: delete() if yes else None)
page.dialog.prompt("New name", value=current).then(rename)
page.dialog.date().then(set_due_date)
page.dialog.bottom_sheet(["Camera", "Gallery"]).then(pick_source)

page.storage.set("profile", {"name": "Ada"})
page.storage.get("profile", default={}).then(render_profile)

page.permissions.request("camera").then(lambda granted: ...)
page.files.pick_image(camera=True).then(upload)
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

### Page commands (v1.1)

```python
page.toast("Saved!")
page.snack_bar("Deleted", action="UNDO")
page.set_title("Inbox")
page.vibrate(30)                       # needs the VIBRATE permission
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

### Theming with Material You (v1.2)

```python
from pydrud import ColorScheme, Theme, Typography

Theme.use(ColorScheme.from_seed(Colors.INDIGO, dark=True))
Theme.scheme.primary_container          # 13 M3 roles
Typography.scale(1.2)                   # accessibility-scaled type ramp
```

### Testing your app (v1.2)

```python
from pydrud.testing import AppTester

def test_login():
    with AppTester(main) as app:
        app.answer("dialog", True)              # stub the native dialog
        app.type_in("email", "ada@example.com")
        app.tap("Sign in")                      # by key *or* visible text
        assert app.shows("Welcome back")
        assert app.requested("prefs_set")["key"] == "token"
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
{"type": "long_press", "key": "card_1", "data": {}}
{"type": "lifecycle",  "key": "",       "data": {"state": "resume"}}
```

**Python -> Android commands:**
```
{"cmd": "full_render",      "tree": {...}}                    # Initial render
{"cmd": "render",           "patches": [...]}                 # Incremental update
{"cmd": "toast",            "message": "Saved"}
{"cmd": "set_title",        "title": "My App"}
{"cmd": "set_system_ui",    "status_bar_color": "#...", "icon_brightness": "light"}
{"cmd": "snackbar",         "message": "Deleted", "action": "UNDO"}
{"cmd": "vibrate",          "duration": 40}
{"cmd": "back_result",      "handled": true}                   # Answer to a back event
{"cmd": "finish_activity"}                                     # Exit app
```

Patches carry `op`, `key`, `parent_key` and — for `create` / `move` / `replace` —
the target child `index`, so the renderer inserts views in the right place:

```
{"op": "update",  "key": "counter", "props": {"value": "3"}}
{"op": "create",  "key": "row-eggs", "parent_key": "list", "index": 2, "tree": {...}}
{"op": "move",    "key": "row-milk", "parent_key": "list", "index": 0}
{"op": "delete",  "key": "row-bread", "parent_key": "list"}
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
| `pydrud run --watch` | Rebuild + reinstall + relaunch on every file change |
| `pydrud watch` | Same loop without rebuilding first |
| `pydrud devices` | List connected devices (`adb devices -l`) |
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

Current test count: **315 tests**, covering:

* unit tests — widgets, state, styling, responsive scaling, diffing, routing,
  the 1.2 component library, gestures, animations, forms and validators;
* runtime tests — `Store`/`Computed`/`ReactiveList`, `Result` futures, the task
  runner, timers, `@debounce` / `@throttle`, and the HTTP client against a real
  local server;
* template tests — every generated Java file is rendered and parsed with
  `javalang`, and the generated project is compiled with `compileall`;
* **end-to-end tests** — `pydrud.testing` implements the Android side of
  the bridge (including patch application), so a complete app is launched,
  tapped, typed into and navigated exactly as it would be on a phone.

```bash
python -m pytest tests/ -v            # everything
python -m pytest tests/test_integration.py       # app ⇄ bridge ⇄ renderer
python -m pytest tests/test_starter_app_e2e.py   # the scaffolded starter app
```

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
| **v1.1.0** | Stable keys + keyed diffing, 10 new widgets, Colors/Icons/Theme, working back button, FAB overlays, toast/snackbar/vibrate, lifecycle hooks, self-bootstrapping Gradle, FakeDevice test harness |
| **v1.2.0** | 21 Material 3 components, gestures, implicit animations + Hero, forms & validation, native services (dialogs/storage/permissions/files/notifications/location/haptics), HTTP client, task runner & timers, Store/Computed/ReactiveList, Material You theming, `pydrud.testing.AppTester` |
| **v1.3** | SQLite store, background services, camera preview widget, Play Store signing flow |
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
