"""
Animations and transitions.

Pydrud animates the way Flutter does: you describe the *end state* and the
renderer interpolates.  When a patch arrives for a widget carrying an
``animation`` style, ``ViewFactory`` runs a ``ValueAnimator``/``ViewPropertyAnimator``
towards the new values instead of snapping to them — so a counter badge
growing from 24dp to 32dp, or a card fading in, costs you one keyword
argument rather than a listener.

Three levels are available:

* :class:`Animation` — the spec (duration, curve, delay) attachable to *any*
  widget via ``widget.animate(...)``;
* implicit widgets — :class:`AnimatedContainer`, :class:`AnimatedOpacity`,
  :class:`AnimatedScale`, :class:`AnimatedRotation`, :class:`AnimatedSwitcher`;
* entrance effects — :class:`FadeIn`, :class:`SlideIn`, :class:`ScaleIn`,
  which play once when the view is created.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Union

from pydrud.widgets.base import Widget

#: Interpolators supported by the Android renderer.
CURVES = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "bounce",
    "overshoot",
    "anticipate",
    "decelerate",
    "accelerate",
)


class Animation:
    """A reusable animation specification."""

    def __init__(self, duration: int = 250, *, curve: str = "ease_in_out",
                 delay: int = 0, repeat: int = 0, reverse: bool = False):
        if curve not in CURVES:
            raise ValueError(f"Unknown curve {curve!r}; expected one of {CURVES}")
        if duration < 0 or delay < 0:
            raise ValueError("Animation duration/delay must be >= 0")
        self.duration = int(duration)
        self.curve = curve
        self.delay = int(delay)
        self.repeat = int(repeat)
        self.reverse = bool(reverse)

    def to_dict(self) -> dict:
        d = {"duration": self.duration, "curve": self.curve}
        if self.delay:
            d["delay"] = self.delay
        if self.repeat:
            d["repeat"] = self.repeat
        if self.reverse:
            d["reverse"] = True
        return d

    # Handy presets -------------------------------------------------------

    @classmethod
    def fast(cls) -> "Animation":
        return cls(150, curve="ease_out")

    @classmethod
    def normal(cls) -> "Animation":
        return cls(250, curve="ease_in_out")

    @classmethod
    def slow(cls) -> "Animation":
        return cls(450, curve="ease_in_out")

    @classmethod
    def springy(cls) -> "Animation":
        return cls(400, curve="overshoot")

    def __repr__(self) -> str:
        return f"Animation({self.duration}ms, {self.curve})"


def _spec(animation: Union[Animation, int, dict, None],
          default_ms: int = 250) -> dict:
    if animation is None:
        return Animation(default_ms).to_dict()
    if isinstance(animation, Animation):
        return animation.to_dict()
    if isinstance(animation, (int, float)):
        return Animation(int(animation)).to_dict()
    if isinstance(animation, dict):
        return dict(animation)
    raise TypeError("animation must be an Animation, milliseconds or dict")


class _Animated(Widget):
    """Base for implicit-animation wrappers."""

    def __init__(self, *, child: Optional[Widget] = None,
                 animation: Union[Animation, int, dict, None] = None,
                 on_end: Optional[Callable] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        if child is not None:
            self.children = [child]
        self.animation = _spec(animation)
        self.style["animation"] = self.animation
        if on_end is not None:
            self.event_handlers["animation_end"] = on_end

    @property
    def duration(self) -> int:
        return int(self.animation.get("duration", 0))


class AnimatedContainer(_Animated):
    """A Container whose size, colour, padding and radius animate on change."""

    _widget_type = "AnimatedContainer"

    def __init__(self, *, child: Optional[Widget] = None,
                 width: Optional[Union[float, str]] = None,
                 height: Optional[Union[float, str]] = None,
                 bg: Optional[str] = None,
                 border_radius: Optional[float] = None,
                 padding: Optional[float] = None,
                 opacity: Optional[float] = None,
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        for name, value in (("width", width), ("height", height),
                            ("bg", bg), ("borderRadius", border_radius),
                            ("padding", padding), ("opacity", opacity)):
            if value is not None:
                self.style[name] = value

    def _serialise_props(self) -> dict:
        return {**self._extra, "animated": sorted(
            k for k in self.style
            if k in ("width", "height", "bg", "borderRadius", "padding", "opacity"))}


class AnimatedOpacity(_Animated):
    """Fades its child to ``opacity`` whenever the value changes."""

    _widget_type = "AnimatedOpacity"

    def __init__(self, opacity: float = 1.0, *, child: Optional[Widget] = None,
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        self.opacity = max(0.0, min(float(opacity), 1.0))
        self.style["opacity"] = self.opacity

    def _serialise_props(self) -> dict:
        return {**self._extra, "opacity": self.opacity}


class AnimatedScale(_Animated):
    """Scales its child (1.0 = natural size)."""

    _widget_type = "AnimatedScale"

    def __init__(self, scale: float = 1.0, *, child: Optional[Widget] = None,
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        self.scale = max(0.0, float(scale))
        self.style["scale"] = self.scale

    def _serialise_props(self) -> dict:
        return {**self._extra, "scale": self.scale}


class AnimatedRotation(_Animated):
    """Rotates its child to ``degrees``."""

    _widget_type = "AnimatedRotation"

    def __init__(self, degrees: float = 0, *, child: Optional[Widget] = None,
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        self.degrees = float(degrees)
        self.style["rotation"] = self.degrees

    def _serialise_props(self) -> dict:
        return {**self._extra, "degrees": self.degrees}


class AnimatedSwitcher(_Animated):
    """Cross-fades between children when the child's key changes.

    Ideal for "loading → content" and tab bodies::

        AnimatedSwitcher(child=Spinner() if loading else Content())
    """

    _widget_type = "AnimatedSwitcher"

    TRANSITIONS = ("fade", "slide_up", "slide_down", "slide_left",
                   "slide_right", "scale")

    def __init__(self, *, child: Optional[Widget] = None,
                 transition: str = "fade",
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        if transition not in self.TRANSITIONS:
            raise ValueError(
                f"AnimatedSwitcher transition must be one of {self.TRANSITIONS}")
        self.transition = transition

    @property
    def child_key(self) -> Optional[str]:
        return self.children[0].key if self.children else None

    def _serialise_props(self) -> dict:
        return {**self._extra, "transition": self.transition,
                "childKey": self.child_key}


class _Entrance(_Animated):
    """Base for one-shot entrance animations."""

    effect = "fade"

    def _serialise_props(self) -> dict:
        return {**self._extra, "effect": self.effect, "once": True}


class FadeIn(_Entrance):
    """Fades the child in when it first appears."""

    _widget_type = "FadeIn"
    effect = "fade"


class ScaleIn(_Entrance):
    """Pops the child in from 80% scale."""

    _widget_type = "ScaleIn"
    effect = "scale"


class SlideIn(_Entrance):
    """Slides the child in from an edge."""

    _widget_type = "SlideIn"
    effect = "slide"

    def __init__(self, *, child: Optional[Widget] = None, direction: str = "up",
                 distance: float = 24,
                 animation: Union[Animation, int, dict, None] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(child=child, animation=animation, key=key, **kwargs)
        if direction not in ("up", "down", "left", "right"):
            raise ValueError("SlideIn direction must be up/down/left/right")
        self.direction = direction
        self.distance = float(distance)

    def _serialise_props(self) -> dict:
        return {**super()._serialise_props(),
                "direction": self.direction, "distance": self.distance}


class Hero(Widget):
    """Marks a widget as a shared element across a route transition.

    Give the same ``tag`` to a thumbnail on the list screen and the full
    image on the detail screen and Android animates between them.
    """

    _widget_type = "Hero"

    def __init__(self, tag: str, *, child: Optional[Widget] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        if not tag:
            raise ValueError("Hero requires a non-empty tag")
        self.tag = str(tag)
        if child is not None:
            self.children = [child]

    def _serialise_props(self) -> dict:
        return {**self._extra, "tag": self.tag}


def animate(widget: Widget, animation: Union[Animation, int, dict, None] = None,
            **properties: Any) -> Widget:
    """Attach an animation spec (and optional target style) to any widget.

    ``animate(card, 300, opacity=1.0)`` makes the renderer tween every future
    change of the listed properties instead of applying them instantly.
    """
    widget.style["animation"] = _spec(animation)
    widget.style.update(properties)
    return widget


# Make it available as a method on every widget — ergonomics matter.
Widget.animate = lambda self, animation=None, **props: animate(  # type: ignore[attr-defined]
    self, animation, **props)
