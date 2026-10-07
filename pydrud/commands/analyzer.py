"""
Static analysis for Pydrud Python projects.

Scans source code for common issues: missing widget keys,
invalid style properties, unhandled async operations, and
other potential problems.

Usage::

    pydrud analyze              # scan src/ directory
    pydrud analyze --path src   # scan custom path
    pydrud analyze --json       # machine-readable JSON output
"""

from __future__ import annotations
import ast
import os
import re

# The one list of valid style keys, shared with the .pss engine. Do not
# copy it here: a second copy silently drifts out of date.
from pydrud.core.styles import VALID_STYLE_KEYS as _VALID_STYLE_KEYS
from pydrud.utils import tui

# ── Issue types ──────────────────────────────────────────────────────────────

_SEVERITY_WARNING = "warning"
_SEVERITY_ERROR = "error"
_WIDGET_CLASSES = {
    "Container", "Column", "Row", "Center", "Spacer", "Divider",
    "Stack", "Positioned", "SizedBox", "Padding", "Card", "ListView", "GridView",
    "PageView", "Carousel",
    "Text", "Button", "FilledButton", "TonalButton", "OutlinedButton",
    "TextButton", "ElevatedButton", "IconButton", "TextField",
    "SearchField", "EmailField", "PasswordField", "NumberField",
    "PhoneField", "UrlField", "Image", "SvgPicture", "Icon", "Checkbox", "Switch",
    "ProgressBar", "LinearProgress", "Slider", "RangeSlider", "Dropdown", "Radio",
    "AppBar", "Scaffold", "FloatingActionButton",
    # v1.2 — Material components
    "ListTile", "ExpansionTile", "Chip", "AssistChip", "FilterChip",
    "InputChip", "SuggestionChip", "Badge", "Avatar", "Banner",
    "Tooltip", "Tabs", "BottomNavigationBar", "NavigationRail", "Drawer",
    "SegmentedButton", "SearchBar", "Rating", "CircularProgress", "Skeleton",
    "RefreshIndicator", "Stepper", "WebView", "VideoPlayer", "Chart",
    "PopupMenu", "DropdownMenu", "PopupMenuButton",
    # v1.2 — gestures, animation and forms
    "GestureDetector", "InkWell", "Dismissible", "Draggable",
    # v1.3 — painting, hardware, maps, rich text, big lists
    "Canvas", "CameraPreview", "QRScanner", "MapView", "RichText", "Markdown",
    "ReorderableList", "InfiniteList",
    "AnimatedContainer", "AnimatedOpacity", "AnimatedScale",
    "AnimatedRotation", "AnimatedSwitcher", "FadeIn", "SlideIn", "ScaleIn",
    "Hero", "Form", "FormField",
    # v1.5 — responsive layout
    "ResponsiveBuilder", "LayoutBuilder", "AdaptiveLayout", "ResponsiveGrid",
    "ShowWhen", "SafeArea", "NavigationBar", "TabBar",
    # state-driven conditional rendering
    "Visible", "Hidden",
    # Flutter-style presets and common app compositions
    "Expanded", "Flexible", "Align", "ColoredBox", "DecoratedBox",
    "ConstrainedBox", "LimitedBox", "Gap", "VerticalDivider",
    "SingleChildScrollView", "Wrap", "ButtonBar", "Heading", "Title",
    "Subtitle", "Label", "Caption", "Link", "NetworkImage", "AssetImage",
    "CircleImage", "Placeholder", "SwitchListTile", "CheckboxListTile",
    "RadioListTile", "ActionChip", "ChoiceChip", "CircleAvatar",
    "BackButton", "CloseButton", "MenuButton", "SectionHeader",
    "EmptyState", "ErrorState", "LoadingState", "InfoCard", "StatCard",
    "SettingsTile", "NavigationTile", "FormSection",
    # v2.0 — Flutter sizing presets and premium compositions
    "FractionallySizedBox", "FittedBox", "DataTable", "MetricCard",
    "Timeline",
    # v2.0.3 — the flex model, the constraint builder and the accordion
    "Flex", "ExpansionPanelList",
    # v2.0.3 — the native escape hatch
    "NativeView",
}


def _analysis_runtime(path: str, runtime: str | None) -> str:
    """Resolve the target used by runtime-sensitive analyzer checks."""
    from pydrud.runtime.runtime import Runtime, resolve_runtime

    if isinstance(runtime, Runtime):
        return runtime.value
    if runtime is not None:
        return Runtime.resolve(runtime).value

    candidate = os.path.abspath(path)
    if not os.path.isdir(candidate):
        candidate = os.path.dirname(candidate)
    while True:
        if (os.path.isfile(os.path.join(candidate, "pydrud.toml"))
                or os.path.isfile(os.path.join(candidate, "pydrud.yaml"))
                or os.path.isfile(os.path.join(candidate, "pydrud.yml"))):
            resolved = resolve_runtime(candidate).runtime.value
            if resolved == Runtime.CHAQUOPY.value:
                # A preview shell runs Python on the host, exactly like
                # Pydash; only standalone targets bundle source into an APK.
                from pydrud.commands.project import android_is_standalone
                if not android_is_standalone(candidate):
                    return Runtime.PYDASH.value
            return resolved
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    return Runtime.PYDASH.value


def run_analysis(path: str = "src", *, runtime: str | None = None) -> list[dict]:
    """Run static analysis on Python and PSS stylesheet files under *path*.

    When omitted, *runtime* is inferred from the nearest Pydrud project
    configuration; an unconfigured project defaults to Pydash. This matters
    for checks whose validity depends on whether source is bundled into an APK.

    Returns a list of issue dicts with keys:
    - file (str): relative file path
    - line (int): line number
    - severity (str): "warning" or "error"
    - message (str): description of the issue
    """
    runtime = _analysis_runtime(path, runtime)
    issues: list[dict] = []
    src_dir = os.path.abspath(path)
    if not os.path.isdir(src_dir):
        return [{
            "file": path,
            "line": 0,
            "severity": _SEVERITY_ERROR,
            "message": f"Directory not found: {path}",
        }]

    issues.extend(_check_shadowing_issues(src_dir))
    issues.extend(_check_camera_optin(src_dir))

    for root, _dirs, files in os.walk(src_dir):
        # Skip __pycache__ and virtual environments.
        if "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        for fname in sorted(files):
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, src_dir)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    issues.extend(_analyze_file(source, rel_path, runtime=runtime))
                except Exception as exc:
                    issues.append({
                        "file": rel_path,
                        "line": 0,
                        "severity": _SEVERITY_WARNING,
                        "message": f"Could not parse: {exc}",
                    })
            elif fname.endswith(".pss"):
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, src_dir)
                issues.extend(_analyze_stylesheet(fpath, rel_path))

    return issues


def _analyze_stylesheet(fpath: str, rel_path: str) -> list[dict]:
    """Report PSS syntax errors and unknown-property warnings."""
    from pydrud.core.styles.parser import parse_pss

    try:
        with open(fpath, encoding="utf-8") as handle:
            sheet = parse_pss(handle.read(), filename=rel_path)
    except Exception as exc:
        return [{
            "file": rel_path,
            "line": 0,
            "severity": _SEVERITY_WARNING,
            "message": f"Could not parse stylesheet: {exc}",
        }]
    issues = []
    for diagnostic in sheet.diagnostics:
        issues.append({
            "file": rel_path,
            "line": diagnostic.line,
            "severity": (_SEVERITY_ERROR if diagnostic.kind == "error"
                         else _SEVERITY_WARNING),
            "message": f"PSS: {diagnostic.message}",
        })
    return issues


def _analyze_file(source: str, filepath: str, *,
                  runtime: str = "pydash") -> list[dict]:
    """Analyze a single Python file in the context of its selected runtime."""
    issues: list[dict] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        issues.append({
            "file": filepath,
            "line": e.lineno or 0,
            "severity": _SEVERITY_ERROR,
            "message": f"Syntax error: {e.msg}",
        })
        return issues

    # Run all checks.
    issues.extend(_check_missing_keys(tree, filepath))
    issues.extend(_check_inline_styles(tree, filepath))
    issues.extend(_check_event_handlers(tree, filepath))
    issues.extend(_check_page_update_in_loops(tree, filepath))
    issues.extend(_check_icon_references(tree, filepath))
    issues.extend(_check_icon_strings(tree, filepath))
    issues.extend(_check_flex_collapse(tree, filepath))
    issues.extend(_check_constant_references(tree, filepath))
    issues.extend(_check_contrast(tree, filepath))
    issues.extend(_check_touch_targets(tree, filepath))
    issues.extend(_check_host_only_imports(tree, filepath, runtime=runtime))

    return _dedupe(issues)


def _dedupe(issues: list[dict]) -> list[dict]:
    """Drop repeats of the same finding.

    Nested loops are visited once per enclosing loop, so a widget inside two
    ``for`` statements used to be reported twice.
    """
    seen: set = set()
    unique: list[dict] = []
    for issue in issues:
        signature = (issue["file"], issue["line"], issue["severity"],
                     issue["message"])
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(issue)
    return sorted(unique, key=lambda i: (i["file"], i["line"]))


# ── Check 1: Missing widget keys ────────────────────────────────────────────


def _check_missing_keys(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn about widgets built inside loops without an explicit ``key=``.

    Pydrud assigns deterministic structural keys automatically, so a static
    widget tree never needs manual keys. Dynamic lists are different: when
    items are inserted or reordered, structural keys shift and the diff
    engine has to rebuild more than it should. An explicit, data-derived key
    (e.g. ``key=f"todo-{item.id}"``) keeps those updates minimal.

    Only the loop's *outermost* widgets need a key: a widget nested inside a
    keyed parent (``Row(key=…, children=[Icon()])``) already gets its
    identity from that parent, so flagging it was a false positive (DX-002).
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While, ast.ListComp,
                                 ast.SetComp, ast.GeneratorExp)):
            continue
        widgets = [c for c in ast.walk(node)
                   if isinstance(c, ast.Call)
                   and _get_call_name(c) in _WIDGET_CLASSES]
        # Any widget call inside another widget call is a nested child.
        nested: set = set()
        for call in widgets:
            for inner in ast.walk(call):
                if inner is not call and isinstance(inner, ast.Call) \
                        and _get_call_name(inner) in _WIDGET_CLASSES:
                    nested.add(id(inner))
        for child in widgets:
            if id(child) in nested:
                continue
            has_key = any(kw.arg == "key" for kw in child.keywords if kw.arg is not None)
            if not has_key:
                issues.append({
                    "file": filepath,
                    "line": child.lineno,
                    "severity": _SEVERITY_WARNING,
                    "message": f"{_get_call_name(child)}() built in a loop without an "
                               "explicit key= -- dynamic lists diff better with "
                               "stable keys",
                })
    return issues


# ── Check 2: Invalid style properties ───────────────────────────────────────


def _check_inline_styles(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn if ``style=`` dicts use keys not in the known valid set."""
    issues: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "style" and isinstance(kw.value, ast.Dict):
                    for key_node in kw.value.keys:
                        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                            if key_node.value not in _VALID_STYLE_KEYS:
                                issues.append({
                                    "file": filepath,
                                    "line": key_node.lineno,
                                    "severity": _SEVERITY_WARNING,
                                    "message": f"Unknown style key: '{key_node.value}'",
                                })
    return issues


# ── Check 3: Unhandled async in event handlers ─────────────────────────────


def _check_event_handlers(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn if lambda event handlers call I/O without error handling."""
    issues: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            body = node.body
            calls = _find_calls_in_node(body)
            for call_name in calls:
                if call_name in {"open", "read", "write", "requests.get",
                                 "requests.post", "subprocess.run"}:
                    issues.append({
                        "file": filepath,
                        "line": node.lineno,
                        "severity": _SEVERITY_WARNING,
                        "message": f"Event handler calls {call_name}() "
                                   "without async - may block the UI",
                    })
    return issues


# ── Check 4: page.update() in loops ────────────────────────────────────────


def _check_page_update_in_loops(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn if page.update() is called inside a for/while loop."""
    issues: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While, ast.ListComp, ast.SetComp)):
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    name = _get_call_name(child)
                    if name == "page.update":
                        issues.append({
                            "file": filepath,
                            "line": child.lineno,
                            "severity": _SEVERITY_WARNING,
                            "message": "page.update() inside a loop - "
                                       "causes excessive re-renders",
                        })
    return issues


# ── Check 5: Invalid icon references ────────────────────────────────────────


def _check_icon_references(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn if code references non-existent Icons constants."""
    from pydrud.widgets.theme import Icons

    issues: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "Icons":
            icon_name = node.attr
            try:
                getattr(Icons, icon_name)
            except AttributeError:
                issues.append({
                    "file": filepath,
                    "line": node.lineno,
                    "severity": _SEVERITY_ERROR,
                    "message": f"Invalid icon reference: 'Icons.{icon_name}' does not exist",
                })
    return issues


# ── Check 6: Unknown icon strings ───────────────────────────────────────────


#: Keyword arguments that carry an icon name on the Python side.
_ICON_KWARGS = {"icon", "active_icon", "selected_icon", "leading_icon",
                "trailing_icon"}


def _check_icon_strings(tree: ast.AST, filepath: str) -> list[dict]:
    """Flag icon names the Android renderer does not ship (PB-005 / DX-005).

    ``Icon("rocket_launch")``, ``Button(icon="play_arrow")`` and friends used
    to render a silent "?" on device. The analyzer resolves every string
    literal used as an icon against the shipped catalogue and reports the
    closest match, so the mistake surfaces at build time, not on screen.
    """
    from pydrud import icons as catalogue

    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        candidates: list = []
        if _get_call_name(node) in {"Icon", "IconButton"} and node.args:
            candidates.append(node.args[0])
        for kw in node.keywords:
            if kw.arg in _ICON_KWARGS:
                candidates.append(kw.value)
        for const in candidates:
            if not (isinstance(const, ast.Constant)
                    and isinstance(const.value, str)
                    and const.value.strip()):
                continue
            value = const.value
            if catalogue.has(value):
                continue
            close = catalogue.suggest(value)
            hint = (f" Did you mean {' or '.join(repr(c) for c in close)}?"
                    if close else "")
            issues.append({
                "file": filepath,
                "line": const.lineno,
                "severity": _SEVERITY_WARNING,
                "message": f"Unknown icon: {value!r}.{hint} "
                           "See pydrud.icons.available() for the full set.",
            })
    return issues


# ── Check 7: Row/Column main-axis collapse ──────────────────────────────────


#: Values that pin a dimension to the parent (fill the available space).
_FILL_VALUES = {"match", "match_parent", "fill", "expand", "100%", "max"}


def _declares_fill(call: ast.Call, axis: str) -> bool:
    """True when *call* pins ``axis`` ("width"/"height") to fill the parent."""
    for kw in call.keywords:
        if kw.arg == axis and isinstance(kw.value, ast.Constant):
            value = str(kw.value.value).strip().lower()
            if value in _FILL_VALUES:
                return True
        if kw.arg == "main_axis_size" and isinstance(kw.value, ast.Constant):
            if str(kw.value.value).strip().lower() == "max":
                return True
        if kw.arg == "style" and isinstance(kw.value, ast.Dict):
            for key, val in zip(kw.value.keys, kw.value.values):
                if (isinstance(key, ast.Constant) and key.value == axis
                        and isinstance(val, ast.Constant)
                        and str(val.value).strip().lower() in _FILL_VALUES):
                    return True
    return False


def _has_weight(call: ast.Call) -> bool:
    return any(kw.arg == "expand" and not (
        isinstance(kw.value, ast.Constant) and kw.value.value in (0, None))
        for kw in call.keywords)


def _check_flex_collapse(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn when a Row/Column has ≥2 unweighted main-axis-filling children.

    Two unweighted children both pinned to fill the main axis fight for the
    same space: the first consumes it and the rest are squeezed to zero,
    clipping their text with no ellipsis and no error (PB-007 / FM-006).
    Give them ``expand=1`` to share the space, or let them hug their content.
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = _get_call_name(node)
        if func not in {"Row", "Column"}:
            continue
        axis = "width" if func == "Row" else "height"
        children_kw = next((kw for kw in node.keywords
                            if kw.arg == "children"
                            and isinstance(kw.value, ast.List)), None)
        if children_kw is None:
            continue
        colliding = [el for el in children_kw.value.elts
                     if isinstance(el, ast.Call)
                     and not _has_weight(el)
                     and _declares_fill(el, axis)]
        if len(colliding) >= 2:
            issues.append({
                "file": filepath,
                "line": node.lineno,
                "severity": _SEVERITY_WARNING,
                "message": f"{len(colliding)} {func} children fill the main axis "
                           "without a weight — they will collapse. Add expand=1 "
                           "to share the space, or a content width.",
            })
    return issues


# ── Check 8: Design-token references ────────────────────────────────────────


def _check_constant_references(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn if code references a design token that does not exist.

    ``Colors.amber`` or ``Elevation.D4`` used to fail at runtime, on the
    device, in whichever screen happened to build first. They resolve now,
    but typos (``Colors.purlpe``) still do not — and the analyzer is the
    cheapest place to find them.
    """
    from pydrud.widgets.theme import Colors, Elevation, Motion, Radius, Spacing

    registries = {"Colors": Colors, "Spacing": Spacing, "Radius": Radius,
                  "Elevation": Elevation, "Motion": Motion}
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)):
            continue
        registry = registries.get(node.value.id)
        if registry is None or node.attr.startswith("_"):
            continue
        try:
            getattr(registry, node.attr)
        except AttributeError as exc:
            issues.append({
                "file": filepath,
                "line": node.lineno,
                "severity": _SEVERITY_ERROR,
                "message": f"Invalid design token: {exc}",
            })
    return issues


# ── Check 9: Accessibility — colour contrast (PYDRUD §14.7) ─────────────────


#: Widgets that render interactive surfaces, and so need a 48 dp target.
_INTERACTIVE_WIDGETS = {
    "Button", "FilledButton", "TonalButton", "OutlinedButton", "TextButton",
    "ElevatedButton", "IconButton", "FloatingActionButton", "PillButton",
    "GestureDetector", "InkWell", "Dismissible", "Checkbox", "Switch",
    "Radio", "Slider", "Dropdown", "SegmentedButton", "Chip", "FilterChip",
    "InputChip", "ActionChip", "ChoiceChip", "AssistChip", "SuggestionChip",
    "Link", "ListTile", "ExpansionTile", "NavigationTile", "SettingsTile",
    "BackButton", "CloseButton", "MenuButton", "SwitchListTile",
    "CheckboxListTile", "RadioListTile", "PopupMenu", "DropdownMenu",
}

#: WCAG AA minimum contrast — normal text, then large text.
_AA_NORMAL = 4.5
_AA_LARGE = 3.0

_HEX_DIGITS = set("0123456789abcdefABCDEF")


def _literal_color(node: ast.AST) -> str | None:
    """Resolve an AST node to a literal ARGB colour, or ``None``.

    Handles both ``"#FF6366F1"`` string literals and ``Colors.PRIMARY``
    token references — the two spellings the analyzer can see statically.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        body = value.lstrip("#")
        if len(body) in (6, 8) and all(ch in _HEX_DIGITS for ch in body):
            return "#" + body
        return None
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "Colors"):
        from pydrud.widgets.theme import Colors

        try:
            value = getattr(Colors, node.attr)
        except AttributeError:
            return None
        return value if isinstance(value, str) else None
    return None


def _dict_path(dict_node: ast.AST, *path: str) -> ast.AST | None:
    """Follow a chain of literal keys into a ``{...}`` dict literal."""
    current = dict_node
    for key in path:
        if not isinstance(current, ast.Dict):
            return None
        for k, v in zip(current.keys, current.values):
            if isinstance(k, ast.Constant) and k.value == key:
                current = v
                break
        else:
            return None
    return current


def _foreground(call: ast.Call) -> str | None:
    """The text colour literal a widget call declares, if any."""
    for kw in call.keywords:
        if kw.arg == "color":
            found = _literal_color(kw.value)
            if found:
                return found
        if kw.arg == "style" and isinstance(kw.value, ast.Dict):
            for path in (("font", "color"), ("color",)):
                found = _literal_color(_dict_path(kw.value, *path))
                if found:
                    return found
    return None


def _background(call: ast.Call) -> str | None:
    """The background colour literal a widget call declares, if any."""
    for kw in call.keywords:
        if kw.arg in ("bg", "bg_color", "background"):
            found = _literal_color(kw.value)
            if found:
                return found
        if kw.arg == "style" and isinstance(kw.value, ast.Dict):
            for path in (("bg",), ("background",)):
                found = _literal_color(_dict_path(kw.value, *path))
                if found:
                    return found
    return None


def _alpha(color: str) -> int:
    """The 0–255 alpha channel of an ARGB/hex colour string."""
    body = color.lstrip("#")
    return int(body[0:2], 16) if len(body) == 8 else 255


def _is_large_text(call: ast.Call) -> bool:
    """True when a call's ``style.font`` marks its text as "large"."""
    for kw in call.keywords:
        if kw.arg != "style" or not isinstance(kw.value, ast.Dict):
            continue
        size_node = _dict_path(kw.value, "font", "size")
        weight_node = _dict_path(kw.value, "font", "weight")
        size = size_node.value if isinstance(size_node, ast.Constant) else None
        weight = (weight_node.value if isinstance(weight_node, ast.Constant)
                  else 400)
        if not isinstance(size, (int, float)):
            continue
        if size >= 18 or (size >= 14 and isinstance(weight, (int, float))
                          and weight >= 700):
            return True
    return False


def _direct_text_child(call: ast.Call) -> ast.Call | None:
    """A direct ``child=``/``children=[...]`` widget call, if present."""
    for kw in call.keywords:
        if kw.arg == "child" and isinstance(kw.value, ast.Call):
            return kw.value
        if kw.arg == "children" and isinstance(kw.value, ast.List):
            for el in kw.value.elts:
                if isinstance(el, ast.Call):
                    return el
    return None


def _contrast_issue(fg: str, bg: str, call: ast.Call, filepath: str,
                    where: str) -> dict | None:
    """Build a contrast finding for *fg* over *bg*, or ``None`` if it passes."""
    if _alpha(fg) == 0 or _alpha(bg) == 0:
        return None  # transparent either side — nothing to measure
    from pydrud.widgets.theme import Colors

    ratio = round(Colors.contrast(fg, bg), 1)
    large = _is_large_text(call)
    threshold = _AA_LARGE if large else _AA_NORMAL
    if ratio >= threshold:
        return None
    kind = "large text" if large else "normal text"
    return {
        "file": filepath,
        "line": call.lineno,
        "severity": _SEVERITY_WARNING,
        "message": f"Low contrast{where}: {fg} on {bg} is {ratio:.1f}:1 — "
                   f"WCAG AA needs {threshold:g}:1 for {kind}. Try "
                   f"Colors.on({bg!r}) for a readable foreground.",
    }


def _check_contrast(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn about text/background pairs that fail WCAG AA (PYDRUD §14.7).

    The check sees two shapes statically: a single widget that declares both
    a text colour and a background (``Button(color=…, bg_color=…)``,
    ``Text(color=…, style={"bg": …})``), and a container whose ``bg`` is a
    literal with a direct text child carrying a literal colour. Colours
    written as ``Colors.X`` tokens are resolved too, so
    ``Colors.GREY_LIGHT`` on ``Colors.WHITE`` is caught as surely as the
    hex strings it expands to.
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fg, bg = _foreground(node), _background(node)
        if fg is not None and bg is not None:
            found = _contrast_issue(fg, bg, node, filepath, "")
            if found:
                issues.append(found)
        # Parent background + direct text child foreground. Report at the
        # child's line, and use the child to judge large text.
        if bg is not None:
            child = _direct_text_child(node)
            if child is not None:
                child_fg = _foreground(child)
                if child_fg is not None:
                    found = _contrast_issue(child_fg, bg, child, filepath,
                                            " (child text)")
                    if found:
                        issues.append(found)
    return issues


# ── Check 10: Accessibility — 48 dp touch targets (PYDRUD §14.7) ────────────


def _literal_dp(node: ast.AST) -> float | None:
    """A dimension literal in dp: ``48``, ``48.0`` or ``"48dp"``."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return None
        if isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node.value, str):
            text = node.value.strip().lower().removesuffix("dp").strip()
            try:
                return float(text)
            except ValueError:
                return None
    return None


def _check_touch_targets(tree: ast.AST, filepath: str) -> list[dict]:
    """Warn when an interactive widget is pinned below 48 dp (PYDRUD §14.7).

    Material and WCAG 2.5.5 both ask for a ≥ 48 dp touch target. Pydrud
    already pads its stock buttons, but an explicit ``width``/``height`` in
    ``style`` overrides that padding — this flags the cases where the
    developer has shrunk a control below the accessible minimum.
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _get_call_name(node) not in _INTERACTIVE_WIDGETS:
            continue
        style = next((kw.value for kw in node.keywords
                      if kw.arg == "style" and isinstance(kw.value, ast.Dict)),
                     None)
        if style is None:
            continue
        for axis in ("width", "height"):
            value = _literal_dp(_dict_path(style, axis))
            if value is not None and value < 48:
                issues.append({
                    "file": filepath,
                    "line": node.lineno,
                    "severity": _SEVERITY_WARNING,
                    "message": f"{_get_call_name(node)} has {axis}={value:g} dp — "
                               "interactive controls need a ≥ 48 dp touch "
                               "target (WCAG 2.5.5). Drop the explicit size or "
                               "grow it to 48.",
                })
    return issues


# ── Check 11: Package shadowing ─────────────────────────────────────────────


def _check_shadowing_issues(src_dir: str) -> list[dict]:
    """Check for directory packages that shadow same-named .py modules."""
    issues: list[dict] = []
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        py_stems = {f[:-3]: f for f in files if f.endswith(".py") and f != "__init__.py"}
        for d in dirs:
            if d in py_stems:
                dir_path = os.path.relpath(os.path.join(root, d), src_dir)
                py_path = os.path.relpath(os.path.join(root, py_stems[d]), src_dir)
                issues.append({
                    "file": py_path,
                    "line": 1,
                    "severity": _SEVERITY_ERROR,
                    "message": f"Package shadowing: directory '{dir_path}' shadows module '{py_path}'. "
                               "Python import resolution prioritizes package directories over modules with the same name.",
                })
    return issues


# ── Check 11b: app code that needs an unbundled camera stack ────────────────


#: Source patterns that only work when the camera stack is bundled.
_CAMERA_USE = re.compile(r"\bCameraPreview\s*\(|\bpage\s*\.\s*camera\b")


def _project_root_of(src_dir: str) -> str | None:
    """The Pydrud project directory containing *src_dir*, if there is one."""
    current = os.path.abspath(src_dir)
    while True:
        if os.path.isfile(os.path.join(current, "pydrud.yaml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _check_camera_optin(src_dir: str) -> list[dict]:
    """Report ``CameraPreview``/``page.camera`` use without the camera stack.

    CameraX and ML Kit are opt-in because they add ~10 MB of native
    libraries to every APK. A project that uses them but never enabled
    ``camera:`` builds fine and then shows a placeholder at runtime, which
    is a confusing way to discover the setting — so say it here instead.
    """
    root = _project_root_of(src_dir)
    if root is None:
        return []

    from pydrud.commands.project import (
        _camera_already_bundled, android_platform_present,
    )
    from pydrud.commands.project.config import _config_bool
    from pydrud.commands.project_config import load_project_config

    if not android_platform_present(root):
        return []  # Pydash renders through the client app, not this APK.

    config = load_project_config(root)
    if _config_bool(config, "camera", _camera_already_bundled(root)):
        return []
    permissions = config.get("permissions")
    if isinstance(permissions, list) and any(
            str(name).strip().upper() == "CAMERA" for name in permissions):
        return []

    issues: list[dict] = []
    for folder, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".venv", "venv"}]
        # ``src/pydrud`` is the framework copy bundled into the APK: it
        # defines CameraPreview rather than using it, so it is not app code.
        if os.path.relpath(folder, src_dir).split(os.sep)[:1] == ["pydrud"]:
            continue
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            try:
                with open(path, encoding="utf-8") as handle:
                    lines = handle.readlines()
            except OSError:
                continue
            for number, line in enumerate(lines, start=1):
                if line.lstrip().startswith("#"):
                    continue
                if _CAMERA_USE.search(line):
                    issues.append({
                        "file": os.path.relpath(path, src_dir),
                        "line": number,
                        "severity": _SEVERITY_WARNING,
                        "message": (
                            "camera use without the camera stack: this build "
                            "does not bundle CameraX/ML Kit, so the widget "
                            "shows its fallback and page.camera calls fail. "
                            "Set 'camera: true' in pydrud.yaml (or run "
                            "'pydrud permissions add camera'), then "
                            "'pydrud sync'."),
                    })
    return issues


# ── Check 12: Build-time-only imports (DX-003) ──────────────────────────────


#: Pydrud submodules the bundler strips from the APK.
#: Kept in step with ``BUNDLE_EXCLUDES`` in ``pydrud.commands.project``.
_HOST_ONLY_MODULES = frozenset({
    "android", "commands", "utils", "packages", "compatibility",
    "preview", "preview_server", "qr",
})


def _host_only_module(module: str) -> str | None:
    """The build-time-only ``pydrud`` submodule *module* names, if any."""
    if not module.startswith("pydrud."):
        return None
    part = module.split(".", 2)[1]
    return part if part in _HOST_ONLY_MODULES else None


def _check_host_only_imports(tree: ast.AST, filepath: str, *,
                             runtime: str = "chaquopy") -> list[dict]:
    """Report imports unavailable in the selected runtime (DX-003).

    Chaquopy strips CLI, Android build tooling and preview-only modules from
    its bundled runtime. Pydash runs against the installed host package, so
    those host modules are not falsely reported as APK omissions; explicit
    Android implementation imports are still rejected for the cross-platform
    host preview.
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
                if node.module in {"pydrud", "pydrud.platforms"}:
                    modules.extend(
                        f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        else:
            continue

        for module in modules:
            if runtime == "pydash":
                if not (module == "pydrud.android"
                        or module.startswith("pydrud.android.")
                        or module == "pydrud.platforms.android"
                        or module.startswith("pydrud.platforms.android.")):
                    continue
                message = (
                    f"'{module}' is Android-specific; Pydash runs the app "
                    "from the host and does not expose Android implementation "
                    "APIs. Use the platform-neutral Pydrud API and renderer-"
                    "advertised capabilities instead."
                )
            else:
                part = _host_only_module(module)
                if part is None:
                    continue
                message = (
                    f"'{module}' is build-time only — the bundler strips "
                    f"pydrud.{part} from the Chaquopy APK, so this import "
                    "works in a checkout but fails on device (DX-003). "
                    "Import only the runtime API from `pydrud`."
                )
            issues.append({
                "file": filepath,
                "line": node.lineno,
                "severity": _SEVERITY_ERROR,
                "message": message,
            })
    return issues


# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_call_name(node: ast.Call) -> str:
    """Extract the full function name from a Call node, e.g. ``page.add``."""
    if isinstance(node.func, ast.Attribute):
        parts = []
        curr = node.func
        while isinstance(curr, ast.Attribute):
            parts.append(curr.attr)
            curr = curr.value
        if isinstance(curr, ast.Name):
            parts.append(curr.id)
        elif isinstance(curr, ast.Call):
            parts.append("<call>")
        return ".".join(reversed(parts))
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _find_calls_in_node(node: ast.AST) -> list[str]:
    """Collect all callable names found in an AST node."""
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _get_call_name(child)
            if name:
                calls.append(name)
    return calls


# ── Formatter ────────────────────────────────────────────────────────────────


def format_report(issues: list[dict], json_output: bool = False) -> str:
    """Format analysis results as a human-readable or JSON report."""
    if json_output:
        import json
        return json.dumps(issues, indent=2)

    header = tui.render_command_header(
        "analyze",
        "Static analysis",
        subtitle="Checking Pydrud source for correctness and performance issues",
    )
    if not issues:
        return header + tui.render_summary(
            "No issues found", (("Status", "source looks good"),)
        )

    errors = [i for i in issues if i["severity"] == _SEVERITY_ERROR]
    warnings = [i for i in issues if i["severity"] == _SEVERITY_WARNING]
    lines: list[str] = [header.rstrip()]

    if errors:
        lines.append(tui.render_section(f"Errors · {len(errors)}", colour=tui.C_ERROR))
        for issue in errors:
            location = f"{issue['file']}:{issue['line']}"
            lines.append(tui.error_badge(
                f"{tui.BOLD}{location}{tui.RESET}  {issue['message']}"))

    if warnings:
        lines.append(tui.render_section(
            f"Warnings · {len(warnings)}", colour=tui.C_WARN))
        for issue in warnings:
            location = f"{issue['file']}:{issue['line']}"
            lines.append(tui.warn_badge(
                f"{tui.BOLD}{location}{tui.RESET}  {issue['message']}"))

    lines.append(tui.render_summary(
        f"{len(issues)} issue(s) found",
        (("Errors", len(errors)), ("Warnings", len(warnings))),
        success=not errors,
    ).rstrip())
    return "\n".join(lines) + "\n"
