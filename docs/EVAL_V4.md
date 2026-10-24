# EVAL v4 — size ambition: the engine uses the canvas when it has room

Generated 2026-10-24 from runs `v3` and `v4` (`chameleon/eval/data/runs/`), 6058 common cases (453 Crello
designs × 12 presets + 608 designer-sibling cases). Tables from `eval/compare_runs.py v3 v4` and a per-case
script over the two runs' `results.jsonl` + `outputs/`. Sanity sheets: `docs/sanity_v4/` (Level 3 and the
Boynton poster across the 12 presets; compare with `docs/sanity_v3/` and `docs/rival_tailsgit/`).

## What changed (engine/candidates.py, floorplan.py, score.py; tests/test_v4_size.py)

Starting point (docs/COMPETITORS.md head-to-head): our v3 output was clean but conservative. On Level 3 at the
wide formats tailsgit's headline, CTA and hero were visibly larger and its badges ran in a row while we stacked
chips in a column and left the canvas empty. Cause: the banner plan is one row `logo | hero | text | chips | CTA`
and on 1584×396 the row is width-bound at a shrink factor k ≈ 0.53 (headline 16 px, hero 165 px); the
scorer's `read.size` saturates at the source-proportional size, so nothing rewarded using the room.

1. **Candidates.** Every family tries `scale_bias` 1.3 and 1.5 (`BOLD`, `BOLDER`) and a *fill* variant
   (`PlanOptions.fill`: one shrink speed for every item, so the k search becomes a single global-scale search
   from 1.5× the proportional size down, gk7494 / tailsgit style). Banners also try `text_flow="column"`: the
   wide plan on a banner canvas ≥ 160 px tall (hero at full height beside one column with logo, headline,
   subhead, chip row, CTA, legal) and keep the v3 stacked chip column as `chips="stack"`. Anchor boost 1.4
   added; `MAX_CANDIDATES` 18 (9.3 judged per task on average, was 6.4).
2. **Floor plans.** A scaled unit's ideal is at least `Metrics.prop` (sqrt of the area ratio) × the bias
   (share-of-canvas ideals alone left a 6 % CTA at its floor on a 396 px banner). The wide plan keeps the hero
   at full size (v3 shrank it with the column's k although it never competed for the column's height) and
   tries hero width shares 0.45 / 0.36 / 0.28, keeping the first whose column stays within 90 % of the best k;
   its fit test also requires the headline on ≤ 3 lines. `_Chips` direction `auto` packs rows first and columns
   only when the rows do not fit the height (banner default). A text line wider than the canvas at its slot's
   wrap width shrinks below its floor instead of overflowing (the fitter shrank it anyway after the clamp, but
   attached bars kept the bigger font's offsets). Bisection steps 14 → 10 (fonts are integers).
3. **Scorer.** New `layout.size` (weight 8): headline / CTA font and hero / logo linear size relative to
   `AMBITION` (1.2) × the proportional size, clamped at 1 so nothing past the cap is rewarded; read.size 12,
   read.lines 7, layout.balance 7, faith.scale 3 keep the weights at 100. `layout.fill` is now 60 % content hull
   + 40 % ink density (`GOOD_DENSITY` 0.30): the hull alone saturated for a thin row across a banner. Fine print
   is left out of the spacing chains (a bottom-anchored legal line is a convention, it cost hero-beside-column
   layouts 3 points). Hard fails, the contrast drop rule, the source-relative rules and the penalties are unchanged.

## Before / after (compare_runs, 6058 common cases)

| metric | v3 | v4 |
|---|---:|---:|
| any hard defect (%) | 0.66 | 0.64 |
| any hard defect (n) | 40 | 39 |
| text overflow (%) | 0.05 | 0.03 |
| text overflow (n) | 3 | 2 |
| headline/CTA below floor (%) | 0.56 | 0.56 |
| headline/CTA below floor (n) | 34 | 34 |
| unwanted overlap (%) | 0.05 | 0.07 |
| unwanted overlap (n) | 3 | 4 |
| off canvas (%) | 0.00 | 0.00 |
| off canvas (n) | 0 | 0 |
| judge contrast fail (%) | 2.24 | 2.26 |
| judge contrast fail (n) | 136 | 137 |
| anchor fallback wins (%) | 0.71 | 0.69 |
| anchor fallback wins (n) | 43 | 42 |
| errors (%) | 0.00 | 0.00 |
| errors (n) | 0 | 0 |
| judge score mean | 51.16 | 53.84 |
| judge score p50 | 82.45 | 85.07 |
| read.size | 0.891 | 0.910 |
| read.lines | 0.936 | 0.933 |
| read.contrast | 0.693 | 0.691 |
| read.presence | 0.864 | 0.886 |
| layout.balance | 0.879 | 0.881 |
| layout.alignment | 0.550 | 0.553 |
| layout.spacing | 0.703 | 0.756 |
| layout.fill | 0.887 | 0.867 |
| layout.margins | 0.929 | 0.928 |
| layout.size | nan | 0.802 |
| faith.order | 0.840 | 0.834 |
| faith.anchors | 0.604 | 0.600 |
| faith.hierarchy | 0.985 | 0.988 |
| faith.scale | 0.737 | 0.749 |
| runtime p50 (s) | 0.17 | 0.13 |
| runtime p95 (s) | 0.43 | 0.69 |
| smallest font p05 (px) | 6.0 | 6.0 |
| gt centre error | 0.152 | 0.156 |
| gt reading-order tau | 0.781 | 0.779 |
| gt size rho | 0.784 | 0.790 |
| gt font ratio (median) | 1.000 | 1.049 |

### Defect rate by preset (%)

| preset | n | v3 any | v4 any | v3 below floor | v4 below floor | v3 overlap | v4 overlap | v3 contrast | v4 contrast |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Facebook cover | 453 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 0.2 | 2.4 | 2.4 |
| Instagram post | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 2.0 |
| Leaderboard ad | 453 | 2.4 | 2.4 | 2.4 | 2.4 | 0.0 | 0.0 | 3.8 | 3.5 |
| LinkedIn banner | 453 | 0.4 | 0.4 | 0.4 | 0.4 | 0.0 | 0.0 | 2.2 | 2.6 |
| Skyscraper ad | 453 | 4.4 | 4.4 | 4.2 | 4.2 | 0.2 | 0.2 | 4.2 | 4.0 |
| Story / Reel | 453 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 0.2 | 2.6 | 2.6 |
| Twitter / X post | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.1 | 1.1 |
| Wide web banner | 453 | 0.2 | 0.2 | 0.2 | 0.2 | 0.0 | 0.0 | 1.8 | 2.2 |
| YouTube thumbnail | 453 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.1 | 1.1 |
| gt (designer siblings) | 622 | 0.5 | 0.5 | 0.2 | 0.2 | 0.0 | 0.2 | 1.6 | 1.6 |


### Size metrics (per-case script over both runs' outputs)

| metric | v3 | v4 |
|---|---:|---:|
| smallest font p05 (px) | 6.0 | 6.0 |
| smallest font p50 (px) | 24.0 | 26.0 |
| smallest headline/CTA font p05 (px) | 12.0 | 12.0 |
| smallest headline/CTA font p50 (px) | 55.0 | 60.0 |
| font scale vs canvas, mean (1 = sqrt(area ratio)) | 0.945 | 1.023 |
| headline font / (source font x sqrt(area ratio)), median | 0.995 | 1.028 |
| headline font / (source font x sqrt(area ratio)), p25 | 0.870 | 0.910 |
| headline font / (source font x sqrt(area ratio)), p75 | 1.104 | 1.148 |
| headline ratio >= 1.0 (%) | 43.1 | 56.2 |
| layout.fill mean | 0.887 | 0.867 |
| layout.size mean | nan | 0.802 |
| read.size mean | 0.891 | 0.910 |
| read.presence mean | 0.864 | 0.886 |
| layout.spacing mean | 0.703 | 0.756 |
| layout.margins mean | 0.929 | 0.928 |
| layout.balance mean | 0.879 | 0.881 |
| score_soft mean (no hard penalties) | 82.04 | 84.56 |
| runtime mean (s) | 0.20 | 0.22 |
| candidates per task, mean | 6.4 | 9.3 |

### Winning strategy / plan family

| run | anchor | floor plan | anchor fallback | scale>=1.3 or fill variant | banner column plan | chips=stack |
|---|---:|---:|---:|---:|---:|---:|
| v3 | 1775 | 4240 | 43 | 86 | 0 | 0 |
| v4 | 1657 | 4359 | 42 | 2323 | 203 | 86 |

Reading: fonts kept pace with the canvas in v3 (mean font scale 0.945 of sqrt(area ratio)) and now slightly
exceed it (1.023); the median headline sits at 1.03× the proportional size (p25 0.91, p75 1.15) and 56 % of
cases have it at or above proportional (43 % before). The smallest headline / CTA font p50 rose 55 → 60 px, the
smallest font of any text p50 24 → 26 px, p05 unchanged at 6 px (legal copy on the 160×600 / 728×90 strips, the
same rescue mode as v3). Hero / logo presence 0.864 → 0.886. `layout.fill` *mean* fell 0.887 → 0.867 because the
term changed (the density half rarely saturates), not because content shrank; the soft score (no hard penalties)
rose 82.0 → 84.6. Against the designer's own versions the median font ratio moved 1.000 → 1.049 and the size-order
agreement (rho) 0.784 → 0.790; centre error and reading-order tau are within noise (0.152 → 0.156, 0.781 → 0.779).
A `scale_bias ≥ 1.3` or fill variant wins 2323 of 6058 cases (86 before); the banner column plan 203.

### Hard defects, case by case

- any hard defect 40 → 39, overflow 3 → 2, headline / CTA below floor 34 → 34, off-canvas 0 → 0, aspect 0 → 0.
- unwanted overlap 3 → 4: `592801a995a7a863ddcd8e70|gt:592813f3…` (1080² → 419×298). Every candidate has a hard
  defect there; the `anchor x1.25` output is byte-identical to v3's (two body texts overflow their boxes under the
  current measurer; the v3 run was measured before the painted-box rules) and the new `anchor x1.4` has one
  overflow plus one collision, which the eval's overlap metric now counts. Not a layout regression, a tie among
  defective candidates decided differently.
- judge contrast fails 136 → 137 (5 new, 4 gone; the drop rule is unchanged). All five new ones are the known
  "text that sat on the photo lands on the canvas" pattern (v3 follow-up 1): `5914233995…` and `5f562c10…` on the
  LinkedIn / Wide web banners (the v3 winner `spacing=0.75` now also fails there, so the stacked-chips variant
  wins with the same defect), `5914245995…` Facebook cover (same candidate name, sizes changed). Two skyscraper
  cases (`59b26b29…`, `59b27f4d…`: all-white copy on a 5:1 gradient photo that shrinks to a sliver on a 160 px
  column) were below-floor + contrast in an intermediate run and are contrast-only now.
- Runtime: mean 0.20 → 0.22 s, p50 0.17 → 0.13 s (the no-render first stage is cheaper than before thanks to the
  shorter bisection), p95 0.43 → 0.69 s (banners and wide canvases with many text units: 16–17 plan variants and
  up to three hero-share searches). With pixels on, the sanity sheets show 0.3–1.6 s per task (v3: 0.13–0.55 s).

## Sanity sheets (docs/sanity_v4 vs docs/sanity_v3 and docs/rival_tailsgit)

Level 3 (`level3_sheet.png`): LinkedIn 1584×396 and Wide web 1600×400 now use the hero-beside-column plan:
headline 16 → 28 px on two lines, CTA label 13 → 14 px, product 165 → 356 px (full height), the four badges in
one row under the subhead, legal at the bottom, 0 hard fails. Against tailsgit's renders (`level3_vs_tailsgit_2.png`)
the type is at least as large and the composition the same (hero on one side, column on the other); tailsgit's
1600×400 has a hard fail, ours none. Facebook cover 820×312: hero 94 → 221 px, subhead 5 → 10 px, badges beside
the CTA. YouTube 1280×720 and Twitter 1600×900 stay on the stacked plan (headline 29 / 37 px, hero 229 / 286 px);
the hero-beside variants are now clean three-line layouts and score within 2 points, the judge still prefers the
stack's alignment. Leaderboard 728×90: unchanged type (10 / 8 px), hero 50 → 61 px, chips in a row.

Boynton (`boynton_sheet.png`): the same layouts as v3 in every format; the second-largest text (the "17" date
sticker / "IS IN DANGER") is now 1.5–2× larger (e.g. 1280×720: 44 → 64 px, 1600×900: 55 → 81 px, 160×600:
19 → 26 px), bars stay under their headings (test in tests/test_v3_rules.py still passes).

## Tests

`tests/test_v4_size.py` (11 tests): Level 3 → 1584×396 headline ≥ 1.5 × the v3 size (16 px) and CTA ≥ 13 px,
hero ≥ 1.5 × 165 px, badges in one row, no hard fail; every wide preset keeps the headline ≥ 0.9 × proportional;
the new variants exist and dedupe on a 90 px strip; the fill variant uses one shrink speed; scaled ideals ≥
proportional × bias; `_Chips` auto packing; `layout.size` rewards bigger primaries, saturates at the cap, and a
hard-failing candidate never beats a clean one; `layout.fill` counts density. Full suite: 275 passed, 1 skipped,
7 xfailed, 32 xpassed (tests/test_vlm.py and tests/test_role_model.py, owned by other sessions, not run).

## Follow-ups

1. Zone-aware placement (the five new contrast cases and the 130-odd old ones): keep text on the photo it sat on,
   or pick the column side by the background's luminance under the text. Largest remaining judge fail.
2. The judge prefers the stacked plan on 16:9 Level 3 by ~2 points (alignment / spacing) although the
   hero-beside layout reads better by eye; the hand-label calibration (S2a) should include that pair.
   `layout.size` is a new scorer key: `score.load_weights` ignores a fitted file that lacks it.
3. p95 runtime: cache `_TextColumn` width searches across the banner line policy, or drop the two least useful
   banner variants (`hero=right, text=inline`, `text=inline, spacing=0.75`) if 0.7 s matters.
