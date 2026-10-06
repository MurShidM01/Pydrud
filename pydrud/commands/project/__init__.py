"""
Pydrud project scaffold — generates a complete Android + Python project tree.

The work is split into cohesive sibling modules: name/constants helpers in
``paths``, Python runtime detection in ``python_runtime``, config reading in
``config``, template rendering in ``templates``, runtime bundling in
``bundle``, the ``init`` entry point in ``scaffold`` and ``sync`` in ``sync``.
This package re-exports every public and internal name so
``from pydrud.commands.project import create_project`` keeps working.
"""

import shutil

from pydrud.commands.project.bundle import (
    _bundle_pydrud_source, _copy_icon_resources, _strip_runtime_comments,
    bundled_runtime_size_kb,
)
from pydrud.commands.project.config import (
    ProjectConfigError, _config_bool, _config_int, _config_list, _config_string,
    _gradle_value, _manifest_permissions, _project_seed, _toml_section,
    _validate_package,
)
from pydrud.commands.project.paths import (
    _camel, _detect_ndk, _detect_sdk, _ensure_dir, _JAVA_KEYWORDS, _JAVA_TEMPLATES,
    _normalise_color, _sanitize_package, _slugify, _theme_colors, _version,
    _version_key, _write_template, BUNDLE_EXCLUDES, _APP_MODULES,
)
from pydrud.commands.project.python_runtime import (
    APP_PYTHON_VERSION, BUILD_PYTHON_VERSIONS, _build_python_candidates,
    _detect_build_python, _python_version_of, _resolve_executable,
)
from pydrud.commands.project.scaffold import create_project
from pydrud.commands.project.sync import (
    _discover_project, _remove_generated_java, _stamp_version,
    _sync_context, _sync_generated_metadata, _sync_toml_identity, sync_project,
)
from pydrud.commands.project.templates import (
    _render_app_package, _render_managed_android, _render_native_layer,
)

__all__ = [
    "create_project", "sync_project",
    "BUNDLE_EXCLUDES", "_APP_MODULES", "_JAVA_TEMPLATES", "_JAVA_KEYWORDS",
    "_ensure_dir", "_write_template", "_sanitize_package", "_slugify", "_camel",
    "_detect_sdk", "_detect_ndk", "_version_key", "_normalise_color", "_theme_colors",
    "_version", "shutil",
    "APP_PYTHON_VERSION", "BUILD_PYTHON_VERSIONS", "_detect_build_python",
    "_python_version_of", "_build_python_candidates", "_resolve_executable",
    "ProjectConfigError", "_config_string", "_config_int", "_config_bool",
    "_config_list", "_validate_package", "_toml_section", "_project_seed",
    "_gradle_value", "_manifest_permissions",
    "_render_native_layer", "_render_app_package", "_render_managed_android",
    "bundled_runtime_size_kb", "_strip_runtime_comments", "_bundle_pydrud_source",
    "_copy_icon_resources",
    "_sync_context", "_remove_generated_java", "_sync_generated_metadata",
    "_sync_toml_identity", "_discover_project", "_stamp_version",
]
