"""
Rendering the native Android layer from the resolved template context.
"""

from __future__ import annotations

import os

from pydrud.commands.project.config import _project_seed
from pydrud.commands.project.paths import (
    _APP_MODULES, _JAVA_TEMPLATES, _ensure_dir, _theme_colors, _write_template,
)

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


def _render_app_package(project_dir: str, ctx: dict) -> None:
    """Write the structured ``src/app`` package."""
    for folder in ("", "components", "screens"):
        _ensure_dir(os.path.join(project_dir, "src", "app", folder))
    for template, relative in _APP_MODULES:
        _write_template(template,
                        os.path.join(project_dir, "src", "app", *relative.split("/")),
                        ctx)


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
