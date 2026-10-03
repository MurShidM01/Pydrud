"""
Pydrud project scaffold — generates a complete Android + Python project tree.
"""

from __future__ import annotations
import io
import os
import re
import tokenize
import unicodedata
import shutil
import sys

from jinja2 import Environment, PackageLoader, select_autoescape

from pydrud.utils.colors import fail, info
from pydrud.utils import tui
from pydrud.compatibility import COMPATIBILITY
from pydrud.commands.project_config import load_project_config


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


def bundled_runtime_size_kb(bundle_dir: str) -> float:
    """Size of a vendored runtime in KB, independent of line endings.

    ``\\r\\n`` counts as one byte so the number is identical on a Windows
    checkout and a Unix one — otherwise the same bundle measures ~3% larger
    on Windows purely because of CRLF, which is not a real APK cost.
    """
    total = 0
    for root, dirs, files in os.walk(bundle_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]  # never vendored
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as fh:
                data = fh.read()
            total += len(data) - data.count(b"\r\n")
    return total / 1024


def _strip_runtime_comments(bundle_dir: str) -> None:
    """Remove comments from vendored Python without changing executable code.

    Pydrud deliberately ships readable source in the repository, while an APK
    benefits from not carrying its many implementation comments. Tokenisation
    keeps line breaks intact (tracebacks still point at useful source lines)
    and is safer than a text-based ``#`` replacement inside string literals.
    """
    for root, _dirs, files in os.walk(bundle_dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
                tokens = tokenize.generate_tokens(io.StringIO(source).readline)
                compact = tokenize.untokenize(
                    token for token in tokens if token.type != tokenize.COMMENT)
                with open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(compact)
            except (OSError, tokenize.TokenError):
                # A source file that cannot be compacted is still safe to
                # ship verbatim; import correctness is more important than a
                # few bytes in a generated project.
                continue


def _bundle_pydrud_source(project_dir: str):
    """Copy the Pydrud *runtime* into the generated project's ``src/``.

    Chaquopy imports the framework from the APK, so it has to be vendored.
    Only the runtime packages are copied: everything in ``BUNDLE_EXCLUDES``
    — the CLI and its terminal UI, the project templates, the launcher icons
    — is build-time only and would otherwise add megabytes of dead weight to
    every APK.
    """
    src_dir = os.path.join(project_dir, "src")
    pydrud_src = os.path.normpath(os.path.dirname(os.path.dirname(__file__)))
    dst = os.path.join(src_dir, "pydrud")
    if not os.path.isdir(pydrud_src):
        print(fail("Could not locate the pydrud package to bundle."))
        return

    if os.path.isdir(dst):
        shutil.rmtree(dst)

    shutil.copytree(pydrud_src, dst,
                    ignore=shutil.ignore_patterns(*BUNDLE_EXCLUDES))
    _strip_runtime_comments(dst)

    files = sum(len(f) for _, _, f in os.walk(dst))
    size_kb = bundled_runtime_size_kb(dst)
    print(info(f"Bundled pydrud runtime ({files} files, {size_kb:.0f} KB)"))


def _copy_icon_resources(project_dir: str, *, overwrite: bool = True):
    """Copy launcher icons from pydrud's template res/ into the generated project.

    With ``overwrite=False`` (used by ``pydrud sync``) only *missing* files
    are filled in, so icons the user generated with ``pydrud icons`` or
    replaced by hand are never clobbered.
    """
    import shutil
    # The res/ lives alongside the templates/ inside the installed package.
    src_res = os.path.join(os.path.dirname(__file__), "..", "android", "templates", "res")
    dst_res = os.path.join(project_dir, "android", "app", "src", "main", "res")
    src_res = os.path.normpath(src_res)
    if not os.path.isdir(src_res):
        return
    for root, _dirs, files in os.walk(src_res):
        relative = os.path.relpath(root, src_res)
        for name in files:
            if not (name.endswith(".png") or name.endswith(".xml")):
                continue
            src_item = os.path.join(root, name)
            dst_item = os.path.join(dst_res, relative, name) \
                if relative != "." else os.path.join(dst_res, name)
            if not overwrite and os.path.exists(dst_item):
                continue
            _ensure_dir(os.path.dirname(dst_item))
            shutil.copy2(src_item, dst_item)


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
            "C:\\Android\\Sdk",
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
)


#: CPython versions Chaquopy accepts as ``buildPython``, newest first.
BUILD_PYTHON_VERSIONS = ("3.13", "3.12", "3.11", "3.10")

#: The Python version the app itself runs on the device.
APP_PYTHON_VERSION = COMPATIBILITY.python_version


def _python_version_of(exe: str, args: list[str] | None = None) -> str:
    """Return ``"3.11"`` for an interpreter, or ``""`` when it will not run."""
    import subprocess

    try:
        probe = subprocess.run(
            [exe, *(args or []), "-c",
             "import sys; print('%d.%d' % sys.version_info[:2]); "
             "print(sys.executable)"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return ""
    if probe.returncode != 0:
        return ""
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    return lines[0] if lines else ""


def _build_python_candidates(
        target: str = APP_PYTHON_VERSION) -> list[tuple[str, list[str]]]:
    """Interpreter commands to probe, most desirable first.

    Each entry is ``(command, extra_args)``. The app's own Python
    (``target``) always comes first so Chaquopy can pre-compile; on
    Windows the ``py`` launcher (``py -3.11``) is preferred because
    versioned ``python3.11.exe`` names rarely exist there.
    """
    preferred = [target] if target else []
    supported = preferred + [v for v in BUILD_PYTHON_VERSIONS
                             if v not in preferred]
    candidates = [(f"python{v}", []) for v in supported]
    if os.name == "nt":
        candidates = [("py", [f"-{v}"]) for v in supported] + candidates
    return candidates


def _detect_build_python(target: str = APP_PYTHON_VERSION) -> str:
    """Pick an interpreter Chaquopy can actually use for ``buildPython``.

    Chaquopy only pre-compiles the app to ``.pyc`` when ``buildPython``
    is the *same* minor version as the Python the APK ships (``target``).
    Otherwise the build prints

        Warning: Failed to compile to .pyc format: [python.exe] is not a
        valid Python 3.11 command: it is version 3.12.

    and ships plain source — the app still works, it just starts a little
    slower. ``target`` is therefore tried first, then any other supported
    version, and the user is told what happened instead of being left to
    decode Chaquopy's warning.
    """
    preferred = [target] if target else []
    supported = preferred + [v for v in BUILD_PYTHON_VERSIONS
                             if v not in preferred]
    candidates = _build_python_candidates(target)

    for command, args in candidates:
        exe = shutil.which(command)
        if not exe:
            continue
        version = _python_version_of(exe, args)
        if not version or version not in supported:
            continue
        resolved = _resolve_executable(exe, args)
        if version != target:
            print(info(
                f"buildPython: using Python {version} "
                f"(the app ships Python {target}); Pydrud will disable "
                f".pyc pre-compilation automatically. The app still runs "
                f"normally, with only a slightly slower first start. Install "
                f"Python {target} or set PYDRUD_PYTHON to enable it."))
        return resolved

    fallback = (shutil.which("python") or shutil.which("python3")
                or sys.executable)
    print(info(
        f"buildPython: no Chaquopy-compatible Python found "
        f"(need {BUILD_PYTHON_VERSIONS[-1]}-{BUILD_PYTHON_VERSIONS[0]}, "
        f"ideally {target}); using {fallback}. "
        f"Set PYDRUD_PYTHON to override."))
    return fallback.replace("\\", "/")


def _resolve_executable(exe: str, args: list[str]) -> str:
    """The real interpreter path behind ``py -3.11`` / ``python3.11``."""
    import subprocess

    try:
        probe = subprocess.run(
            [exe, *args, "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=15,
        )
        path = probe.stdout.strip()
        if probe.returncode == 0 and path:
            return path.replace("\\", "/")
    except Exception:
        pass
    return exe.replace("\\", "/")


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


def _toml_section(project_dir: str, wanted: str) -> dict[str, str]:
    """Read a small scalar section from ``pydrud.toml``.

    TOML remains the home of Python dependencies and the theme seed. Android
    identity and build settings are authoritative in ``pydrud.yaml``; the
    legacy ``[app]`` table is only used as a fallback for older projects.
    """
    path = os.path.join(project_dir, "pydrud.toml")
    if not os.path.isfile(path):
        return {}
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            section = False
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("[") and stripped.endswith("]"):
                    section = stripped == f"[{wanted}]"
                    continue
                if section and "=" in stripped:
                    key, value = stripped.split("=", 1)
                    values[key.strip()] = value.split(" #", 1)[0].strip().strip('"\'')
    except OSError:
        return {}
    return values


def _project_seed(project_dir: str) -> str | None:
    """Read ``[theme] seed`` from pydrud.toml, if the user set one."""
    return _toml_section(project_dir, "theme").get("seed") or None


class ProjectConfigError(ValueError):
    """A user-editable project setting is invalid."""


def _config_string(config: dict, key: str, default: str = "") -> str:
    value = config.get(key, default)
    if isinstance(value, list):
        raise ProjectConfigError(f"'{key}' must be a scalar value")
    return str(value).strip()


def _config_int(config: dict, key: str, default: int, *, minimum: int = 0) -> int:
    value = _config_string(config, key, str(default))
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ProjectConfigError(f"'{key}' must be an integer, got {value!r}") from exc
    if parsed < minimum:
        raise ProjectConfigError(f"'{key}' must be at least {minimum}")
    return parsed


def _config_bool(config: dict, key: str, default: bool = False) -> bool:
    value = _config_string(config, key, "true" if default else "false").lower()
    if value in {"true", "yes", "on", "1"}:
        return True
    if value in {"false", "no", "off", "0", ""}:
        return False
    raise ProjectConfigError(
        f"'{key}' must be true or false, got {value!r}")


def _config_list(config: dict, key: str, default=()) -> list[str]:
    if key not in config:
        return list(default)
    value = config[key]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    # A comma-separated scalar is accepted for compatibility with the old
    # flat parser, though generated manifests always use a real YAML list.
    return [item.strip().strip('"\'') for item in text.split(",") if item.strip()]


def _validate_package(package: str) -> str:
    parts = package.split(".")
    if len(parts) < 2 or any(
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
            or part in _JAVA_KEYWORDS for part in parts):
        raise ProjectConfigError(
            f"'package' must be a Java package such as com.example.my_app, got {package!r}")
    return package


def _gradle_value(project_dir: str, pattern: str, default: str) -> str:
    """Read a generated Gradle value so old projects retain it on migration."""
    path = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    try:
        with open(path, encoding="utf-8") as handle:
            match = re.search(pattern, handle.read())
    except OSError:
        match = None
    return match.group(1) if match else default


def _manifest_permissions(project_dir: str) -> list[str]:
    """Recover explicit permissions from a pre-manifest-config project."""
    import xml.etree.ElementTree as ET

    path = os.path.join(project_dir, "android", "app", "src", "main",
                        "AndroidManifest.xml")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    attribute = "{http://schemas.android.com/apk/res/android}name"
    built_in = {"INTERNET", "ACCESS_NETWORK_STATE"}
    return [
        name.rsplit(".", 1)[-1]
        for node in root.findall("uses-permission")
        if (name := node.get(attribute, "")) and name.rsplit(".", 1)[-1] not in built_in
    ]


def _sync_context(project_dir: str, found: dict) -> dict:
    """Resolve the complete Android template context from ``pydrud.yaml``."""
    config = load_project_config(project_dir)
    legacy_app = _toml_section(project_dir, "app")

    display_name = (_config_string(config, "app_name")
                    or legacy_app.get("name")
                    or os.path.basename(os.path.abspath(project_dir)))
    if not display_name:
        raise ProjectConfigError("'app_name' cannot be empty")
    package = _validate_package(
        _config_string(config, "package")
        or legacy_app.get("package")
        or found["package"])

    min_sdk = _config_int(config, "min_sdk", COMPATIBILITY.min_sdk, minimum=1)
    target_sdk = _config_int(config, "target_sdk", COMPATIBILITY.target_sdk,
                             minimum=1)
    compile_sdk = _config_int(
        config, "compile_sdk", max(target_sdk, COMPATIBILITY.compile_sdk),
        minimum=1)
    if min_sdk > target_sdk:
        raise ProjectConfigError("'min_sdk' cannot be greater than 'target_sdk'")
    if compile_sdk < target_sdk:
        raise ProjectConfigError("'compile_sdk' cannot be lower than 'target_sdk'")

    version_code_default = int(_gradle_value(
        project_dir, r"versionCode\s*=\s*(\d+)", "1"))
    version_name_default = _gradle_value(
        project_dir, r'versionName\s*=\s*"([^"]+)"', "1.0.0")
    version_code = _config_int(
        config, "version_code", version_code_default, minimum=1)
    version_name = _config_string(
        config, "version_name", version_name_default) or version_name_default

    pydrud_app_name = _slugify(display_name)
    android_app_name = _camel(display_name)
    scheme = (_config_string(config, "scheme")
              or legacy_app.get("scheme")
              or pydrud_app_name.replace("_", ""))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", scheme):
        raise ProjectConfigError(
            f"'scheme' must be a valid Android URI scheme, got {scheme!r}")

    permissions = _config_list(
        config, "permissions",
        _manifest_permissions(project_dir) if "permissions" not in config else ())
    from pydrud.commands.release import resolve_permission
    permissions = list(dict.fromkeys(
        resolved for name in permissions
        if (resolved := resolve_permission(name))
        not in {"INTERNET", "ACCESS_NETWORK_STATE"}
    ))

    from pydrud.commands.release import (
        CAPABILITY_PERMISSIONS, KNOWN_CAPABILITIES, resolve_capability,
    )
    try:
        capability_names = {resolve_capability(name)
                            for name in _config_list(config, "capabilities")}
    except ValueError as exc:
        raise ProjectConfigError(str(exc)) from exc
    known_capabilities = set(KNOWN_CAPABILITIES)
    generated_permissions = set().union(*(
        CAPABILITY_PERMISSIONS[name] for name in capability_names
    )) if capability_names else set()
    permissions = [name for name in permissions if name not in generated_permissions]

    abi_filters_list = _config_list(
        config, "abi_filters", ("arm64-v8a", "armeabi-v7a", "x86_64"))
    if not abi_filters_list:
        raise ProjectConfigError("'abi_filters' must contain at least one ABI")

    assets_dir = _config_string(config, "assets_dir", "assets") or "assets"
    assets_dir = assets_dir.replace("\\", "/").strip("/")
    if not assets_dir or any(part == ".." for part in assets_dir.split("/")):
        raise ProjectConfigError("'assets_dir' must stay inside the project")

    python_version = _config_string(
        config, "python_version", COMPATIBILITY.python_version)
    old_python = _gradle_value(
        project_dir,
        r'buildPython\(System\.getenv\("PYDRUD_PYTHON"\)\s*\?:\s*"([^"]+)"\)',
        sys.executable.replace("\\", "/"))
    seed = _normalise_color(_project_seed(project_dir))

    from pydrud.commands.packages import Requirements

    return {
        "project_name": display_name,
        "app_name": android_app_name,
        "pydrud_app_name": pydrud_app_name,
        "package": package,
        "package_path": package.replace(".", "/"),
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "compile_sdk": compile_sdk,
        "ndk": _config_string(config, "ndk", COMPATIBILITY.ndk_version),
        "python_version": python_version,
        "python_executable": old_python,
        "pydrud_runtime_version": _config_string(
            config, "framework_version", COMPATIBILITY.android_runtime_version),
        "protocol_version": _config_int(
            config, "protocol_version", COMPATIBILITY.protocol_version,
            minimum=1),
        "chaquopy_version": _config_string(
            config, "chaquopy_version", COMPATIBILITY.chaquopy_version),
        "agp_version": _config_string(
            config, "agp_version", COMPATIBILITY.agp_version),
        "gradle_version": _config_string(
            config, "gradle_version", COMPATIBILITY.gradle_version),
        "assets_dir": assets_dir,
        "version_code": version_code,
        "version_name": version_name,
        "scheme": scheme,
        "app_links_host": _config_string(config, "app_links_host"),
        "abi_filters_list": abi_filters_list,
        "abi_filters": ", ".join(f'"{abi}"' for abi in abi_filters_list),
        "permissions": permissions,
        "capabilities_list": sorted(capability_names),
        "capabilities": {name: name in capability_names
                         for name in known_capabilities},
        "firebase": _config_bool(
            config, "firebase", found.get("firebase", False)
            or os.path.isfile(os.path.join(project_dir, "google-services.json"))),
        "shrink": "true" if _config_bool(config, "shrink", False) else "false",
        "pip_packages": Requirements(project_dir).requirement_strings(),
        "seed_color": seed,
    }


def _render_native_layer(project_dir: str, java_package_path: str, ctx: dict):
    """Write the Java renderer and its theme resources.

    Shared by ``pydrud init`` and ``pydrud sync`` so an existing project can
    pick up a new Pydrud release without being recreated.
    """
    java_dir = f"{project_dir}/android/app/src/main/java/{java_package_path}"
    _ensure_dir(java_dir)

    _write_template("android/MainActivity.java.j2",
                    f"{java_dir}/{ctx['app_name']}Activity.java", ctx)
    for name in _JAVA_TEMPLATES:
        _write_template(f"android/{name}.java.j2", f"{java_dir}/{name}.java", ctx)
    if ctx.get("firebase"):
        _write_template("android/PydrudMessagingService.java.j2",
                        f"{java_dir}/PydrudMessagingService.java", ctx)

    # Material theme resources. The night variant keeps native dialogs and
    # system bars in step with ``Theme.dark()`` on the Python side.
    _ensure_dir(f"{project_dir}/android/app/src/main/res/values")
    _ensure_dir(f"{project_dir}/android/app/src/main/res/values-night")
    colors = _theme_colors(ctx.get("seed_color") or _project_seed(project_dir))
    _write_template("android/themes.xml.j2",
                    f"{project_dir}/android/app/src/main/res/values/themes.xml",
                    {**ctx, "night": False, "colors": colors["light"]})
    _write_template("android/themes.xml.j2",
                    f"{project_dir}/android/app/src/main/res/values-night/themes.xml",
                    {**ctx, "night": True, "colors": colors["dark"]})

    # App-specific tag IDs. ViewFactory/MaterialViews use keyed view tags
    # (slider ranges, change listeners, composite child hosts), and Android
    # rejects framework IDs there — these must come from the app's own
    # resources or every Slider/Switch/Tabs render fails at runtime.
    _write_template("android/ids.xml.j2",
                    f"{project_dir}/android/app/src/main/res/values/ids.xml", ctx)


def create_project(
    name: str,
    org: str = "com.example",
    min_sdk: int = 24,
    target_sdk: int = COMPATIBILITY.target_sdk,
    pip_packages=None,
    firebase: bool = False,
    permissions=None,
    accent: str | None = None,
):
    """Scaffold a new Pydrud project in a subdirectory ``./<name>/``.

    ``accent`` is the brand colour the whole design system is generated
    from — the Python palette, the generated ``themes.xml`` and the
    starter app all start from it.
    """

    project_dir = os.path.join(os.getcwd(), _slugify(name))
    if os.path.exists(project_dir):
        print(fail(f"Directory '{project_dir}' already exists."))
        sys.exit(1)

    pydrud_app_name = _slugify(name)
    package = _sanitize_package(org, pydrud_app_name)
    android_app_name = _camel(name)
    package_path = package.replace(".", "/")

    # Build the package path for the generated Java source.
    java_package_path = package_path  # e.g. "com/example/my_app"

    # Detect SDK for local.properties
    sdk_dir = _detect_sdk()
    # Detect Python executable for Chaquopy buildPython
    python_exe = _detect_build_python()

    # Normalise paths — Windows users get backslashes, but Gradle Kotlin DSL
    # and .properties files treat ``\`` as an escape character.
    sdk_dir = sdk_dir.replace("\\", "/")

    # Detect NDK version for pydrud.yaml
    ndk_version = _detect_ndk(sdk_dir)

    from pydrud.widgets.theme import Colors as _Colors

    seed_color = _normalise_color(accent) or _Colors.PRIMARY
    default_capabilities = ["haptics", "notifications"]
    ctx = {
        "project_name": name,
        "app_name": android_app_name,
        "pydrud_version": _version(),
        "seed_color": seed_color,
        "pydrud_app_name": pydrud_app_name,
        "package": package,
        "package_path": java_package_path,
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "build_tools_version": "36.0.0",  # match what we have
        "compile_sdk": max(int(target_sdk), COMPATIBILITY.compile_sdk),
        "gradle_version": COMPATIBILITY.gradle_version,
        "chaquopy_version": COMPATIBILITY.chaquopy_version,
        "python_version": COMPATIBILITY.python_version,
        "pydrud_runtime_version": COMPATIBILITY.android_runtime_version,
        "protocol_version": COMPATIBILITY.protocol_version,
        "sdk_dir": sdk_dir,
        "python_executable": python_exe,
        "ndk": ndk_version,
        # v1.3: Chaquopy pip packages, Firebase and R8 are data-driven.
        "pip_packages": list(pip_packages or []),
        "firebase": bool(firebase) or os.path.isfile(
            os.path.join(project_dir, "google-services.json")),
        "shrink": "false",
        "version_code": 1,
        "version_name": "1.0.0",
        "permissions": list(permissions or []),
        "capabilities_list": default_capabilities,
        "capabilities": {
            "foreground_service": False,
            "boot_receiver": False,
            "wake_lock": False,
            "haptics": True,
            "notifications": True,
        },
        # ABIs shipped in the APK. 32-bit arm is still common on budget
        # devices; x86_64 keeps the emulator working.
        "abi_filters_list": ["arm64-v8a", "armeabi-v7a", "x86_64"],
        "abi_filters": ", ".join(
            f'"{abi}"' for abi in ("arm64-v8a", "armeabi-v7a", "x86_64")),
        "scheme": pydrud_app_name.replace("_", ""),
        "app_links_host": "",
        "assets_dir": "assets",
    }

    print(tui.render_command_header(
        "init",
        f"Creating {name}",
        subtitle="Scaffolding a native Android application powered by Python",
        details=(("Package", package), ("Directory", project_dir),
                 ("Android", f"API {min_sdk} → {target_sdk}")),
    ))

    # ── 1.  Python source ────────────────────────────────────────────────
    _render_app_package(project_dir, ctx)

    # ── 1b. Bundle pydrud source into the project so Chaquopy can import
    #        it at runtime without needing pip install or network access.
    _bundle_pydrud_source(project_dir)

    # ── 2.  Android / Gradle ─────────────────────────────────────────────
    _render_native_layer(project_dir, java_package_path, ctx)

    # AndroidManifest.xml
    _ensure_dir(f"{project_dir}/android/app/src/main")
    _write_template("android/AndroidManifest.xml.j2",
                    f"{project_dir}/android/app/src/main/AndroidManifest.xml", ctx)

    # Build files
    _write_template("android/build.gradle.kts.j2",
                    f"{project_dir}/android/build.gradle.kts", ctx)
    _write_template("android/app/build.gradle.kts.j2",
                    f"{project_dir}/android/app/build.gradle.kts", ctx)
    _write_template("android/proguard-rules.pro.j2",
                    f"{project_dir}/android/app/proguard-rules.pro", ctx)
    _write_template("android/settings.gradle.kts.j2",
                    f"{project_dir}/android/settings.gradle.kts", ctx)
    _write_template("android/gradle.properties.j2",
                    f"{project_dir}/android/gradle.properties", ctx)
    _write_template("android/local.properties.j2",
                    f"{project_dir}/android/local.properties", ctx)

    # Launcher icons — copy from the pydrud package res/ directory.
    _copy_icon_resources(project_dir)

    # Gradle wrapper
    _ensure_dir(f"{project_dir}/android/gradle/wrapper")
    _ensure_dir(f"{project_dir}/android/gradle")
    _write_template("android/gradlew.j2",
                    f"{project_dir}/android/gradlew", ctx)
    _write_template("android/gradlew.bat.j2",
                    f"{project_dir}/android/gradlew.bat", ctx)
    _write_template("android/gradle/wrapper/gradle-wrapper.properties.j2",
                    f"{project_dir}/android/gradle/wrapper/gradle-wrapper.properties", ctx)

    # Make gradlew executable
    gradlew_path = os.path.join(project_dir, "android", "gradlew")
    os.chmod(gradlew_path, 0o755)

    # ── 3.  Assets directory ──────────────────────────────────────────────
    _ensure_dir(f"{project_dir}/assets")
    # Create a placeholder
    with open(f"{project_dir}/assets/.gitkeep", "w", encoding="utf-8") as f:
        f.write("")
    _write_template("python/pydrud_config.py.j2",
                    f"{project_dir}/src/pydrud_config.py", ctx)

    # ── 3b. Python setup for Chaquopy ─────────────────────────────────────
    _write_template("python/setup.py.j2",
                    f"{project_dir}/setup.py", ctx)

    # ── 4.  Top-level config ──────────────────────────────────────────────
    _write_template("pydrud.yaml.j2", f"{project_dir}/pydrud.yaml", ctx)
    _write_template("pydrud.toml.j2", f"{project_dir}/pydrud.toml", ctx)

    # Write .gitignore
    _write_template("dot.gitignore.j2", f"{project_dir}/.gitignore", ctx)

    # Write a small Python runner script at the top-level
    _write_template("python/run.py.j2", f"{project_dir}/run.py", ctx)

    # ── 5.  Docs and tests ────────────────────────────────────────────────
    _write_template("README.md.j2", f"{project_dir}/README.md", ctx)
    _ensure_dir(f"{project_dir}/tests")
    _write_template("python/project_tests/test_app.py.j2",
                    f"{project_dir}/tests/test_app.py", ctx)
    with open(f"{project_dir}/tests/__init__.py", "w", encoding="utf-8") as f:
        f.write("")

    print(tui.render_summary(
        f"Project '{name}' created",
        (("Package", package), ("Files", "Android + Python scaffold")),
    ))
    print(tui.render_next_steps((
        (f"cd {_slugify(name)}", "enter the project"),
        ("pydrud run", "build, install and start Hot Reload"),
    )))


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


def _render_app_package(project_dir: str, ctx: dict) -> None:
    """Write the structured ``src/app`` package."""
    for folder in ("", "components", "screens"):
        _ensure_dir(os.path.join(project_dir, "src", "app", folder))
    for template, relative in _APP_MODULES:
        _write_template(template,
                        os.path.join(project_dir, "src", "app", *relative.split("/")),
                        ctx)


# ── Upgrading an existing project ────────────────────────────────────────────


def _remove_generated_java(project_dir: str, found: dict) -> None:
    """Remove stale generated classes before a package/name migration.

    Only files owned by Pydrud are removed. Any hand-written Java class in the
    old package is retained, and now-empty package directories are pruned.
    """
    java_root = os.path.join(project_dir, "android", "app", "src", "main", "java")
    old_dir = os.path.join(java_root, *found["package_path"].split("/"))
    generated = {f"{name}.java" for name in _JAVA_TEMPLATES}
    generated.update({"PydrudMessagingService.java",
                      f"{found['app_name']}Activity.java"})
    for filename in generated:
        try:
            os.remove(os.path.join(old_dir, filename))
        except FileNotFoundError:
            pass
    current = old_dir
    while os.path.normpath(current) != os.path.normpath(java_root):
        try:
            os.rmdir(current)
        except OSError:
            break
        current = os.path.dirname(current)


def _render_managed_android(project_dir: str, ctx: dict) -> None:
    """Regenerate every Android file controlled by ``pydrud.yaml``."""
    _render_native_layer(project_dir, ctx["package_path"], ctx)
    main_dir = os.path.join(project_dir, "android", "app", "src", "main")
    _ensure_dir(main_dir)
    _write_template("android/AndroidManifest.xml.j2",
                    os.path.join(main_dir, "AndroidManifest.xml"), ctx)

    android_dir = os.path.join(project_dir, "android")
    _write_template("android/build.gradle.kts.j2",
                    os.path.join(android_dir, "build.gradle.kts"), ctx)
    _write_template("android/app/build.gradle.kts.j2",
                    os.path.join(android_dir, "app", "build.gradle.kts"), ctx)
    _write_template("android/proguard-rules.pro.j2",
                    os.path.join(android_dir, "app", "proguard-rules.pro"), ctx)
    _write_template("android/settings.gradle.kts.j2",
                    os.path.join(android_dir, "settings.gradle.kts"), ctx)
    _write_template("android/gradle.properties.j2",
                    os.path.join(android_dir, "gradle.properties"), ctx)
    _write_template("android/gradlew.j2", os.path.join(android_dir, "gradlew"), ctx)
    _write_template("android/gradlew.bat.j2",
                    os.path.join(android_dir, "gradlew.bat"), ctx)
    _write_template("android/gradle/wrapper/gradle-wrapper.properties.j2",
                    os.path.join(android_dir, "gradle", "wrapper",
                                 "gradle-wrapper.properties"), ctx)
    try:
        os.chmod(os.path.join(android_dir, "gradlew"), 0o755)
    except OSError:
        pass


def _sync_generated_metadata(project_dir: str, ctx: dict) -> None:
    """Refresh generated non-app metadata without touching ``src/app``."""
    _write_template("python/pydrud_config.py.j2",
                    os.path.join(project_dir, "src", "pydrud_config.py"), ctx)
    _write_template("python/setup.py.j2",
                    os.path.join(project_dir, "setup.py"), ctx)


def _sync_toml_identity(project_dir: str, ctx: dict) -> None:
    """Keep the legacy TOML identity mirror aligned with YAML.

    Dependencies, theme settings, comments and unknown TOML sections are
    preserved verbatim.
    """
    path = os.path.join(project_dir, "pydrud.toml")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return

    replacements = {
        "name": ctx["project_name"],
        "package": ctx["package"],
        "scheme": ctx["scheme"],
    }

    def assignment(key: str) -> str:
        escaped = replacements[key].replace("\\", "\\\\").replace('"', '\\"')
        return f'{key} = "{escaped}"'

    in_app = False
    app_found = False
    seen: set[str] = set()
    app_end: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_app:
                app_end = index
            in_app = stripped == "[app]"
            app_found = app_found or in_app
            continue
        if not in_app or "=" not in stripped or stripped.startswith("#"):
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in replacements:
            lines[index] = assignment(key)
            seen.add(key)
    if in_app:
        app_end = len(lines)

    if app_found and app_end is not None:
        missing = [key for key in ("name", "package", "scheme") if key not in seen]
        lines[app_end:app_end] = [assignment(key) for key in missing]
    elif not app_found:
        block = ["[app]"] + [assignment(key)
                             for key in ("name", "package", "scheme")]
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _discover_project(project_dir: str) -> dict | None:
    """Locate the currently generated package and activity.

    This identifies stale files which may need migrating; desired values are
    resolved separately from ``pydrud.yaml``.
    """
    java_root = os.path.join(project_dir, "android", "app", "src", "main", "java")
    if not os.path.isdir(java_root):
        return None

    for root, _dirs, files in os.walk(java_root):
        if "BridgeService.java" not in files:
            continue
        package_path = os.path.relpath(root, java_root).replace(os.sep, "/")
        activity = next((f for f in files if f.endswith("Activity.java")), None)
        app_name = activity[: -len("Activity.java")] if activity else _camel(
            os.path.basename(package_path))
        return {
            "package": package_path.replace("/", "."),
            "package_path": package_path,
            "app_name": app_name,
            "firebase": "PydrudMessagingService.java" in files,
        }
    return None


def sync_project(project_dir: str, *, update_runtime: bool = True) -> bool:
    """Apply ``pydrud.yaml`` to the complete generated Android project.

    Package, app name, SDK/toolchain versions, release metadata, assets,
    permissions and deep-link settings all flow from the system-level YAML
    manifest. The generated Java package is migrated when identity changes.
    User code under ``src/app/`` is never touched.

        $ pydrud sync && pydrud run
    """
    found = _discover_project(project_dir)
    if not found:
        print(fail("No generated Android sources found — is this a Pydrud project?"))
        return False

    try:
        ctx = _sync_context(project_dir, found)
    except (ProjectConfigError, ValueError) as exc:
        print(fail(f"Invalid pydrud.yaml: {exc}"))
        return False

    print(tui.render_command_header(
        "sync",
        f"Syncing {ctx['project_name']}",
        subtitle="Applying pydrud.yaml to the generated Android project",
        details=(("Package", ctx["package"]), ("Pydrud", _version()),
                 ("Runtime", ctx["pydrud_runtime_version"])),
    ))

    identity_changed = (found["package"] != ctx["package"]
                        or found["app_name"] != ctx["app_name"])
    _remove_generated_java(project_dir, found)
    _render_managed_android(project_dir, ctx)
    _sync_generated_metadata(project_dir, ctx)
    _sync_toml_identity(project_dir, ctx)
    # Fill in any launcher icon files the project is missing (never
    # overwriting icons the user generated or replaced themselves).
    _copy_icon_resources(project_dir, overwrite=False)

    count = len(_JAVA_TEMPLATES) + 1 + (1 if ctx["firebase"] else 0)
    detail = "all Android configuration"
    if identity_changed:
        detail += " + package migration"
    print(info(f"Rewrote {count} Java classes + {detail}"))

    if update_runtime:
        _bundle_pydrud_source(project_dir)

    _stamp_version(project_dir)
    print(tui.render_summary(
        "Project synchronized",
        (("Java classes", count), ("Package", ctx["package"]),
         ("Runtime", "updated" if update_runtime else "kept")),
    ))
    print(tui.render_next_steps((("pydrud run", "rebuild and launch"),)))
    return True


def _stamp_version(project_dir: str) -> None:
    """Record which Pydrud generated the native layer, in ``pydrud.yaml``.

    ``pydrud run`` compares this with the installed version and tells the
    user to ``pydrud sync`` when they drift apart — the generated Java and
    the Python runtime are two halves of one protocol.
    """
    path = os.path.join(project_dir, "pydrud.yaml")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return
    stamp = f'pydrud_version: "{_version()}"'
    for index, line in enumerate(lines):
        if line.strip().startswith("pydrud_version:"):
            lines[index] = stamp
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, stamp)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _version() -> str:
    from pydrud import __version__

    return __version__
