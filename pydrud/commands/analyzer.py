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

from pydrud.utils import tui

# ── Issue types ──────────────────────────────────────────────────────────────

_SEVERITY_WARNING = "warning"
_SEVERITY_ERROR = "error"

# Known Pydrud widget classes that should have keys in dynamic lists.
_WIDGET_CLASSES = {
    "Container", "Column", "Row", "Center", "Spacer", "Divider",
    "Stack", "Positioned", "SizedBox", "Padding", "Card", "ListView", "GridView",
    "Text", "Button", "FilledButton", "TonalButton", "OutlinedButton",
    "TextButton", "ElevatedButton", "IconButton", "TextField",
    "SearchField", "EmailField", "PasswordField", "NumberField",
    "PhoneField", "UrlField", "Image", "SvgPicture", "Icon", "Checkbox", "Switch",
    "ProgressBar", "LinearProgress", "Slider", "Dropdown", "Radio",
    "AppBar", "Scaffold", "FloatingActionButton",
    # v1.2 — Material components
    "ListTile", "ExpansionTile", "Chip", "AssistChip", "FilterChip",
    "InputChip", "SuggestionChip", "Badge", "Avatar", "Banner",
    "Tooltip", "Tabs", "BottomNavigationBar", "NavigationRail", "Drawer",
    "SegmentedButton", "SearchBar", "Rating", "CircularProgress", "Skeleton",
    "RefreshIndicator", "Stepper", "WebView", "VideoPlayer", "Chart",
    # v1.2 — gestures, animation and forms
    "GestureDetector", "InkWell", "Dismissible", "Draggable",
    # v1.3 — painting, hardware, maps, rich text, big lists
    "Canvas", "CameraPreview", "QRScanner", "MapView", "RichText", "Markdown",
    "ReorderableList", "InfiniteList",
    "AnimatedContainer", "AnimatedOpacity", "AnimatedScale",
    "AnimatedRotation", "AnimatedSwitcher", "FadeIn", "SlideIn", "ScaleIn",
    "Hero", "Form", "FormField",
    # v1.5 — responsive layout
    "ResponsiveBuilder", "AdaptiveLayout", "ResponsiveGrid", "ShowWhen",
    "SafeArea", "NavigationBar", "TabBar",
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
}

# Style property keys known to be valid.
_VALID_STYLE_KEYS = {
    "bg", "opacity", "width", "height", "minWidth", "maxWidth",
    "minHeight", "maxHeight", "padding", "margin", "border", "borderRadius",
    "font", "textAlign", "alignment", "expand", "visible", "tooltip",
    "rotate", "fit", "bgImage", "elevation", "position", "bottom", "right",
    "top", "left", "spacing", "mainAxis", "crossAxisAlignment", "scroll",
    "variant", "icon", "buttonSize", "disabled", "multiline", "password",
    "readOnly", "keyboard", "activeColor", "color", "thickness",
    "textScale", "status_bar_color", "icon_brightness",
    "borderLeft", "borderRight", "borderTop", "borderBottom",
    "columns", "circular", "divisions", "maxLines", "overflow", "selectable",
    "tristate", "crossAxis", "mainAxisAlignment",
    # v1.2
    "animation", "scale", "rotation", "drawerSide", "fabPosition",
    "safeArea", "resizeForKeyboard", "shadow", "aspectRatio", "zIndex",
    # v1.5 — responsive
    "safeAreaTop", "safeAreaBottom", "breakpoint",
    # read by the native renderer (ViewFactory / MaterialViews)
    "gradient", "feedback", "role", "pill", "accent", "size",
    "minItemWidth", "maxColumns", "tabletColumns",
}


def run_analysis(path: str = "src") -> list[dict]:
    """Run static analysis on all Python files under *path*.

    Returns a list of issue dicts with keys:
    - file (str): relative file path
    - line (int): line number
    - severity (str): "warning" or "error"
    - message (str): description of the issue
    """
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

    for root, _dirs, files in os.walk(src_dir):
        # Skip __pycache__ and virtual environments.
        if "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        for fname in sorted(files):
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, os.getcwd())
                try:
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    issues.extend(_analyze_file(source, rel_path))
                except Exception as exc:
                    issues.append({
                        "file": rel_path,
                        "line": 0,
                        "severity": _SEVERITY_WARNING,
                        "message": f"Could not parse: {exc}",
                    })

    return issues


def _analyze_file(source: str, filepath: str) -> list[dict]:
    """Analyze a single Python file and return issues."""
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
    """
    issues: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While, ast.ListComp,
                                 ast.SetComp, ast.GeneratorExp)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = _get_call_name(child)
            if func not in _WIDGET_CLASSES:
                continue
            has_key = any(kw.arg == "key" for kw in child.keywords if kw.arg is not None)
            if not has_key:
                issues.append({
                    "file": filepath,
                    "line": child.lineno,
                    "severity": _SEVERITY_WARNING,
                    "message": f"{func}() built in a loop without an explicit key= "
                               "-- dynamic lists diff better with stable keys",
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


# ── Check 6: Package shadowing ──────────────────────────────────────────────


def _check_shadowing_issues(src_dir: str) -> list[dict]:
    """Check for directory packages that shadow same-named .py modules."""
    issues: list[dict] = []
    for root, dirs, files in os.walk(src_dir):
        if "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        py_stems = {f[:-3]: f for f in files if f.endswith(".py") and f != "__init__.py"}
        for d in dirs:
            if d in py_stems:
                dir_path = os.path.relpath(os.path.join(root, d), os.getcwd())
                py_path = os.path.relpath(os.path.join(root, py_stems[d]), os.getcwd())
                issues.append({
                    "file": py_path,
                    "line": 1,
                    "severity": _SEVERITY_ERROR,
                    "message": f"Package shadowing: directory '{dir_path}' shadows module '{py_path}'. "
                               "Python import resolution prioritizes package directories over modules with the same name.",
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
