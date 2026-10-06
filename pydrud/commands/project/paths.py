"""
Shared names, constants and the Jinja2 environment for project scaffolding.

These are the leaf helpers every other ``project`` submodule reaches for:
filesystem helpers, package/name sanitisers, the shared template renderer
and the build constants the rest of the tooling reads.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata

from jinja2 import Environment, PackageLoader, select_autoescape

from pydrud.compatibility import COMPATIBILITY

# Jinja2 environment — templates live under ``android/templates/``.
_env = Environment(
    loader=PackageLoader("pydrud", "android/templates"),
    autoescape=select_autoescape(["xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _write_template(template_name: str, dest: str, ctx: dict):
    """Render a Jinja2 template and write it to *dest*."""
    template = _env.get_template(template_name)
    content = template.render(**ctx)
    if content and not content.endswith("\n"):
        content += "\n"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)


# Everything that only ever runs on the developer's machine. None of it is
# reachable from ``import pydrud`` on a device, so shipping it would just make
# every APK heavier. ``tests/test_scaffold_project.py`` pins this list and
# proves the bundle never imports its way back into one of these.
BUNDLE_EXCLUDES = (
    "__pycache__", "*.pyc", "*.pyo", ".git", "tests",
    "android",      # Jinja templates + launcher icons (build-time only)
    "commands",     # the CLI (build-time only)
    "utils",        # terminal colours/TUI — imported only by the CLI
    "packages.py",  # deprecated shim for pydrud.commands.packages (CLI only)
    "compatibility.py",  # generated Android toolchain matrix (build-time only)
    "preview.py", "preview_server.py",  # host-only Pydash session/listener
    "qr.py",        # terminal QR encoder for ``pydrud dev`` (host-only)
)


def _sanitize_package(org: str, app_slug: str = "") -> str:
    """Build a valid Java package name from the org prefix and app name.

    ``--org com.example`` + project ``my_app`` → ``com.example.my_app``.
    The app segment is only appended when the org does not already end with
    it, so ``--org com.example.my_app`` stays untouched. Without this, every
    app generated under the same org would share one ``applicationId`` and
    overwrite each other on the device.
    """
    parts = org.strip().lower().split(".")
    clean = []
    for p in parts:
        p = re.sub(r"[^a-z0-9_]", "", p)
        if p and (p[0].isdigit() or p in _JAVA_KEYWORDS):
            p = "_" + p
        if p:
            clean.append(p)
    if not clean:
        clean = ["com", "example"]

    slug = re.sub(r"[^a-z0-9_]", "", (app_slug or "").lower())
    if slug:
        if slug[0].isdigit() or slug in _JAVA_KEYWORDS:
            slug = "_" + slug
        if clean[-1] != slug:
            clean.append(slug)
    return ".".join(clean)


_JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while",
}


def _slugify(name: str) -> str:
    """Convert a project name to a valid Python module name."""
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode(
        "ascii", "ignore").decode("ascii")
    s = ascii_name.strip().lower().replace("-", "_").replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", s)
    if not re.search(r"[a-z0-9]", slug):
        return "my_app"
    # A Python module (and a Java package segment) cannot start with a digit.
    return f"app_{slug}" if slug[0].isdigit() else slug


def _detect_sdk() -> str:
    """Locate the Android SDK directory for local.properties."""
    sdk = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    if sdk and os.path.isdir(sdk):
        return sdk
    if sys.platform == "win32":
        candidates = [
            os.path.expanduser("~\\AppData\\Local\\Android\\Sdk"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Android", "Sdk"),
            os.path.expanduser("~\\Android\\Sdk"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            os.path.expanduser("~/Library/Android/sdk"),
            os.path.expanduser("~/Android/Sdk"),
        ]
    else:
        candidates = [
            "/root/android-sdk",
            os.path.expanduser("~/Android/Sdk"),
            os.path.expanduser("~/android-sdk"),
        ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return ""


def _camel(name: str) -> str:
    """Convert ``my_app`` / ``my-app`` to a valid Java class prefix.

    The result names generated classes (``MyAppActivity``) and is spliced
    into the manifest, so it must be a legal Java identifier: ``2cool``
    produced ``public class 2coolActivity``, which does not compile.
    Separators are dropped, invalid characters are stripped and a leading
    digit is prefixed.
    """
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode(
        "ascii", "ignore").decode("ascii")
    words = re.split(r"[^A-Za-z0-9]+", ascii_name)
    camel = "".join(word[:1].upper() + word[1:] for word in words if word)
    camel = re.sub(r"[^A-Za-z0-9_]", "", camel)
    if not camel:
        return "MyApp"
    if camel[0].isdigit():
        camel = "App" + camel
    return camel


def _version_key(name: str) -> tuple:
    """Sort key that orders ``9.0.1`` *before* ``28.2.3`` (numeric, not text)."""
    return tuple(int(part) if part.isdigit() else -1
                 for part in str(name).split("."))


def _detect_ndk(sdk_dir: str) -> str:
    """Detect the newest installed NDK version from the SDK directory.

    Directory names are compared numerically: a plain ``sorted()`` would
    rank ``"9.0.9519653"`` above ``"28.2.13676358"`` and hand Gradle an NDK
    that is years too old.
    """
    ndk_dir = os.path.join(sdk_dir, "ndk") if sdk_dir else ""
    if ndk_dir and os.path.isdir(ndk_dir):
        try:
            versions = sorted(
                (n for n in os.listdir(ndk_dir)
                 if os.path.isdir(os.path.join(ndk_dir, n))),
                key=_version_key,
            )
            if versions:
                return versions[-1]
        except OSError:
            pass
    return COMPATIBILITY.ndk_version


#: Every Java class that makes up the generated native layer, with the
#: file name it is written to. ``MainActivity`` is special-cased because
#: its class name is derived from the app name.
_JAVA_TEMPLATES = (
    "BridgeService", "ViewFactory", "EventDispatcher", "WidgetRegistry",
    "ViewCreator", "MaterialViews", "PydrudTheme", "PydrudIcons",
    "PydrudNavigation", "GestureBinder", "NativeServices", "PlatformServices", "AdvancedViews",
    "PydrudWorker", "PydrudForegroundService",
    "CaptureServices", "ConnectivityServices",
    # ViewFactory collaborators (extracted to keep every renderer file small).
    "ImageLoader", "ViewStyler", "LayoutEngine", "TreePatcher",
    "EventBinder", "NativeViewFactory", "ViewAnimator", "BuiltinViews",
    # MaterialViews collaborator (navigation family).
    "MaterialNavigationViews",
)


def _normalise_color(value: str | None) -> str | None:
    """Accept #RGB, #RRGGBB and #AARRGGBB (with or without the hash)."""
    if not value:
        return None
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6:
        text = "FF" + text
    if len(text) != 8 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise ValueError(f"'{value}' is not a colour like '#FF0EA5E9'")
    return "#" + text.upper()


def _theme_colors(seed: str | None = None) -> dict:
    """Build the XML palette from the Python colour scheme.

    ``themes.xml`` exists only so native dialogs, text-selection handles
    and the system bars match the app.  Rather than hand-maintaining hex
    in XML, both variants are generated from the same
    :class:`~pydrud.ColorScheme` Python uses at runtime.
    """
    from pydrud.widgets.theme import Colors, ColorScheme

    seed = seed or Colors.PRIMARY

    def palette(dark: bool) -> dict:
        scheme = ColorScheme.from_seed(seed, dark=dark)
        return {
            "primary": scheme.primary,
            "on_primary": scheme.on_primary,
            "primary_container": scheme.primary_container,
            "on_primary_container": Colors.on(scheme.primary_container),
            "secondary": scheme.secondary,
            "on_secondary": scheme.on_secondary,
            "surface": scheme.surface,
            "on_surface": scheme.on_surface,
            "surface_variant": scheme.surface_variant,
            "on_surface_variant": Colors.mix(scheme.on_surface,
                                             scheme.surface_variant, 0.42),
            "outline": scheme.outline,
            "error": scheme.error,
            "background": scheme.background,
            "hint": Colors.mix(scheme.on_surface, scheme.surface, 0.58),
        }

    return {"light": palette(False), "dark": palette(True), "seed": seed}


#: The generated ``src/app`` package: template → path inside ``src/app``.
#: One module per concern, so a real app grows by adding files instead of
#: by growing a single ``main.py``.
_APP_MODULES = (
    ("python/app.py.j2",                     "__init__.py"),
    ("python/main.py.j2",                    "main.py"),
    ("python/app/config.py.j2",              "config.py"),
    ("python/app/state.py.j2",               "state.py"),
    ("python/app/runtime.py.j2",             "runtime.py"),
    ("python/app/jobs.py.j2",                "jobs.py"),
    # ``ui.py`` remains a compatibility shim; reusable UI belongs in the
    # components package so a growing app can split it across modules.
    ("python/app/ui.py.j2",                  "ui.py"),
    ("python/app/components/__init__.py.j2", "components/__init__.py"),
    ("python/app/components/common.py.j2",   "components/common.py"),
    ("python/app/screens/__init__.py.j2",    "screens/__init__.py"),
    ("python/app/screens/playground.py.j2",  "screens/playground.py"),
    ("python/app/screens/details.py.j2",     "screens/details.py"),
)


def _version() -> str:
    from pydrud import __version__

    return __version__
