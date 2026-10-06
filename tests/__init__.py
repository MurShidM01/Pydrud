"""Pydrud test suite."""

import glob
import os

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pydrud", "android", "templates", "android",
)


def read_template(name: str) -> str:
    """Read a single ``*.j2`` template from the Android template dir."""
    with open(os.path.join(TEMPLATES_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def all_java_templates() -> str:
    """Combined source of every ``*.java.j2`` renderer.

    The renderer was split into collaborator classes (ViewFactory +
    BuiltinViews/ViewStyler/LayoutEngine/TreePatcher/EventBinder/
    NativeViewFactory/ViewAnimator/ImageLoader), so assertions about "the
    renderer implements X" must look across all of the generated classes.
    """
    parts = []
    for path in sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.java.j2"))):
        with open(path, encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n".join(parts)
