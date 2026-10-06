#!/usr/bin/env python3
"""
Generate ``pydrud/android/templates/android/PydrudIcons.java.j2``.

Pydrud draws its icons as real vector paths (Android's ``PathParser`` +
``Canvas.drawPath``) instead of the ancient ``android.R.drawable.ic_menu_*``
bitmaps, so every icon stays crisp at any size and can be tinted freely.

The outlines come from **Material Design Icons** (Pictogrammers, Apache-2.0),
extracted from the webfont shipped with the ``qtawesome`` PyPI package::

    pip install qtawesome fonttools
    python tools/generate_icons.py

The script is only needed when the icon catalogue changes — the generated
Java template is committed, so building a Pydrud app needs no extra tooling.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from fontTools.misc.transform import Transform
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover - developer tool
    sys.exit("pip install fonttools qtawesome first")

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pydrud" / "android" / "templates" / "android" / "PydrudIcons.java.j2"

#: Pydrud icon name -> Material Design Icons glyph name.
ICONS: dict[str, str] = {
    # ── navigation ───────────────────────────────────────────────────────
    "home": "home",
    "menu": "menu",
    "close": "close",
    "back": "arrow-left",
    "forward": "arrow-right",
    "arrow_up": "arrow-up",
    "arrow_down": "arrow-down",
    "chevron_left": "chevron-left",
    "chevron_right": "chevron-right",
    "expand_more": "chevron-down",
    "expand_less": "chevron-up",
    "more_vert": "dots-vertical",
    "more_horiz": "dots-horizontal",
    "apps": "apps",
    "dashboard": "view-dashboard",
    "grid": "view-grid",
    "list": "format-list-bulleted",
    "agenda": "format-list-checks",
    "open_in_new": "open-in-new",
    "fullscreen": "fullscreen",
    "fullscreen_exit": "fullscreen-exit",
    # ── actions ──────────────────────────────────────────────────────────
    "add": "plus",
    "add_circle": "plus-circle",
    "remove": "minus",
    "remove_circle": "minus-circle",
    "edit": "pencil",
    "delete": "delete",
    "save": "content-save",
    "copy": "content-copy",
    "paste": "content-paste",
    "cut": "content-cut",
    "undo": "undo",
    "redo": "redo",
    "refresh": "refresh",
    "sync": "sync",
    "search": "magnify",
    "filter": "filter-variant",
    "sort": "sort",
    "tune": "tune",
    "share": "share-variant",
    "send": "send",
    "link": "link-variant",
    "attach": "paperclip",
    "download": "download",
    "upload": "upload",
    "print": "printer",
    "zoom_in": "magnify-plus-outline",
    "zoom_out": "magnify-minus-outline",
    "crop": "crop",
    "rotate": "rotate-right",
    "swap": "swap-horizontal",
    "drag": "drag-horizontal-variant",
    "check": "check",
    "check_circle": "check-circle",
    "cancel": "close-circle",
    "logout": "logout",
    "login": "login",
    "settings": "cog",
    "build": "wrench",
    "code": "code-tags",
    "terminal": "console",
    "bug": "bug-outline",
    # ── status ───────────────────────────────────────────────────────────
    "info": "information",
    "help": "help-circle",
    "warning": "alert",
    "error": "alert-circle",
    "verified": "check-decagram",
    "shield": "shield-check",
    "star": "star",
    "star_border": "star-outline",
    "favorite": "heart",
    "favorite_border": "heart-outline",
    "thumb_up": "thumb-up",
    "thumb_down": "thumb-down",
    "bookmark": "bookmark",
    "bookmark_border": "bookmark-outline",
    "flag": "flag",
    "tag": "tag",
    "notifications": "bell",
    "notifications_off": "bell-off",
    "visibility": "eye",
    "visibility_off": "eye-off",
    "lock": "lock",
    "lock_open": "lock-open-variant",
    "key": "key-variant",
    "fingerprint": "fingerprint",
    # ── people & social ──────────────────────────────────────────────────
    "person": "account",
    "person_add": "account-plus",
    "person_remove": "account-minus",
    "group": "account-group",
    "chat": "chat",
    "comment": "comment-text-outline",
    "email": "email",
    "inbox": "inbox",
    "call": "phone",
    "call_end": "phone-hangup",
    "emoji": "emoticon-happy-outline",
    # ── media ────────────────────────────────────────────────────────────
    "play": "play",
    "pause": "pause",
    "stop": "stop",
    "skip_next": "skip-next",
    "skip_previous": "skip-previous",
    "volume": "volume-high",
    "volume_off": "volume-off",
    "mic": "microphone",
    "mic_off": "microphone-off",
    "music": "music",
    "video": "video",
    "camera": "camera",
    "image": "image",
    "gallery": "image-multiple",
    "palette": "palette",
    "brush": "brush",
    # ── files ────────────────────────────────────────────────────────────
    "folder": "folder",
    "folder_open": "folder-open",
    "file": "file-document-outline",
    "archive": "archive",
    "cloud": "cloud",
    "cloud_upload": "cloud-upload",
    "cloud_download": "cloud-download",
    "database": "database",
    "qr_code": "qrcode",
    # ── data ─────────────────────────────────────────────────────────────
    "chart": "chart-bar",
    "pie_chart": "chart-pie",
    "trending_up": "trending-up",
    "trending_down": "trending-down",
    "timer": "timer-outline",
    "alarm": "alarm",
    "clock": "clock-outline",
    "history": "history",
    "calendar": "calendar-month-outline",
    "event": "calendar-check",
    # ── places & things ──────────────────────────────────────────────────
    "location": "map-marker",
    "map": "map",
    "globe": "earth",
    "navigation": "navigation-variant",
    "cart": "cart",
    "payment": "credit-card-outline",
    "wallet": "wallet",
    "bank": "bank",
    "store": "storefront-outline",
    "gift": "gift",
    "truck": "truck-delivery",
    "food": "silverware-fork-knife",
    "coffee": "coffee",
    "work": "briefcase",
    "school": "school",
    "book": "book-open-page-variant",
    "translate": "translate",
    "rocket": "rocket-launch",
    "lightbulb": "lightbulb-on",
    "fire": "fire",
    "leaf": "leaf",
    "water": "water",
    # ── system ───────────────────────────────────────────────────────────
    "wifi": "wifi",
    "wifi_off": "wifi-off",
    "bluetooth": "bluetooth",
    "battery": "battery",
    "battery_charging": "battery-charging",
    "dark_mode": "weather-night",
    "light_mode": "white-balance-sunny",
    "brightness": "brightness-6",
    "phone_android": "cellphone",
    "desktop": "monitor",
    "watch": "watch",
    "headphones": "headphones",
    "power": "power",
    "layers": "layers-outline",
    "puzzle": "puzzle-outline",
    "sparkle": "star-four-points",
    "python": "language-python",
    "android": "android",
}

#: Icons with no Material Design Icons glyph in the webfont, hand-authored as
#: plain 24x24 path data. Kept here (not in the generated Java) so a future
#: ``python tools/generate_icons.py`` reproduces them instead of dropping them.
EXTRA_PATHS: dict[str, str] = {
    "circle": "M12,2 A10,10 0 1,0 12,22 A10,10 0 1,0 12,2 Z",
    "diamond": "M12,2 L22,12 L12,22 L2,12 Z",
    "square": "M4,4 L20,4 L20,20 L4,20 Z",
    "triangle": "M12,3 L21.5,20 L2.5,20 Z",
}

FONT_DIRS = [
    Path(p) / "qtawesome" / "fonts" for p in sys.path if p
]


def _font_paths() -> tuple[Path, Path]:
    for directory in FONT_DIRS:
        font = directory / "materialdesignicons6-webfont-6.9.96.ttf"
        charmap = directory / "materialdesignicons6-webfont-charmap-6.9.96.json"
        if font.exists() and charmap.exists():
            return font, charmap
    sys.exit("materialdesignicons6 webfont not found — pip install qtawesome")


def extract() -> dict[str, str]:
    """Return ``{pydrud_name: svg_path_data}`` in a 24x24 viewport."""
    font_path, charmap_path = _font_paths()
    font = TTFont(str(font_path))
    charmap = json.loads(charmap_path.read_text())
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upem = font["head"].unitsPerEm
    ascent = font["hhea"].ascent
    scale = 24.0 / upem
    # Font coordinates are y-up with the baseline at 0; SVG/Android is y-down
    # with the 24x24 box starting at the ascender line.
    transform = Transform(scale, 0, 0, -scale, 0, ascent * scale)

    out: dict[str, str] = {}
    missing: list[str] = []
    for name, mdi in ICONS.items():
        code = charmap.get(mdi)
        if code is None or int(code, 16) not in cmap:
            missing.append(f"{name} ({mdi})")
            continue
        glyph_name = cmap[int(code, 16)]
        pen = SVGPathPen(glyphs, ntos=lambda v: f"{round(v, 2):g}")
        glyphs[glyph_name].draw(TransformPen(pen, transform))
        data = pen.getCommands().replace("\n", " ").strip()
        if data:
            out[name] = data
        else:
            missing.append(f"{name} ({mdi}) — empty")
    if missing:
        print("WARNING missing glyphs:", ", ".join(missing), file=sys.stderr)
    return out


JAVA_HEADER = '''package {{ package }};

import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.util.Log;

import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * PydrudIcons — crisp vector icons, drawn from path data.
 *
 * <p>Every icon is a 24x24 outline rendered with {@link Path} at the exact
 * size requested, so icons stay sharp on any density and can be tinted to
 * any colour. Outlines come from Material Design Icons (Pictogrammers,
 * Apache License 2.0) and are generated by {@code tools/generate_icons.py}.
 *
 * <p>Do not edit by hand.
 */
public final class PydrudIcons {

    /** Stable logcat tag (PB-005 / DX-004). */
    public static final String TAG = "Pydrud";

    private static final Map<String, String> PATHS = new HashMap<>();
    private static final Map<String, String> ALIASES = new HashMap<>();
    private static final Set<String> WARNED = Collections.synchronizedSet(new HashSet<String>());

    private PydrudIcons() {}

    /** @return true when an icon with this name (or alias) exists. */
    public static boolean has(String name) {
        return name != null && !name.isEmpty() && pathData(name) != null;
    }

    /** Every icon name (and alias) this build understands, sorted. */
    public static Set<String> available() {
        Set<String> names = new TreeSet<>();
        names.addAll(PATHS.keySet());
        names.addAll(ALIASES.keySet());
        return Collections.unmodifiableSet(names);
    }

    /** Raw 24x24 SVG path data for {@code name}, or null. */
    public static String pathData(String name) {
        if (name == null) return null;
        String key = name.trim().toLowerCase();
        String data = PATHS.get(key);
        if (data != null) return data;
        String alias = ALIASES.get(key);
        return alias == null ? null : PATHS.get(alias);
    }

    /**
     * A tintable, size-independent drawable for {@code name}.
     *
     * <p>An unknown name used to render a silent "?" (the {@code help}
     * glyph), which made a typo look like a design choice (PB-005). It now
     * logs a warning once per unknown name before falling back, so the
     * mistake is visible in logcat and in {@code pydrud analyze} output.
     */
    public static Drawable drawable(String name, int color, int sizePx) {
        String data = pathData(name);
        if (data == null) {
            warnUnknown(name);
            data = PATHS.get("help");
        }
        return new IconDrawable(data, color, sizePx);
    }

    /**
     * A drawable for arbitrary 24x24 SVG path data.
     *
     * <p>Backs {@code Icon.svg(...)}: an app can render its own iconography
     * without the framework knowing the name, so the icon set is effectively
     * unlimited (PYDRUD §16.2).
     */
    public static Drawable drawablePath(String data, int color, int sizePx) {
        if (data == null || data.trim().isEmpty()) {
            warnUnknown("<empty svg path>");
            data = PATHS.get("help");
        }
        return new IconDrawable(data, color, sizePx);
    }

    private static void warnUnknown(String name) {
        String key = name == null ? "" : name.trim().toLowerCase();
        if (!WARNED.add(key)) return;   // once per name, per process
        Log.w(TAG, "unknown icon '" + name + "' — falling back to 'help'. "
            + "Call pydrud.icons.has(name) (Python) or PydrudIcons.has(name) "
            + "(Java) for the supported set.");
    }

    /** Drawable that rasterises 24x24 path data at any size. */
    public static final class IconDrawable extends Drawable {

        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path source = new Path();
        private final Path scaled = new Path();
        private final Matrix matrix = new Matrix();
        private final int size;
        private int tint;

        IconDrawable(String data, int color, int sizePx) {
            this.size = sizePx > 0 ? sizePx : 1;
            this.tint = color;
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(color);
            try {
                Path parsed = androidx.core.graphics.PathParser
                    .createPathFromPathData(data);
                if (parsed != null) source.set(parsed);
            } catch (Throwable ignored) {}
            setBounds(0, 0, this.size, this.size);
        }

        @Override public int getIntrinsicWidth()  { return size; }
        @Override public int getIntrinsicHeight() { return size; }

        @Override public void draw(Canvas canvas) {
            Rect b = getBounds();
            float side = Math.min(b.width(), b.height());
            if (side <= 0) side = size;
            float scale = side / 24f;
            matrix.reset();
            matrix.setScale(scale, scale);
            matrix.postTranslate(b.left + (b.width() - side) / 2f,
                                 b.top + (b.height() - side) / 2f);
            source.transform(matrix, scaled);
            canvas.drawPath(scaled, paint);
        }

        /** Re-tint in place (cheaper than rebuilding the drawable). */
        public void setTint(int color) {
            this.tint = color;
            paint.setColor(color);
            invalidateSelf();
        }

        public int tintColor() { return tint; }

        @Override public void setAlpha(int alpha) { paint.setAlpha(alpha); }
        @Override public void setColorFilter(ColorFilter cf) { paint.setColorFilter(cf); }
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
'''

JAVA_FOOTER = """}
"""

#: Extra names that resolve to an existing icon.
ALIASES = {
    "plus": "add",
    "minus": "remove",
    "trash": "delete",
    "bin": "delete",
    "pencil": "edit",
    "cog": "settings",
    "gear": "settings",
    "magnify": "search",
    "account": "person",
    "user": "person",
    "profile": "person",
    "users": "group",
    "people": "group",
    "bell": "notifications",
    "heart": "favorite",
    "heart_border": "favorite_border",
    "heart_broken": "favorite_border",
    "eye": "visibility",
    "eye_off": "visibility_off",
    "arrow_back": "back",
    "arrow_forward": "forward",
    "arrow_left": "back",
    "arrow_right": "forward",
    "keyboard_arrow_down": "expand_more",
    "keyboard_arrow_up": "expand_less",
    "keyboard_arrow_left": "chevron_left",
    "keyboard_arrow_right": "chevron_right",
    "dots": "more_vert",
    "mail": "email",
    "phone": "call",
    "message": "chat",
    "attachment": "attach",
    "picture": "image",
    "photo": "image",
    "photos": "gallery",
    "document": "file",
    "doc": "file",
    "money": "payment",
    "credit_card": "payment",
    "shopping_cart": "cart",
    "shop": "store",
    "clock_outline": "clock",
    "time": "clock",
    "schedule": "clock",
    "date": "calendar",
    "today": "event",
    "pin": "location",
    "place": "location",
    "location_pin": "location",
    "compass": "navigation",
    "directions_car": "navigation",
    "night": "dark_mode",
    "sun": "light_mode",
    "moon": "dark_mode",
    "graph": "chart",
    "analytics": "chart",
    "stats": "chart",
    "bar_chart": "chart",
    "api": "code",
    "server": "database",
    "security": "shield",
    "trophy": "verified",
    "exit": "logout",
    "sign_out": "logout",
    "sign_in": "login",
    "ok": "check",
    "done": "check",
    "tick": "check",
    "alert": "warning",
    "danger": "error",
    "question": "help",
    "support": "help",
    "idea": "lightbulb",
    "spark": "sparkle",
    "magic": "sparkle",
    "flash": "sparkle",
    "cast": "fullscreen",
    "flight": "rocket",
    "home_work": "home",
    "hotel": "home",
    "language": "translate",
    "pause_circle": "pause",
    "play_circle": "play",
    "print_outline": "print",
    "record": "stop",
    "restaurant": "food",
    "scan": "qr_code",
}

#: Extra spellings on top of :data:`ALIASES` — the framework's own shorthands
#: plus the Material Symbols names developers copy straight from the docs.
#: The shipped vocabulary is smaller than Material's, so each name maps onto
#: the closest real icon (PB-005). A target must be a **path** name: aliases
#: resolve in a single hop, so chaining an alias to another alias silently
#: falls back to ``help``.
EXTRA_ALIASES: dict[str, str] = {
    # framework shorthands
    "animation": "sparkle",
    "arrow_down": "expand_more",
    "arrow_up": "expand_less",
    "astrophysics": "rocket",
    "canvas": "palette",
    "controller": "play",
    "fullscreen_exit": "fullscreen",
    "gamepad": "play",
    "games": "play",
    "joystick": "play",
    "mute": "volume",
    "screen_rotation": "refresh",
    "sound": "volume",
    "sparkles": "sparkle",
    "state": "sync",
    "touch": "drag",
    "touch_app": "drag",
    "vibration": "notifications",
    "volume_mute": "volume",
    "volume_off": "volume",
    "volume_up": "volume",
    # Material Symbols names (see PYDRUD §16.1)
    "account_tree": "list",
    "add_circle_outline": "add_circle",
    "arrow_circle_down": "arrow_down",
    "arrow_circle_up": "arrow_up",
    "arrow_drop_down": "expand_more",
    "arrow_drop_up": "expand_less",
    "backspace": "back",
    "block": "cancel",
    "bolt": "sparkle",
    "calendar_today": "calendar",
    "check_circle_outline": "check_circle",
    "circle": "circle",
    "clear": "close",
    "cloud_done": "cloud",
    "content_copy": "copy",
    "content_cut": "cut",
    "content_paste": "paste",
    "delete_outline": "delete",
    "diamond": "diamond",
    "done_all": "check",
    "edit_note": "edit",
    "emoji_events": "verified",
    "error_outline": "error",
    "favorite_outline": "favorite_border",
    "file_download": "download",
    "file_upload": "upload",
    "filter_alt": "filter",
    "first_page": "skip_previous",
    "flash_on": "sparkle",
    "hourglass_bottom": "timer",
    "last_page": "skip_next",
    "library_books": "book",
    "lock_outline": "lock",
    "more_time": "timer",
    "note_add": "add",
    "notification_important": "notifications",
    "notifications_active": "notifications",
    "open_in_full": "fullscreen",
    "person_outline": "person",
    "picture_as_pdf": "file",
    "play_arrow": "play",
    "playlist_add": "list",
    "publish": "upload",
    "queue_music": "music",
    "remove_red_eye": "visibility",
    "replay": "refresh",
    "repeat": "sync",
    "repeat_one": "sync",
    "restart_alt": "undo",
    "rocket_launch": "rocket",
    "save_alt": "save",
    "shopping_bag": "cart",
    "shuffle": "swap",
    "speed": "timer",
    "sports_esports": "play",
    "square": "square",
    "star_outline": "star_border",
    "star_rate": "star",
    "sync_alt": "sync",
    "task_alt": "check_circle",
    "thumb_up_alt": "thumb_up",
    "trending_flat": "trending_up",
    "triangle": "triangle",
    "upload_file": "upload",
    "verified_user": "shield",
    "videocam": "video",
    "view_list": "list",
    "warning_amber": "warning",
    "work_outline": "work",
    "zoom_out_map": "fullscreen",
}
ALIASES.update(EXTRA_ALIASES)


def java_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(paths: dict[str, str]) -> str:
    chunks: list[str] = []
    names = list(paths)
    per_method = 25
    groups = [names[i:i + per_method] for i in range(0, len(names), per_method)]
    # Alias targets must be real paths; hand-authored icons count too.
    known = set(paths) | set(EXTRA_PATHS)

    body = [JAVA_HEADER, "\n    static {\n"]
    for index in range(len(groups)):
        body.append(f"        load{index}();\n")
    body.append("        aliases();\n")
    body.append("        extras();\n    }\n")

    for index, group in enumerate(groups):
        body.append(f"\n    private static void load{index}() {{\n")
        for name in group:
            body.append(
                f"        PATHS.put({java_literal(name)},\n"
                f"            {java_literal(paths[name])});\n"
            )
        body.append("    }\n")

    body.append("\n    private static void aliases() {\n")
    for alias, target in sorted(ALIASES.items()):
        if target in known:
            body.append(
                f"        ALIASES.put({java_literal(alias)}, {java_literal(target)});\n"
            )
    body.append("    }\n")

    # Hand-authored icons live in their own method so a regeneration keeps
    # them visibly separate from the webfont-derived outlines.
    body.append("\n    private static void extras() {\n")
    for name in sorted(EXTRA_PATHS):
        body.append(
            f"        PATHS.put({java_literal(name)},\n"
            f"            {java_literal(EXTRA_PATHS[name])});\n"
        )
    body.append("    }\n")
    body.append(JAVA_FOOTER)
    chunks.append("".join(body))
    return "".join(chunks)


def main() -> int:
    paths = extract()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(paths), encoding="utf-8")
    size = os.path.getsize(OUT)
    print(f"wrote {OUT.relative_to(REPO)} — {len(paths)} webfont icons "
          f"+ {len(EXTRA_PATHS)} hand-authored, {size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
