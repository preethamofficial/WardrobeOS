"""Tests for the offline colour engine: naming, extraction, pattern, harmony."""
import os
import random
import tempfile

from django.test import SimpleTestCase

from ai.colors import (detect_pattern, describe_color, extract_palette,
                       families_pair_score, normalize_palette, pair_score,
                       palette_harmony)


def _garment_image(path, garment_rgb, bg_rgb=(255, 255, 255), size=(240, 240), noise=6):
    """Draw a centred garment block on a background with slight photo noise."""
    from PIL import Image

    rng = random.Random(3)
    im = Image.new("RGB", size, bg_rgb)
    x0, y0 = size[0] // 4, size[1] // 4
    x1, y1 = size[0] - x0, size[1] - y0
    for y in range(y0, y1):
        for x in range(x0, x1):
            im.putpixel((x, y), tuple(max(0, min(255, c + rng.randint(-noise, noise)))
                                      for c in garment_rgb))
    im.save(path, quality=95)


class NamingTests(SimpleTestCase):
    def test_known_colors(self):
        cases = [
            ("#1a1a1a", "Black", "black"), ("#f5f5f0", "White", "white"),
            ("#808080", "Grey", "grey"), ("#1b2a4a", "Navy", "blue"),
            ("#c8a415", "Mustard", "yellow"), ("#d2b48c", "Tan", "neutral"),
            ("#722f37", "Wine", "red"), ("#2e8b57", "Emerald", "green"),
            ("#e8b4bc", "Blush Pink", "pink"), ("#4f75b0", "Denim", "denim"),
            ("#87ceeb", "Sky Blue", "blue"), ("#708238", "Olive", "green"),
            ("#e75480", "Hot Pink", "pink"), ("#c19a6b", "Camel", "neutral"),
        ]
        for hexv, name, family in cases:
            with self.subTest(hexv=hexv):
                result = describe_color(hexv)
                self.assertEqual(result["name"], name)
                self.assertEqual(result["family"], family)

    def test_family_from_word(self):
        self.assertEqual(families_pair_score.__name__, "families_pair_score")
        from ai.colors import family_from_word
        self.assertEqual(family_from_word("navy blue"), "blue")
        self.assertEqual(family_from_word("cream"), "neutral")
        self.assertEqual(family_from_word(""), "")


class ExtractionTests(SimpleTestCase):
    def test_garment_focus_ignores_background(self):
        """Navy garment on a white hanger must read Navy, not White."""
        path = os.path.join(tempfile.mkdtemp(), "navy.jpg")
        _garment_image(path, (27, 42, 74), bg_rgb=(250, 250, 250))
        palette = extract_palette(path)
        self.assertTrue(palette)
        top = palette[0]
        self.assertEqual(top["family"], "blue")
        self.assertIn("Navy", top["name"])
        self.assertGreaterEqual(top["share"], 0.5)
        for entry in palette[:2]:  # white must not dominate
            self.assertNotEqual(entry["family"], "white")

    def test_extracts_are_deterministic(self):
        path = os.path.join(tempfile.mkdtemp(), "same.jpg")
        _garment_image(path, (200, 16, 46))
        self.assertEqual(extract_palette(path), extract_palette(path))

    def test_multicolour_pattern_detected(self):
        from PIL import Image
        path = os.path.join(tempfile.mkdtemp(), "multi.jpg")
        im = Image.new("RGB", (240, 240), (250, 250, 250))
        rng = random.Random(5)
        for y in range(60, 180):
            for x in range(60, 120):
                im.putpixel((x, y), (200, 16 + rng.randint(-6, 6), 46))
        for y in range(60, 180):
            for x in range(120, 180):
                im.putpixel((x, y), (27, 42 + rng.randint(-6, 6), 74))
        im.save(path, quality=95)
        palette = extract_palette(path)
        self.assertEqual(detect_pattern(palette), "multicolour")
        families = {e["family"] for e in palette[:3]}
        self.assertIn("red", families)
        self.assertIn("blue", families)

    def test_solid_navy_reads_solid(self):
        path = os.path.join(tempfile.mkdtemp(), "solid.jpg")
        _garment_image(path, (27, 42, 74), bg_rgb=(240, 240, 240), noise=4)
        palette = extract_palette(path)
        self.assertEqual(detect_pattern(palette), "solid")


class HarmonyTests(SimpleTestCase):
    def test_pair_rules(self):
        self.assertEqual(pair_score("#1b2a4a", "#1b2a4a"), 0.35)  # identical = flat
        self.assertGreaterEqual(pair_score("#1a1a1a", "#f5f5f0"), 0.85)  # black/white
        self.assertLessEqual(pair_score("#1b2a4a", "#1a1a1a"), 0.7)  # navy/black faux pas
        self.assertGreaterEqual(pair_score("#1b2a4a", "#e8dcc8"), 0.85)  # navy/beige
        self.assertGreaterEqual(pair_score("#1b2a4a", "#e86a17"), 0.7)  # blue/orange pop
        self.assertLessEqual(pair_score("#b31217", "#2c5f2d"), 0.65)  # red/green clash
        self.assertTrue(0.6 <= pair_score("#1b2a4a", "#87ceeb") <= 0.85)  # tonal blues

    def test_legacy_string_palettes_still_score(self):
        score = palette_harmony(["#f7f1e1"], ["#1b2a4a"])
        self.assertGreaterEqual(score, 0.85)

    def test_normalize_palette_from_strings(self):
        entries = normalize_palette(["#1b2a4a", "#f5f5f0"])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["name"], "Navy")
        self.assertAlmostEqual(sum(e["share"] for e in entries), 1.0, places=5)

    def test_harmony_empty_fallback(self):
        self.assertEqual(palette_harmony([], ["#1b2a4a"]), 0.65)