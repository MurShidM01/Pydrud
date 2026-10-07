"""
Python package management for Pydrud projects.

Supports two runtimes:

* ``chaquopy`` — packages are bundled into the APK via Chaquopy's
  Gradle ``pip { install(...) }`` block at build time. Only verified
  packages can be added without ``--force``.
* ``pydash`` — packages run in the host Python environment. Dependencies
  are recorded in ``pydrud.toml`` but are not installed automatically, and
  Android registry restrictions or Gradle files do not apply.

    pydrud pip add yt-dlp requests
    pydrud pip list
    pydrud pip search qr
    pydrud pip remove requests
    pydrud pip sync            # re-apply pydrud.toml to the Gradle build

Dependencies are recorded in ``pydrud.toml`` under ``[python.packages]``
and injected into ``app/build.gradle.kts`` inside Chaquopy's
``python { pip { install(...) } }`` block for chaquopy projects.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Iterable, Optional
from dataclasses import dataclass


class SupportCategory(Enum):
    """What category of dependency this package is."""
    NATIVE_EQUIVALENT = "native_equivalent"   # works on Android via Chaquopy wheel or pure Python
    HOST_ONLY = "host_only"                    # desktop-only, will never work on device
    DEVICE_NATIVE = "device_native"            # needs native ABI wheel for Android
    UNSUPPORTED = "unsupported"                # explicitly blocked


#: name → (version spec, category, support_category, import_names, description)
REGISTRY: dict[str, tuple[str, str, str, tuple[str, ...], str]] = {
    # ── networking & APIs ───────────────────────────────────────────────
    "requests": ("", "network", "native_equivalent", ("requests",), "The classic HTTP client"),
    "httpx": ("", "network", "native_equivalent", ("httpx",), "Async-capable HTTP client"),
    "urllib3": ("", "network", "native_equivalent", ("urllib3",), "Low-level HTTP plumbing"),
    "certifi": ("", "network", "native_equivalent", ("certifi",), "Mozilla CA bundle for TLS"),
    "charset-normalizer": ("", "network", "native_equivalent", ("charset_normalizer",), "Encoding detection"),
    "idna": ("", "network", "native_equivalent", ("idna",), "Internationalised domain names"),
    "websockets": ("", "network", "native_equivalent", ("websockets",), "WebSocket client and server"),
    "websocket-client": ("", "network", "native_equivalent", ("websocket_client",), "Blocking WebSocket client"),
    "aiohttp": ("", "network", "device_native", ("aiohttp",), "Async HTTP client/server"),
    "sseclient-py": ("", "network", "native_equivalent", ("sseclient_py",), "Server-sent events"),
    "paho-mqtt": ("", "network", "native_equivalent", ("paho",), "MQTT client for IoT devices"),
    "feedparser": ("", "network", "native_equivalent", ("feedparser",), "RSS and Atom parsing"),
    "yt-dlp": ("", "media", "device_native", ("yt_dlp",), "Download video/audio from 1000+ sites"),
    "youtube-search-python": ("", "media", "native_equivalent", ("youtube_search",), "Search YouTube without an API key"),
    "pytube": ("", "media", "native_equivalent", ("pytube",), "Lightweight YouTube downloader"),
    "instaloader": ("", "media", "native_equivalent", ("instaloader",), "Download Instagram media"),
    "telethon": ("", "network", "native_equivalent", ("telethon",), "Telegram MTProto client"),
    "tweepy": ("", "network", "native_equivalent", ("tweepy",), "Twitter/X API client"),
    "praw": ("", "network", "native_equivalent", ("praw",), "Reddit API client"),
    "googletrans": ("4.0.0rc1", "network", "native_equivalent", ("googletrans",), "Unofficial Google Translate"),
    "deep-translator": ("", "network", "native_equivalent", ("deep_translator",), "Translation via many providers"),
    "wikipedia": ("", "network", "native_equivalent", ("wikipedia",), "Wikipedia article search"),
    "geopy": ("", "network", "native_equivalent", ("geopy",), "Geocoding and distance maths"),
    "python-dotenv": ("", "utility", "native_equivalent", ("dotenv",), "Load .env configuration"),

    # ── data & parsing ──────────────────────────────────────────────────
    "beautifulsoup4": ("", "parsing", "native_equivalent", ("bs4",), "HTML/XML scraping"),
    "soupsieve": ("", "parsing", "native_equivalent", ("soupsieve",), "CSS selectors for BeautifulSoup"),
    "lxml": ("", "parsing", "device_native", ("lxml",), "Fast XML/HTML parser (Chaquopy wheel)"),
    "html5lib": ("", "parsing", "native_equivalent", ("html5lib",), "Spec-compliant HTML parser"),
    "markdownify": ("", "parsing", "native_equivalent", ("markdownify",), "HTML → Markdown"),
    "markdown": ("", "parsing", "native_equivalent", ("markdown",), "Markdown → HTML"),
    "pyyaml": ("", "parsing", "device_native", ("yaml",), "YAML parsing (Chaquopy wheel)"),
    "toml": ("", "parsing", "native_equivalent", ("toml",), "TOML reader"),
    "tomli": ("", "parsing", "native_equivalent", ("tomli",), "Fast TOML reader"),
    "orjson": ("", "parsing", "device_native", ("orjson",), "Very fast JSON (Chaquopy wheel)"),
    "ujson": ("", "parsing", "device_native", ("ujson",), "Fast JSON (Chaquopy wheel)"),
    "jsonschema": ("", "parsing", "native_equivalent", ("jsonschema",), "Validate JSON documents"),
    "python-dateutil": ("", "utility", "native_equivalent", ("dateutil",), "Flexible date parsing"),
    "pytz": ("", "utility", "native_equivalent", ("pytz",), "Timezone database"),
    "tzdata": ("", "utility", "native_equivalent", ("tzdata",), "IANA timezones for zoneinfo"),
    "arrow": ("", "utility", "native_equivalent", ("arrow",), "Human-friendly datetimes"),
    "humanize": ("", "utility", "native_equivalent", ("humanize",), "Human-readable sizes and durations"),
    "chardet": ("", "parsing", "native_equivalent", ("chardet",), "Character encoding detection"),
    "xmltodict": ("", "parsing", "native_equivalent", ("xmltodict",), "XML as nested dicts"),
    "csvkit": ("", "parsing", "native_equivalent", ("csvkit",), "CSV utilities"),
    "openpyxl": ("", "documents", "native_equivalent", ("openpyxl",), "Read and write .xlsx workbooks"),
    "et-xmlfile": ("", "documents", "native_equivalent", (), "openpyxl dependency"),
    "python-docx": ("", "documents", "native_equivalent", ("docx",), "Read and write .docx"),
    "pypdf": ("", "documents", "native_equivalent", ("pypdf",), "Pure-Python PDF reading/merging"),
    "reportlab": ("", "documents", "device_native", ("reportlab",), "Generate PDFs (Chaquopy wheel)"),
    "qrcode": ("", "media", "native_equivalent", ("qrcode",), "Generate QR codes"),
    "python-barcode": ("", "media", "native_equivalent", ("barcode",), "Generate barcodes"),
    "pyzbar": ("", "media", "device_native", ("pyzbar",), "Decode QR/barcodes (needs zbar wheel)"),

    # ── science & numerics ──────────────────────────────────────────────
    "numpy": ("", "science", "device_native", ("numpy",), "Arrays and linear algebra"),
    "scipy": ("", "science", "device_native", ("scipy",), "Scientific computing"),
    "pandas": ("", "science", "device_native", ("pandas",), "DataFrames and analysis"),
    "matplotlib": ("", "science", "device_native", ("matplotlib",), "Plotting (render to PNG, not a window)"),
    "scikit-learn": ("", "science", "device_native", ("sklearn",), "Classical machine learning"),
    "statsmodels": ("", "science", "device_native", ("statsmodels",), "Statistical models"),
    "sympy": ("", "science", "native_equivalent", ("sympy",), "Symbolic mathematics"),
    "mpmath": ("", "science", "native_equivalent", ("mpmath",), "Arbitrary-precision arithmetic"),
    "networkx": ("", "science", "native_equivalent", ("networkx",), "Graph algorithms"),
    "opencv-python": ("", "media", "device_native", ("cv2",), "Computer vision (large: ~40 MB)"),
    "pillow": ("", "media", "device_native", ("PIL",), "Image processing (Chaquopy wheel)"),
    "imageio": ("", "media", "native_equivalent", ("imageio",), "Read/write image formats"),
    "qiskit": ("", "science", "device_native", ("qiskit",), "Quantum computing SDK (large)"),

    # ── AI / ML clients ─────────────────────────────────────────────────
    "openai": ("", "ai", "native_equivalent", ("openai",), "OpenAI API client"),
    "anthropic": ("", "ai", "native_equivalent", ("anthropic",), "Anthropic API client"),
    "google-generativeai": ("", "ai", "native_equivalent", ("google.generativeai",), "Gemini API client"),
    "groq": ("", "ai", "native_equivalent", ("groq",), "Groq API client"),
    "tiktoken": ("", "ai", "device_native", ("tiktoken",), "BPE tokeniser (Chaquopy wheel)"),
    "transformers": ("", "ai", "device_native", ("transformers",), "Hugging Face models (needs a backend)"),
    "huggingface-hub": ("", "ai", "native_equivalent", ("huggingface_hub",), "Download models and datasets"),
    "sentencepiece": ("", "ai", "device_native", ("sentencepiece",), "Subword tokenisation"),

    # ── crypto & security ───────────────────────────────────────────────
    "cryptography": ("", "security", "device_native", ("cryptography",), "Modern crypto primitives"),
    "pycryptodome": ("", "security", "device_native", ("Crypto",), "AES, RSA, hashing"),
    "bcrypt": ("", "security", "device_native", ("bcrypt",), "Password hashing"),
    "passlib": ("", "security", "native_equivalent", ("passlib",), "Password hashing framework"),
    "pyjwt": ("", "security", "native_equivalent", ("jwt",), "JSON Web Tokens"),
    "pyotp": ("", "security", "native_equivalent", ("pyotp",), "TOTP/HOTP two-factor codes"),
    "python-jose": ("", "security", "native_equivalent", ("jose",), "JOSE/JWT implementation"),
    "keyring": ("", "security", "native_equivalent", ("keyring",), "Credential storage frontend"),

    # ── databases ───────────────────────────────────────────────────────
    "sqlalchemy": ("", "database", "native_equivalent", ("sqlalchemy",), "SQL toolkit and ORM"),
    "peewee": ("", "database", "native_equivalent", ("peewee",), "Tiny ORM over SQLite"),
    "tinydb": ("", "database", "native_equivalent", ("tinydb",), "Document database in a JSON file"),
    "pysqlcipher3": ("", "database", "device_native", ("Cipher",), "Encrypted SQLite"),
    "redis": ("", "database", "native_equivalent", ("redis",), "Redis client"),
    "pymongo": ("", "database", "device_native", ("pymongo",), "MongoDB client"),
    "supabase": ("", "database", "native_equivalent", ("supabase",), "Supabase client"),
    "firebase-admin": ("", "database", "native_equivalent", ("firebase_admin",), "Firebase admin SDK"),

    # ── utilities ───────────────────────────────────────────────────────
    "attrs": ("", "utility", "native_equivalent", ("attr", "aiohttp"), "Classes without boilerplate"),
    "pydantic": ("", "utility", "device_native", ("pydantic",), "Typed data validation (v2 needs a wheel)"),
    "typing-extensions": ("", "utility", "native_equivalent", ("typing_extensions",), "Back-ported typing features"),
    "cachetools": ("", "utility", "native_equivalent", ("cachetools",), "In-memory caches"),
    "tenacity": ("", "utility", "native_equivalent", ("tenacity",), "Retrying with backoff"),
    "more-itertools": ("", "utility", "native_equivalent", ("more_itertools",), "Iterator recipes"),
    "rich": ("", "utility", "native_equivalent", ("rich",), "Pretty text rendering (also to strings)"),
    "tabulate": ("", "utility", "native_equivalent", ("tabulate",), "Render tables as text"),
    "faker": ("", "utility", "native_equivalent", ("faker",), "Generate fake data"),
    "shortuuid": ("", "utility", "native_equivalent", ("shortuuid",), "Short unique IDs"),
    "emoji": ("", "utility", "native_equivalent", ("emoji",), "Emoji lookup and stripping"),
    "phonenumbers": ("", "utility", "native_equivalent", ("phonenumbers",), "Parse and format phone numbers"),
    "validators": ("", "utility", "native_equivalent", ("validators",), "Common value validators"),
    "python-slugify": ("", "utility", "native_equivalent", ("slugify",), "URL-safe slugs"),
    "fuzzywuzzy": ("", "utility", "native_equivalent", ("fuzzywuzzy",), "Fuzzy string matching"),
    "rapidfuzz": ("", "utility", "device_native", ("rapidfuzz",), "Fast fuzzy matching"),
    "regex": ("", "utility", "device_native", ("regex",), "Extended regular expressions"),
    "chevron": ("", "utility", "native_equivalent", ("chevron",), "Mustache templating"),
    "jinja2": ("", "utility", "native_equivalent", ("jinja2",), "Templating engine"),
    "markupsafe": ("", "utility", "native_equivalent", ("markupsafe",), "Jinja2 dependency"),
    "schedule": ("", "utility", "native_equivalent", ("schedule",), "Human-friendly job scheduling"),
    "croniter": ("", "utility", "native_equivalent", ("croniter",), "Cron expression maths"),
    "psutil": ("", "utility", "host_only", ("psutil",), "Process and system metrics"),
    "qrcode-terminal": ("", "utility", "native_equivalent", ("qrcode_terminal",), "QR codes as text"),
    "mutagen": ("", "media", "native_equivalent", ("mutagen",), "Audio metadata tags"),
    "pydub": ("", "media", "native_equivalent", (), "Audio slicing (needs ffmpeg for mp3)"),
    "ffmpeg-python": ("", "media", "native_equivalent", ("ffmpeg_python",), "ffmpeg command builder"),
    "moviepy": ("", "media", "native_equivalent", ("moviepy",), "Video editing (needs ffmpeg)"),
    "gtts": ("", "media", "native_equivalent", ("gTTS",), "Google text-to-speech (online)"),
    "speechrecognition": ("", "media", "native_equivalent", ("speech_recognition",), "Speech-to-text frontends"),
}

#: Packages that will *never* work on Android, with the reason why.
BLOCKED: dict[str, tuple[str, tuple[str, ...]]] = {
    "tkinter": ("desktop-only GUI toolkit; use Pydrud widgets", ("tkinter",)),
    "tk": ("desktop-only GUI toolkit; use Pydrud widgets", ("tk",)),
    "pyqt5": ("Qt does not run under Chaquopy; use Pydrud widgets", ("PyQt5",)),
    "pyqt6": ("Qt does not run under Chaquopy; use Pydrud widgets", ("PyQt6",)),
    "pyside6": ("Qt does not run under Chaquopy; use Pydrud widgets", ("PySide6",)),
    "kivy": ("another Android UI framework — it cannot share the process", ("kivy",)),
    "flet": ("another UI framework — use Pydrud widgets instead", ("flet",)),
    "pygame": ("needs SDL; no Android wheel for Chaquopy", ("pygame",)),
    "pyautogui": ("needs a desktop display server", ("pyautogui",)),
    "selenium": ("needs a desktop browser driver", ("selenium",)),
    "playwright": ("ships desktop browser binaries", ("playwright",)),
    "tensorflow": ("too large for an APK; use TensorFlow Lite via Java", ("tensorflow",)),
    "torch": ("no Android wheel; use ExecuTorch or a server", ("torch",)),
    "scrapy": ("relies on Twisted's reactor and desktop networking", ("scrapy",)),
    "django": ("server framework; run it on a server, not on the phone", ("django",)),
    "flask": ("server framework; nothing can reach a localhost port on a phone", ("flask",)),
    "fastapi": ("server framework; use page.http to call your API instead", ("fastapi",)),
    "uvicorn": ("ASGI server; not useful inside an app", ("uvicorn",)),
    "psycopg2": ("needs libpq; no Android build", ("psycopg2",)),
    "mysqlclient": ("needs libmysqlclient; no Android build", ("MySQLdb",)),
    "pyaudio": ("needs PortAudio; use page.audio instead", ("pyaudio",)),
    "sounddevice": ("needs PortAudio; use page.audio instead", ("sounddevice",)),
    "wxpython": ("desktop-only GUI toolkit", ("wx",)),
    "pywin32": ("Windows-only", ("win32com", "win32api")),
    "pyobjc": ("macOS-only", ("objc",)),
}

CATEGORIES = ("network", "media", "parsing", "documents", "science", "ai",
              "security", "database", "utility")

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _parse_registry_entry(raw: tuple) -> dict:
    """Normalise a raw REGISTRY entry into a dict.

    Handles both the legacy 4-tuple format and the new 5-tuple format
    gracefully so the module continues to work during migration.
    """
    if len(raw) == 4:
        version, category, native, description = raw
        return {
            "name": "",  # filled in by caller
            "version": version,
            "category": category,
            "support_category": "device_native" if native else "native_equivalent",
            "import_names": (),
            "description": description,
        }
    version, category, support_category, import_names, description = raw
    return {
        "name": "",  # filled in by caller
        "version": version,
        "category": category,
        "support_category": support_category,
        "import_names": import_names,
        "description": description,
    }


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
            f"{key} cannot run on Android: {BLOCKED[key][0]}.")
    if key not in REGISTRY:
        suggestions = search(key, limit=3)
        hint = (f" Did you mean: {', '.join(s['name'] for s in suggestions)}?"
                if suggestions else "")
        raise PackageError(
            f"{key} is not in Pydrud's verified registry.{hint}\n"
            f"Run 'pydrud pip list --all' to see the {len(REGISTRY)} "
            f"supported packages, or add it anyway with --force "
            f"(the Gradle build may fail).")
    entry = _parse_registry_entry(REGISTRY[key])
    entry["name"] = key
    return entry


def search(query: str, *, limit: int = 20) -> list[dict]:
    """Fuzzy search over names, categories and descriptions."""
    needle = normalise(query)
    scored: list[tuple[int, dict]] = []
    for name, raw in REGISTRY.items():
        entry = _parse_registry_entry(raw)
        entry["name"] = name
        score = 0
        if needle == name:
            score = 100
        elif name.startswith(needle):
            score = 70
        elif needle in name:
            score = 50
        elif needle in entry["category"]:
            score = 30
        elif needle in entry["description"].lower():
            score = 20
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1]["name"]))
    return [entry for _, entry in scored[:limit]]


def by_category() -> dict[str, list[dict]]:
    """The whole registry grouped by category, for docs and ``pip list``."""
    grouped: dict[str, list[dict]] = {c: [] for c in CATEGORIES}
    for name, raw in REGISTRY.items():
        entry = _parse_registry_entry(raw)
        entry["name"] = name
        grouped.setdefault(entry["category"], []).append(entry)
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
        with open(self.path, encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in lines:
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
                "# Packages are declared for the selected runtime.\n"
                "# Chaquopy installs them in APK builds; Pydash uses the host\n"
                "# Python environment.\n\n")
            self._write(header + section)
            return

        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
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
        self._write(text)

    def _write(self, text: str) -> None:
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

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
                     "support_category": "host_only",
                     "import_names": (),
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
# Pluggable package backends
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PackageResult:
    """The result of a package operation."""
    success: bool
    message: str
    details: dict | None = None


class PackageBackend:
    """Base class for runtime-aware package management.

    Subclasses implement the behaviour for a specific runtime
    (chaquopy bundles into APK, pydash runs on host only).
    """

    def supports(self, runtime: str) -> bool:
        """Whether this backend handles *runtime*."""
        return False

    def add(self, project_dir: str, requirement: str, *, force: bool = False) -> PackageResult:
        raise NotImplementedError

    def remove(self, project_dir: str, name: str) -> PackageResult:
        raise NotImplementedError

    def list_packages(self, project_dir: str) -> list[dict]:
        raise NotImplementedError

    def search(self, query: str) -> list[dict]:
        raise NotImplementedError

    def sync_gradle(self, project_dir: str) -> PackageResult:
        raise NotImplementedError


class ChaquopyBackend(PackageBackend):
    """Handles package management for chaquopy projects.

    Reads/writes ``pydrud.toml`` and injects requirements into
    ``build.gradle.kts`` so Chaquopy installs them into the APK at
    build time.
    """

    def supports(self, runtime: str) -> bool:
        return runtime == "chaquopy"

    def add(self, project_dir: str, requirement: str, *, force: bool = False) -> PackageResult:
        reqs = Requirements(project_dir)
        if not force:
            try:
                name, _ = split_requirement(requirement)
                entry = info(name)
            except PackageError as exc:
                return PackageResult(success=False, message=str(exc))
            if entry.get("support_category") == "host_only":
                return PackageResult(
                    success=False,
                    message=(
                        f"{name} is host-only and cannot be installed into a "
                        "Chaquopy APK. Use a Pydash project for host-side "
                        "dependencies."
                    ),
                )
        try:
            entry = reqs.add(requirement, force=force)
        except PackageError as exc:
            return PackageResult(success=False, message=str(exc))
        return PackageResult(
            success=True,
            message=f"Added {entry['name']}{entry.get('spec', '')}",
            details=entry,
        )

    def remove(self, project_dir: str, name: str) -> PackageResult:
        reqs = Requirements(project_dir)
        removed = reqs.remove(name)
        if not removed:
            return PackageResult(success=False, message=f"{name} was not installed")
        return PackageResult(success=True, message=f"Removed {name}")

    def list_packages(self, project_dir: str) -> list[dict]:
        return installed_summary(project_dir)

    def search(self, query: str) -> list[dict]:
        return search(query)

    def sync_gradle(self, project_dir: str) -> PackageResult:
        try:
            path = sync_gradle(project_dir)
            return PackageResult(success=True, message=f"Synced to {path}")
        except PackageError as exc:
            return PackageResult(success=False, message=str(exc))


def _host_package_entry(name: str) -> dict:
    """Package metadata for a host-side Pydash dependency.

    Pydash metadata deliberately does not inherit Android registry limits.
    The optional Android category remains visible as a separate annotation
    for users who maintain another Chaquopy project.
    """
    key = normalise(name)
    if key in REGISTRY:
        entry = _parse_registry_entry(REGISTRY[key])
        entry["name"] = key
        entry["android_support_category"] = entry["support_category"]
        entry["support_category"] = "host"
        return entry
    if key in BLOCKED:
        reason, import_names = BLOCKED[key]
        return {
            "name": key,
            "version": "",
            "category": "host",
            "support_category": "host",
            "android_support_category": "blocked",
            "import_names": import_names,
            "description": (
                "Host-side dependency; Android restriction does not apply: "
                f"{reason}"
            ),
        }
    return {
        "name": key,
        "version": "",
        "category": "host",
        "support_category": "host",
        "android_support_category": "unverified",
        "import_names": (),
        "description": "Unverified host-side PyPI dependency",
    }


class PydashBackend(PackageBackend):
    """Handles package management for pydash projects.

    Records host-side package requirements in ``pydrud.toml`` without
    applying the Chaquopy registry or Android compatibility restrictions.
    It never installs packages or touches Gradle; users install dependencies
    in the Python environment that runs ``pydrud dev``.
    """

    def supports(self, runtime: str) -> bool:
        return runtime == "pydash"

    def add(self, project_dir: str, requirement: str, *, force: bool = False) -> PackageResult:
        # ``force`` is kept for backend API parity; host dependencies are not
        # gated on Chaquopy verification, so it has no effect here.
        _ = force
        try:
            name, spec = split_requirement(requirement)
        except PackageError as exc:
            return PackageResult(success=False, message=str(exc))
        if not _NAME_RE.match(name):
            return PackageResult(
                success=False, message=f"Invalid package name {name!r}")

        # The registry describes Chaquopy compatibility, not what may run on
        # the host. Pydash projects can declare any syntactically valid PyPI
        # dependency, including packages that are desktop/server-only or not
        # listed in the Android compatibility catalogue.
        entry = _host_package_entry(name)
        reqs = Requirements(project_dir)
        packages = reqs.load()
        packages[name] = spec
        reqs.save(packages)

        return PackageResult(
            success=True,
            message=(
                f"Recorded {name}{spec} for the host Python environment; "
                "install it there before running 'pydrud dev'."
            ),
            details={**entry, "spec": spec},
        )

    def remove(self, project_dir: str, name: str) -> PackageResult:
        reqs = Requirements(project_dir)
        removed = reqs.remove(name)
        if not removed:
            return PackageResult(success=False, message=f"{name} was not installed")
        return PackageResult(success=True, message=f"Removed {name}")

    def list_packages(self, project_dir: str) -> list[dict]:
        return installed_summary(project_dir, runtime="pydash")

    def search(self, query: str) -> list[dict]:
        return [_host_package_entry(entry["name"]) for entry in search(query)]

    def sync_gradle(self, project_dir: str) -> PackageResult:
        return PackageResult(
            success=False,
            message=(
                "Pydash has no Gradle or APK dependency sync. Install declared "
                "packages in the host Python environment used by 'pydrud dev'. "
                "Add an Android target with 'pydrud init android "
                "--standalone' to use Gradle."
            ),
        )


def get_backend(runtime: str) -> PackageBackend:
    """Return the appropriate backend for *runtime*."""
    for cls in (ChaquopyBackend, PydashBackend):
        inst = cls()
        if inst.supports(runtime):
            return inst
    raise PackageError(f"Unknown runtime: {runtime}")


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

    with open(gradle_path, encoding="utf-8") as handle:
        text = handle.read()
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

    with open(gradle_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return gradle_path


def installed_summary(project_dir: str = ".", *,
                      runtime: str = "chaquopy") -> list[dict]:
    """Rows for ``pydrud pip list`` with support interpreted per runtime."""
    rows = []
    for name, spec in sorted(Requirements(project_dir).load().items()):
        if runtime == "pydash":
            entry = _host_package_entry(name)
        else:
            try:
                entry = info(name)
            except PackageError:
                entry = {"name": name, "category": "unverified",
                         "support_category": "host_only", "import_names": (),
                         "description": "not in the verified registry"}
        entry["spec"] = spec or "latest"
        rows.append(entry)
    return rows
