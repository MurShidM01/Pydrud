"""
Python package management for Android — ``pydrud pip add <name>``.

Apps built with Pydrud embed CPython through Chaquopy, which can install
packages from PyPI *at build time*. Not everything works: a package has to
be pure Python, or be one of the native wheels Chaquopy publishes for
Android ABIs. Installing something unsupported fails deep inside Gradle
with an unhelpful error, so Pydrud keeps a curated registry and refuses
early with an explanation.

    pydrud pip add yt-dlp requests
    pydrud pip list
    pydrud pip search qr
    pydrud pip remove requests
    pydrud pip sync            # re-apply pydrud.toml to the Gradle build

Dependencies are recorded in ``pydrud.toml`` under ``[python.packages]``
and injected into ``app/build.gradle.kts`` inside Chaquopy's
``python { pip { install(...) } }`` block.
"""

from __future__ import annotations

import os
import re
from typing import Iterable, Optional

#: name → (version spec, category, needs ABI wheel, one-line description)
REGISTRY: dict[str, tuple[str, str, bool, str]] = {
    # ── networking & APIs ───────────────────────────────────────────────
    "requests": ("", "network", False, "The classic HTTP client"),
    "httpx": ("", "network", False, "Async-capable HTTP client"),
    "urllib3": ("", "network", False, "Low-level HTTP plumbing"),
    "certifi": ("", "network", False, "Mozilla CA bundle for TLS"),
    "charset-normalizer": ("", "network", False, "Encoding detection"),
    "idna": ("", "network", False, "Internationalised domain names"),
    "websockets": ("", "network", False, "WebSocket client and server"),
    "websocket-client": ("", "network", False, "Blocking WebSocket client"),
    "aiohttp": ("", "network", True, "Async HTTP client/server"),
    "sseclient-py": ("", "network", False, "Server-sent events"),
    "paho-mqtt": ("", "network", False, "MQTT client for IoT devices"),
    "feedparser": ("", "network", False, "RSS and Atom parsing"),
    "yt-dlp": ("", "media", False, "Download video/audio from 1000+ sites"),
    "youtube-search-python": ("", "media", False, "Search YouTube without an API key"),
    "pytube": ("", "media", False, "Lightweight YouTube downloader"),
    "instaloader": ("", "media", False, "Download Instagram media"),
    "telethon": ("", "network", False, "Telegram MTProto client"),
    "tweepy": ("", "network", False, "Twitter/X API client"),
    "praw": ("", "network", False, "Reddit API client"),
    "googletrans": ("4.0.0rc1", "network", False, "Unofficial Google Translate"),
    "deep-translator": ("", "network", False, "Translation via many providers"),
    "wikipedia": ("", "network", False, "Wikipedia article search"),
    "geopy": ("", "network", False, "Geocoding and distance maths"),
    "python-dotenv": ("", "utility", False, "Load .env configuration"),

    # ── data & parsing ──────────────────────────────────────────────────
    "beautifulsoup4": ("", "parsing", False, "HTML/XML scraping"),
    "soupsieve": ("", "parsing", False, "CSS selectors for BeautifulSoup"),
    "lxml": ("", "parsing", True, "Fast XML/HTML parser (Chaquopy wheel)"),
    "html5lib": ("", "parsing", False, "Spec-compliant HTML parser"),
    "markdownify": ("", "parsing", False, "HTML → Markdown"),
    "markdown": ("", "parsing", False, "Markdown → HTML"),
    "pyyaml": ("", "parsing", True, "YAML parsing (Chaquopy wheel)"),
    "toml": ("", "parsing", False, "TOML reader"),
    "tomli": ("", "parsing", False, "Fast TOML reader"),
    "orjson": ("", "parsing", True, "Very fast JSON (Chaquopy wheel)"),
    "ujson": ("", "parsing", True, "Fast JSON (Chaquopy wheel)"),
    "jsonschema": ("", "parsing", False, "Validate JSON documents"),
    "python-dateutil": ("", "utility", False, "Flexible date parsing"),
    "pytz": ("", "utility", False, "Timezone database"),
    "tzdata": ("", "utility", False, "IANA timezones for zoneinfo"),
    "arrow": ("", "utility", False, "Human-friendly datetimes"),
    "humanize": ("", "utility", False, "Human-readable sizes and durations"),
    "chardet": ("", "parsing", False, "Character encoding detection"),
    "xmltodict": ("", "parsing", False, "XML as nested dicts"),
    "csvkit": ("", "parsing", False, "CSV utilities"),
    "openpyxl": ("", "documents", False, "Read and write .xlsx workbooks"),
    "et-xmlfile": ("", "documents", False, "openpyxl dependency"),
    "python-docx": ("", "documents", False, "Read and write .docx"),
    "pypdf": ("", "documents", False, "Pure-Python PDF reading/merging"),
    "reportlab": ("", "documents", True, "Generate PDFs (Chaquopy wheel)"),
    "qrcode": ("", "media", False, "Generate QR codes"),
    "python-barcode": ("", "media", False, "Generate barcodes"),
    "pyzbar": ("", "media", True, "Decode QR/barcodes (needs zbar wheel)"),

    # ── science & numerics ──────────────────────────────────────────────
    "numpy": ("", "science", True, "Arrays and linear algebra"),
    "scipy": ("", "science", True, "Scientific computing"),
    "pandas": ("", "science", True, "DataFrames and analysis"),
    "matplotlib": ("", "science", True, "Plotting (render to PNG, not a window)"),
    "scikit-learn": ("", "science", True, "Classical machine learning"),
    "statsmodels": ("", "science", True, "Statistical models"),
    "sympy": ("", "science", False, "Symbolic mathematics"),
    "mpmath": ("", "science", False, "Arbitrary-precision arithmetic"),
    "networkx": ("", "science", False, "Graph algorithms"),
    "opencv-python": ("", "media", True, "Computer vision (large: ~40 MB)"),
    "pillow": ("", "media", True, "Image processing (Chaquopy wheel)"),
    "imageio": ("", "media", False, "Read/write image formats"),
    "qiskit": ("", "science", True, "Quantum computing SDK (large)"),

    # ── AI / ML clients ─────────────────────────────────────────────────
    "openai": ("", "ai", False, "OpenAI API client"),
    "anthropic": ("", "ai", False, "Anthropic API client"),
    "google-generativeai": ("", "ai", False, "Gemini API client"),
    "groq": ("", "ai", False, "Groq API client"),
    "tiktoken": ("", "ai", True, "BPE tokeniser (Chaquopy wheel)"),
    "transformers": ("", "ai", False, "Hugging Face models (needs a backend)"),
    "huggingface-hub": ("", "ai", False, "Download models and datasets"),
    "sentencepiece": ("", "ai", True, "Subword tokenisation"),

    # ── crypto & security ───────────────────────────────────────────────
    "cryptography": ("", "security", True, "Modern crypto primitives"),
    "pycryptodome": ("", "security", True, "AES, RSA, hashing"),
    "bcrypt": ("", "security", True, "Password hashing"),
    "passlib": ("", "security", False, "Password hashing framework"),
    "pyjwt": ("", "security", False, "JSON Web Tokens"),
    "pyotp": ("", "security", False, "TOTP/HOTP two-factor codes"),
    "python-jose": ("", "security", False, "JOSE/JWT implementation"),
    "keyring": ("", "security", False, "Credential storage frontend"),

    # ── databases ───────────────────────────────────────────────────────
    "sqlalchemy": ("", "database", False, "SQL toolkit and ORM"),
    "peewee": ("", "database", False, "Tiny ORM over SQLite"),
    "tinydb": ("", "database", False, "Document database in a JSON file"),
    "pysqlcipher3": ("", "database", True, "Encrypted SQLite"),
    "redis": ("", "database", False, "Redis client"),
    "pymongo": ("", "database", True, "MongoDB client"),
    "supabase": ("", "database", False, "Supabase client"),
    "firebase-admin": ("", "database", False, "Firebase admin SDK"),

    # ── utilities ───────────────────────────────────────────────────────
    "attrs": ("", "utility", False, "Classes without boilerplate"),
    "pydantic": ("", "utility", True, "Typed data validation (v2 needs a wheel)"),
    "typing-extensions": ("", "utility", False, "Back-ported typing features"),
    "cachetools": ("", "utility", False, "In-memory caches"),
    "tenacity": ("", "utility", False, "Retrying with backoff"),
    "more-itertools": ("", "utility", False, "Iterator recipes"),
    "rich": ("", "utility", False, "Pretty text rendering (also to strings)"),
    "tabulate": ("", "utility", False, "Render tables as text"),
    "faker": ("", "utility", False, "Generate fake data"),
    "shortuuid": ("", "utility", False, "Short unique IDs"),
    "emoji": ("", "utility", False, "Emoji lookup and stripping"),
    "phonenumbers": ("", "utility", False, "Parse and format phone numbers"),
    "validators": ("", "utility", False, "Common value validators"),
    "python-slugify": ("", "utility", False, "URL-safe slugs"),
    "fuzzywuzzy": ("", "utility", False, "Fuzzy string matching"),
    "rapidfuzz": ("", "utility", True, "Fast fuzzy matching"),
    "regex": ("", "utility", True, "Extended regular expressions"),
    "chevron": ("", "utility", False, "Mustache templating"),
    "jinja2": ("", "utility", False, "Templating engine"),
    "markupsafe": ("", "utility", False, "Jinja2 dependency"),
    "schedule": ("", "utility", False, "Human-friendly job scheduling"),
    "croniter": ("", "utility", False, "Cron expression maths"),
    "psutil": ("", "utility", True, "Process and system metrics"),
    "qrcode-terminal": ("", "utility", False, "QR codes as text"),
    "mutagen": ("", "media", False, "Audio metadata tags"),
    "pydub": ("", "media", False, "Audio slicing (needs ffmpeg for mp3)"),
    "ffmpeg-python": ("", "media", False, "ffmpeg command builder"),
    "moviepy": ("", "media", False, "Video editing (needs ffmpeg)"),
    "gtts": ("", "media", False, "Google text-to-speech (online)"),
    "speechrecognition": ("", "media", False, "Speech-to-text frontends"),
}

#: Packages that will *never* work on Android, with the reason why.
BLOCKED: dict[str, str] = {
    "tkinter": "desktop-only GUI toolkit; use Pydrud widgets",
    "tk": "desktop-only GUI toolkit; use Pydrud widgets",
    "pyqt5": "Qt does not run under Chaquopy; use Pydrud widgets",
    "pyqt6": "Qt does not run under Chaquopy; use Pydrud widgets",
    "pyside6": "Qt does not run under Chaquopy; use Pydrud widgets",
    "kivy": "another Android UI framework — it cannot share the process",
    "flet": "another UI framework — use Pydrud widgets instead",
    "pygame": "needs SDL; no Android wheel for Chaquopy",
    "pyautogui": "needs a desktop display server",
    "selenium": "needs a desktop browser driver",
    "playwright": "ships desktop browser binaries",
    "tensorflow": "too large for an APK; use TensorFlow Lite via Java",
    "torch": "no Android wheel; use ExecuTorch or a server",
    "scrapy": "relies on Twisted's reactor and desktop networking",
    "django": "server framework; run it on a server, not on the phone",
    "flask": "server framework; nothing can reach a localhost port on a phone",
    "fastapi": "server framework; use page.http to call your API instead",
    "uvicorn": "ASGI server; not useful inside an app",
    "psycopg2": "needs libpq; no Android build",
    "mysqlclient": "needs libmysqlclient; no Android build",
    "pyaudio": "needs PortAudio; use page.audio instead",
    "sounddevice": "needs PortAudio; use page.audio instead",
    "wxpython": "desktop-only GUI toolkit",
    "pywin32": "Windows-only",
    "pyobjc": "macOS-only",
}

CATEGORIES = ("network", "media", "parsing", "documents", "science", "ai",
              "security", "database", "utility")

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PackageError(RuntimeError):
    """Raised for unknown, blocked or malformed package requests."""


def normalise(name: str) -> str:
    """PyPI treats ``_`` and ``-`` alike and is case-insensitive."""
    return str(name).strip().lower().replace("_", "-")


def split_requirement(requirement: str) -> tuple[str, str]:
    """``"requests>=2.31"`` → ``("requests", ">=2.31")``."""
    text = str(requirement).strip()
    match = re.match(r"^([A-Za-z0-9._-]+)\s*(.*)$", text)
    if not match:
        raise PackageError(f"Cannot parse requirement {requirement!r}")
    name, spec = match.group(1), match.group(2).strip()
    if spec and not re.match(r"^(==|>=|<=|~=|!=|<|>)", spec):
        raise PackageError(
            f"Invalid version specifier {spec!r} for {name!r} — "
            f"use something like '{name}>=1.2'")
    return normalise(name), spec


def is_supported(name: str) -> bool:
    return normalise(name) in REGISTRY


def info(name: str) -> dict:
    """Registry entry for *name* (raises :class:`PackageError` if unknown)."""
    key = normalise(name)
    if key in BLOCKED:
        raise PackageError(
            f"{key} cannot run on Android: {BLOCKED[key]}.")
    if key not in REGISTRY:
        suggestions = search(key, limit=3)
        hint = (f" Did you mean: {', '.join(s['name'] for s in suggestions)}?"
                if suggestions else "")
        raise PackageError(
            f"{key} is not in Pydrud's verified registry.{hint}\n"
            f"Run 'pydrud pip list --all' to see the {len(REGISTRY)} "
            f"supported packages, or add it anyway with --force "
            f"(the Gradle build may fail).")
    version, category, native, description = REGISTRY[key]
    return {"name": key, "version": version, "category": category,
            "native": native, "description": description}


def search(query: str, *, limit: int = 20) -> list[dict]:
    """Fuzzy search over names, categories and descriptions."""
    needle = normalise(query)
    scored: list[tuple[int, dict]] = []
    for name, (version, category, native, description) in REGISTRY.items():
        score = 0
        if needle == name:
            score = 100
        elif name.startswith(needle):
            score = 70
        elif needle in name:
            score = 50
        elif needle in category:
            score = 30
        elif needle in description.lower():
            score = 20
        if score:
            scored.append((score, {"name": name, "version": version,
                                   "category": category, "native": native,
                                   "description": description}))
    scored.sort(key=lambda item: (-item[0], item[1]["name"]))
    return [entry for _, entry in scored[:limit]]


def by_category() -> dict[str, list[dict]]:
    """The whole registry grouped by category, for docs and ``pip list``."""
    grouped: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for name, (version, category, native, description) in sorted(REGISTRY.items()):
        grouped.setdefault(category, []).append(
            {"name": name, "version": version, "native": native,
             "description": description})
    return {k: v for k, v in grouped.items() if v}


# ──────────────────────────────────────────────────────────────────────────
# Project manifest (pydrud.toml)
# ──────────────────────────────────────────────────────────────────────────


class Requirements:
    """The ``[python.packages]`` section of a project's ``pydrud.toml``."""

    def __init__(self, project_dir: str = "."):
        self.project_dir = os.path.abspath(project_dir)
        self.path = os.path.join(self.project_dir, "pydrud.toml")

    # ── read / write ─────────────────────────────────────────────────────

    def load(self) -> dict[str, str]:
        """``{"requests": ">=2.31", "yt-dlp": ""}`` in declaration order."""
        if not os.path.exists(self.path):
            return {}
        packages: dict[str, str] = {}
        in_section = False
        for line in open(self.path, encoding="utf-8"):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_section = stripped == "[python.packages]"
                continue
            if not in_section or not stripped or stripped.startswith("#"):
                continue
            name, _, spec = stripped.partition("=")
            packages[normalise(name)] = spec.strip().strip('"').strip("'")
        return packages

    def save(self, packages: dict[str, str]) -> None:
        body = "\n".join(f'{name} = "{spec}"'
                         for name, spec in sorted(packages.items()))
        section = f"[python.packages]\n{body}\n" if packages else \
            "[python.packages]\n"

        if not os.path.exists(self.path):
            header = (
                "# Pydrud project configuration.\n"
                "# Packages below are installed into the APK by Chaquopy at\n"
                "# build time — manage them with 'pydrud pip add/remove'.\n\n")
            open(self.path, "w", encoding="utf-8").write(header + section)
            return

        text = open(self.path, encoding="utf-8").read()
        if "[python.packages]" in text:
            lines, out, skipping = text.splitlines(), [], False
            for line in lines:
                stripped = line.strip()
                if stripped == "[python.packages]":
                    skipping = True
                    out.append(section.rstrip("\n"))
                    continue
                if skipping:
                    if stripped.startswith("[") and stripped.endswith("]"):
                        skipping = False
                    else:
                        continue
                out.append(line)
            text = "\n".join(out).rstrip("\n") + "\n"
        else:
            text = text.rstrip("\n") + "\n\n" + section
        open(self.path, "w", encoding="utf-8").write(text)

    # ── mutations ────────────────────────────────────────────────────────

    def add(self, requirement: str, *, force: bool = False) -> dict:
        name, spec = split_requirement(requirement)
        if not _NAME_RE.match(name):
            raise PackageError(f"Invalid package name {name!r}")
        if not force:
            entry = info(name)                 # raises when unsupported
            if not spec and entry["version"]:
                spec = f"=={entry['version']}"
        else:
            entry = {"name": name, "version": "", "category": "unverified",
                     "native": False,
                     "description": "forced; not verified on Android"}
        packages = self.load()
        packages[name] = spec
        self.save(packages)
        entry["spec"] = spec
        return entry

    def remove(self, name: str) -> bool:
        key = normalise(name)
        packages = self.load()
        if key not in packages:
            return False
        packages.pop(key)
        self.save(packages)
        return True

    def requirement_strings(self) -> list[str]:
        """Exactly what goes into Chaquopy's ``install(...)`` calls."""
        return [f"{name}{spec}" if spec else name
                for name, spec in sorted(self.load().items())]

    def __contains__(self, name: str) -> bool:
        return normalise(name) in self.load()

    def __len__(self) -> int:
        return len(self.load())


# ──────────────────────────────────────────────────────────────────────────
# Gradle injection
# ──────────────────────────────────────────────────────────────────────────

_BEGIN = "// pydrud:pip:begin"
_END = "// pydrud:pip:end"


def render_pip_block(requirements: Iterable[str], *, indent: str = "            ") -> str:
    """The ``install(...)`` lines Chaquopy expects, between marker comments."""
    lines = [f'{indent}{_BEGIN}']
    for requirement in requirements:
        lines.append(f'{indent}install("{requirement}")')
    lines.append(f'{indent}{_END}')
    return "\n".join(lines)


def sync_gradle(project_dir: str = ".",
                requirements: Optional[Iterable[str]] = None) -> str:
    """Rewrite the managed pip block inside ``app/build.gradle.kts``.

    Returns the path that was written. Raises :class:`PackageError` when the
    file has no Chaquopy ``pip { }`` block (an old or hand-edited project).
    """
    gradle_path = os.path.join(project_dir, "android", "app", "build.gradle.kts")
    if not os.path.exists(gradle_path):
        gradle_path = os.path.join(project_dir, "app", "build.gradle.kts")
    if not os.path.exists(gradle_path):
        raise PackageError(
            "No android/app/build.gradle.kts found — run this inside a "
            "Pydrud project (or run 'pydrud build' once to generate it).")

    if requirements is None:
        requirements = Requirements(project_dir).requirement_strings()
    requirements = list(requirements)

    text = open(gradle_path, encoding="utf-8").read()
    block = render_pip_block(requirements)

    if _BEGIN in text and _END in text:
        start = text.index(_BEGIN)
        line_start = text.rfind("\n", 0, start) + 1
        end = text.index(_END) + len(_END)
        text = text[:line_start] + block.lstrip("\n") + text[end:]
    elif "pip {" in text:
        marker = text.index("pip {") + len("pip {")
        text = text[:marker] + "\n" + block + text[marker:]
    else:
        raise PackageError(
            "The Chaquopy 'pip { }' block is missing from build.gradle.kts.")

    open(gradle_path, "w", encoding="utf-8").write(text)
    return gradle_path


def installed_summary(project_dir: str = ".") -> list[dict]:
    """Rows for ``pydrud pip list``: what this project depends on."""
    rows = []
    for name, spec in sorted(Requirements(project_dir).load().items()):
        try:
            entry = info(name)
        except PackageError:
            entry = {"name": name, "category": "unverified", "native": False,
                     "description": "not in the verified registry"}
        entry["spec"] = spec or "latest"
        rows.append(entry)
    return rows
