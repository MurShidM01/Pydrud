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
import sys
from typing import Any

# ── Issue types ──────────────────────────────────────────────────────────────

_SEVERITY_WARNING = "warning"
_SEVERITY_ERROR = "error"

# Known Pydrud widget classes that should have keys in dynamic lists.
_WIDGET_CLASSES = {
    "Container", "Column", "Row", "Center", "Spacer", "Divider",
    "Stack", "Positioned", "SizedBox", "Padding", "Card", "ListView", "GridView",
    "Text", "Button", "TextField", "Image", "Icon", "Checkbox", "Switch",
    "ProgressBar", "Slider", "Dropdown", "Radio",
    "AppBar", "Scaffold", "FloatingActionButton",
    # v1.2 — Material components
    "ListTile", "ExpansionTile", "Chip", "Badge", "Avatar", "Banner",
    "Tooltip", "Tabs", "BottomNavigationBar", "NavigationRail", "Drawer",
    "SegmentedButton", "SearchBar", "Rating", "CircularProgress", "Skeleton",
    "RefreshIndicator", "Stepper", "WebView", "VideoPlayer", "Chart",
    # v1.2 — gestures, animation and forms
    "GestureDetector", "InkWell", "Dismissible", "Draggable",
    # v1.3 — painting, hardware, maps, rich text, big lists
    "Canvas", "CameraPreview", "MapView", "RichText", "Markdown",
    "ReorderableList", "InfiniteList",
    "AnimatedContainer", "AnimatedOpacity", "AnimatedScale",
    "AnimatedRotation", "AnimatedSwitcher", "FadeIn", "SlideIn", "ScaleIn",
    "Hero", "Form", "FormField",
    # v1.5 — responsive layout
    "ResponsiveBuilder", "AdaptiveLayout", "ResponsiveGrid", "ShowWhen",
    "SafeArea", "NavigationBar", "TabBar",
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
    "minItemWidth", "tabletColumns",
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

    return issues


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

    if not issues:
        return "\n  [OK] No issues found.\n"

    lines: list[str] = ["\n  [ANALYSIS] Pydrud Analysis Report"]
    lines.append(f"  {'=' * 50}")

    errors = [i for i in issues if i["severity"] == _SEVERITY_ERROR]
    warnings = [i for i in issues if i["severity"] == _SEVERITY_WARNING]

    if errors:
        lines.append(f"\n  [ERRORS] ({len(errors)}):")
        for i in errors:
            lines.append(f"    {i['file']}:{i['line']}  {i['message']}")

    if warnings:
        lines.append(f"\n  [WARNINGS] ({len(warnings)}):")
        for i in warnings:
            lines.append(f"    {i['file']}:{i['line']}  {i['message']}")

    lines.append(f"\n  {'=' * 50}")
    lines.append(f"  Total: {len(issues)} issues "
                 f"({len(errors)} errors, {len(warnings)} warnings)\n")
    return "\n".join(lines)
