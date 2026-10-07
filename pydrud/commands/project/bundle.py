"""
Bundling the Pydrud runtime into a generated project.
"""

from __future__ import annotations

import io
import os
import shutil
import tokenize

from pydrud.commands.project.paths import BUNDLE_EXCLUDES, _ensure_dir
from pydrud.utils.colors import fail, info

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
                lines = [line.rstrip() for line in compact.splitlines()]
                cleaned = []
                for line in lines:
                    if not line and (not cleaned or not cleaned[-1]):
                        continue
                    cleaned.append(line)
                with open(path, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write("\n".join(cleaned) + "\n")
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
    # ``__file__`` is ``pydrud/commands/project/bundle.py``: three ``dirname``
    # calls land on the ``pydrud`` package directory.
    pydrud_src = os.path.normpath(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    dst = os.path.join(src_dir, "pydrud")
    if not os.path.isdir(pydrud_src):
        print(fail("Could not locate the pydrud package to bundle."))
        return

    if os.path.isdir(dst):
        shutil.rmtree(dst)

    # ``android`` is excluded only at the package root: it contains the
    # generator templates, while ``platforms/android`` contains runtime
    # adapters required by standalone apps. A basename-only ignore pattern
    # would accidentally remove both.
    patterns = tuple(name for name in BUNDLE_EXCLUDES if name != "android")
    ignore_patterns = shutil.ignore_patterns(*patterns)
    package_root = os.path.normcase(os.path.abspath(pydrud_src))

    def ignore_runtime_sources(directory: str, names: list[str]) -> set[str]:
        ignored = set(ignore_patterns(directory, names))
        if os.path.normcase(os.path.abspath(directory)) == package_root:
            ignored.add("android")
        return ignored

    shutil.copytree(pydrud_src, dst, ignore=ignore_runtime_sources)
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
    # The res/ lives alongside the templates/ inside the installed package;
    # from ``pydrud/commands/project/bundle.py`` that is two levels up.
    src_res = os.path.join(os.path.dirname(__file__), "..", "..",
                          "android", "templates", "res")
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
