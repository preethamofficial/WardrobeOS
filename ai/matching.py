"""Outfit engine v3.

Scoring blends: rotation balance, occasion formality, season, live weather,
family-aware colour harmony (perceptual, palette-driven), pattern clash
detection - and layers (jackets/hoodies/sweaters), dresses and properly
scored shoes. Every recommendation ships honest, item-specific reasons.
"""
from datetime import datetime, timezone as dt_timezone

from ai.colors import (NEUTRAL_FAMILIES, families_pair_score, harmony_label,
                       normalize_palette, palette_harmony)

TOPS = {"shirt", "tshirt"}
WARM_TOPS = {"hoodie", "sweater"}          # can act as top OR as a layer
LAYERS = {"jacket", "hoodie", "sweater"}
BOTTOMS = {"pant", "jeans", "shorts", "skirt"}
DRESSES = {"dress"}
SHOES = {"shoes"}

_OCCASION_FORMALITY = {
    "office": {"formal", "smart_casual"}, "meeting": {"formal", "smart_casual"},
    "party": {"smart_casual", "casual"}, "casual": {"casual", "sport"},
    "college": {"casual", "sport"}, "sport": {"sport", "casual"},
    "formal": {"formal"}, "date": {"smart_casual", "casual"},
    "travel": {"casual", "sport"}}

_SEASONS = {"winter": (12, 1, 2), "spring": (3, 4, 5),
            "summer": (6, 7, 8), "autumn": (9, 10, 11)}


def days_since(item):
    if not item.last_worn:
        return 999
    lw = item.last_worn
    if lw.tzinfo is None:  # naive timestamps: assume UTC instead of maxing out
        lw = lw.replace(tzinfo=dt_timezone.utc)
    return max(0, (datetime.now(dt_timezone.utc) - lw).days)


def _entries(item):
    return normalize_palette(getattr(item, "palette", None))


def _item_family(item):
    fam = (getattr(item, "color_family", "") or "").strip()
    if fam:
        return fam
    from ai.colors import family_from_word
    return family_from_word(getattr(item, "color", ""))


def color_score(a, b):
    """Colour harmony: photo palettes first, colour families as fallback."""
    ea, eb = _entries(a), _entries(b)
    if ea and eb:
        return palette_harmony(ea, eb)
    fa, fb = _item_family(a), _item_family(b)
    if fa and fb:
        return families_pair_score(fa, fb)
    return 0.65


def weather_score(item, temperature, kind=None):
    cat = item.category
    if temperature >= 30 and cat in {"tshirt", "shirt", "shorts", "skirt", "dress"}:
        return 20
    if 20 < temperature < 30 and cat in {"tshirt", "shirt", "jeans", "pant", "skirt", "dress"}:
        return 16
    if temperature <= 20 and cat in {"jacket", "hoodie", "sweater", "shirt"}:
        return 20
    if temperature <= 12 and cat in {"jacket", "sweater", "hoodie"}:
        return 22
    if kind in ("rain", "storm"):
        if cat in {"jacket", "hoodie"}:
            return 14
        if cat == "shoes":
            return 8  # favour sturdy footwear in the wet
        if cat in {"skirt", "shorts"}:
            return 4
    if kind == "snow" and cat in {"jacket", "sweater", "hoodie", "shoes"}:
        return 16
    if kind == "fog" and cat == "jacket":
        return 14
    return 10


def _season_score(item):
    season = (item.season or "all").strip().lower()
    if not season or season == "all":
        return 0
    month = datetime.now(dt_timezone.utc).month
    for name, months in _SEASONS.items():
        if name in season:
            return 6 if month in months else -8
    return 0


def item_score(item, occasion, temperature, kind=None):
    """0..100 piece score: status, rotation, occasion, season, weather."""
    score = 25 if item.status == "clean" else -40
    score += min(25, days_since(item) / 7 * 25)
    occ = {x.strip().lower() for x in (item.occasions or "").split(",") if x.strip()}
    if occasion:
        if occasion.lower() in occ:
            score += 20
        elif item.formality in _OCCASION_FORMALITY.get(occasion.lower(), set()):
            score += 14
        else:
            score += 4
    score += _season_score(item)
    score += weather_score(item, temperature, kind)
    return max(0, min(100, score))

def _patterned(item):
    """True when the item is not plain (prints, stripes, checks, multicolour)."""
    return (item.pattern or "").strip().lower() not in ("", "solid", "plain", "none")


def _pick_shoes(a, b, shoes, occasion, temperature, kind):
    """Best shoe: piece score plus harmony with BOTH anchor pieces."""
    best, best_s = None, -1e9
    for s in shoes:
        sc = item_score(s, occasion, temperature, kind)
        if a is not b:
            sc += 10 * color_score(a, s) + 10 * color_score(b, s)
        else:
            sc += 20 * color_score(a, s)
        if sc > best_s:
            best, best_s = s, sc
    return best


def _combo_harmony(t, b, layer, shoe):
    """Weighted harmony across the outfit + pattern-clash flag."""
    pairs = [(t, b, 0.55)]
    if layer and shoe:
        pairs += [(t, layer, 0.15), (b, layer, 0.15), (t, shoe, 0.08), (b, shoe, 0.07)]
    elif layer:
        pairs += [(t, layer, 0.25), (b, layer, 0.20)]
    elif shoe:
        pairs += [(t, shoe, 0.25), (b, shoe, 0.20)]
    harmony = sum(w * color_score(x, y) for x, y, w in pairs)
    clash = _patterned(t) and _patterned(b) and _item_family(t) != _item_family(b)
    return harmony, clash


def _combo_score(pieces, occasion, temperature, kind, harmony, clash):
    ns = [item_score(p, occasion, temperature, kind) for p in pieces]
    base = sum(ns) / len(ns)
    total = 0.58 * base + 0.42 * harmony * 100
    if clash:
        total -= 8
    return round(max(0, min(100, total)), 1)


def _build(t, b, layers, shoes, want_layer, occasion, temperature, kind):
    layer = None
    if want_layer and layers:
        layer = max(layers, key=lambda l: item_score(l, occasion, temperature, kind)
                    + 10 * color_score(t, l))
    shoe = _pick_shoes(t, b, shoes, occasion, temperature, kind)
    pieces = [t, b] + ([layer] if layer else []) + ([shoe] if shoe else [])
    harmony, clash = _combo_harmony(t, b, layer, shoe)
    score = _combo_score(pieces, occasion, temperature, kind, harmony, clash)
    palette = (t.palette or [])[:3] + (b.palette or [])[:2]
    if layer:
        palette += (layer.palette or [])[:1]
    return {"items": pieces, "score": score,
            "why": _explain(t, b, layer, shoe, temperature, kind, harmony, clash),
            "palette": palette, "harmony": round(harmony * 100)}

def _explain(t, b, layer, shoe, temperature, kind, harmony, clash):
    why = []
    why.append("✓ Clean and ready to wear" if t.status == b.status == "clean"
               else "✓ Best available pieces today")
    ages = [(days_since(p), p) for p in (t, b, layer) if p]
    if ages:
        m, who = max(ages, key=lambda x: x[0])
        if m >= 5:
            why.append(f"✓ {who.name} hasn't been worn in {m} days - rotation stays balanced")
    if temperature is not None and temperature >= 30:
        why.append("✓ Breathable picks for the heat")
    elif temperature is not None and temperature <= 20:
        why.append("✓ Warm picks for cooler air")
    if kind in ("rain", "storm"):
        why.append("✓ Rain-smart layering")
    elif kind == "snow":
        why.append("✓ Snow-ready warmth")
    if layer:
        why.append(f"✓ {layer.name} adds a warm structured layer")
    pct = round(harmony * 100)
    why.append(f"✓ Colour harmony {pct}% - {harmony_label(pct)}")
    if clash:
        why.append("⚠ Two printed pieces - swap one for a quieter look")
    return why[:5]


def _build_dress(d, shoes, occasion, temperature, kind):
    shoe = _pick_shoes(d, d, shoes, occasion, temperature, kind)
    pieces = [d] + ([shoe] if shoe else [])
    harmony = color_score(d, shoe) if shoe else 0.9
    ns = [item_score(p, occasion, temperature, kind) for p in pieces]
    total = 0.58 * (sum(ns) / len(ns)) + 0.42 * harmony * 100
    why = ["✓ One-piece outfit - effortless and clean",
           f"✓ Colour harmony {round(harmony * 100)}% - {harmony_label(round(harmony * 100))}"]
    if temperature is not None and temperature <= 20:
        why.append("✓ Pair with tights or a coat when it gets colder")
    return {"items": pieces, "score": round(max(0, min(100, total)), 1),
            "why": why[:5], "palette": (d.palette or [])[:3], "harmony": round(harmony * 100)}


def recommend(items, occasion="office", temperature=25, kind=None, limit=6):
    """Ranked outfits: tops×bottoms(+layer+shoes) and dresses, score + reasons.

    Buckets are pre-ranked and capped so large wardrobes stay fast, and the
    hottest combos still rise to the top.
    """
    clean = [x for x in items if x.status == "clean"]
    if not clean:
        return []

    def bucket(cats, cap):
        pool = [x for x in clean if x.category in cats]
        pool.sort(key=lambda x: -item_score(x, occasion, temperature, kind))
        return pool[:cap]

    tops = bucket(TOPS | WARM_TOPS, 12)
    bottoms = bucket(BOTTOMS, 12)
    layers = bucket(LAYERS, 8)
    shoes = bucket(SHOES, 8)
    dresses = bucket(DRESSES, 8)
    occasion_l = (occasion or "").lower()
    want_layer = (temperature is not None and temperature < 21) or \
                 kind in ("rain", "storm", "snow") or \
                 occasion_l in ("office", "meeting", "formal")

    out = []
    for t in tops:
        for b in bottoms:
            out.append(_build(t, b, layers, shoes, want_layer,
                              occasion, temperature, kind))
    for d in dresses:
        out.append(_build_dress(d, shoes, occasion, temperature, kind))
    out.sort(key=lambda x: -x["score"])
    return out[:limit]
