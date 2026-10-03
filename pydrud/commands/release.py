"""
Shipping to the Play Store: signing keys, launcher icons and
manifest permissions.

``pydrud keygen`` creates an upload key and writes ``keystore.properties``
(already in ``.gitignore``); the generated ``app/build.gradle.kts`` picks it
up automatically, so ``pydrud build --release`` produces a *signed* APK or
AAB instead of a debug-signed one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Iterable, Optional

from pydrud.utils import tui

#: Friendly names → the real Android permission constants. Keep this in
#: sync with :class:`pydrud.services.native.Permissions` so command-line and
#: runtime code understand the same human names.
PERMISSIONS = {
    "camera": "CAMERA",
    "microphone": "RECORD_AUDIO",
    "mic": "RECORD_AUDIO",
    "record_audio": "RECORD_AUDIO",
    "audio": "RECORD_AUDIO",
    "location": "ACCESS_FINE_LOCATION",
    "fine_location": "ACCESS_FINE_LOCATION",
    "location_fine": "ACCESS_FINE_LOCATION",
    "coarse_location": "ACCESS_COARSE_LOCATION",
    "location_coarse": "ACCESS_COARSE_LOCATION",
    "background_location": "ACCESS_BACKGROUND_LOCATION",
    "location_background": "ACCESS_BACKGROUND_LOCATION",
    "notifications": "POST_NOTIFICATIONS",
    "notification": "POST_NOTIFICATIONS",
    "post_notifications": "POST_NOTIFICATIONS",
    "vibrate": "VIBRATE",
    "haptics": "VIBRATE",
    "haptic": "VIBRATE",
    "internet": "INTERNET",
    "network": "ACCESS_NETWORK_STATE",
    "storage": "READ_MEDIA_IMAGES",
    "photos": "READ_MEDIA_IMAGES",
    "images": "READ_MEDIA_IMAGES",
    "media_images": "READ_MEDIA_IMAGES",
    "videos": "READ_MEDIA_VIDEO",
    "video": "READ_MEDIA_VIDEO",
    "storage_video": "READ_MEDIA_VIDEO",
    "media_video": "READ_MEDIA_VIDEO",
    "music": "READ_MEDIA_AUDIO",
    "audio_files": "READ_MEDIA_AUDIO",
    "storage_audio": "READ_MEDIA_AUDIO",
    "media_audio": "READ_MEDIA_AUDIO",
    "read_storage": "READ_EXTERNAL_STORAGE",
    "write_storage": "WRITE_EXTERNAL_STORAGE",
    "contacts": "READ_CONTACTS",
    "contacts_write": "WRITE_CONTACTS",
    "write_contacts": "WRITE_CONTACTS",
    "calendar": "READ_CALENDAR",
    "calendar_write": "WRITE_CALENDAR",
    "write_calendar": "WRITE_CALENDAR",
    "phone": "READ_PHONE_STATE",
    "phone_state": "READ_PHONE_STATE",
    "read_phone_state": "READ_PHONE_STATE",
    "call_phone": "CALL_PHONE",
    "sms": "RECEIVE_SMS",
    "send_sms": "SEND_SMS",
    "bluetooth": "BLUETOOTH_CONNECT",
    "nearby_devices": "BLUETOOTH_CONNECT",
    "bluetooth_connect": "BLUETOOTH_CONNECT",
    "bluetooth_scan": "BLUETOOTH_SCAN",
    "bluetooth_advertise": "BLUETOOTH_ADVERTISE",
    "bluetooth_legacy": "BLUETOOTH",
    "bluetooth_admin": "BLUETOOTH_ADMIN",
    "nfc": "NFC",
    "biometric": "USE_BIOMETRIC",
    "fingerprint": "USE_BIOMETRIC",
    "activity": "ACTIVITY_RECOGNITION",
    "activity_recognition": "ACTIVITY_RECOGNITION",
    "boot": "RECEIVE_BOOT_COMPLETED",
    "boot_completed": "RECEIVE_BOOT_COMPLETED",
    "foreground_service": "FOREGROUND_SERVICE",
    "foreground_data_sync": "FOREGROUND_SERVICE_DATA_SYNC",
    "wake_lock": "WAKE_LOCK",
    "alarms": "SCHEDULE_EXACT_ALARM",
    "exact_alarm": "SCHEDULE_EXACT_ALARM",
}

#: Build-time features generated from ``pydrud.yaml``. Capabilities are a
#: friendlier, production-safe layer over common permission bundles.
CAPABILITY_ALIASES = {
    "haptic": "haptics",
    "haptics": "haptics",
    "vibrate": "haptics",
    "notification": "notifications",
    "notifications": "notifications",
    "push": "notifications",
    "foreground": "foreground_service",
    "foreground_service": "foreground_service",
    "service": "foreground_service",
    "boot": "boot_receiver",
    "boot_receiver": "boot_receiver",
    "wake": "wake_lock",
    "wake_lock": "wake_lock",
}

CAPABILITY_PERMISSIONS = {
    "foreground_service": {"FOREGROUND_SERVICE", "FOREGROUND_SERVICE_DATA_SYNC"},
    "boot_receiver": {"RECEIVE_BOOT_COMPLETED"},
    "wake_lock": {"WAKE_LOCK"},
    "haptics": {"VIBRATE"},
    "notifications": {"POST_NOTIFICATIONS"},
}

KNOWN_CAPABILITIES = frozenset(CAPABILITY_PERMISSIONS)

ANDROID_NS = "http://schemas.android.com/apk/res/android"

#: Launcher icon sizes (density bucket → pixels).
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144,
              "xxxhdpi": 192}


def resolve_permission(name: str) -> str:
    """``"camera"`` → ``"CAMERA"``; unknown names pass through upper-cased."""
    key = str(name).strip().lower().replace("-", "_")
    return PERMISSIONS.get(key, key.upper())


def resolve_capability(name: str) -> str:
    """Return the canonical capability name or raise ``ValueError``."""
    key = str(name).strip().lower().replace("-", "_")
    resolved = CAPABILITY_ALIASES.get(key, key)
    if resolved not in KNOWN_CAPABILITIES:
        raise ValueError(
            f"Unknown capability {name!r}; use one of "
            f"{', '.join(sorted(KNOWN_CAPABILITIES))}")
    return resolved


# ──────────────────────────────────────────────────────────────────────────
# Signing
# ──────────────────────────────────────────────────────────────────────────


def create_keystore(project_dir: str, *, alias: str = "release",
                    password: str = "", validity: int = 10000,
                    dname: Optional[str] = None,
                    filename: str = "upload-keystore.jks") -> bool:
    """Generate an upload keystore with ``keytool`` and record its settings.

    Returns True on success. The private key never leaves the project, and
    ``keystore.properties`` is git-ignored by the scaffold.
    """
    keytool = shutil.which("keytool")
    if not keytool:
        print(tui.error_badge("keytool not found — install a JDK 17+ and retry."))
        return False
    if len(password) < 6:
        print(tui.error_badge("Keystore passwords must be at least 6 characters."))
        return False

    android_dir = os.path.join(project_dir, "android")
    os.makedirs(android_dir, exist_ok=True)
    keystore_path = os.path.join(android_dir, filename)
    if os.path.exists(keystore_path):
        print(tui.warn_badge(
            f"{filename} already exists — keeping it (delete it first to regenerate)."))
        return False

    name = dname or (f"CN={os.path.basename(os.path.abspath(project_dir))}, "
                     f"OU=Pydrud, O=Pydrud, C=US")
    command = [
        keytool, "-genkeypair", "-v",
        "-keystore", keystore_path,
        "-alias", alias,
        "-keyalg", "RSA", "-keysize", "2048",
        "-validity", str(int(validity)),
        "-storepass", password, "-keypass", password,
        "-dname", name,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(tui.error_badge("keytool failed:"))
        print(tui.neutral_badge((result.stderr.strip().splitlines() or ["unknown"])[-1]))
        return False

    properties = os.path.join(android_dir, "keystore.properties")
    with open(properties, "w", encoding="utf-8") as handle:
        handle.write(
            "# Generated by 'pydrud keygen' — NEVER commit this file.\n"
            f"storeFile={filename}\n"
            f"storePassword={password}\n"
            f"keyAlias={alias}\n"
            f"keyPassword={password}\n")
    os.chmod(properties, 0o600)

    print(tui.ok_badge(f"Keystore     android/{filename}"))
    print(tui.ok_badge("Properties   android/keystore.properties (chmod 600)"))
    print(tui.warn_badge(
        "Back up both files safely — losing them prevents future Play updates."))
    print(tui.render_next_steps((
        ("pydrud build --release", "build a signed release APK"),
    )))
    return True


def signing_status(project_dir: str) -> dict:
    """What ``pydrud build --release`` will actually do."""
    properties = os.path.join(project_dir, "android", "keystore.properties")
    if not os.path.exists(properties):
        return {"configured": False, "reason": "no keystore.properties",
                "signed_with": "debug key"}
    values = {}
    with open(properties, encoding="utf-8") as handle:
        property_lines = handle.readlines()
    for line in property_lines:
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    store = os.path.join(project_dir, "android", values.get("storeFile", ""))
    return {"configured": os.path.exists(store),
            "alias": values.get("keyAlias", ""),
            "store": values.get("storeFile", ""),
            "signed_with": "release key" if os.path.exists(store) else "debug key"}


# ──────────────────────────────────────────────────────────────────────────
# Icons
# ──────────────────────────────────────────────────────────────────────────


#: How much of the adaptive canvas the art may occupy. Android masks the
#: outer ~25% of an adaptive icon, so the art has to live inside the safe
#: zone (66dp of the 108dp canvas) or launchers crop it.
_ADAPTIVE_SAFE_ZONE = 66 / 108

#: Adaptive layers are drawn on a 108dp canvas, 2.25x the 48dp base icon.
_ADAPTIVE_SCALE = 108 / 48


def generate_icons(project_dir: str, *, source: Optional[str] = None,
                   background: Optional[str] = None) -> list[str]:
    """Render launcher icons (legacy, round and adaptive) for every density.

    With no *source* image, a clean lettermark is generated from the app
    name, so a brand-new project still looks deliberate on the home screen.

    The adaptive background colour is taken from ``background`` when given;
    otherwise it is sampled from the edges of the source art, so the icon
    blends into its own brand colour instead of a hard-coded solid tile.

    This command deliberately does **not** touch the splash screen: the
    splash is a customisable screen owned by the app theme (see the
    generated ``themes.xml``), not a surface for stamping the launcher icon.
    """
    try:
        # Availability probe — the helpers below import what they need.
        from PIL import Image  # noqa: F401
    except ImportError:                                  # pragma: no cover
        print(tui.error_badge("Pillow is required: pip install pillow"))
        return []

    res_dir = os.path.join(project_dir, "android", "app", "src", "main", "res")
    name = os.path.basename(os.path.abspath(project_dir))
    written: list[str] = []

    if source and os.path.exists(source):
        master = Image.open(source).convert("RGBA")
        bg_color = _rgba(background) if background else _edge_color(master)
    else:
        bg_color = _rgba(background or "#FF6366F1")
        master = _lettermark(name, background or "#FF6366F1")

    # Legacy icon (API < 26): art flattened onto the background colour so
    # transparent logos never end up on a black square.
    flat = Image.new("RGBA", master.size, bg_color)
    flat.paste(master, (0, 0), master)
    for bucket, size in ICON_SIZES.items():
        folder = os.path.join(res_dir, f"mipmap-{bucket}")
        os.makedirs(folder, exist_ok=True)
        icon = flat.resize((size, size), Image.LANCZOS)
        path = os.path.join(folder, "ic_launcher.png")
        icon.save(path)
        written.append(path)
        # Round icon: same art, circular mask.
        round_path = os.path.join(folder, "ic_launcher_round.png")
        _circular(icon).save(round_path)
        written.append(round_path)

    # Adaptive icon (API 26+): a full-bleed background layer plus the art
    # centred in the safe zone of the foreground layer — the same structure
    # the `pydrud init` template ships, so both pipelines stay compatible.
    anydpi = os.path.join(res_dir, "mipmap-anydpi-v26")
    os.makedirs(anydpi, exist_ok=True)
    adaptive = os.path.join(anydpi, "ic_launcher.xml")
    with open(adaptive, "w", encoding="utf-8") as handle:
        handle.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@mipmap/ic_launcher_adaptive_back" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_adaptive_fore" />\n'
            '</adaptive-icon>\n')
    written.append(adaptive)

    for bucket, size in ICON_SIZES.items():
        folder = os.path.join(res_dir, f"mipmap-{bucket}")
        canvas = int(round(size * _ADAPTIVE_SCALE))     # 108dp layer canvas

        back = Image.new("RGBA", (canvas, canvas), bg_color)
        back_path = os.path.join(folder, "ic_launcher_adaptive_back.png")
        back.save(back_path)
        written.append(back_path)

        fore = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        inner_size = int(canvas * _ADAPTIVE_SAFE_ZONE)
        inner = master.resize((inner_size, inner_size), Image.LANCZOS)
        offset = (canvas - inner_size) // 2
        fore.paste(inner, (offset, offset), inner)
        fore_path = os.path.join(folder, "ic_launcher_adaptive_fore.png")
        fore.save(fore_path)
        written.append(fore_path)

    # Clean up artefacts older pydrud versions generated: the icon-stamped
    # splash drawable and the solid colour resource it referenced.
    for stale in (os.path.join(res_dir, "drawable", "splash.xml"),
                  os.path.join(res_dir, "values", "ic_launcher_background.xml")):
        if os.path.exists(stale):
            try:
                os.remove(stale)
                print(tui.info_badge(
                    f"Removed legacy {os.path.relpath(stale, res_dir)}"))
            except OSError:
                pass
    # Older runs also wrote a padded foreground under this name.
    for bucket in ICON_SIZES:
        stale = os.path.join(res_dir, f"mipmap-{bucket}",
                             "ic_launcher_foreground.png")
        if os.path.exists(stale):
            try:
                os.remove(stale)
            except OSError:
                pass

    print(tui.ok_badge(f"Launcher icons for {len(ICON_SIZES)} densities"))
    print(tui.ok_badge("Adaptive icon (background + safe-zone foreground)"))
    print(tui.info_badge(
        "Splash screen untouched — it follows your app theme, not the icon."))
    return written


def _edge_color(image) -> tuple:
    """Sample the dominant opaque colour along the edges of *image*.

    A logo exported on its own brand background keeps that exact colour
    behind the adaptive icon; fully transparent edges fall back to white so
    the icon sits on a clean card instead of a random solid tile.
    """
    width, height = image.size
    pixels = image.load()
    votes: dict[tuple, int] = {}
    step = max(1, width // 64)
    for x in range(0, width, step):
        for y in (0, height - 1):
            r, g, b, a = pixels[x, y]
            if a > 200:
                votes[(r, g, b, 255)] = votes.get((r, g, b, 255), 0) + 1
    for y in range(0, height, step):
        for x in (0, width - 1):
            r, g, b, a = pixels[x, y]
            if a > 200:
                votes[(r, g, b, 255)] = votes.get((r, g, b, 255), 0) + 1
    if not votes:
        return (255, 255, 255, 255)
    return max(votes, key=votes.get)


def _lettermark(name: str, background: str):
    from PIL import Image, ImageDraw, ImageFont

    size = 512
    image = Image.new("RGBA", (size, size), _rgba(background))
    draw = ImageDraw.Draw(image)
    letters = "".join(part[0] for part in name.replace("_", " ").split()[:2])
    letters = (letters or name[:1] or "P").upper()
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 230)
    except OSError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letters, font=font)
    draw.text(((size - box[2] + box[0]) / 2, (size - box[3] + box[1]) / 2 - 12),
              letters, font=font, fill=(255, 255, 255, 255))
    return image


def _circular(image):
    from PIL import Image, ImageDraw

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + image.size, fill=255)
    out = image.copy()
    out.putalpha(mask)
    return out


def _rgba(color: str) -> tuple:
    value = color.lstrip("#")
    if len(value) == 8:                     # ARGB
        a, r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, a)
    if len(value) == 6:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    return (99, 102, 241, 255)


# ──────────────────────────────────────────────────────────────────────────
# Permissions and capabilities
# ──────────────────────────────────────────────────────────────────────────


def _manifest_path(project_dir: str) -> str:
    return os.path.join(project_dir, "android", "app", "src", "main",
                        "AndroidManifest.xml")


def _load_manifest(project_dir: str):
    manifest_path = _manifest_path(project_dir)
    if not os.path.exists(manifest_path):
        print(tui.error_badge(
            "AndroidManifest.xml not found — run 'pydrud sync' first."))
        return None, None, None
    ET.register_namespace("android", ANDROID_NS)
    tree = ET.parse(manifest_path)
    return manifest_path, tree, tree.getroot()


def _write_manifest(path: str, tree) -> None:
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _manifest_permissions(root) -> set[str]:
    attribute = f"{{{ANDROID_NS}}}name"
    return {node.get(attribute, "") for node in root.findall("uses-permission")}


def _add_manifest_permission(root, permission: str) -> bool:
    attribute = f"{{{ANDROID_NS}}}name"
    full = f"android.permission.{permission}"
    if full in _manifest_permissions(root):
        return False
    node = ET.SubElement(root, "uses-permission")
    node.set(attribute, full)
    return True


def _remove_manifest_permission(root, permission: str) -> bool:
    attribute = f"{{{ANDROID_NS}}}name"
    full = f"android.permission.{permission}"
    removed = False
    for node in list(root.findall("uses-permission")):
        if node.get(attribute) == full:
            root.remove(node)
            removed = True
    return removed


def _config_list(project_dir: str, key: str) -> list[str]:
    from pydrud.commands.project_config import load_project_config

    configured = load_project_config(project_dir).get(key, [])
    if isinstance(configured, list):
        return [str(item) for item in configured]
    return [part.strip() for part in str(configured).split(",") if part.strip()]


def update_permissions(project_dir: str, *, add: Optional[Iterable[str]] = None,
                       remove: Optional[Iterable[str]] = None) -> list[str]:
    """Add or remove ``<uses-permission>`` entries in the manifest."""
    manifest_path, tree, root = _load_manifest(project_dir)
    if root is None:
        return []

    changed: list[str] = []
    for name in add or []:
        resolved = resolve_permission(name)
        if _add_manifest_permission(root, resolved):
            changed.append(resolved)

    for name in remove or []:
        resolved = resolve_permission(name)
        if _remove_manifest_permission(root, resolved):
            changed.append(resolved)

    if changed:
        _write_manifest(manifest_path, tree)

    # The manifest is generated by `pydrud sync`, so persist the requested
    # permissions in its system-level source of truth as well. This keeps a
    # later package/toolchain sync from silently discarding CLI changes.
    try:
        from pydrud.commands.project_config import set_list

        configured = [resolve_permission(name)
                      for name in _config_list(project_dir, "permissions")]
        for name in add or []:
            resolved = resolve_permission(name)
            if resolved not in configured:
                configured.append(resolved)
        removed = {resolve_permission(name) for name in remove or []}
        configured = [name for name in configured if name not in removed]
        set_list(project_dir, "permissions", configured)
    except OSError:
        # The direct manifest operation has still succeeded. A read-only YAML
        # file should not turn the permission command into a false failure.
        pass
    return changed


def update_capabilities(project_dir: str, *, add: Optional[Iterable[str]] = None,
                        remove: Optional[Iterable[str]] = None) -> list[str]:
    """Add/remove generated Android capabilities in YAML and manifest.

    Capabilities are higher-level switches such as ``haptics`` and
    ``notifications``. They keep normal permissions out of the hand-maintained
    ``permissions:`` list while still surviving every future ``pydrud sync``.
    """
    manifest_path, tree, root = _load_manifest(project_dir)
    if root is None:
        return []

    try:
        from pydrud.commands.project_config import set_list

        configured = [resolve_capability(name)
                      for name in _config_list(project_dir, "capabilities")]
        changed: list[str] = []
        for name in add or []:
            capability = resolve_capability(name)
            if capability not in configured:
                configured.append(capability)
                changed.append(capability)
        removed = {resolve_capability(name) for name in remove or []}
        for capability in list(configured):
            if capability in removed:
                configured.remove(capability)
                changed.append(capability)
        set_list(project_dir, "capabilities", sorted(configured))
    except OSError:
        return []

    manifest_changed = False
    for capability in add or []:
        for permission in CAPABILITY_PERMISSIONS[resolve_capability(capability)]:
            manifest_changed = _add_manifest_permission(root, permission) or manifest_changed
    for capability in remove or []:
        for permission in CAPABILITY_PERMISSIONS[resolve_capability(capability)]:
            manifest_changed = _remove_manifest_permission(root, permission) or manifest_changed
    if manifest_changed:
        _write_manifest(manifest_path, tree)
    return changed


def list_permissions(project_dir: str) -> list[str]:
    manifest_path = _manifest_path(project_dir)
    if not os.path.exists(manifest_path):
        return []
    tree = ET.parse(manifest_path)
    attribute = f"{{{ANDROID_NS}}}name"
    return sorted(node.get(attribute, "").rsplit(".", 1)[-1]
                  for node in tree.getroot().findall("uses-permission"))


def list_capabilities(project_dir: str) -> list[str]:
    return sorted(resolve_capability(name)
                  for name in _config_list(project_dir, "capabilities"))
