"""
Rendering the native Android layer from the resolved template context.

Every file written here is managed by Pydrud, so each write goes through the
ownership rules in :mod:`pydrud.commands.project.managed`:

* files Pydrud owns end to end carry a provenance hash and are only
  rewritten when nobody edited them;
* files with a managed region (manifest, ProGuard, Gradle dependencies) are
  merged, so hand-written entries survive;
* `gradle.properties` is ensure-only: Pydrud adds the keys it needs and
  never overrides a value the developer set.
"""

from __future__ import annotations

import os

from pydrud.commands.project.config import _project_seed
from pydrud.commands.project.managed import (
    ChangeLog, merge_gradle, merge_manifest, merge_properties,
    merge_proguard,
)
from pydrud.commands.project.paths import (
    _APP_MODULES, _JAVA_TEMPLATES, _RUNTIME_BACKENDS, _ensure_dir,
    _theme_colors, _write_managed, _write_managed_merged, _write_template,
)


def _render_native_layer(project_dir: str, java_package_path: str, ctx: dict,
                         log: ChangeLog | None = None) -> None:
    """Write the Java renderer and its theme resources.

    Shared by `pydrud create`, `pydrud init android` and `pydrud sync`
    so an existing project can pick up a new Pydrud release without being
    recreated.
    """
    java_dir = f"{project_dir}/android/app/src/main/java/{java_package_path}"
    _ensure_dir(java_dir)

    _write_managed("android/MainActivity.java.j2",
                   f"{java_dir}/{ctx['app_name']}Activity.java", ctx, "java",
                   log=log)
    for name in _JAVA_TEMPLATES:
        _write_managed(f"android/{name}.java.j2", f"{java_dir}/{name}.java",
                       ctx, "java", log=log)

    # The concrete runtime backend. Only one is ever generated, so a host/none
    # project never compiles - or even contains - ChaquopyRuntime.
    backend = _RUNTIME_BACKENDS.get(
        ctx.get("runtime_backend", "chaquopy"), "ChaquopyRuntime")
    _write_managed(f"android/{backend}.java.j2",
                   f"{java_dir}/{backend}.java", ctx, "java", log=log)

    if ctx.get("firebase"):
        _write_managed("android/PydrudMessagingService.java.j2",
                       f"{java_dir}/PydrudMessagingService.java", ctx, "java",
                       log=log)

    # Material theme resources. The night variant keeps native dialogs and
    # system bars in step with Theme.dark() on the Python side.
    _ensure_dir(f"{project_dir}/android/app/src/main/res/values")
    _ensure_dir(f"{project_dir}/android/app/src/main/res/values-night")
    colors = _theme_colors(ctx.get("seed_color") or _project_seed(project_dir))
    _write_managed("android/themes.xml.j2",
                   f"{project_dir}/android/app/src/main/res/values/themes.xml",
                   {**ctx, "night": False, "colors": colors["light"]}, "xml",
                   log=log)
    _write_managed("android/themes.xml.j2",
                   f"{project_dir}/android/app/src/main/res/values-night/themes.xml",
                   {**ctx, "night": True, "colors": colors["dark"]}, "xml",
                   log=log)

    # App-specific tag IDs. ViewFactory/MaterialViews use keyed view tags
    # (slider ranges, change listeners, composite child hosts), and Android
    # rejects framework IDs there - these must come from the app's own
    # resources or every Slider/Switch/Tabs render fails at runtime.
    _write_managed("android/ids.xml.j2",
                   f"{project_dir}/android/app/src/main/res/values/ids.xml",
                   ctx, "xml", log=log)


def _render_app_package(project_dir: str, ctx: dict) -> None:
    """Write the structured `src/app` package."""
    for folder in ("", "components", "screens"):
        _ensure_dir(os.path.join(project_dir, "src", "app", folder))
    for template, relative in _APP_MODULES:
        if ctx.get("runtime") == "pydash" and relative == "jobs.py":
            continue  # WorkManager adapter is only part of the Android target.
        _write_template(template,
                        os.path.join(project_dir, "src", "app", *relative.split("/")),
                        ctx)
    _write_template("python/app/theme.pss.j2",
                    os.path.join(project_dir, "src", "app", "theme.pss"), ctx)


def _render_managed_android(project_dir: str, ctx: dict,
                            log: ChangeLog | None = None) -> ChangeLog:
    """Regenerate every Android file controlled by `pydrud.yaml`.

    *log* collects per-file outcomes so the caller can report how much
    actually changed. Sync on an untouched project rewrites nothing.
    """
    log = log if log is not None else ChangeLog()
    _render_native_layer(project_dir, ctx["package_path"], ctx, log)

    main_dir = os.path.join(project_dir, "android", "app", "src", "main")
    _ensure_dir(main_dir)
    _write_managed_merged("android/AndroidManifest.xml.j2",
                          os.path.join(main_dir, "AndroidManifest.xml"),
                          ctx, merge_manifest, log=log)

    android_dir = os.path.join(project_dir, "android")
    _write_managed("android/build.gradle.kts.j2",
                   os.path.join(android_dir, "build.gradle.kts"), ctx,
                   "kotlin", log=log)
    _write_managed("android/app/build.gradle.kts.j2",
                   os.path.join(android_dir, "app", "build.gradle.kts"), ctx,
                   "kotlin", patch=merge_gradle, log=log)
    _write_managed("android/proguard-rules.pro.j2",
                   os.path.join(android_dir, "app", "proguard-rules.pro"), ctx,
                   "hash", patch=merge_proguard, log=log)
    _write_managed("android/settings.gradle.kts.j2",
                   os.path.join(android_dir, "settings.gradle.kts"), ctx,
                   "kotlin", log=log)
    _write_managed_merged("android/gradle.properties.j2",
                          os.path.join(android_dir, "gradle.properties"),
                          ctx, merge_properties, log=log)
    _write_managed("android/gradlew.j2", os.path.join(android_dir, "gradlew"),
                   ctx, "hash", log=log)
    _write_managed("android/gradlew.bat.j2",
                   os.path.join(android_dir, "gradlew.bat"), ctx, "bat",
                   log=log)
    _write_managed("android/gradle/wrapper/gradle-wrapper.properties.j2",
                   os.path.join(android_dir, "gradle", "wrapper",
                                "gradle-wrapper.properties"), ctx, "hash",
                   log=log)
    try:
        os.chmod(os.path.join(android_dir, "gradlew"), 0o755)
    except OSError:
        pass
    return log
