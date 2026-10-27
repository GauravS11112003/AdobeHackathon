# Backdrop awareness — the background as a composition (v10, 2026-10-26)

Until v9 the engine laid furniture out on a canvas it treated as blank. A headline that sat in
the glow of a gradient, a quote on the quiet part of a photo, a label over the dark bottom of a
picture were moved to where the plan's slot put them, and the relation to what lies *under*
them was lost; decorative shapes (two circles in opposite corners, confetti around the border)
were moved one by one, each keeping its offset from the nearest corner. `engine/backdrop.py`
and `engine/patterns.py` give the engine a coarse picture of the backdrop and keep those
relations: the relation, not the coordinates.

Everything is behind `CHAMELEON_BACKGROUND` (=0 is byte-identical to the v9 engine; the 18
v5 goldens pass with the flag off) and each piece behind `CHAMELEON_BACKDROP_SLIDE / _QUIET /
_JUDGE / _PATTERNS` for measurement. **Shipped defaults: slide, quiet area and patterns on, the
judge term off** (§4: it never paid on the designer references at weight 1, 2 or 3).

## 1. Design

```
backdrop.BackdropMap     24 x 24 cells x 3 x 3 samples of luminance / colour, summed-area tables
                         from_json   : the non-text layers composited at the samples (engine/contrast.py's
                                       layer model: canvas, shapes x fill alpha x opacity, image assets
                                       sampled through their fit, missing asset = the grey placeholder)
                         from_image  : a render without text (max_size 400), when pixels are allowed
backdrop.Signature       of a text in a design, under its painted (ink) box:
                           lum   mean lightness (relative luminance ** 0.45: the dark half of a gradient
                                 spans 0.02 of luminance and a third of lightness)
                           busy  spread of the colours (0..255, engine/contrast.py's `busy`)
                           glow  lum minus the canvas median lightness (in the bright part of a dark
                                 gradient, or the dark part of a bright one)
                           hue / sat of the mean colour, and `over`: the non-text element drawn below
                                 the text that holds >= 50 % of its ink
                         distance = 0.6 |d lum| + 1.0 |d glow| + 0.6 |d busy / 60| + 0.3 sat |d hue| / 180
                         source_signatures(analysis): every text's signature in the source, cached per task
2a  slide                floorplan._place_column records a *slot* per text item (the column's width, the
                         room down to the neighbours' gaps: reading order cannot change); after the plan
                         (floorplan_relayout, structure_relayout) backdrop.slide_texts builds the target's
                         map from the placement's non-text elements (48 x 48 JSON composite, ~1 ms) and
                         moves each headline / subhead / body / CTA text to the position in its slot whose
                         signature is closest to the source's (7 x 5 positions, shortest move among equals,
                         +0.5 when it leaves the element it sat over), only when that is >= MIN_GAIN (0.12)
                         closer, never onto another content unit (pairs the source overlapped excepted);
                         panels re-wrap afterwards; the moves are in Placement.notes["slide"]
2b  quiet area           critic recipe "<role> onto the quiet area" (directive `quiet`): on a `cover`
                         picture it replaces the v9 `onto` move (the crop changes with the box, the pixels
                         under the source position are not the source's); on a `contain` picture it is a
                         second recipe after `onto`. backdrop.quiet_position samples the text's own
                         contrast estimate (engine/contrast.py: colour vs composited pixels, 25th
                         percentile, slices) at 5 x 5 positions over the picture (inside it when the text
                         was inside in the source, else anywhere with >= 30 % of the ink on it), on
                         canvas, not onto another unit, no straddle; best ratio (capped at 4.5), then the
                         shortest move; accepted when the ratio improves 1.2x or crosses the drop rule's 3.0
2c  judge term           score.py `read.backdrop` (weight BACKDROP_WEIGHT 3, taken proportionally from the
                         layout block so the sum stays 100, `active_weights`; the fitted file is untouched):
                         importance-weighted similarity (1 - distance / 0.6) of each headline / subhead / CTA
                         signature to the source's. Stage 1 measures both sides on the JSON composite (the
                         per-text statistics come free with the contrast estimate, the canvas median from a
                         24 x 24 composite); with CHAMELEON_BACKDROP_PIXELS=1 stage 2 measures both sides on
                         pixels (the source rendered once per task without text, ~70 ms, so off by default).
                         Off by default (§4).
3   patterns             analyze() -> Analysis.patterns (engine/patterns.detect_patterns on the free
                         decorative units whose on-canvas area is < 20 % of the canvas: bleeding photos and
                         washes are backdrops, not confetti): corners (each item near a different corner,
                         <= 4), edge (all within 20 % of one edge, spread >= 30 % of it), mirrored (pairs
                         mirrored about the vertical / horizontal centre line within 6 %, areas within
                         0.6x), diagonal (>= 3 centres on a line, minor / major variance <= 0.1, >= 15 deg
                         from both axes), else scatter. relayout.decorative_boxes places a pattern as a
                         whole in anchor_relayout / floorplan_relayout / structure_relayout: corners keep
                         the source's inset ratios, an edge run its edge and positions along it, a mirrored
                         pair its axis and distance, a diagonal its angle through the centroid and its
                         spacing ratio (scaled down until every item keeps its source bleed + 5 %), a
                         scatter its centre fractions; sizes x min(sx, sy) as before.
```

Pixels are a bonus, never a dependency: every map degrades to the JSON composite, every piece is
wrapped so a failure keeps the placement (`floorplan.slide_backdrop`, `relayout.decorative_boxes`).
Nothing reads element ids except to carry them through; `tests/test_metamorphic.py` (renamed
ids, shuffled order) passes unchanged.

## 2. What the signatures say (the three samples, JSON map)

| sample | text | lum | busy | glow | hue | over |
|---|---|---:|---:|---:|---:|---|
| Level 1 | headline | 0.23 | 3.8 | +0.07 | 352 | bg (gradient) |
| Level 2 | headline / subhead | 0.16 / 0.31 | 7.7 / 39.8 | −0.01 / +0.14 | 289 / 347 | bg |
| Level 2 | CTA label | 0.56 | 0.1 | +0.39 | 17 (orange) | cta_bg |
| Level 3 | ribbon label / legal | 0.43 / 0.27 | 25.8 / 43.4 | +0.26 / +0.10 | 2 / 271 | ribbon_bg / bg |

The pixel map and the JSON map agree: cell-luminance correlation 0.97 on Level 3, signature
lightness within 0.12 on every tested box (`tests/test_v10_backdrop.py`).

## 3. Pattern census (`eval/backdrop_report.py census`)

| set | designs | with a pattern | corners | edge | diagonal | mirrored | scatter |
|---|---:|---:|---:|---:|---:|---:|---:|
| eval corpus (Crello) | 450 | 15 | 3 | 0 | 0 | 1 | 11 |
| samples | 3 | 1 (Level 2) | 1 | 0 | 0 | 0 | 0 |

Items per pattern: corners 2, mirrored 2, scatter 4 (median). 370 of the 450 corpus designs
have no free decoration at all and 58 have one; patterns touch 3 % of the corpus. Edge runs and
diagonals exist in the detector and the tests but not in this corpus. Before the 20 % size cap
the census counted 22 designs: the extra 7 were bleeding photos the analyzer calls decorative
(`5d5ec02d`, `5ea00c67`: an 80–180 % photo and a sticker were "scattered" by their centre
fractions, which uncovered the canvas; both are hold-out designs and they drove the first
patterns ablation, hold-out agreement 0.613 → 0.610; §4 has the run after the cap).

## 4. Numbers

All runs on this tree with the shipped defaults unless a column says otherwise; "off" is
`CHAMELEON_BACKGROUND=0` (byte-identical to v9).

### 4.1 Eval slice with pixels (150 designs × 12 presets + designer siblings, `CHAMELEON_RENDER=1`, runs `bg_off` / `bg_on`)

| metric (2152 common cases) | off | on |
|---|---:|---:|
| winners with any hard defect | 7 | 7 (all headline / CTA below the floor on strips) |
| text overflow / unwanted overlap / off canvas / judge contrast fail | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| anchor fallback wins | 0 | 0 |
| judge score mean / p50 | 82.71 / 86.36 | 82.69 / 86.31 |
| every breakdown term | — | within 0.003 of off (`layout.spacing` 0.907 → 0.910 the largest) |
| designer-sibling centre error / reading-order tau / size rho | 0.1435 / 0.7211 / 0.7978 | 0.1442 / 0.7211 / 0.7981 |
| winner changed | | 102 cases (4.7 %); a "quiet area" repair won 1 |
| runtime p50 / p95 (4 workers, the designer run and the test suite alongside) | 0.63 / 1.42 s | 0.75 / 4.32 s (contention; §4.5 has the clean numbers) |

The slice has no text-over-picture contrast fail to begin with when pixels are on; the
no-pixel slice (4.2) is where the judge's contrast rule still bites.

### 4.2 Eval slice without pixels (300 designs, 4198 cases, `--no-render`, runs `bg_off_np` / `bg_on_np`)

| metric | off | on |
|---|---:|---:|
| winners with any hard defect (eval) | 13 | 13 (below floor; overlap / off canvas 0) |
| **judge contrast fail (winner)** | 11 | **10** |
| **anchor fallback wins** | 7 | **5** |
| judge-hard winners | 24 | 23 |
| judge score mean / p50 | 80.41 / 86.54 | 80.64 / 86.49 |
| designer-sibling centre error / tau / rho | 0.144 / 0.790 / 0.782 | 0.145 / 0.787 / 0.782 |
| winner changed | | 227 cases (5.4 %); a "quiet area" repair won 10 |
| runtime p50 / p95 | 0.36 / 1.09 s | 0.36 / 1.02 s |

### 4.3 Designer references (720 cases, `eval/compare_optimize.py --flag CHAMELEON_BACKGROUND`, no pixels, `docs/designer/compare/v10_backdrop`)

| | tuning (600) off | on | hold-out (120) off | on |
|---|---:|---:|---:|---:|
| designer agreement, mean | 0.608 | 0.607 | 0.614 | **0.615** |
| agreement ≥ 0.7 | 198 | 199 | 38 | 39 |
| centre error / reading-order tau | 0.140 / 0.702 | 0.141 / 0.702 | 0.140 / 0.727 | 0.141 / 0.725 |
| engine cases with a hard fail | 0 | 0 | 1 | 1 |
| designer wins by judge score | 165 | 163 | 29 | 29 |
| agreement up / down / unchanged | | 9 / 7 / 584 | | 2 / 4 / 114 |
| runtime p50 | 0.45 s | 0.47 s | 0.49 s | 0.52 s |

### 4.4 Per-piece ablations on the designer references (each piece off vs on, everything else on; `v10_ablate_*`)

| piece | tuning off → on | hold-out off → on | up / down (tuning, hold-out) | verdict |
|---|---:|---:|---|---|
| slide | 0.603 → 0.603 | 0.610 → 0.610 | 8 / 6, 2 / 2 | neutral on the metric; acts in 8.6 % of plan / structure candidates (26 % of tasks), median move 10 % of the width, 0.6 % of the height; rarely in the winner (4 of 2152 slice winners changed backdrop through it, 2 closer / 1 farther) |
| quiet area | 0.604 → 0.603 | 0.611 → 0.610 | 0 / 1, 2 / 2 | neutral; wins 10 no-pixel cases, takes 2 of the 7 fallback wins and 1 contrast fail |
| patterns (before the size cap) | 0.603 → 0.603 | **0.613 → 0.610** | 0 / 1, 2 / 9 | two hold-out designs whose "decorations" are bleeding photos (§3); the 20 % cap fixed it (4.3 is after the cap: hold-out 0.614 → 0.615) |
| judge term, weight 3 | **0.607 → 0.603** | 0.611 → 0.610 | 29 / 41, 8 / 9 | moves 14 % of the winners, net against the designer |
| judge term, weight 2 | 0.607 → 0.604 | 0.611 → 0.612 | 21 / 33, 7 / 5 | 9 % of the winners, still net against on tuning |
| judge term, weight 1 | 0.607 → 0.606 | 0.611 → 0.609 | 9 / 16, 1 / 3 | 4 % of the winners, same sign |

The ablation rows were measured before the pattern size cap (the first three with the judge
on at weight 3), so their absolute values sit below 4.3; the direction per piece is what they
are for.

### 4.5 Runtime (single process, `eval/backdrop_report.py runtime --limit 20`, pixels on: 23 designs × 12 presets)

| | off | on |
|---|---:|---:|
| runtime p50 | 0.626 s | 0.645 s (+0.019) |
| runtime p95 | 0.994 s | 1.011 s (+0.017) |
| mean | 0.611 s | 0.624 s |

276 tasks (the three samples + 20 corpus designs × 12 presets), pixels on, nothing else running.

Where the time goes (samples, per task, judge on for the measurement): the slide's map
~1 ms per plan candidate and the signatures ~2 ms per slid candidate (≈ 20–30 ms per task),
the quiet move ≈ 25 ms per repair that tries it, the judge term's canvas median ≈ 7 ms per
task; a pixel-vs-pixel judge term would add the source render, ~70 ms per task, which is why
`CHAMELEON_BACKDROP_PIXELS` is off.

### 4.6 Recommendation

Default on with the shipped piece defaults (slide, quiet area, patterns on; judge term off):
no hard fail moves on either slice, one fewer judge contrast fail and two fewer fallback wins on
the no-pixel slice, hold-out designer agreement 0.614 → 0.615 (tuning 0.608 → 0.607, within the
±0.002 noise of 9 / 7 changed cases), runtime p50 within the budget (4.5). The judge term stays
available (`CHAMELEON_BACKDROP_JUDGE=1`, `CHAMELEON_BACKDROP_WEIGHT`) for a fit on labels that
value the backdrop relation, which the designer-agreement metric does not.

## 5. By eye

- `docs/sanity_v10/backdrop_moves.png` (`eval/backdrop_report.py moves bg_off bg_on`): the ten
  cases of the slice whose headline / subhead / CTA landed on a different backdrop with the flag
  on, source | off | on, the text boxed in magenta. 46 texts changed backdrop between the two runs (signature distance ≥ 0.25);
  22 ended closer to the source backdrop, 21 farther, 3 the same. Only 4 of them changed inside
  an unchanged winner (the slide or the quiet move acting: 2 closer, 1 farther, 1 same); the
  other 42 are different winners, i.e. the judge re-ranking candidates whose geometry the slide
  or the patterns changed a little, and those land on either side. The sheet's rows: the
  "Charity Night" subhead back onto the dark photo (1.53 → 0.00), the Ecomix subheads back
  onto the dark panel they read against in the source, "Nothing haunts" (5889bcd3) with the
  subhead back on the plum panel (1.55 → 0.08), the Boynton story's subhead (1.37 → 0.45); the
  Skyscraper rows (59528ec0, 5888a295) are the farther kind, a different template winning.
- `docs/sanity_v10/<name>_sheet.png`: the three samples, the Boynton poster (`5947b6c3`), the
  Crello quote on a photo (`59b2651d`, "clothes don't make the man") and the pets poster
  (`5954bee3`, colour blocks with scattered squares) across the 12 presets, flag on.
  Level 2's two circles stay in their source corners (top-left, bottom-right) on every format,
  including the 160 × 600 strip and the 728 × 90 banner, where the old corner-offset mapping put
  both on the same side. The quote on a photo keeps its lines (an underline bar unit and the
  framing lines are attachments, not pattern items) and the quote stays in the dark lower half
  on every format. The pets poster's small yellow / plum squares keep their scatter
  (centre fractions) on the strips instead of piling into two corners.

## 6. Tests and goldens

- `tests/test_v10_backdrop.py` (38): map band / glow / busyness, tiny and off-canvas boxes,
  `over`, pixel-vs-estimate agreement, the slide toward a glow and its slot bounds, no slide on a
  flat backdrop, the flag off, the quiet move on a half-dark picture, the critic's recipe choice
  on `cover` vs the flag off, the five pattern kinds and their placement invariants, Level 2's
  corner pattern end to end, the judge term's weight accounting and direction, the contract on
  the samples, and the goldens.
- `tests/fixtures/golden_v5` is unchanged and still the flag-off reference
  (`tests/test_perceive.py` now pins `CHAMELEON_BACKGROUND=0`). `tests/fixtures/golden_v10`
  holds the **5 files whose default output deliberately changed**, all Level 2 (1080 × 1920,
  160 × 600, 1200 × 628, 1584 × 396, 728 × 90): only `deco_circle_1` / `deco_circle_2` move,
  because the corners pattern keeps each circle's inset ratio to its own corner instead of a
  px offset scaled by min(sx, sy). The 13 other goldens are byte-identical with the flag on.
  (With the judge term on, Level 3 → 728 × 90 also changed its winner: a near tie between
  "banner scale=1.5, fill" and "banner structure flip" flipped when the layout block was
  re-proportioned; that is one more reason the term is off.)

## 7. How to re-run

```bash
cd chameleon
CHAMELEON_RENDER=1 CHAMELEON_BACKGROUND=0 .venv/bin/python -m eval.run_eval --limit 150 --workers 4 --name bg_off
CHAMELEON_RENDER=1 CHAMELEON_BACKGROUND=1 .venv/bin/python -m eval.run_eval --limit 150 --workers 4 --name bg_on
.venv/bin/python -m eval.compare_runs bg_off bg_on
.venv/bin/python -m eval.compare_optimize --flag CHAMELEON_BACKGROUND --out ../docs/designer/compare/v10_backdrop
CHAMELEON_BACKGROUND=1 .venv/bin/python -m eval.compare_optimize --flag CHAMELEON_BACKDROP_JUDGE --out ../docs/designer/compare/v10_ablate_judge   # one piece
.venv/bin/python -m eval.backdrop_report census | moves bg_off bg_on ../docs/sanity_v10 | runtime --limit 20
CHAMELEON_RENDER=1 .venv/bin/python -m eval.sanity_sheet input/chameleon_sample_level2_core.json ../docs/sanity_v10 --prefix level2 --label "engine v10 (backdrop on)"
```

## 8. Limits

- **The cover crop (schema).** An image with `fit: cover` is cropped to its box by the renderer
  and the schema has no focal point or offset, so a text can only be laid *where the crop happens
  to be quiet*: the quiet-area move samples the candidate's own crop (through engine/contrast.py's
  fit model) rather than the source's pixels, which is why it replaces `onto` on `cover`
  pictures; it cannot ask for a different crop.
- **The judge term fights legitimate re-composition.** A headline that sat at the dark bottom
  of a vertical gradient and goes to the top of a banner reads against the bright part; the
  designer does that too. At weights 3 / 2 / 1 the term moved 14 % / 9 % / 4 % of the winners and
  the designer references liked the old winners better on balance. The signature is better used
  where it decides between two placements of the *same* layout (the slide, the quiet move) than
  between layouts.
- **Slots exist only in column placers.** The banner `_TextColumn` and `_Row` place their texts
  themselves and record no slot, so the slide never acts on a banner's text run (the strip has no
  vertical slack anyway) or on a CTA beside its chips.
- **The map is 24 cells wide.** A 12 px line on a 1920 px story is sampled by a single row of
  cells; the signature is the cell average, not the glyph's. The contrast rules keep their own
  32 × 8 sampling.
- **Patterns need a free decoration.** A decoration absorbed into a unit (an underline bar) is
  not an item; a lone one keeps the old mapping; a "decoration" that is really a bleeding photo
  (>= 20 % of the canvas on canvas) is a backdrop and keeps the old mapping too.
- **No render per candidate.** The slide and the quiet move use the JSON composite; the renderer's
  cost is mostly setup (~70 ms at any size), so a render per candidate would double the runtime.
