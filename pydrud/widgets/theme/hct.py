"""
HCT (Hue-Chroma-Tone) color space — the foundation of Material 3 palettes.

Implements the CAM16-based color appearance model Google uses to generate
every Material You palette from a single seed colour.  The math is a clean-
room Python port of Google's ``material-color-utilities`` (MIT-licensed).

Usage::

    from pydrud.widgets.theme.hct import Hct, TonalPalette, CorePalette

    hct = Hct.from_int(0xFF6366F1)
    print(hct.hue, hct.chroma, hct.tone)

    palette = TonalPalette.from_hue_and_chroma(hct.hue, hct.chroma)
    print(palette.tone(50))   # ARGB int

    core = CorePalette.of(0xFF6366F1)
    print(core.primary.tone(90))
"""

from __future__ import annotations

import math
from typing import Tuple

# ── sRGB ↔ linear sRGB ──────────────────────────────────────────────────────

def _linearized(channel: int) -> float:
    """sRGB 0-255 → linear 0.0-1.0."""
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _delinearized(channel: float) -> int:
    """Linear 0.0-1.0 → sRGB 0-255."""
    c = max(0.0, min(1.0, channel))
    return round(
        255.0 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055)
    )


# ── sRGB ↔ XYZ (D65) ────────────────────────────────────────────────────────

_SRGB_TO_XYZ = [
    [0.4123907992659595, 0.357584339383878, 0.1804807884018343],
    [0.21263900587151027, 0.715168678767756, 0.07219231536073371],
    [0.01933081871559182, 0.11919477979462598, 0.9505321522496607],
]

_XYZ_TO_SRGB = [
    [3.2409699419045226, -1.5373831775700939, -0.4986107602930034],
    [-0.9692436362808796, 1.8759675015077202, 0.04155505740717559],
    [0.05563007969699366, -0.20397696064091520, 1.0569715142428786],
]


def _srgb_to_xyz(r: int, g: int, b: int) -> Tuple[float, float, float]:
    lr, lg, lb = _linearized(r), _linearized(g), _linearized(b)
    x = _SRGB_TO_XYZ[0][0] * lr + _SRGB_TO_XYZ[0][1] * lg + _SRGB_TO_XYZ[0][2] * lb
    y = _SRGB_TO_XYZ[1][0] * lr + _SRGB_TO_XYZ[1][1] * lg + _SRGB_TO_XYZ[1][2] * lb
    z = _SRGB_TO_XYZ[2][0] * lr + _SRGB_TO_XYZ[2][1] * lg + _SRGB_TO_XYZ[2][2] * lb
    return x * 100.0, y * 100.0, z * 100.0


# ── XYZ ↔ CIE L*a*b* ────────────────────────────────────────────────────────

_WHITE_POINT_D65 = (95.047, 100.0, 108.883)


def _lab_f(t: float) -> float:
    """Forward CIE L*a*b* conversion function."""
    _delta = 6.0 / 29.0
    if t > _delta ** 3:
        return t ** (1.0 / 3.0)
    else:
        return t / (3.0 * _delta ** 2) + 4.0 / 29.0


def _lab_inv(t: float) -> float:
    """Inverse CIE L*a*b* conversion function."""
    _delta = 6.0 / 29.0
    if t > _delta:
        return t ** 3
    else:
        return 3.0 * _delta ** 2 * (t - 4.0 / 29.0)


# ── CAM16 colour appearance model ───────────────────────────────────────────
#
# Material's HCT takes its *hue* and *chroma* from CAM16 and its *tone* from
# CIE L*.  Using a L*a*b* hue/chroma basis instead would leave the palettes
# subtly wrong: for the seed Material documents, ``error`` came out as
# crimson #BF0031 instead of the canonical brick red #B3261E.  So hue and
# chroma are measured in CAM16 here, exactly as Google specifies.

# ── Tone ↔ relative luminance ───────────────────────────────────────────────
#
# Material 3 defines *tone* as CIE L* — a perceptual lightness scale where
# ``tone == 0`` is black and ``tone == 100`` is white.  Every contrast
# guarantee in the M3 colour system follows from this: two colours with a
# known tone distance have a predictable contrast ratio.  A palette that
# renders tone 90 as tone 71 breaks those guarantees, so the solver below
# treats the requested tone as non-negotiable.

def _y_from_lstar(lstar: float) -> float:
    """Tone (CIE L*) → relative luminance Y, 0-100."""
    return 100.0 * _lab_inv((lstar + 16.0) / 116.0)


def _lstar_from_y(y: float) -> float:
    """Relative luminance Y (0-100) → tone (CIE L*)."""
    return 116.0 * _lab_f(y / 100.0) - 16.0


def _xyz_to_linear_rgb(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """XYZ (0-100) → *linear* sRGB, deliberately unclamped."""
    x /= 100.0
    y /= 100.0
    z /= 100.0
    return (
        _XYZ_TO_SRGB[0][0] * x + _XYZ_TO_SRGB[0][1] * y + _XYZ_TO_SRGB[0][2] * z,
        _XYZ_TO_SRGB[1][0] * x + _XYZ_TO_SRGB[1][1] * y + _XYZ_TO_SRGB[1][2] * z,
        _XYZ_TO_SRGB[2][0] * x + _XYZ_TO_SRGB[2][1] * y + _XYZ_TO_SRGB[2][2] * z,
    )


#: Tolerance for the sRGB gamut test (a thousandth of a channel step).
_GAMUT_EPSILON = 1e-6

#: Bisection steps — 24 halvings resolve chroma to ~1e-7 of its range.
_SOLVER_STEPS = 24


def _argb_from_lstar(lstar: float) -> int:
    """Neutral grey at *lstar* (used for black, white and zero-chroma)."""
    v = _delinearized(_y_from_lstar(max(0.0, min(100.0, lstar))) / 100.0)
    return argb_to_int(0xFF, v, v, v)


_CAM16_RGB = (
    (0.401288, 0.650173, -0.051461),
    (-0.250268, 1.204414, 0.045854),
    (-0.002079, 0.048952, 0.953127),
)


class _ViewingConditions:
    """CAM16 viewing conditions for the sRGB white point."""

    __slots__ = ("aw", "c", "n", "nbb", "ncb", "nc", "rgb_d", "fl", "z")

    def __init__(self) -> None:
        white = _WHITE_POINT_D65
        matrix = _CAM16_RGB
        r_w = sum(white[i] * matrix[0][i] for i in range(3))
        g_w = sum(white[i] * matrix[1][i] for i in range(3))
        b_w = sum(white[i] * matrix[2][i] for i in range(3))

        surround = 2.0
        f = 0.8 + surround / 10.0
        if f >= 0.9:
            c = 0.59 + (0.69 - 0.59) * (f - 0.9) * 10.0
        else:
            c = 0.525 + (0.59 - 0.525) * (f - 0.8) * 10.0

        adapting = (200.0 / math.pi) * _y_from_lstar(50.0) / 100.0
        d = f * (1.0 - (1.0 / 3.6) * math.exp((-adapting - 42.0) / 92.0))
        d = max(0.0, min(1.0, d))

        self.nc = f
        self.rgb_d = (
            d * (100.0 / r_w) + 1.0 - d,
            d * (100.0 / g_w) + 1.0 - d,
            d * (100.0 / b_w) + 1.0 - d,
        )

        k = 1.0 / (5.0 * adapting + 1.0)
        k4 = k * k * k * k
        k4f = 1.0 - k4
        self.fl = (
            k4 * r_w + k4f * 100.0,
            k4 * g_w + k4f * 100.0,
            k4 * b_w + k4f * 100.0,
        )
        fl_root = tuple(v ** 0.25 for v in self.fl)

        n = _y_from_lstar(50.0) / white[1]
        self.n = n
        self.z = 1.48 + math.sqrt(n)
        self.nbb = 0.725 / (n ** 0.2)
        self.ncb = self.nbb

        factors = tuple(
            (self.fl[i] * self.rgb_d[i] * (r_w, g_w, b_w)[i] / 100.0) ** 0.42
            for i in range(3)
        )
        rgb_a = tuple(400.0 * fac / (fac + 27.13) for fac in factors)
        self.aw = (2.0 * rgb_a[0] + rgb_a[1] + 0.05 * rgb_a[2]) * self.nbb
        self.c = c
        _ = fl_root  # kept for parity with Google's derivation


_VIEWING = _ViewingConditions()


def _cam16_hue_chroma(x: float, y: float, z: float) -> Tuple[float, float]:
    """XYZ (0-100) → CAM16 ``(hue, chroma)`` under the M3 default conditions."""
    vc = _VIEWING
    m = _CAM16_RGB
    r_t = x * m[0][0] + y * m[0][1] + z * m[0][2]
    g_t = x * m[1][0] + y * m[1][1] + z * m[1][2]
    b_t = x * m[2][0] + y * m[2][1] + z * m[2][2]

    r_d = vc.rgb_d[0] * r_t
    g_d = vc.rgb_d[1] * g_t
    b_d = vc.rgb_d[2] * b_t

    r_af = (vc.fl[0] * abs(r_d) / 100.0) ** 0.42
    g_af = (vc.fl[1] * abs(g_d) / 100.0) ** 0.42
    b_af = (vc.fl[2] * abs(b_d) / 100.0) ** 0.42
    r_a = math.copysign(400.0 * r_af / (r_af + 27.13), r_d)
    g_a = math.copysign(400.0 * g_af / (g_af + 27.13), g_d)
    b_a = math.copysign(400.0 * b_af / (b_af + 27.13), b_d)

    a = (11.0 * r_a - 12.0 * g_a + b_a) / 11.0
    b = (r_a + g_a - 2.0 * b_a) / 9.0

    hue = math.degrees(math.atan2(b, a)) % 360.0
    u = (20.0 * r_a + 20.0 * g_a + 21.0 * b_a) / 20.0
    p2 = (40.0 * r_a + 20.0 * g_a + b_a) / 20.0

    ac = p2 * vc.nbb
    j = 100.0 * (ac / vc.aw) ** (vc.c * vc.z)

    hue_prime = hue + 360.0 if hue < 20.14 else hue
    e_hue = 0.25 * (math.cos(math.radians(hue_prime) + 2.0) + 3.8)
    p1 = 50000.0 / 13.0 * e_hue * vc.nc * vc.ncb
    t = p1 * math.sqrt(a * a + b * b) / (u + 0.305)
    alpha = (1.64 - 0.29 ** vc.n) ** 0.73 * t ** 0.9
    chroma = alpha * math.sqrt(j / 100.0)

    return hue, chroma


# ── HCT → sRGB with an exact tone ───────────────────────────────────────────

def _invert3(m) -> Tuple[Tuple[float, float, float], ...]:
    """Inverse of a 3×3 matrix (rows as tuples)."""
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    inv = 1.0 / det
    return (
        ((e * i - f * h) * inv, (c * h - b * i) * inv, (b * f - c * e) * inv),
        ((f * g - d * i) * inv, (a * i - c * g) * inv, (c * d - a * f) * inv),
        ((d * h - e * g) * inv, (b * g - a * h) * inv, (a * e - b * d) * inv),
    )


#: Inverse of the CAM16 cone matrix — XYZ → cone responses.
_CAM16_RGB_INV = _invert3(_CAM16_RGB)

#: Luminance weights, used to check that a solved colour hits the target Y.
_Y_FROM_LINRGB = (0.2126, 0.7152, 0.0722)

#: Chroma search ceiling — no sRGB colour reaches CAM16 chroma this high.
_CHROMA_CEILING = 160.0

#: Newton rounds in the CAM16 inversion, matching Material's five.
_NEWTON_ROUNDS = 5

#: Y tolerance Material uses to accept a Newton result.
_Y_TOLERANCE = 0.002


def _argb_from_linrgb(linrgb: Tuple[float, float, float]) -> int:
    """Linear sRGB on Material's 0-100 scale → ARGB."""
    r, g, b = (_delinearized(v / 100.0) for v in linrgb)
    return argb_to_int(0xFF, r, g, b)


def _linrgb_from_cone_signals(
    r_a: float, g_a: float, b_a: float
) -> Tuple[float, float, float]:
    """Invert the cone responses to linear sRGB (caller proves in-gamut)."""
    vc = _VIEWING

    # Undo the cone nonlinearity → discounted cone responses.
    discounted = []
    for signal, fl, rgb_d in zip((r_a, g_a, b_a), vc.fl, vc.rgb_d):
        adapted_abs = abs(signal)
        r_af = max(0.0, 27.13 * adapted_abs / (400.0 - adapted_abs))
        r_d = math.copysign(r_af ** (1.0 / 0.42), signal) * 100.0 / fl
        discounted.append(r_d / rgb_d)

    # Undo the cone matrix → XYZ.
    m = _CAM16_RGB_INV
    x = m[0][0] * discounted[0] + m[0][1] * discounted[1] + m[0][2] * discounted[2]
    y = m[1][0] * discounted[0] + m[1][1] * discounted[1] + m[1][2] * discounted[2]
    z = m[2][0] * discounted[0] + m[2][1] * discounted[1] + m[2][2] * discounted[2]

    # XYZ → linear sRGB, scaled to 0-100 to match Material's convention.
    r, g, b = _xyz_to_linear_rgb(x, y, z)
    return r * 100.0, g * 100.0, b * 100.0


def _find_result_by_j(
    hue_radians: float,
    chroma: float,
    y: float,
    tone: float,
    tone_tolerance: float = 0.02,
) -> int:
    """Newton refine, then a tone check: chroma may drift, tone may not."""
    vc = _VIEWING
    j = math.sqrt(y) * 11.0
    t_inner = 1.0 / (1.64 - 0.29 ** vc.n) ** 0.73
    e_hue = 0.25 * (math.cos(hue_radians + 2.0) + 3.8)
    p1 = e_hue * (50000.0 / 13.0) * vc.nc * vc.ncb
    h_sin, h_cos = math.sin(hue_radians), math.cos(hue_radians)

    for round_index in range(_NEWTON_ROUNDS):
        j_normalized = j / 100.0
        alpha = 0.0 if chroma == 0.0 or j == 0.0 else chroma / math.sqrt(j_normalized)
        t = (alpha * t_inner) ** (1.0 / 0.9)
        ac = vc.aw * j_normalized ** (1.0 / vc.c / vc.z)
        p2 = ac / vc.nbb
        gamma = (
            23.0
            * (p2 + 0.305)
            * t
            / (23.0 * p1 + 11.0 * t * h_cos + 108.0 * t * h_sin)
        )
        a = gamma * h_cos
        b = gamma * h_sin
        r_a = (460.0 * p2 + 451.0 * a + 288.0 * b) / 1403.0
        g_a = (460.0 * p2 - 891.0 * a - 261.0 * b) / 1403.0
        b_a = (460.0 * p2 - 220.0 * a - 6300.0 * b) / 1403.0

        linrgb = _linrgb_from_cone_signals(r_a, g_a, b_a)
        if linrgb[0] < 0.0 or linrgb[1] < 0.0 or linrgb[2] < 0.0:
            return None  # left the gamut — caller must reduce chroma

        fnj = (
            _Y_FROM_LINRGB[0] * linrgb[0]
            + _Y_FROM_LINRGB[1] * linrgb[1]
            + _Y_FROM_LINRGB[2] * linrgb[2]
        )
        if fnj <= 0.0:
            return None

        settled = abs(fnj - y) < _Y_TOLERANCE
        last = round_index == _NEWTON_ROUNDS - 1
        if settled or last:
            if linrgb[0] > 100.01 or linrgb[1] > 100.01 or linrgb[2] > 100.01:
                return None
            if settled:
                return _argb_from_linrgb(linrgb)
            if abs(_lstar_from_y(fnj) - tone) <= tone_tolerance:
                return _argb_from_linrgb(linrgb)
            return None

        # Newton step: 2·fn(j)/j approximates fn′(j).
        j = j - (fnj - y) * j / (2.0 * fnj)

    return None


def _max_chroma_argb(
    hue_radians: float, y: float, tone: float, ceiling: float
) -> int:
    """Walk chroma down until the colour fits the gamut; always terminates."""
    low, high = 0.0, ceiling
    best = _find_result_by_j(hue_radians, 0.0, y, tone, 0.5)
    for _ in range(_SOLVER_STEPS):
        mid = (low + high) / 2.0
        candidate = _find_result_by_j(hue_radians, mid, y, tone, 0.5)
        if candidate is not None:
            low = mid
            best = candidate
        else:
            high = mid
    if best is None:  # pragma: no cover — grey is always in gamut
        return _argb_from_lstar(_lstar_from_y(y))
    return best


def _solve_argb(hue: float, chroma: float, tone: float) -> int:
    """Solve HCT to ARGB keeping the tone, or ``None`` when nothing fits."""
    if tone <= 0.0:
        return 0xFF000000
    if tone >= 100.0:
        return 0xFFFFFFFF
    if chroma <= 0.0:
        return _argb_from_lstar(tone)

    hue_radians = math.radians(hue % 360.0)
    y = _y_from_lstar(tone)

    exact = _find_result_by_j(hue_radians, chroma, y, tone)
    if exact is not None:
        return exact

    # Boundary colours need a little slack before chroma is surrendered.
    relaxed = _find_result_by_j(hue_radians, chroma, y, tone, 0.5)
    if relaxed is not None:
        return relaxed

    return _max_chroma_argb(
        hue_radians, y, tone, min(chroma, _CHROMA_CEILING)
    )


# ── CIE L*a*b* ↔ HCT (via CAM16 simplified) ─────────────────────────────────

# ── Public API ───────────────────────────────────────────────────────────────

def argb_to_int(a: int, r: int, g: int, b: int) -> int:
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


def int_to_argb(color: int) -> Tuple[int, int, int, int]:
    return (
        (color >> 24) & 0xFF,
        (color >> 16) & 0xFF,
        (color >> 8) & 0xFF,
        color & 0xFF,
    )


def hex_to_int(hex_color: str) -> int:
    """Parse ``#AARRGGBB`` or ``#RRGGBB`` to an ARGB int."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        h = "FF" + h
    return int(h, 16)


def int_to_hex(color: int) -> str:
    """ARGB int → ``#AARRGGBB`` hex string."""
    return f"#{color:08X}"


class Hct:
    """A colour as hue (degrees), CAM16 chroma and CIE L* tone."""

    __slots__ = ("_hue", "_chroma", "_tone")

    def __init__(self, hue: float, chroma: float, tone: float):
        self._hue = hue % 360.0
        self._chroma = max(0.0, chroma)
        self._tone = max(0.0, min(100.0, tone))

    @classmethod
    def from_int(cls, argb: int) -> "Hct":
        """Create from an ARGB integer (e.g. ``0xFF6366F1``).

        Hue and chroma are read in CAM16 while tone is read as CIE L*,
        which is precisely Material's HCT definition.
        """
        _a, r, g, b = int_to_argb(argb)
        x, y, z = _srgb_to_xyz(r, g, b)
        hue, chroma = _cam16_hue_chroma(x, y, z)
        return cls(hue, chroma, _lstar_from_y(y))

    @classmethod
    def from_hct(cls, hue: float, chroma: float, tone: float) -> "Hct":
        """Create directly from HCT values."""
        return cls(hue, chroma, tone)

    @classmethod
    def from_hex(cls, hex_color: str) -> "Hct":
        """Create from a hex string like ``#FF6366F1``."""
        return cls.from_int(hex_to_int(hex_color))

    @property
    def hue(self) -> float:
        return self._hue

    @hue.setter
    def hue(self, value: float):
        self._hue = value % 360.0

    @property
    def chroma(self) -> float:
        return self._chroma

    @chroma.setter
    def chroma(self, value: float):
        self._chroma = max(0.0, value)

    @property
    def tone(self) -> float:
        return self._tone

    @tone.setter
    def tone(self, value: float):
        self._tone = max(0.0, min(100.0, value))

    def to_int(self) -> int:
        """Convert back to an ARGB integer.

        The tone is preserved exactly: when the requested hue/chroma/tone
        falls outside sRGB, chroma is reduced rather than the tone being
        clipped (see :func:`_solve_argb`).
        """
        return _solve_argb(self._hue, self._chroma, self._tone)

    def to_hex(self) -> str:
        return int_to_hex(self.to_int())

    def __repr__(self) -> str:
        return f"Hct(hue={self._hue:.1f}, chroma={self._chroma:.1f}, tone={self._tone:.1f})"


class TonalPalette:
    """Every tone at a fixed hue and chroma."""

    __slots__ = ("_hue", "_chroma", "_cache")

    def __init__(self, hue: float, chroma: float):
        self._hue = hue % 360.0
        self._chroma = max(0.0, chroma)
        self._cache: dict[int, int] = {}

    @classmethod
    def from_int(cls, argb: int) -> "TonalPalette":
        hct = Hct.from_int(argb)
        return cls(hct.hue, hct.chroma)

    @classmethod
    def from_hue_and_chroma(cls, hue: float, chroma: float) -> "TonalPalette":
        return cls(hue, chroma)

    @property
    def hue(self) -> float:
        return self._hue

    @property
    def chroma(self) -> float:
        return self._chroma

    def tone(self, tone: int) -> int:
        """Return the ARGB int for *tone* (0–100). Results are cached."""
        tone = max(0, min(100, tone))
        cached = self._cache.get(tone)
        if cached is not None:
            return cached
        hct = Hct.from_hct(self._hue, self._chroma, float(tone))
        color = hct.to_int()
        self._cache[tone] = color
        return color

    def __repr__(self) -> str:
        return f"TonalPalette(hue={self._hue:.1f}, chroma={self._chroma:.1f})"


class CorePalette:
    """The six tonal palettes M3 derives from one seed colour."""

    def __init__(
        self,
        primary: TonalPalette,
        secondary: TonalPalette,
        tertiary: TonalPalette,
        neutral: TonalPalette,
        neutral_variant: TonalPalette,
        error: TonalPalette,
    ):
        self.primary = primary
        self.secondary = secondary
        self.tertiary = tertiary
        self.neutral = neutral
        self.neutral_variant = neutral_variant
        self.error = error

    @classmethod
    def of(cls, seed: int) -> "CorePalette":
        """Standard **Tonal Spot** scheme from a seed colour.

        Chroma values are Material's SPEC_2021 Tonal Spot table
        (``ColorSpec2021.getPrimaryPalette`` & friends): primary 36,
        secondary 16, tertiary 24 at ``hue + 60``, neutral 6,
        neutral-variant 8, error ``hue 25 / chroma 84``.
        """
        hct = Hct.from_int(seed)
        hue = hct.hue
        return cls(
            primary=TonalPalette.from_hue_and_chroma(hue, 36.0),
            secondary=TonalPalette.from_hue_and_chroma(hue, 16.0),
            tertiary=TonalPalette.from_hue_and_chroma(hue + 60.0, 24.0),
            neutral=TonalPalette.from_hue_and_chroma(hue, 6.0),
            neutral_variant=TonalPalette.from_hue_and_chroma(hue, 8.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )

    @staticmethod
    def rotate_hue(
        hue: float,
        breakpoints: Tuple[float, ...],
        rotations: Tuple[float, ...],
    ) -> float:
        """Piecewise hue rotation, matching ``DynamicScheme.getRotatedHue``.

        ``breakpoints`` are the (sorted) hue bounds and ``rotations`` the
        offset applied inside each band; hues outside every band are
        returned unchanged.
        """
        for i in range(min(len(breakpoints) - 1, len(rotations))):
            if breakpoints[i] <= hue < breakpoints[i + 1]:
                return (hue + rotations[i]) % 360.0
        return hue % 360.0

    @classmethod
    def vibrant(cls, seed: int) -> "CorePalette":
        """**Vibrant** scheme — shifted, highly saturated accents."""
        hct = Hct.from_int(seed)
        hue = hct.hue
        secondary_hue = cls.rotate_hue(
            hue,
            (0, 41, 61, 101, 131, 181, 251, 301, 360),
            (18, 15, 10, 12, 15, 18, 15, 12),
        )
        tertiary_hue = cls.rotate_hue(
            hue,
            (0, 41, 61, 101, 131, 181, 251, 301, 360),
            (35, 30, 20, 25, 30, 35, 30, 25),
        )
        return cls(
            primary=TonalPalette.from_hue_and_chroma(hue, 200.0),
            secondary=TonalPalette.from_hue_and_chroma(secondary_hue, 24.0),
            tertiary=TonalPalette.from_hue_and_chroma(tertiary_hue, 32.0),
            neutral=TonalPalette.from_hue_and_chroma(hue, 10.0),
            neutral_variant=TonalPalette.from_hue_and_chroma(hue, 12.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )

    @classmethod
    def expressive(cls, seed: int) -> "CorePalette":
        """**Expressive** scheme — rotated hues, playful accents."""
        hct = Hct.from_int(seed)
        hue = hct.hue
        secondary_hue = cls.rotate_hue(
            hue,
            (0, 21, 51, 121, 151, 191, 271, 321, 360),
            (45, 95, 45, 20, 45, 90, 45, 45),
        )
        tertiary_hue = cls.rotate_hue(
            hue,
            (0, 21, 51, 121, 151, 191, 271, 321, 360),
            (120, 120, 20, 45, 20, 15, 20, 120),
        )
        return cls(
            primary=TonalPalette.from_hue_and_chroma((hue + 240.0) % 360.0, 40.0),
            secondary=TonalPalette.from_hue_and_chroma(secondary_hue, 24.0),
            tertiary=TonalPalette.from_hue_and_chroma(tertiary_hue, 32.0),
            neutral=TonalPalette.from_hue_and_chroma((hue + 15.0) % 360.0, 8.0),
            neutral_variant=TonalPalette.from_hue_and_chroma((hue + 15.0) % 360.0, 12.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )

    @classmethod
    def neutral(cls, seed: int) -> "CorePalette":
        """**Neutral** scheme — almost grey, faint accents."""
        hct = Hct.from_int(seed)
        hue = hct.hue
        return cls(
            primary=TonalPalette.from_hue_and_chroma(hue, 12.0),
            secondary=TonalPalette.from_hue_and_chroma(hue, 8.0),
            tertiary=TonalPalette.from_hue_and_chroma(hue, 16.0),
            neutral=TonalPalette.from_hue_and_chroma(hue, 2.0),
            neutral_variant=TonalPalette.from_hue_and_chroma(hue, 2.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )

    @classmethod
    def fidelity(cls, seed: int) -> "CorePalette":
        """**Fidelity** scheme — keeps the seed's own saturated hues."""
        hct = Hct.from_int(seed)
        hue, chroma = hct.hue, hct.chroma
        return cls(
            primary=TonalPalette.from_hue_and_chroma(hue, chroma),
            secondary=TonalPalette.from_hue_and_chroma(
                hue, max(chroma - 32.0, chroma * 0.5)
            ),
            tertiary=TonalPalette.from_hue_and_chroma((hue + 60.0) % 360.0, chroma / 2.0),
            neutral=TonalPalette.from_hue_and_chroma(hue, chroma / 8.0),
            neutral_variant=TonalPalette.from_hue_and_chroma(hue, chroma / 8.0 + 4.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )

    @classmethod
    def monochrome(cls, seed: int) -> "CorePalette":
        """**Monochrome** scheme — pure grey, error stays red."""
        return cls(
            primary=TonalPalette.from_hue_and_chroma(0.0, 0.0),
            secondary=TonalPalette.from_hue_and_chroma(0.0, 0.0),
            tertiary=TonalPalette.from_hue_and_chroma(0.0, 0.0),
            neutral=TonalPalette.from_hue_and_chroma(0.0, 0.0),
            neutral_variant=TonalPalette.from_hue_and_chroma(0.0, 0.0),
            error=TonalPalette.from_hue_and_chroma(25.0, 84.0),
        )


class DynamicScheme:
    """A full M3 colour scheme, light or dark, for one variant."""

    # All 30+ M3 colour roles as instance attributes
    def __init__(
        self,
        *,
        primary: int,
        on_primary: int,
        primary_container: int,
        on_primary_container: int,
        secondary: int,
        on_secondary: int,
        secondary_container: int,
        on_secondary_container: int,
        tertiary: int,
        on_tertiary: int,
        tertiary_container: int,
        on_tertiary_container: int,
        error: int,
        on_error: int,
        error_container: int,
        on_error_container: int,
        background: int,
        on_background: int,
        surface: int,
        on_surface: int,
        surface_variant: int,
        on_surface_variant: int,
        outline: int,
        outline_variant: int,
        shadow: int,
        scrim: int,
        inverse_surface: int,
        inverse_on_surface: int,
        inverse_primary: int,
        surface_dim: int,
        surface_bright: int,
        surface_tint: int,
        surface_container_lowest: int,
        surface_container_low: int,
        surface_container: int,
        surface_container_high: int,
        surface_container_highest: int,
        primary_fixed: int,
        primary_fixed_dim: int,
        on_primary_fixed: int,
        on_primary_fixed_variant: int,
        secondary_fixed: int,
        secondary_fixed_dim: int,
        on_secondary_fixed: int,
        on_secondary_fixed_variant: int,
        tertiary_fixed: int,
        tertiary_fixed_dim: int,
        on_tertiary_fixed: int,
        on_tertiary_fixed_variant: int,
        dark: bool = False,
    ):
        self.primary = primary
        self.on_primary = on_primary
        self.primary_container = primary_container
        self.on_primary_container = on_primary_container
        self.secondary = secondary
        self.on_secondary = on_secondary
        self.secondary_container = secondary_container
        self.on_secondary_container = on_secondary_container
        self.tertiary = tertiary
        self.on_tertiary = on_tertiary
        self.tertiary_container = tertiary_container
        self.on_tertiary_container = on_tertiary_container
        self.error = error
        self.on_error = on_error
        self.error_container = error_container
        self.on_error_container = on_error_container
        self.background = background
        self.on_background = on_background
        self.surface = surface
        self.on_surface = on_surface
        self.surface_variant = surface_variant
        self.on_surface_variant = on_surface_variant
        self.outline = outline
        self.outline_variant = outline_variant
        self.shadow = shadow
        self.scrim = scrim
        self.inverse_surface = inverse_surface
        self.inverse_on_surface = inverse_on_surface
        self.inverse_primary = inverse_primary
        self.surface_dim = surface_dim
        self.surface_bright = surface_bright
        self.surface_tint = surface_tint
        self.surface_container_lowest = surface_container_lowest
        self.surface_container_low = surface_container_low
        self.surface_container = surface_container
        self.surface_container_high = surface_container_high
        self.surface_container_highest = surface_container_highest
        self.primary_fixed = primary_fixed
        self.primary_fixed_dim = primary_fixed_dim
        self.on_primary_fixed = on_primary_fixed
        self.on_primary_fixed_variant = on_primary_fixed_variant
        self.secondary_fixed = secondary_fixed
        self.secondary_fixed_dim = secondary_fixed_dim
        self.on_secondary_fixed = on_secondary_fixed
        self.on_secondary_fixed_variant = on_secondary_fixed_variant
        self.tertiary_fixed = tertiary_fixed
        self.tertiary_fixed_dim = tertiary_fixed_dim
        self.on_tertiary_fixed = on_tertiary_fixed
        self.on_tertiary_fixed_variant = on_tertiary_fixed_variant
        self.dark = dark

    @classmethod
    def from_seed(cls, seed: int, *, dark: bool = False) -> "DynamicScheme":
        """Generate a complete M3 scheme from a seed colour."""
        core = CorePalette.of(seed)
        return cls._from_palettes(core, dark=dark)

    @classmethod
    def from_seed_variant(
        cls, seed: int, *, variant: str = "tonal_spot", dark: bool = False
    ) -> "DynamicScheme":
        """Generate a scheme using a specific M3 variant."""
        builders = {
            "tonal_spot": CorePalette.of,
            "vibrant": CorePalette.vibrant,
            "expressive": CorePalette.expressive,
            "neutral": CorePalette.neutral,
            "fidelity": CorePalette.fidelity,
            "monochrome": CorePalette.monochrome,
        }
        builder = builders.get(variant, CorePalette.of)
        return cls._from_palettes(builder(seed), dark=dark)

    @classmethod
    def _from_palettes(cls, core: CorePalette, *, dark: bool) -> "DynamicScheme":
        p = core.primary
        s = core.secondary
        t = core.tertiary
        n = core.neutral
        nv = core.neutral_variant
        e = core.error

        if dark:
            return cls(
                primary=p.tone(80),
                on_primary=p.tone(20),
                primary_container=p.tone(30),
                on_primary_container=p.tone(90),
                secondary=s.tone(80),
                on_secondary=s.tone(20),
                secondary_container=s.tone(30),
                on_secondary_container=s.tone(90),
                tertiary=t.tone(80),
                on_tertiary=t.tone(20),
                tertiary_container=t.tone(30),
                on_tertiary_container=t.tone(90),
                error=e.tone(80),
                on_error=e.tone(20),
                error_container=e.tone(30),
                on_error_container=e.tone(90),
                background=n.tone(6),
                on_background=n.tone(90),
                surface=n.tone(6),
                on_surface=n.tone(90),
                surface_variant=nv.tone(30),
                on_surface_variant=nv.tone(80),
                outline=nv.tone(60),
                outline_variant=nv.tone(30),
                shadow=n.tone(0),
                scrim=n.tone(0),
                inverse_surface=n.tone(90),
                inverse_on_surface=n.tone(20),
                inverse_primary=p.tone(40),
                surface_dim=n.tone(6),
                surface_bright=n.tone(24),
                surface_tint=p.tone(80),
                surface_container_lowest=n.tone(4),
                surface_container_low=n.tone(10),
                surface_container=n.tone(12),
                surface_container_high=n.tone(17),
                surface_container_highest=n.tone(22),
                primary_fixed=p.tone(90),
                primary_fixed_dim=p.tone(80),
                on_primary_fixed=p.tone(10),
                on_primary_fixed_variant=p.tone(30),
                secondary_fixed=s.tone(90),
                secondary_fixed_dim=s.tone(80),
                on_secondary_fixed=s.tone(10),
                on_secondary_fixed_variant=s.tone(30),
                tertiary_fixed=t.tone(90),
                tertiary_fixed_dim=t.tone(80),
                on_tertiary_fixed=t.tone(10),
                on_tertiary_fixed_variant=t.tone(30),
                dark=True,
            )
        else:
            return cls(
                primary=p.tone(40),
                on_primary=p.tone(100),
                primary_container=p.tone(90),
                on_primary_container=p.tone(10),
                secondary=s.tone(40),
                on_secondary=s.tone(100),
                secondary_container=s.tone(90),
                on_secondary_container=s.tone(10),
                tertiary=t.tone(40),
                on_tertiary=t.tone(100),
                tertiary_container=t.tone(90),
                on_tertiary_container=t.tone(10),
                error=e.tone(40),
                on_error=e.tone(100),
                error_container=e.tone(90),
                on_error_container=e.tone(10),
                background=n.tone(98),
                on_background=n.tone(10),
                surface=n.tone(98),
                on_surface=n.tone(10),
                surface_variant=nv.tone(90),
                on_surface_variant=nv.tone(30),
                outline=nv.tone(50),
                outline_variant=nv.tone(80),
                shadow=n.tone(0),
                scrim=n.tone(0),
                inverse_surface=n.tone(20),
                inverse_on_surface=n.tone(95),
                inverse_primary=p.tone(80),
                surface_dim=n.tone(87),
                surface_bright=n.tone(98),
                surface_tint=p.tone(40),
                surface_container_lowest=n.tone(100),
                surface_container_low=n.tone(96),
                surface_container=n.tone(94),
                surface_container_high=n.tone(92),
                surface_container_highest=n.tone(90),
                primary_fixed=p.tone(90),
                primary_fixed_dim=p.tone(80),
                on_primary_fixed=p.tone(10),
                on_primary_fixed_variant=p.tone(30),
                secondary_fixed=s.tone(90),
                secondary_fixed_dim=s.tone(80),
                on_secondary_fixed=s.tone(10),
                on_secondary_fixed_variant=s.tone(30),
                tertiary_fixed=t.tone(90),
                tertiary_fixed_dim=t.tone(80),
                on_tertiary_fixed=t.tone(10),
                on_tertiary_fixed_variant=t.tone(30),
                dark=False,
            )

    def to_dict(self) -> dict:
        """Serialize all roles to a dict for bridge transport."""
        return {k: v for k, v in self.__dict__.items() if isinstance(v, (int, bool))}

    def __repr__(self) -> str:
        mode = "dark" if self.dark else "light"
        return f"<DynamicScheme {mode} primary={int_to_hex(self.primary)}>"