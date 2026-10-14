"""
Material 3 shape morphing.

Material's shapes are a small parametric family — circles, rounded polygons,
puffy squircles and the "cookie", "clover", "burst" and "flower" waves — and
morphing moves between two members of that family by matching their vertices
while a spring drives the motion.

::

    ShapeMorph(
        from_shape=Shapes.CIRCLE, to_shape=Shapes.COOKIE_9,
        progress=1 if selected else 0, rotation=90, size=96,
        bg=Theme.primary_container, child=Icon(Icons.FAVORITE),
    )

``progress`` is the whole animation: 0 paints ``from_shape``, 1 paints
``to_shape``, and everything between is a real member of the family rather
than a tangle of crossing curves. Moving it does not jump — the renderer
runs the change on the spring named by ``spring``, which is a Material 3
spring (a damping ratio and a stiffness) rather than a curve and a duration,
so the motion adapts to how far it has to travel.
"""

from __future__ import annotations

from typing import Optional

from pydrud.widgets.base import Widget

#: Every shape the renderer can draw, and therefore every shape a morph can
#: start or end at. Names match the Material shape catalogue's family.
SHAPES = (
    "circle",
    "square",
    "puffy_square",
    "diamond",
    "puffy_diamond",
    "pentagon",
    "hexagon",
    "octagon",
    "gem",
    "clover_4",
    "clover_6",
    "clover_8",
    "clover_12",
    "cookie_4",
    "cookie_6",
    "cookie_9",
    "cookie_12",
    "burst",
    "soft_burst",
    "flower",
    "sunny",
)

#: The Material 3 springs a morph can be driven by, by speed and by what is
#: being animated. A spatial spring moves the shape; an effects spring is
#: critically damped and is for colour or opacity.
SPRINGS = (
    "spring_fast_spatial",
    "spring_default_spatial",
    "spring_slow_spatial",
    "spring_fast_effects",
    "spring_default_effects",
    "spring_slow_effects",
)

#: Where a shape change sits in the spring table: a shape is spatial motion,
#: and one that changes while a finger is on it is small and quick.
DEFAULT_SPRING = "spring_fast_spatial"


class Shapes:
    """The shape names, for completion and for validation.

    Names are forgiving: ``COOKIE_9``, ``cookie_9`` and ``cookie-9`` all
    normalise to the same shape.
    """

    CIRCLE = "circle"
    SQUARE = "square"
    PUFFY_SQUARE = "puffy_square"
    DIAMOND = "diamond"
    PUFFY_DIAMOND = "puffy_diamond"
    PENTAGON = "pentagon"
    HEXAGON = "hexagon"
    OCTAGON = "octagon"
    GEM = "gem"
    CLOVER_4 = "clover_4"
    CLOVER_6 = "clover_6"
    CLOVER_8 = "clover_8"
    CLOVER_12 = "clover_12"
    COOKIE_4 = "cookie_4"
    COOKIE_6 = "cookie_6"
    COOKIE_9 = "cookie_9"
    COOKIE_12 = "cookie_12"
    BURST = "burst"
    SOFT_BURST = "soft_burst"
    FLOWER = "flower"
    SUNNY = "sunny"

    @staticmethod
    def normalize(name: str) -> str:
        """``COOKIE-9`` → ``cookie_9``; raises on an unknown shape."""
        text = str(name or "").strip().lower().replace("-", "_")
        if text not in SHAPES:
            raise ValueError(
                f"Unknown shape {name!r}. Available: {', '.join(SHAPES)}")
        return text

    @staticmethod
    def names() -> tuple:
        return SHAPES


def _spring(value: Optional[str]) -> str:
    name = (value or DEFAULT_SPRING).strip().lower().replace("-", "_")
    if name not in SPRINGS:
        raise ValueError(
            f"Unknown spring {value!r}. Available: {', '.join(SPRINGS)}")
    return name


class ShapeMorph(Widget):
    """A container whose outline morphs between two Material shapes.

    The shape is the container's background, so children — an icon, a label —
    sit inside it exactly as they would inside a Card. ``progress`` is what
    moves: change it on any update and the renderer springs from the old shape
    to the new one instead of snapping.

    ``rotation`` turns the shape as it morphs, which is how Material makes a
    morph read as a turn as well as a reshape (a 90° rotation on a cookie
    shape lands its points exactly where a circle's were).

    One name is a shape — ``ShapeMorph(Shapes.COOKIE_9)`` draws a cookie, and
    can morph away from it later; two names are the morph itself.
    """

    _widget_type = "ShapeMorph"

    def __init__(
        self,
        from_shape: str = "circle",
        to_shape: Optional[str] = None,
        *,
        progress: float = 0.0,
        rotation: float = 0.0,
        spring: Optional[str] = None,
        bg: Optional[str] = None,
        child: Optional[Widget] = None,
        children: Optional[list] = None,
        size: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        padding: Optional[float] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible,
                         **kwargs)
        self.from_shape = Shapes.normalize(from_shape)
        # One name is a shape; two are a morph between them.
        self.to_shape = Shapes.normalize(
            from_shape if to_shape is None else to_shape)
        self.progress = max(0.0, min(1.0, float(progress)))
        self.rotation = float(rotation)
        self.spring = _spring(spring)
        if bg:
            self.style["bg"] = bg
        # A shape is a background, so the box has to have a size to draw into.
        for name, value in (("width", width), ("height", height),
                            ("padding", padding)):
            if value is not None:
                self.style[name] = value
        if size is not None:
            self.style.setdefault("width", size)
            self.style.setdefault("height", size)
        self.children = []
        if child is not None:
            self.children.append(child)
        self.children.extend(children or [])

    def _serialise_props(self) -> dict:
        return {
            "from": self.from_shape,
            "to": self.to_shape,
            "progress": self.progress,
            "rotation": self.rotation,
            "spring": self.spring,
        }


__all__ = ["SHAPES", "SPRINGS", "DEFAULT_SPRING", "Shapes", "ShapeMorph"]
