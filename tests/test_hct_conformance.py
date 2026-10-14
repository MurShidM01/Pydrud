"""HCT colour science — conformance with Material's own algorithms.

GAP #0 from the Material 3 audit.  Pydrud's palette generator had two
defects that together broke the colour system at its foundation:

1. ``CorePalette.of`` used invented chroma constants (``max(chroma, 48)``,
   ``primary * 0.66``, ``primary + 16``) instead of Material's SPEC_2021
   Tonal Spot table, so secondary and tertiary ran 3–4x over-saturated.
2. The tone solver clipped out-of-gamut sRGB channels instead of reducing
   chroma, so the *tone* that came back was not the tone that was asked for.
   ``on_tertiary`` rendered at tone 78.65 instead of 100 and
   ``on_error`` at 81.89 instead of 100 — which produced two outright
   contrast failures (2.82:1 and 3.64:1 against the required 4.5:1).

These tests pin the fix: tone exactness, round-trip fidelity, Material's
palette chroma table, and the contrast guarantees that follow from it.
"""

from __future__ import annotations

import unittest

from pydrud.widgets.theme.colors import ColorScheme, Colors
from pydrud.widgets.theme.hct import (
    CorePalette,
    DynamicScheme,
    Hct,
    _solve_argb,
)

#: Material's SPEC_2021 Tonal Spot palette chromas, straight from
#: ``ColorSpec2021.getPrimaryPalette`` and friends.
TONAL_SPOT_CHROMAS = {
    "primary": 36.0,
    "secondary": 16.0,
    "tertiary": 24.0,
    "neutral": 6.0,
    "neutral_variant": 8.0,
    "error": 84.0,
}

#: Material's fixed error hue.
ERROR_HUE = 25.0


class TestCam16ColorSpace(unittest.TestCase):
    """Tone is CIE L*; hue and chroma come from CAM16."""

    def test_greys_have_no_chroma(self):
        for value in ("#FF000000", "#FF808080", "#FFFFFFFF"):
            hct = Hct.from_int(int(value[1:], 16))
            self.assertLess(hct.chroma, 2.5, f"{value} should be near-neutral")

    def test_tone_matchles_lstar_endpoints(self):
        self.assertAlmostEqual(Hct.from_int(0xFF000000).tone, 0.0, places=2)
        self.assertAlmostEqual(Hct.from_int(0xFFFFFFFF).tone, 100.0, places=2)

    def _round_trip_delta(self, probe: int) -> int:
        hct = Hct.from_int(probe)
        back = _solve_argb(hct.hue, hct.chroma, hct.tone)
        return max(
            abs(((back >> shift) & 0xFF) - ((probe >> shift) & 0xFF))
            for shift in (16, 8, 0)
        )

    def test_round_trip_is_lossless(self):
        """HCT → ARGB → HCT must return the colour we started with."""
        probes = (
            0xFF6750A4, 0xFF6366F1, 0xFF7D5260, 0xFFB3261E, 0xFF888888,
            0xFFE8DEF8, 0xFF21005D, 0xFF131317, 0xFFFFFFFF, 0xFF000000,
        )
        for probe in probes:
            self.assertLessEqual(
                self._round_trip_delta(probe),
                2,
                f"round trip drifted #{probe:08X}",
            )

    def test_round_trip_holds_near_the_gamut_boundary(self):
        """Saturated primaries sit exactly on the boundary.

        Recovering the last channel step there is genuinely approximate —
        every HCT implementation has this property (an independently
        maintained port misses pure green by 40 steps; Pydrud misses it by
        2).  The bound below is loose enough to be true and tight enough to
        catch a solver that has genuinely gone wrong.
        """
        for probe in (0xFFFF0000, 0xFF00FF00, 0xFF0000FF, 0xFFFFFF00):
            delta = self._round_trip_delta(probe)
            self.assertLessEqual(
                delta, 12, f"round trip drifted #{probe:08X} by {delta}"
            )

    def test_tone_is_never_sacrificed(self):
        """Out-of-gamut requests give up chroma, never tone.

        This is the property the whole palette rests on: two colours a
        known number of tones apart have a predictable contrast ratio.
        """
        for hue in (0, 45, 120, 200, 299, 359):
            for chroma in (20.0, 60.0, 100.0, 160.0):
                for tone in (0, 10, 25, 40, 50, 70, 90, 95, 100):
                    argb = _solve_argb(hue, chroma, tone)
                    achieved = Hct.from_int(argb).tone
                    self.assertLess(
                        abs(achieved - tone),
                        0.75,
                        f"hue={hue} chroma={chroma} asked tone {tone}, "
                        f"got {achieved:.2f}",
                    )

    def test_solver_never_produces_an_out_of_gamut_colour(self):
        """Every solved colour must survive a trip through 8-bit sRGB."""
        for hue in (0, 90, 180, 270):
            for chroma in (40.0, 120.0):
                for tone in (15, 55, 85):
                    argb = _solve_argb(hue, chroma, tone)
                    self.assertEqual(argb >> 24, 0xFF)
                    back = Hct.from_int(argb)
                    self.assertLess(abs(back.tone - tone), 0.75)

    def test_white_and_black_are_exact(self):
        self.assertEqual(_solve_argb(0.0, 100.0, 100.0), 0xFFFFFFFF)
        self.assertEqual(_solve_argb(180.0, 50.0, 0.0), 0xFF000000)
        self.assertEqual(_solve_argb(0.0, 0.0, 100.0), 0xFFFFFFFF)
        self.assertEqual(_solve_argb(0.0, 0.0, 0.0), 0xFF000000)


class TestPaletteChromaTable(unittest.TestCase):
    """The palettes must use Material's chroma values, not invented ones."""

    def _palette_chromas(self, core):
        return {
            "primary": core.primary.chroma,
            "secondary": core.secondary.chroma,
            "tertiary": core.tertiary.chroma,
            "neutral": core.neutral.chroma,
            "neutral_variant": core.neutral_variant.chroma,
            "error": core.error.chroma,
        }

    def test_tonal_spot_matches_spec_2021(self):
        core = CorePalette.of(0xFF6750A4)
        for name, expected in TONAL_SPOT_CHROMAS.items():
            self.assertAlmostEqual(
                self._palette_chromas(core)[name],
                expected,
                places=3,
                msg=f"Tonal Spot {name} chroma",
            )

    def test_tonal_spot_does_not_scale_with_seed_chroma(self):
        """A saturated seed must not inflate secondary/tertiary."""
        for seed in (0xFF6366F1, 0xFFFF0000, 0xFF00FF00, 0xFF0000FF):
            core = CorePalette.of(seed)
            self.assertAlmostEqual(core.secondary.chroma, 16.0, places=3)
            self.assertAlmostEqual(core.tertiary.chroma, 24.0, places=3)
            self.assertAlmostEqual(core.neutral.chroma, 6.0, places=3)

    def test_error_palette_is_materials_fixed_red(self):
        for seed in (0xFF6750A4, 0xFF00FF00, 0xFF888888):
            core = CorePalette.of(seed)
            self.assertAlmostEqual(core.error.hue, ERROR_HUE, places=6)
            self.assertAlmostEqual(core.error.chroma, 84.0, places=3)

    def test_tertiary_hue_is_sixty_degrees_from_primary(self):
        core = CorePalette.of(0xFF6750A4)
        self.assertAlmostEqual(
            (core.tertiary.hue - core.primary.hue) % 360.0, 60.0, places=6
        )

    def test_neutral_variant_is_more_chromatic_than_neutral(self):
        core = CorePalette.of(0xFF6750A4)
        self.assertGreater(core.neutral_variant.chroma, core.neutral.chroma)

    def test_monochrome_has_no_chroma_but_keeps_red_error(self):
        core = CorePalette.monochrome(0xFF6750A4)
        for name in ("primary", "secondary", "tertiary", "neutral", "neutral_variant"):
            self.assertAlmostEqual(self._palette_chromas(core)[name], 0.0, places=6)
        self.assertAlmostEqual(core.error.chroma, 84.0, places=3)

    def test_variants_exist_and_differ(self):
        seed = 0xFF6750A4
        spot = CorePalette.of(seed)
        for builder in (
            CorePalette.vibrant,
            CorePalette.expressive,
            CorePalette.neutral,
            CorePalette.fidelity,
            CorePalette.monochrome,
        ):
            other = builder(seed)
            self.assertNotEqual(
                (spot.primary.hue, spot.primary.chroma),
                (other.primary.hue, other.primary.chroma),
                f"{builder.__name__} should differ from Tonal Spot",
            )

    def test_rotate_hue_applies_the_right_band(self):
        breakpoints = (0.0, 41.0, 61.0, 101.0, 131.0, 181.0, 251.0, 301.0, 360.0)
        rotations = (18.0, 15.0, 10.0, 12.0, 15.0, 18.0, 15.0, 12.0)
        self.assertAlmostEqual(
            CorePalette.rotate_hue(10.0, breakpoints, rotations), 28.0
        )
        self.assertAlmostEqual(
            CorePalette.rotate_hue(70.0, breakpoints, rotations), 80.0
        )
        self.assertAlmostEqual(
            CorePalette.rotate_hue(340.0, breakpoints, rotations), 352.0
        )


class TestSchemeRoles(unittest.TestCase):
    """Tone targets per role, and the contrast they guarantee."""

    #: Role → (palette, SPEC_2021 light tone).
    LIGHT_TONES = {
        "primary": 40, "on_primary": 100,
        "primary_container": 90, "on_primary_container": 10,
        "secondary": 40, "on_secondary": 100,
        "secondary_container": 90, "on_secondary_container": 10,
        "tertiary": 40, "on_tertiary": 100,
        "tertiary_container": 90, "on_tertiary_container": 10,
        "error": 40, "on_error": 100,
        "error_container": 90, "on_error_container": 10,
        "outline": 50, "outline_variant": 80,
        "on_surface_variant": 30, "on_surface": 10,
    }

    def test_light_roles_land_on_their_declared_tone(self):
        scheme = DynamicScheme.from_seed(0xFF6366F1).to_dict()
        for role, expected_tone in self.LIGHT_TONES.items():
            achieved = Hct.from_int(scheme[role]).tone
            self.assertLess(
                abs(achieved - expected_tone),
                1.0,
                f"{role} should sit at tone {expected_tone}, got {achieved:.2f}",
            )

    def test_dark_roles_land_on_their_declared_tone(self):
        scheme = DynamicScheme.from_seed(0xFF6366F1, dark=True).to_dict()
        dark_tones = {
            "primary": 80, "on_primary": 20, "primary_container": 30,
            "on_primary_container": 90, "surface": 6,
        }
        for role, expected_tone in dark_tones.items():
            achieved = Hct.from_int(scheme[role]).tone
            self.assertLess(abs(achieved - expected_tone), 1.0, role)

    def test_tone_100_roles_are_pure_white(self):
        """The specific bug: on_* roles must be #FFFFFF, not near-white."""
        light = DynamicScheme.from_seed(0xFF6366F1).to_dict()
        for role in ("on_primary", "on_secondary", "on_tertiary", "on_error"):
            self.assertEqual(
                light[role], 0xFFFFFFFF, f"{role} must be pure white in light mode"
            )

    def test_every_seed_yields_accessible_contrast(self):
        """No seed may produce an unreadable foreground/background pair."""
        pairs = [
            ("on_surface", "surface", 4.5),
            ("on_background", "background", 4.5),
            ("on_primary", "primary", 4.5),
            ("on_secondary", "secondary", 4.5),
            ("on_tertiary", "tertiary", 4.5),
            ("on_error", "error", 4.5),
            ("on_primary_container", "primary_container", 4.5),
            ("on_secondary_container", "secondary_container", 4.5),
            ("on_tertiary_container", "tertiary_container", 4.5),
            ("on_error_container", "error_container", 4.5),
            ("on_surface_variant", "surface", 4.5),
            ("primary", "surface", 3.0),
            ("outline", "surface", 3.0),
        ]
        seeds = (
            0xFF6750A4, 0xFF6366F1, 0xFFFF0000, 0xFF00FF00, 0xFF0000FF,
            0xFFFFFF00, 0xFF00FFFF, 0xFFFF00FF, 0xFF888888, 0xFF123456,
        )
        for seed in seeds:
            for dark in (False, True):
                scheme = DynamicScheme.from_seed(seed, dark=dark).to_dict()
                from pydrud.widgets.theme.hct import int_to_hex

                for fg, bg, required in pairs:
                    ratio = Colors.contrast(
                        int_to_hex(scheme[fg]), int_to_hex(scheme[bg])
                    )
                    self.assertGreaterEqual(
                        ratio,
                        required - 0.02,
                        f"seed #{seed:08X} {'dark' if dark else 'light'}: "
                        f"{fg} on {bg} = {ratio:.2f}:1 (need {required})",
                    )

    def test_every_role_is_present(self):
        """49 colour roles, plus the ``dark`` flag the serializer adds."""
        payload = DynamicScheme.from_seed(0xFF6366F1).to_dict()
        roles = [key for key in payload if key != "dark"]
        self.assertEqual(len(roles), 49)
        for role in self.LIGHT_TONES:
            self.assertIn(role, roles)
        # The twelve fixed-accent roles M3 defines on top of the standard set.
        for role in (
            "primary_fixed", "primary_fixed_dim",
            "on_primary_fixed", "on_primary_fixed_variant",
            "secondary_fixed", "secondary_fixed_dim",
            "on_secondary_fixed", "on_secondary_fixed_variant",
            "tertiary_fixed", "tertiary_fixed_dim",
            "on_tertiary_fixed", "on_tertiary_fixed_variant",
        ):
            self.assertIn(role, roles)

    def test_seeding_is_deterministic(self):
        a = DynamicScheme.from_seed(0xFF6750A4).to_dict()
        b = DynamicScheme.from_seed(0xFF6750A4).to_dict()
        self.assertEqual(a, b)


class TestColorSchemeIntegration(unittest.TestCase):
    """The public ``ColorScheme`` surfaces the corrected values."""

    def test_from_seed_exposes_every_role(self):
        scheme = ColorScheme.from_seed("#6750A4")
        for role in ColorScheme.ROLES:
            self.assertTrue(hasattr(scheme, role), role)

    def test_light_and_dark_differ(self):
        light = ColorScheme.from_seed("#6750A4", dark=False)
        dark = ColorScheme.from_seed("#6750A4", dark=True)
        self.assertNotEqual(light.primary, dark.primary)
        self.assertNotEqual(light.surface, dark.surface)

    def test_primary_is_the_seed_hue(self):
        """A generated primary keeps the seed's hue."""
        seed = 0xFF6750A4
        scheme = DynamicScheme.from_seed(seed).to_dict()
        seed_hue = Hct.from_int(seed).hue
        primary_hue = Hct.from_int(scheme["primary"]).hue
        delta = abs((seed_hue - primary_hue + 180.0) % 360.0 - 180.0)
        self.assertLess(delta, 1.0, "primary hue drifted from the seed hue")

    def test_tertiary_hue_sits_sixty_degrees_round(self):
        seed = 0xFF6750A4
        scheme = DynamicScheme.from_seed(seed).to_dict()
        primary_hue = Hct.from_int(scheme["primary"]).hue
        tertiary_hue = Hct.from_int(scheme["tertiary"]).hue
        self.assertAlmostEqual(
            (tertiary_hue - primary_hue) % 360.0, 60.0, delta=2.0
        )


if __name__ == "__main__":
    unittest.main()
