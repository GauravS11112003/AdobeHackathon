# EVAL v5 — generation fixes from the human labels

Generated 2026-10-24 from runs `v4` and `v5` (`chameleon/eval/data/runs/`), 6058 common cases (453 Crello
designs × 12 presets + 622 designer-sibling cases). Tables from `eval/compare_runs.py v4 v5` plus a per-case
script over both runs' `results.jsonl`. Sanity sheets: `docs/sanity_v5/` (Level 3, the Boynton poster and the
seven label designs below, each across the 12 presets; compare with `docs/sanity_v4/`).

## What changed (engine/floorplan.py, score.py, rectify.py, contrast.py, analyze.py, relayout.py, resize.py; tests/test_v5_labels.py)

Starting point: docs/LABELS_V1.md, round 1 of human labelling (109 pairs, 49 "both bad"). Half of the both-bad
pairs were eval-data artefacts; the other half were generation weaknesses, one mechanism each here. The named
designs are regression cases only; every rule is general.

1. **Banner cohesion** (Real Estate `5dc130c8abc8ea6d1cc3675d` → 728×90: bottle at the far left, wordmark at the
   far right, 80 % empty strip). `_plan_banner` spread the leftover width evenly between the items. Each gap is
   now capped at max(3 × base gap, 8 % of the width) and the clustered row is centred; the scorer's new
   `layout.cohesion` (weight 4; `read.size` 12 → 11, `layout.fill` 9 → 7, which rewarded the wide hull) is the
   widest empty stretch between the runs of visible boxes along either axis, free up to the same cap and 0 at
   half the span (fine print excluded, a bottom-anchored legal line is a convention).
2. **Importance tiers / water-filling** (Saturday eco talks `592d1fbc95a7a863ddcd9d6f` → 728×90: everything at
   2–10 px). Every plan item carries a `tier` (primary / hero / secondary / minor, from the nominal shrink speed,
   so `fill` variants keep it). When even the floors do not fit, `_largest_k` lowers floors tier by tier
   (`RESCUE_STEPS`: minor ×0.55, secondary ×0.55, minor, hero, secondary), never the primary tier and never below
   `ABS_MIN_FONT` 4 px; the k search then hands the room to headline / logo / CTA first. Two things made this
   bite on the strip: the banner text column now *flows* into several columns when one column cannot fit the
   strip at the floors (`_TextColumn._flow`, reading order kept), and an attachment never makes a text's
   footprint taller than its slot (the red bar beside the guest list is attached to "OUR GUESTS:" at 8.5 font
   units, so the CTA could never fit 81 px whatever the fonts). Headline 10 → 32 px, 0 hard fails.
3. **Rotated text** (Furniture Expo `5952645b95a7a863ddcde7c9` → 1584×396 / 728×90, NY Furniture Fair
   `58dbb7af95a7a863ddccf7ae` → 160×600). A vertical text in a column consumed column height equal to its
   length, so the k search was bound by it and everything collapsed to the floors (rails at 5 px). Now a vertical
   text in a column runs along at most `VERTICAL_LEN_SHARE` (0.5) of the column and wraps beyond (spine-label
   style); vertical texts that ran along the hero's sides in the source become *rails* (`_HeroRails`,
   `_beside`): one line each, sized against the hero's height (up to `RAIL_LEN_SHARE` 0.6 of the column), the hero
   gets the width they leave. Column plans keep the hero in its source reading position (texts that preceded it
   stay above it, the rest below). Rails 5 → 10 px, headline 12 → 13 px; Furniture Expo's rotated texts
   14/17 → 38/44 px, the "01" 107 → 193 px.
4. **Tall strips** (`w/h ≤ STRIP_MAX_RATIO` 0.5): font floors also relative to the width (`STRIP_FONT_FRAC`:
   headline 4.5 %, CTA 3.5 %, other 3 %, fine print 2.5 %, badge 2.2 %; the absolute 12 px still wins at 160 px,
   a 300×1050 strip gets 14 px), and `_absorb_leftover` grows the hero (`_Scaled.grow`, capped by the builder's
   ceiling and `HERO_MAX_SHARE` 0.55 of the height) when the width-bound text leaves the column short.
5. **Straddles** (Chandelier `5952591895a7a863ddcde4f1` → 1080², anchor candidates: dark text half over the
   dark photo, half on white). `contrast.estimate` also reports the 25th-percentile ratio per slice (`SLICES` 4
   along the long side) and caps `ratio` by the worst slice; `rectify.is_straddle` = one slice < 3, another ≥ 4.5
   and ≥ 4× the worst (a sharp edge, not a gradient's glow: without the ratio it fired on the brand gradient and
   anchor candidates with real collisions won). A straddling text that did not straddle in the source is a hard
   fail in `score_design` (`notes["straddles"]`), and `rectify.fix_straddles` (first two passes) slides the unit
   fully onto the side where the estimate reads, when that spot is free and on canvas. The square floor plan
   (text on white) now wins; the drop rule alone could never fire because the source text sits on the dark
   photo too (ratio 1.05).
6. **Graze rule** (Citation `595290bb95a7a863ddcdfcf0` → A4: "PRAY" over "When Life Is Great" in both
   candidates). The overlap exists in the *source*: font substitution wrapped "Life Is Great" onto three lines
   and 66 % of PRAY's ink is covered, so the source-relative rule carried it as designed. `rectify.text_graze`:
   a source text-on-text overlap thinner than `GRAZE_EM` (0.9) × the smaller font in either direction is a
   collision (lines that ran into each other), left out of the source-overlap table, so the output must not keep
   it; a lockup ("mega" over "SHOES") overlaps by a full line and is still kept.
7. **Layered panels** (Sparkling night `59b26b3c1350e8329300d498` → 1280×720: the offset double card became a
   stray bar plus a card). `analyze._panel_stacks`: rectangular panels of about the same size lying on each
   other (areas within 0.7, the smaller ≥ 0.6 inside the larger, same fill or ≥ 0.85 inside) are one
   `kind="stack"` PANEL unit; `relayout.stack_boxes` keeps each layer's inset from the hull (scaled by the padding
   scale) in `place_panels` and `grow_panels`. The double card survives in all 12 formats.

Also, found while fixing the above: text boxes in floor plans hug their wrapped lines (widest line + one space,
glyph width for negative letter spacing; wrap-safe under the renderer's character-based wrap, which counts the
trailing space before it breaks), so a centred text's box no longer starts off canvas and gets dragged into its
neighbour by the rectifier; the pre-judge `resolve_vertical_collisions` compares a sibling row per part (a
chip packed between the row's lines was pushed to the bottom corner onto the legal line on the Level 3
skyscraper); `_finalize` shrinks a rotated shape / image whose extent is larger than the canvas.

## Before / after (compare_runs, 6058 common cases)

| metric | v4 | v5 |
|---|---:|---:|
| any hard defect (%) | 0.64 | 0.63 |
| any hard defect (n) | 39 | 38 |
| text overflow (%) | 0.03 | 0.02 |
| text overflow (n) | 2 | 1 |
| headline/CTA below floor (%) | 0.56 | 0.56 |
| headline/CTA below floor (n) | 34 | 34 |
| unwanted overlap (%) | 0.07 | 0.07 |
| unwanted overlap (n) | 4 | 4 |
| off canvas (%) | 0.00 | 0.00 |
| off canvas (n) | 0 | 0 |
| judge contrast fail (%) | 2.26 | 2.05 |
| judge contrast fail (n) | 137 | 124 |
| anchor fallback wins (%) | 0.69 | 0.64 |
| anchor fallback wins (n) | 42 | 39 |
| errors (%) | 0.00 | 0.00 |
| errors (n) | 0 | 0 |
| judge score mean | 53.84 | 58.54 |
| judge score p50 | 85.07 | 86.89 |
| read.size | 0.910 | 0.923 |
| read.lines | 0.933 | 0.934 |
| read.contrast | 0.691 | 0.697 |
| read.presence | 0.886 | 0.886 |
| layout.balance | 0.881 | 0.899 |
| layout.alignment | 0.553 | 0.578 |
| layout.spacing | 0.756 | 0.767 |
| layout.fill | 0.867 | 0.862 |
| layout.margins | 0.928 | 0.938 |
| layout.size | 0.802 | 0.812 |
| layout.cohesion | nan | 0.932 |
| faith.order | 0.834 | 0.843 |
| faith.anchors | 0.600 | 0.595 |
| faith.hierarchy | 0.988 | 0.989 |
| faith.scale | 0.749 | 0.786 |
| runtime p50 (s) | 0.13 | 0.25 |
| runtime p95 (s) | 0.69 | 0.55 |
| smallest font p05 (px) | 6.0 | 7.0 |
| smallest font p50 (px) | 26.0 | 27.0 |
| smallest headline/CTA font p05 (px) | 12.0 | 12.0 |
| smallest headline/CTA font p50 (px) | 60.0 | 61.0 |
| gt centre error | 0.156 | 0.156 |
| gt reading-order tau | 0.779 | 0.771 |
| gt size rho | 0.790 | 0.788 |
| gt font ratio (median) | 1.049 | 1.054 |

### Defect rate by preset (%)

| preset | n | v4 any | v5 any | v4 below floor | v5 below floor | v4 overlap | v5 overlap | v4 contrast | v5 contrast |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A4 poster | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 1.8 |
| Facebook cover | 453 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 0.2 | 2.4 | 2.2 |
| Instagram portrait | 453 | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | 0.0 | 2.2 | 2.0 |
| Instagram post | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 1.8 |
| Leaderboard ad | 453 | 2.4 | 2.4 | 2.4 | 2.4 | 0.0 | 0.0 | 3.5 | 3.8 |
| LinkedIn banner | 453 | 0.4 | 0.4 | 0.4 | 0.4 | 0.0 | 0.0 | 2.6 | 2.2 |
| Pinterest pin | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.2 | 2.0 |
| Skyscraper ad | 453 | 4.4 | 4.2 | 4.2 | 4.2 | 0.2 | 0.2 | 4.0 | 3.3 |
| Story / Reel | 453 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 0.2 | 2.6 | 2.4 |
| Twitter / X post | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.1 | 1.1 |
| Wide web banner | 453 | 0.2 | 0.2 | 0.2 | 0.2 | 0.0 | 0.0 | 2.2 | 2.0 |
| YouTube thumbnail | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.1 | 1.1 |
| gt (designer siblings) | 622 | 0.5 | 0.3 | 0.2 | 0.2 | 0.2 | 0.2 | 1.6 | 1.3 |


### Winning strategy

| run | anchor | floor plan | anchor fallback | scale>=1.3 or fill | banner column plan | text=inline |
|---|---:|---:|---:|---:|---:|---:|
| v4 | 1699 | 4359 | 42 | 2323 | 203 | 517 |
| v5 | 1545 | 4513 | 39 | 2488 | 215 | 267 |

### The seven label cases

| case | preset | v4 winner | v5 winner | v4 min font / primary | v5 min font / primary | v4 judge | v5 judge | v4 defects | v5 defects |
|---|---|---|---|---:|---:|---:|---:|---|---|
| Real Estate (banner cohesion) | Leaderboard ad | banner scale=1.3 | banner scale=1.3 | 39 / 39 | 39 / 39 | 85.2 | 85.1 | - | - |
| Saturday eco talks (tiers, column flow) | Leaderboard ad | banner scale=1.5, fill | banner scale=1.5 | 2 / 7 | 8 / 10 | 68.6 | 84.3 | - | - |
| Furniture Expo (rotated text, flow) | LinkedIn banner | banner hero=right, text=inline | banner hero=right | 11 / 107 | 26 / 193 | 72.4 | 81.5 | - | - |
| Furniture Expo 728x90 | Leaderboard ad | banner hero=right, text=inline | banner hero=right, text=inline | 2 / 28 | 8 / 61 | 69.1 | 77.8 | - | - |
| NY Furniture Fair (rails) | Skyscraper ad | tall scale=1.15 | tall spacing=1.3 | 5 / 12 | 10 / 12 | 85.4 | 94.7 | - | - |
| Chandelier (straddle) | Instagram post | anchor x1.12 scale=2.400 | square hero=left | 24 / 41 | 25 / 43 | 89.1 | 83.5 | - | - |
| Citation PRAY (graze) | A4 poster | anchor x1.25 scale=5.167 | anchor x1.4 scale=5.787 | 83 / 83 | 93 / 93 | 94.8 | 91.1 | - | - |
| Sparkling night (layered panels) | YouTube thumbnail | wide hero=stack, scale=1.3 | wide scale=1.5 | 26 / 40 | 31 / 46 | 86.8 | 88.1 | - | - |

### Defects new in v5 / gone since v4 (cases)

- **below_floor**: new 0, gone 0
- **overlap**: new 2, gone 2; new: `5909b06c95a7a863ddcd2f5e|Skyscraper ad` (tall spacing=1.3), `5f464b6fa637ee11e3023d22|Facebook cover` (wide chips=corner)
- **offcanvas**: new 0, gone 0
- **overflow**: new 1, gone 2; new: `5953577595a7a863ddce0dad|Instagram portrait` (anchor x1.25 scale=1.406)
- **judge_contrast**: new 5, gone 18; new: `58ac689d95a7a863ddcc7eda|Wide web banner` (banner scale=1.15), `58b4323f95a7a863ddcc9b34|Leaderboard ad` (banner chips=stack), `5d5ec02dcf657b21effed4f3|Facebook cover` (wide hero=stack), `5d68df79e79a2a634ea55321|Leaderboard ad` (banner text=inline), `5f562c10a637ee11e36d83d1|Leaderboard ad` (banner chips=stack)
- **fallback**: new 8, gone 11; new: `5888d91a95a7a863ddcc2a53|Facebook cover` (anchor fallback scale=1.126), `5952654195a7a863ddcde88c|Instagram post` (anchor fallback scale=0.360), `59b26bab1350e8329300d51a|Twitter / X post` (anchor fallback scale=1.500), `5d5ec02dcf657b21effed4f3|LinkedIn banner` (anchor fallback scale=0.503), `5d5ec02dcf657b21effed4f3|Story / Reel` (anchor fallback scale=1.149), `5d5ec02dcf657b21effed4f3|Wide web banner` (anchor fallback scale=0.508), `5f562c10a637ee11e36d83d1|Twitter / X post` (anchor fallback scale=0.469), `5f562c10a637ee11e36d83d1|YouTube thumbnail` (anchor fallback scale=0.375)

## Reading

- **Hard defects**: 39 → 38. Below-floor and overlap counts are unchanged (34 / 4), off canvas 0, overflow
  2 → 1; the two new overlap cases and the one new overflow are matched by two / two that went away. Judge
  contrast fails 137 → 124 (18 gone, 5 new: banners whose text lands on a same-coloured area, the known pattern).
  Anchor-fallback wins 42 → 39.
- **Judge score** mean 53.8 → 58.5, p50 85.1 → 86.9. Up: balance (+0.018), alignment (+0.025), spacing,
  margins, size, faith.order (+0.009), faith.scale (+0.037, hugging boxes and rails scale things more
  uniformly). Down: layout.fill −0.005 (its weight dropped, and spread rows no longer score it), faith.anchors
  −0.005, gt reading-order tau 0.779 → 0.771 (the hero's reading position now follows the source in column plans,
  which the designer siblings do not always do).
- **Sizes**: smallest font p05 6 → 7 px, p50 26 → 27 px; smallest headline / CTA p05 12 (unchanged floor),
  p50 60 → 61 px. The strips are where it shows: the seven cases' smallest font 2–5 px → 8–10 px.
- **Strategy**: floor plans win 4359 → 4513 (anchor 1699 → 1545, the straddle rule rejects anchors that
  slide text across a photo edge); `text=inline` banner wins 517 → 267 (the flowing column makes the default
  banner plan competitive on strips).
- **Runtime**: p50 0.13 → 0.25 s (the straddle estimate on every candidate and the multi-column flow), p95
  0.69 → 0.55 s. Still far under any plausible budget.
- Level 3 and Boynton (`docs/sanity_v5/`): the same layouts as v4 in every format except the Level 3 skyscraper
  (headline 12 → 13 px, subhead 8 → 10 px, badge labels 6 → 4 px: the subhead takes the room before the chips,
  see the follow-ups) and the Boynton banners (`chips=stack` instead of `text=column`, the date sticker keeps its
  size).

## Follow-ups

1. Vertical text on 90 px banners is still 3 px (Furniture Expo → 728×90): only un-rotating it would help, and
   rotation is not listed as immutable but it changes the design. Decide.
2. Chip labels on the Level 3 skyscraper sit at the 4 px bottom (v4: 6 px): a per-role share floor for chips, or
   relaxing secondary before minor in the second rescue step, would keep 6 px.
3. `fix_straddles` only slides along the crossing element's edges; a text that straddles two edges stays.
4. The straddle estimate runs on every candidate and pass; caching the composited layers per candidate would
   win back most of the runtime p50.
