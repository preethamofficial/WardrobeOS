"""Colour engine v3: garment-focused palette extraction + precise colour naming.

Everything runs offline with Pillow only - no external APIs, no heavy CV deps.

Pipeline
--------
1. The photo is downsampled to <=160px (plenty for colour statistics).
2. Background candidates are learned from the border ring (hanger, wall,
   floor) and rejected perceptually in CIELAB space.
3. Remaining pixels are weighted toward the frame centre (garments are
   normally centred) and clustered with a seeded, deterministic k-means.
4. Every cluster is named against a curated fashion lexicon using weighted
   CIELAB distance and classified into a colour family for outfit rules.

Public API
----------
extract_palette(path, n)   -> [{"hex", "name", "family", "share"}, ...]
normalize_palette(p)       -> same shape, tolerant of legacy hex-string lists
describe_color(rgb | hex)  -> {"hex", "name", "family"}
detect_pattern(palette)    -> solid | two-tone | multicolour | patterned
pair_score(hex_a, hex_b)   -> 0.35..0.95 outfit harmony (family aware)
palette_harmony(a, b)      -> best pair score across two palettes
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageOps

__all__ = [
    "extract_palette", "normalize_palette", "describe_color", "color_name",
    "family_of", "family_from_word", "detect_pattern", "pair_score",
    "palette_harmony", "palette_primary", "palette_entries",
    "NEUTRAL_FAMILIES",
]

NEUTRAL_FAMILIES = {"black", "white", "grey", "neutral", "denim"}

# ---------------------------------------------------------------- RGB / hex

def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(round(v))))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*[_clamp(x) for x in rgb[:3]])


def _norm_hex(hex_in):
    h = str(hex_in).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    if len(h) != 6:
        return "#808080"
    try:
        int(h, 16)
    except ValueError:
        return "#808080"
    return "#" + h.lower()


def hex_to_rgb(hex_in):
    h = _norm_hex(hex_in).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ------------------------------------------------- sRGB -> CIELAB (D65)

def _srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb):
    r, g, b = (_srgb_to_linear(x) for x in rgb[:3])
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_chroma(lab):
    return math.hypot(lab[1], lab[2])


def lab_hue(lab):
    h = math.degrees(math.atan2(lab[2], lab[1]))
    return h + 360 if h < 0 else h


_LAB_CACHE = {}


def _lab(rgb):
    key = tuple(_clamp(v) for v in rgb[:3])
    val = _LAB_CACHE.get(key)
    if val is None:
        val = rgb_to_lab(key)
        _LAB_CACHE[key] = val
    return val


def _lab_dist(l1, l2):
    return math.sqrt((l1[0] - l2[0]) ** 2 + (l1[1] - l2[1]) ** 2 +
                     (l1[2] - l2[2]) ** 2)


# ------------------------------------------------------------- colour names

# Curated fashion palette anchors: (name, hex, family). Naming works by
# weighted CIELAB distance to these anchors, so breadth here == precision.
LEXICON = [
    # reds
    ("Cherry Red", "#b31217", "red"), ("Scarlet", "#c81d25", "red"),
    ("Crimson", "#a4243b", "red"), ("Brick Red", "#8e3b2f", "red"),
    ("Burgundy", "#6e1423", "red"), ("Wine", "#5f1a25", "red"),
    ("Maroon", "#7c1f2e", "red"),
    # pinks
    ("Hot Pink", "#e75480", "pink"), ("Rose Pink", "#d76a8c", "pink"),
    ("Blush Pink", "#e8b4bc", "pink"), ("Dusty Rose", "#c98d8d", "pink"),
    ("Fuchsia", "#c22184", "pink"), ("Mauve", "#b49ea6", "pink"),
    ("Salmon", "#e9967a", "pink"),
    # oranges
    ("Tangerine", "#e86a17", "orange"), ("Burnt Orange", "#b7521e", "orange"),
    ("Terracotta", "#c96f4a", "orange"), ("Coral", "#f28473", "orange"),
    ("Rust", "#a44a2a", "orange"), ("Apricot", "#efc09a", "orange"),
    # yellows
    ("Mustard", "#c8a415", "yellow"), ("Marigold", "#eaa221", "yellow"),
    ("Lemon Yellow", "#f3e151", "yellow"), ("Butter Yellow", "#f5e6a8", "yellow"),
    ("Gold", "#c9a227", "yellow"), ("Ochre", "#c9973b", "yellow"),
    # greens
    ("Olive", "#708238", "green"), ("Army Green", "#5b6b3a", "green"),
    ("Sage", "#9caf88", "green"), ("Mint", "#b2e8c8", "green"),
    ("Emerald", "#2e8b57", "green"), ("Forest Green", "#2c5f2d", "green"),
    ("Pistachio", "#a8c66c", "green"), ("Hunter Green", "#386641", "green"),
    ("Sea Green", "#2e8b74", "green"),
    # blues
    ("Navy", "#1b2a4a", "blue"), ("Royal Blue", "#2a52be", "blue"),
    ("Cobalt", "#0047ab", "blue"), ("Denim", "#4f75b0", "denim"),
    ("Sky Blue", "#87ceeb", "blue"), ("Powder Blue", "#b0c4de", "blue"),
    ("Baby Blue", "#89cff0", "blue"), ("Steel Blue", "#4682b4", "blue"),
    ("Teal", "#0f7b7b", "blue"), ("Turquoise", "#30d5c8", "blue"),
    ("Slate Blue", "#6a7ba2", "blue"), ("Ice Blue", "#d6eef7", "blue"),
    # purples
    ("Lavender", "#c3b1e1", "purple"), ("Lilac", "#c9a9dc", "purple"),
    ("Plum", "#8e4585", "purple"), ("Violet", "#7f4fa8", "purple"),
    ("Royal Purple", "#5c3a8e", "purple"), ("Eggplant", "#47304f", "purple"),
    ("Amethyst", "#9b7fce", "purple"),
    # browns
    ("Chocolate", "#4b3621", "brown"), ("Coffee", "#6f4e37", "brown"),
    ("Brown", "#8b5a2b", "brown"), ("Chestnut", "#7b3f28", "brown"),
    ("Tan", "#d2b48c", "neutral"), ("Camel", "#c19a6b", "neutral"),
    ("Taupe", "#a89c94", "neutral"), ("Khaki", "#c3b091", "neutral"),
    ("Mushroom", "#b5ada5", "neutral"),
    # lights / neutrals
    ("Beige", "#e8dcc8", "neutral"), ("Cream", "#f7f1e1", "neutral"),
    ("Ivory", "#fdf6e3", "neutral"),
    # greys
    ("Charcoal", "#3c3c41", "grey"), ("Slate Grey", "#6d7278", "grey"),
    ("Stone Grey", "#9a9a9a", "grey"),
]

# Precomputed (name, lab, family) anchors for fast, allocation-free matching.
_ANCHORS = [(_n, _lab(hex_to_rgb(_h)), _f) for _n, _h, _f in LEXICON]

# Anchors whose names already encode depth - never prefix them again.
_LIGHT_PREFIXES = {"light", "pale", "baby", "sky", "powder", "butter", "ice"}
_DARK_PREFIXES = {"dark", "deep", "navy", "charcoal", "forest", "hunter",
                  "eggplant", "burgundy", "wine", "maroon", "burnt",
                  "chocolate", "coffee", "chestnut", "royal"}

# Free-text fallback for the human-typed `color` field -> family.
WORD_FAMILIES = {
    "black": "black", "white": "white", "grey": "grey", "gray": "grey",
    "silver": "grey", "charcoal": "grey", "navy": "blue", "blue": "blue",
    "denim": "denim", "sky": "blue", "teal": "blue", "turquoise": "blue",
    "red": "red", "maroon": "red", "burgundy": "red", "wine": "red",
    "crimson": "red", "rust": "orange", "orange": "orange", "coral": "orange",
    "peach": "orange", "yellow": "yellow", "mustard": "yellow",
    "gold": "yellow", "green": "green", "olive": "green", "sage": "green",
    "mint": "green", "emerald": "green", "pink": "pink", "blush": "pink",
    "rose": "pink", "fuchsia": "pink", "purple": "purple", "violet": "purple",
    "lavender": "purple", "lilac": "purple", "plum": "purple",
    "brown": "brown", "chocolate": "brown", "coffee": "brown",
    "tan": "neutral", "beige": "neutral", "cream": "neutral",
    "ivory": "neutral", "camel": "neutral", "khaki": "neutral",
    "taupe": "neutral",
}


def _describe_rgb(rgb):
    """CIELAB-guided naming: (name, family) for an RGB tuple."""
    L, a, b = _lab(rgb)
    C = lab_chroma((L, a, b))
    if L <= 14 and C < 26:
        return "Black", "black"
    if L >= 93 and C < 12:
        return "White", "white"
    if C < 11:  # true grey scale
        if L < 34:
            return "Charcoal", "grey"
        if L < 58:
            return "Grey", "grey"
        if L < 80:
            return "Silver", "grey"
        return "Off White", "white"
    hue = lab_hue((L, a, b))
    best_name, best_family, best_L, best_d = None, None, None, None
    for name, (aL, aa, ab), family in _ANCHORS:
        aC = math.hypot(aa, ab)
        aHue = math.degrees(math.atan2(ab, aa)) % 360
        dh = abs(hue - aHue)
        dh = min(dh, 360 - dh)
        d = (L - aL) ** 2 + 0.55 * (C - aC) ** 2 + 0.9 * (dh / 1.9) ** 2
        if best_d is None or d < best_d:
            best_name, best_family, best_L, best_d = name, family, aL, d
    first = best_name.split()[0].lower()
    if L - best_L >= 17 and first not in _LIGHT_PREFIXES:
        return "Light " + best_name, best_family
    if best_L - L >= 17 and first not in _DARK_PREFIXES:
        return "Dark " + best_name, best_family
    return best_name, best_family


def describe_color(color):
    """rgb tuple/list or hex string -> {"hex", "name", "family"}."""
    if isinstance(color, str):
        hexv = _norm_hex(color)
        rgb = hex_to_rgb(hexv)
    else:
        rgb = tuple(_clamp(x) for x in color[:3])
        hexv = rgb_to_hex(rgb)
    name, family = _describe_rgb(rgb)
    return {"hex": hexv, "name": name, "family": family}


def color_name(color):
    return describe_color(color)["name"]


def family_of(color):
    return describe_color(color)["family"]


def family_from_word(word):
    """Best-effort family for a human-typed colour word ("navy blue" -> blue)."""
    w = str(word or "").strip().lower()
    if not w:
        return ""
    if w in WORD_FAMILIES:
        return WORD_FAMILIES[w]
    for key, fam in WORD_FAMILIES.items():
        if key in w:
            return fam
    return ""


def normalize_palette(palette):
    """Canonical palette shape: [{"hex","name","family","share"}].

    Accepts legacy lists of hex strings (shares become even) or dicts that
    may be missing name/family/share - every entry gets fully described.
    """
    if not palette:
        return []
    out = []
    for entry in palette:
        if isinstance(entry, dict):
            hexv = entry.get("hex")
            if not hexv:
                continue
            d = describe_color(hexv)
            out.append({"hex": _norm_hex(hexv),
                        "name": str(entry.get("name") or d["name"]),
                        "family": entry.get("family") or d["family"],
                        "share": float(entry.get("share") or 0.0)})
        else:
            d = describe_color(entry)
            out.append({"hex": d["hex"], "name": d["name"],
                        "family": d["family"], "share": 0.0})
    if out and all(e["share"] <= 0 for e in out):
        even = 1.0 / len(out)
        for e in out:
            e["share"] = even
    return out


def palette_entries(palette):
    return normalize_palette(palette)


def palette_primary(palette):
    """Hex of the dominant colour, or None."""
    entries = normalize_palette(palette)
    return entries[0]["hex"] if entries else None
# --------------------------------------------- garment palette extraction

_DOWNSCALE = 160       # statistics do not need more pixels than this
_MAX_SAMPLES = 3500    # k-means input cap for snappy uploads
_BG_REJECT_DE = 20.0   # CIELAB distance that counts as "background"
_MERGE_DE = 12.0       # clusters closer than this are the same colour


def _background_candidates(px, w, h):
    """Learn 0-2 background colours from the photo's border ring."""
    ring = max(2, int(min(w, h) * 0.08))
    buckets = {}
    for (r, g, b, x, y) in px:
        if x < ring or y < ring or x >= w - ring or y >= h - ring:
            buckets.setdefault((r >> 5, g >> 5, b >> 5), []).append((r, g, b))
    total = sum(len(v) for v in buckets.values()) or 1
    out = []
    for key, group in sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:2]:
        if len(group) < total * 0.10:
            continue
        n = len(group)
        out.append((sum(p[0] for p in group) // n,
                    sum(p[1] for p in group) // n,
                    sum(p[2] for p in group) // n))
    return out


def _kmeans(points, weights, k, iters=12, seed=7):
    """Deterministic weighted k-means -> [(center_rgb, share), ...]."""
    n = len(points)
    if n == 0:
        return []
    k = max(1, min(k, n))
    rng = random.Random(seed)
    centers = [points[rng.randrange(n)]]
    while len(centers) < k:  # k-means++ style farthest-point seeding
        best_i, best_d = 0, -1.0
        for i, p in enumerate(points):
            d = min(_dist(p, c) for c in centers)
            if d > best_d:
                best_i, best_d = i, d
        if best_d <= 0.0:
            break
        centers.append(points[best_i])
    assign = [0] * n
    for _ in range(iters):
        changed = False
        for i, p in enumerate(points):
            bi, bd = 0, None
            for ci, c in enumerate(centers):
                d = _dist(p, c)
                if bd is None or d < bd:
                    bi, bd = ci, d
            if assign[i] != bi:
                assign[i] = bi
                changed = True
        sums = [[0.0, 0.0, 0.0, 0.0] for _ in centers]
        for i, p in enumerate(points):
            s = sums[assign[i]]
            w = weights[i]
            s[0] += p[0] * w
            s[1] += p[1] * w
            s[2] += p[2] * w
            s[3] += w
        for ci, s in enumerate(sums):
            if s[3] > 0:
                centers[ci] = (s[0] / s[3], s[1] / s[3], s[2] / s[3])
        if not changed:
            break
    totals = [0.0] * len(centers)
    for i, p in enumerate(points):
        totals[assign[i]] += weights[i]
    wsum = sum(weights) or 1.0
    return [(tuple(_clamp(v) for v in c), totals[ci] / wsum)
            for ci, c in enumerate(centers) if totals[ci] > 0]

def _merge_clusters(clusters):
    """Merge perceptually identical clusters (weighted mean in RGB space)."""
    changed = True
    while changed and len(clusters) > 1:
        changed = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if _lab_dist(_lab(clusters[i][0]), _lab(clusters[j][0])) < _MERGE_DE:
                    sw = clusters[i][1] + clusters[j][1]
                    wa = clusters[i][1] / sw
                    wb = clusters[j][1] / sw
                    merged = tuple(wa * a + wb * b
                                   for a, b in zip(clusters[i][0], clusters[j][0]))
                    clusters[i] = (merged, sw)
                    del clusters[j]
                    changed = True
                    break
            if changed:
                break
    return clusters


def extract_palette(image_path, n=5):
    """Dominant GARMENT colours of a photo.

    Returns [{"hex", "name", "family", "share"}, ...] sorted by share.
    Backgrounds (hanger, wall, floor) are rejected before clustering, so a
    navy shirt on a white hanger yields Navy - not White.
    """
    try:
        with Image.open(image_path) as im:
            im.load()
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((_DOWNSCALE, _DOWNSCALE), Image.Resampling.LANCZOS)
            w, h = im.size
            data = list(im.getdata())
            px = []
            idx = 0
            for y in range(h):
                for x in range(w):
                    p = data[idx]
                    idx += 1
                    px.append((p[0], p[1], p[2], x, y))
            bg = _background_candidates(px, w, h)
            cx, cy = (w - 1) / 2, (h - 1) / 2
            norm = math.hypot(cx, cy) or 1.0
            garment = []
            for (r, g, b, x, y) in px:
                lab = _lab((r, g, b))
                if bg and min(_lab_dist(lab, _lab(c)) for c in bg) < _BG_REJECT_DE:
                    continue
                d = math.hypot(x - cx, y - cy) / norm
                garment.append((r, g, b, 1.0 - 0.55 * min(1.0, d)))
            if len(garment) < max(300, int(0.08 * len(px))):
                # garment probably fills the frame - keep every pixel
                garment = [(r, g, b,
                            1.0 - 0.55 * min(1.0, math.hypot(x - cx, y - cy) / norm))
                           for (r, g, b, x, y) in px]
            pts = [(r, g, b) for (r, g, b, _wt) in garment]
            wts = [wt for (_r, _g, _b, wt) in garment]
            if len(pts) > _MAX_SAMPLES:
                keep = random.Random(7).sample(range(len(pts)), _MAX_SAMPLES)
                pts = [pts[i] for i in keep]
                wts = [wts[i] for i in keep]
            clusters = _kmeans(pts, wts, k=min(5, n + 1))
            clusters = _merge_clusters(clusters)
            clusters.sort(key=lambda c: -c[1])
            out, seen = [], set()
            for rgb, share in clusters:
                if share < 0.05 and out:
                    continue
                info = describe_color(rgb)
                if info["name"] in seen:
                    continue
                seen.add(info["name"])
                out.append({"hex": info["hex"], "name": info["name"],
                            "family": info["family"],
                            "share": round(float(share), 4)})
                if len(out) >= n:
                    break
            if not out:  # last-resort fallback: quantize + describe
                q = im.quantize(colors=min(3, n))
                pal = q.getpalette() or []
                counts = sorted(q.getcolors(maxcolors=256) or [], reverse=True)
                for count, cidx in counts[:n]:
                    if not pal:
                        break
                    info = describe_color(tuple(pal[cidx * 3:cidx * 3 + 3]))
                    if info["name"] in seen:
                        continue
                    seen.add(info["name"])
                    out.append({"hex": info["hex"], "name": info["name"],
                                "family": info["family"], "share": 0.0})
                if out:
                    even = 1.0 / len(out)
                    for e in out:
                        e["share"] = even
            return out
    except Exception:
        return []


def detect_pattern(palette):
    """Heuristic garment pattern from the colour clusters."""
    entries = normalize_palette(palette)
    if not entries:
        return ""
    if len(entries) == 1:
        return "solid"
    shares = [e["share"] for e in entries]
    top = shares[0]
    if top >= 0.82:
        return "solid"
    chromatic = [e for e in entries[:3]
                 if e["family"] not in NEUTRAL_FAMILIES and e["share"] >= 0.12]
    if len({e["family"] for e in chromatic}) >= 2:
        return "multicolour"
    if len(entries) >= 2 and shares[1] >= 0.12:
        if entries[0]["family"] == entries[1]["family"] and top >= 0.55:
            return "two-tone"
        if top < 0.55:
            return "two-tone" if top + shares[1] >= 0.78 else "patterned"
    if top >= 0.55:
        return "solid"
    return "patterned"
# ------------------------------------------------------- outfit colour rules

def pair_score(hex_a, hex_b):
    """0.35 (flat/clash) .. 0.95 (harmonious) for two hex colours.

    Family-aware fashion rules:
    - neutrals pair with everything (black+navy and black+very dark brown
      are the classic exceptions and get penalised)
    - same saturated family works when the depths differ (tonal dressing)
    - analogous hues are safe, complementary hues pop, neighbours clash
    """
    a, b = hex_to_rgb(hex_a), hex_to_rgb(hex_b)
    if _dist(a, b) < 40:
        return 0.35  # effectively the same tone - looks flat together
    fa = describe_color(a)["family"]
    fb = describe_color(b)["family"]
    return _family_pair_score(fa, fb, _lab(a), _lab(b))


def _family_pair_score(fa, fb, lab_a=None, lab_b=None):
    neutral = NEUTRAL_FAMILIES
    if fa == fb and fa in neutral:
        return 0.88
    if fa == fb:
        # same saturated family: tonal works when depths differ, else flat
        if lab_a and lab_b:
            dl = abs(lab_a[0] - lab_b[0])
            return 0.78 if dl >= 18 else 0.5
        return 0.78
    if fa in neutral and fb in neutral:
        return 0.88
    if fa in neutral or fb in neutral:
        other = fb if fa in neutral else fa
        other_lab = lab_b if fa in neutral else lab_a
        n_lab = lab_a if fa in neutral else lab_b
        n_is_dark = bool(n_lab) and n_lab[0] < 26 and lab_chroma(n_lab) < 14
        if n_is_dark:
            if other == "blue" and other_lab and other_lab[0] < 32:
                return 0.6   # navy + black - classic faux pas
            if other == "brown" and other_lab and other_lab[0] < 30:
                return 0.65  # very dark brown + black goes muddy
        return 0.92
    if lab_a and lab_b:
        h1, h2 = lab_hue(lab_a), lab_hue(lab_b)
        diff = abs(h1 - h2)
        diff = min(diff, 360 - diff)
        if diff <= 40:
            return 0.82   # analogous - safe and tasteful
        if diff <= 90:
            return 0.62   # competing neighbours
        if diff <= 120:
            return 0.58   # triadic boldness
        return 0.76       # complementary accent (blue/orange, purple/yellow)
    return 0.7


def families_pair_score(fa, fb):
    """Harmony for two colour families when exact hexes are unknown."""
    return _family_pair_score(fa, fb, None, None)


def harmony_label(pct):
    """Human verdict for a 0-100 harmony score."""
    if pct >= 88:
        return "classic neutral base - hard to get wrong"
    if pct >= 75:
        return "tasteful pairing"
    if pct >= 60:
        return "confident contrast"
    return "bold - carry it with attitude"


def palette_harmony(pal_a, pal_b):
    """Best pair_score between two palettes; 0.65 when either is empty."""
    a, b = normalize_palette(pal_a), normalize_palette(pal_b)
    if not a or not b:
        return 0.65
    return max(pair_score(x["hex"], y["hex"]) for x in a[:3] for y in b[:3])