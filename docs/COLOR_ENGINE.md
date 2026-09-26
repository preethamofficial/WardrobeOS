# Colour Engine v3 - design notes

The colour engine is the heart of wardrobe intelligence. It runs 100% offline
(Pillow + pure Python, no numpy, no APIs) and turns a photo into structured
colour knowledge.

## Pipeline

```
photo ──► downsample ≤160px ──► background rejection ──► centre weighting
      ──► seeded k-means ──► perceptual merge ──► lexicon naming ──► family
```

### 1. Garment focus (background rejection)
Product photos usually carry large "junk" areas: hangers, walls, floors.
- The border ring (outer 8% of the frame) is bucketed on coarse colour keys.
- The two most common buckets become background candidates.
- Every pixel within a CIELAB ΔE of 20 of a candidate is discarded.
- If <8% of pixels survive (garment fills the frame), rejection is skipped -
  the guard keeps flat-lay photos working.

### 2. Centre weighting
Garments are normally centred, so surviving pixels get a radial weight from
1.0 at the centre down to 0.45 at the corners before clustering.

### 3. Deterministic clustering
- Pixels are deterministically subsampled to ≤3500 (`random.Random(7)`).
- Weighted k-means (k ≤ 6) with farthest-point seeding, ≤12 iterations.
- Clusters closer than ΔE 12 are merged (weighted mean in RGB).
- Shares are weight-normalised; clusters under 5% share are dropped.

### 4. Naming (the part that must be *perfect*)
- RGB → linear sRGB → XYZ (D65) → CIELAB. (Note: a = 500·(f(x/Xn) − f(y/Yn))
  - the classic off-by-one-variable bug that makes greens read red.)
- Achromatics first: L≤14 → Black, L≥93 & low chroma → White, otherwise a
  grey ramp (Charcoal / Grey / Silver / Off White).
- Chromatics: weighted distance to a ~65-anchor fashion lexicon
  `(ΔL² + 0.55·ΔC² + 0.9·(Δh/1.9)²)` where Δh is wrapped Lab hue distance.
  Lightness dominates, chroma second, hue third - matching how people name
  clothes ("dark blue" before "blue").
- Depth qualifiers are appended only when the anchor's name does not already
  encode depth ("Light Blue", "Dark Brown" - never "Dark Navy").

### 5. Family + pattern
Families (`black, white, grey, neutral, denim, red, pink, orange, yellow,
green, blue, purple, brown`) are what the outfit engine consumes. Pattern is
inferred from cluster shares: `solid` / `two-tone` / `multicolour` /
`patterned`.

## Harmony rules (outfit pairing)
- Neutrals pair with everything (0.88-0.92) **except** black+navy (0.60) and
  black+very dark brown (0.65) - the classic faux pas.
- Same chromatic family: tonal when depths differ (0.78), flat when near
  identical (0.50).
- Hue distance on the Lab wheel: ≤40° analogous (0.82), ≤90° competing
  (0.62), ≤120° triadic bold (0.58), otherwise complementary pop (0.76) -
  blue/orange and purple/yellow score as intended.

## Why the photo enhancer is colour-safe
- Autocontrast fires only when the luminance spread is <150 (washed photos).
- Exposure correction brightens truly dark photos, gently tames blown-out
  ones, and leaves healthy photos untouched - global darkening is what turns
  navy into black.
- Enhancement is idempotent via an EXIF Software tag, so re-scans never
  double-process a photo.

## Verification
`python manage.py test` covers naming anchors, garment-focus extraction,
determinism, pattern detection, harmony rules and the full upload pipeline
(auto-detected colour + family + pattern + thumbnail).
