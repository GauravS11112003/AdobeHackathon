# EVAL v7 — seed, then optimise an energy of design principles (2026-10-25)

Until v6 the engine picked the best of a fixed set of templates: nothing ever moved an element to
improve a layout. v7 adds the retargeting loop of O'Donovan, Agarwala and Hertzmann ("Learning Layouts
for Single-Page Graphic Designs", TVCG 2014): read the perceptual relations of the source (alignment
groups, proximity groups, containment, symmetry, importance, reading order), define one energy over a
layout (hard penalties + preservation of those relations + aesthetic terms), and walk the top seeds
down that energy with the source as prior. The judge still has the last word: every refined layout
competes as a candidate of its own.

Modules: `engine/relations.py`, `engine/energy.py`, `engine/optimize.py`; wiring in `engine/resize.py`
(`refine`, `CHAMELEON_OPTIMIZE`, `CHAMELEON_OPTIMIZE_K`); data and fitting in `eval/perturb_designer.py`,
`eval/calibrate.py --energy`; comparison in `eval/compare_optimize.py`; tests in
`tests/test_v7_optimize.py`. Renders: `docs/sanity_v7/` (optimiser on) and `docs/sanity_v7/off/`.

## 1. Relations (`engine/relations.py`)

`relations(analysis, elements, canvas)` computes, on the units' *visible* boxes (painted text, rotated
extents, like the scorer):

| relation | definition |
|---|---|
| alignment | single-linkage clusters per line type (left / cx / right / top / cy / bottom) within `max(2 px, 1 % of min(W, H))`; groups of ≥ 2, the shared line types per pair, and *near misses* (consecutive clusters closer than 3 × the tolerance, unless the pair aligns on another line of the same axis) |
| proximity | the nearest neighbour below / to the right (overlap on the other axis ≥ 50 % of the smaller span) when the gap is ≤ `max(0.6 × the smaller extent, 2.5 % of the span)` |
| containment | the smallest content unit holding ≥ 80 % of a unit, else the panel holding ≥ `PANEL_CARRY` of it |
| symmetry | centred on a canvas axis (centre within 2 % of the span); mirror pairs about either axis |
| importance, reading order, anchors, size, fonts | the analyzer's importance; `score.reading_order`; `_anchors`; linear size share; largest font per unit |

The same function runs on the source (cached as `source_relations`) and on any output of it, so the
graphs compare key by key: `lost_alignments` (per axis), `broken_proximity` (graded: 0 at the threshold,
1 at an excess gap of half the span or when the pair is no longer stacked / in a row), `order_discordance`
(importance-weighted flipped pairs), `lost_containment`, `lost_symmetry`. `Relations.to_dict()` is JSON.

## 2. Energy (`engine/energy.py`)

`E = Σ_k W_k · t_k + 1000 · |hard|`, every term a cost in [0, 1]. Hard terms mirror the judge rule for
rule (off canvas beyond the source's bleed allowance, measured overflow, image aspect drift, headline /
CTA below the floor, unwanted collision under `rectify.OverlapRules`, the contrast drop rule, a new
straddle); the v6 helpers of score.py / rectify.py are called when present, so energy and judge never
disagree on what a defect is. Soft terms:

| group | terms |
|---|---|
| preservation (source as prior) | `pres.align`, `pres.prox`, `pres.order`, `pres.hier`, `pres.anchor`, `pres.contain`, `pres.symmetry`, `pres.scale`, `pres.drift` (displacement / resize against the proportional copy of the source, counting in full for a same-shape target and fading to 0 at the judge's `DISRUPT_RATIO`) — each weighted by the importance of the units involved |
| aesthetics | `aes.align`, `aes.near_miss`, `aes.balance`, `aes.spacing` (white space *between* proximity groups), `aes.cohesion`, `aes.fill`, `aes.margins` (text and small pieces, fine print excluded), `aes.hier` (headline ≥ 1.4 × the next text), `aes.read`, `aes.lines`, `aes.contrast` (JSON estimate + busyness), `aes.size`, `aes.presence` |

Component functions are reused from `engine/score.py` wherever they exist (`_balance`, `_alignment`,
`_cohesion`, `_fill`, `_margins`, `_hierarchy`, `_anchor_keep`, `_order`, `_scale_consistency`,
`_primary_size`, `_presence`). `Layout` is the mutable unit-level state (built on `rectify._Rectifier`:
groups move and scale as one piece, fonts follow a scale and are re-fitted); it caches text layouts and
the contrast estimate per text keyed by its ink box and the non-text elements under it, so one evaluation
costs 0.3–1.5 ms. Weights live in `energy.WEIGHTS`; `engine/energy_weights.json` (the fit, §5) overrides
them when present; `CHAMELEON_ENERGY_WEIGHTS=0` restores the hand weights.

## 3. Optimiser (`engine/optimize.py`)

Greedy best-improvement local search, units most important first. Moves per unit: snap one of its six
lines to the nearest line of another unit (≤ 6 % of the span away), nudge ± 2 % of the span on either axis,
grow / shrink 10 % about the unit's anchored point (images keep their aspect, fonts follow), re-wrap a
single text at 0.75 × / 1.3 × its width (height from the measurer, the text's own alignment decides which
edge stays), swap places with the next unit of its stack or row. A move is kept only if it lowers the energy
and adds no hard fail the seed did not have. Budget: `max_evals` = 160 energy evaluations (deterministic;
no randomness, fixed order), at most 3 sweeps; `time_cap_s` = 1.5 s is a safety net only.

## 4. Wiring (`engine/resize.py`)

After the no-pixel stage, the top K = 3 non-fallback seeds are optimised; each changed result is scored by
the judge and added as "<seed> +opt" with the seed's strategy and prior, dropped if the judge finds a hard
fail the seed did not have; then the usual sort and the pixel re-judging of the top 3. `CHAMELEON_OPTIMIZE=0`
disables the step with byte-identical output (test). Targets of the source's shape (`ratio_change` ≤ 1.02:
identity, pure scale) are not refined: a finished design is not re-arranged for nothing.

## 5. Fitting the weights

### 5.1 Data

- 2787 PRISM-style perturbation pairs (`eval/perturb_designer.py`) from 684 designer references (batch
  one 240 + batch two 444 present at the time): per reference one of each — *misalign* (one member of an
  alignment group slides 4 % off its line), *shrink_text* (a headline / CTA at 0.55 × its font),
  *break_prox* (one neighbour of a proximity pair moves 12 % away), *swap_order* (two neighbours exchange
  places), *busy* (a text is centred on the hero). Reference > perturbed copy, weight 0.3.
- 684 designer pairs: reference vs the engine's output for the same source and target, reference > engine,
  weight 1 (`eval/data/labels.designer.jsonl`).
- 300 harness perturbation weak pairs (v5 labels) and 114 human labels (`eval/data/labels.jsonl`, 61 decisive).
- Pairs of the 10 sealed hold-out designs are never fitted and reported separately. Pairs whose two sides
  differ in hard-fail count are left out as well: the hard terms are pinned at 1000, so such a pair says
  nothing about the soft weights, and a label that contradicts a hard rule (a designer who layers text on
  the hero on purpose) only drives the logistic temperature to zero (the first fit did exactly that).

### 5.2 Result

Fit on the 50 non-hold-out designs (batch one + 30 of batch two); `--l2 0.5`, weak pairs x 0.3, designer
pairs x 1, floor 1 % per term (`.venv/bin/python -m eval.calibrate --energy --install`; the fit is
`eval/data/energy_weights.json`, the shipped copy `engine/energy_weights.json`). Agreement = share of decisive
pairs ordered like the label (a predicted tie counts half).

```
designer pairs: 600; the reference trips a hard rule in 47 (kinds {'floor': 6, 'collide': 46, 'contrast': 6}), the engine in 1: those pairs are unwinnable for any soft weights and are left out of the fit
pairs fitted: 2459 (552 designer, 57 human, 1850 weak); skipped: {'both_bad': 52, 'hard fails differ (reported, not fitted)': 895}
agreement with decisive labels (n=2442): hand weights 0.7666, fitted 0.7981 (in sample), fitted leave-one-design-out 0.6489 over 60 folds
  designer: n=552 hand 0.2663 fitted 0.3859
  human: n=40 hand 0.575 fitted 0.55
  weak: n=1850 hand 0.92 fitted 0.9265
HELD OUT (never fitted; n=476 decisive): hand 0.7542, fitted 0.792
temperature 0.0818, loss 0.6712, floor 1% of the sum; frozen at the hand weight (no evidence): none

| term | hand | fitted | change | pairs where it differs | agrees with label |
|---|---|---|---|---|---|
| pres.align | 8.0 | 10.0 | +2.0 | 945 | 0.80 |
| pres.prox | 7.0 | 11.9 | +4.9 | 934 | 0.72 |
| pres.order | 10.0 | 18.1 | +8.1 | 981 | 0.78 |
| pres.hier | 6.0 | 6.7 | +0.7 | 327 | 0.68 |
| pres.anchor | 5.0 | 1.0 | -4.0 | 867 | 0.60 |
| pres.contain | 4.0 | 10.3 | +6.3 | 307 | 0.74 |
| pres.symmetry | 3.0 | 1.0 | -2.0 | 442 | 0.67 |
| pres.scale | 3.0 | 1.0 | -2.0 | 589 | 0.37 |
| pres.drift | 8.0 | 7.7 | -0.3 | 793 | 0.73 |
| aes.align | 6.0 | 1.0 | -5.0 | 1698 | 0.59 |
| aes.near_miss | 3.0 | 1.0 | -2.0 | 1016 | 0.47 |
| aes.balance | 5.0 | 2.5 | -2.5 | 2393 | 0.53 |
| aes.spacing | 4.0 | 1.0 | -3.0 | 897 | 0.50 |
| aes.cohesion | 3.0 | 1.0 | -2.0 | 654 | 0.58 |
| aes.fill | 5.0 | 1.0 | -4.0 | 974 | 0.44 |
| aes.margins | 3.0 | 1.0 | -2.0 | 347 | 0.42 |
| aes.hier | 3.0 | 4.6 | +1.6 | 480 | 0.74 |
| aes.read | 7.0 | 4.8 | -2.2 | 963 | 0.67 |
| aes.lines | 3.0 | 2.0 | -1.0 | 63 | 0.21 |
| aes.contrast | 5.0 | 7.9 | +2.9 | 438 | 0.61 |
| aes.size | 4.0 | 2.5 | -1.5 | 1058 | 0.66 |
| aes.presence | 3.0 | 2.1 | -0.9 | 244 | 0.36 |

```

Reading the table. The designer references lose to the engine's own output on almost every *regularity*
term (even spacing, margins, number of alignment lines, uniform scale, symmetry, balance, fill) and win on
reading order, proximity, containment, hierarchy, contrast and presence; the fit moves the weight there
(pres.order 10 → 18, pres.prox 7 → 12, pres.contain 4 → 10, aes.contrast 5 → 8, pres.drift ≈ 8) and sends
the regularity terms to the 1 % floor. The leave-one-design-out figure is below the hand weights because the
labels are close to inseparable for a linear energy (loss 0.67 vs 0.69 for a flat prediction): in some folds the
fit degenerates to a flat predictor whose "ties" count half. The sealed hold-out, never fitted, agrees with the
fitted weights more than with the hand weights (0.754 → 0.792 over 476 decisive pairs), which is the number
that justified installing them. Human labels (40 decisive pairs, two engine candidates each) barely move.
The reference itself trips a hard rule of the judge in 47 of 600 tuning cases (46 collisions, 6 floors, 6
contrast drops): deliberate layering the v6 allowances do not yet cover; those pairs cannot be won by weights.

## 6. Verification

### 6.1 Designer references: optimiser off vs on (`docs/designer/compare/v7_optimizer/SUMMARY.md`)

`.venv/bin/python -m eval.compare_optimize`: every reference (720 = 60 designs × 12 formats) run with
`CHAMELEON_OPTIMIZE=0` and `=1` on the same code (engine v6 + v7), judged without pixels.

| metric | fit designs (600 cases) off → on | HOLD-OUT (120 cases, never tuned on) off → on |
|---|---:|---:|
| designer agreement, mean (winner) | 0.587 → 0.595 | 0.595 → 0.603 |
| cases with agreement ≥ 0.7 | 172 → 179 | 34 → 35 |
| reading-order tau vs the reference | 0.651 → 0.665 | 0.688 → 0.716 |
| centre error (fraction of the diagonal) | 0.148 → 0.145 | 0.148 → 0.146 |
| engine cases with a judge hard fail | 1 → 1 | 1 → 1 |
| designer wins by judge score | 167 → 127 | 31 → 27 |
| judge score, mean | 88.2 → 89.2 | 79.9 → 81.2 |
| energy, mean (lower is better) | 17.9 → 15.4 | 26.1 → 23.2 |
| refined candidate is the winner | 387 / 600 | 78 / 120 |
| runtime p50 / p95 (s, one process) | 0.09 / 0.33 → 0.38 / 0.83 | 0.12 / 0.35 → 0.46 / 0.83 |

Agreement rises in 219 cases, falls in 153, is unchanged in 228 (hold-out: 41 / 35 / 44). References with a hard
fail under the current judge: 47 of 600 and 12 of 120 (deliberate layering and bleed). The largest agreement
*drops* are all cases where a `structure` seed (the v6 preserve-structure family, close to the designer) loses
the final judging to a refined template seed; the largest *gains* are refined anchor seeds on small shape
changes. Per-format tables in `docs/designer/compare/v7_optimizer/SUMMARY.md`, per-case rows in
`results.jsonl`.

### 6.2 Full eval (`eval/data/runs/v7_off`, `v7_hand`, `v7`; `eval/compare_runs.py`)

`eval/run_eval.py --workers 4 --no-render --name v7` against the gap session's committed `v6` run (same
code with `CHAMELEON_OPTIMIZE=0`), 6058 common cases (450 Crello designs × 12 presets + 622 designer-sibling
targets). Full table: `.venv/bin/python -m eval.compare_runs v6 v7`.

| metric | v6 (optimiser off) | v7 (optimiser on) |
|---|---:|---:|
| any hard defect (n of 6058) | 30 | 28 |
| text overflow / unwanted overlap / off canvas | 1 / 1 / 0 | 0 / 0 / 0 |
| headline or CTA below floor | 28 | 28 |
| judge contrast fail | 44 | 40 |
| anchor-fallback wins | 14 | 13 |
| judge score mean / p50 | 75.8 / 88.6 | 77.7 / 89.5 |
| layout.alignment / margins / size / cohesion | 0.580 / 0.942 / 0.825 / 0.936 | 0.613 / 0.961 / 0.841 / 0.943 |
| faith.order / anchors | 0.867 / 0.627 | 0.885 / 0.649 |
| read.contrast / faith.scale | 0.693 / 0.795 | 0.687 / 0.789 |
| Crello designer siblings: reading-order tau / centre error | 0.775 / 0.151 | 0.783 / 0.150 |
| smallest headline-CTA font p05 / p50 (px) | 12 / 61 | 12 / 62 |
| runtime p50 / p95 (s, 4 workers) | 0.25 / 1.04 | 0.32 / 0.87 |
| refined candidate is the winner | – | 3934 / 6058 (65 %) |

No regression on any defect count (two fewer cases with a defect, the single overflow and the single overlap
gone, contrast fails 44 → 40, off canvas stays at 0; a first run had 5 off-canvas cases from rotated text boxes
grown past the canvas, since fixed by the `bleed` constraint). Judge score +1.9 mean; the biggest component
gains are alignment, margins, order and anchors; contrast and uniform scale give back a little, as the fitted
weights predict. Runtime: the single-process figure in §6.1 is the honest one (p50 0.09 → 0.38 s per task);
the harness figures were taken on a shared CPU. The hand-weight variant (`CHAMELEON_ENERGY_WEIGHTS=0`) was
not re-run after the final fit.

### 6.3 Sanity renders (`docs/sanity_v7/`)

`docs/sanity_v7/<design>_sheet.png` (optimiser on) next to `docs/sanity_v7/off/<design>_sheet.png` (same code,
`CHAMELEON_OPTIMIZE=0`) for Level 3, the Boynton poster and the Charity Night poster (`5888cec2…`, the
designer-reference design; `5888d7d2…` "Corporate Charity Night" was rendered first by mistake and replaced).

- **Level 3.** The refined candidates win 10 of 12 formats. Most changes are small (headline grown one step,
  logo nudged, badges snapped to a shared line). Two formats change plan: the square and the Twitter post now
  take `chips=corner +opt` over the row plan, because the optimiser repaired the corner plan's spacing defect
  (layout.spacing 0.00 → 0.82) and the judge's `layout.size` prefers its bigger headline (0.97 vs 0.82). By eye
  the v5/v6 badge row is tidier; that is a judge preference (size over row integrity), not an optimiser defect.
- **Boynton.** Visually the same layouts; nudges of a few per cent. The square picks a different anchor seed
  (x1.25) whose rectified lockup already has "IS IN DANGER" above "THE OCEAN" (the seed, not the optimiser:
  the source overlaps the two lines; see the gap session's lockup rules). Text-to-text swaps are forbidden in
  the optimiser since an early version flipped exactly this pair.
- **Charity Night.** Same structure in every format; the optimiser mostly grows the photo and tightens the
  header. The 1080² and 1080×1350 versions enlarge the photo under the subhead, which the v6 layering rules
  allow (the source layered that role over the photo).

## 7. Known limits and follow-ups

- **The judge, not the energy, picks the final layout.** Where a refined corner plan beats a row plan it is the
  judge's `layout.size` term speaking; a row-integrity term (a sibling row stays a row) in the judge would settle
  it. Likewise the structure family's seeds sometimes lose to a refined template seed with lower designer
  agreement (the largest drops in the comparison are all "structure → <template> +opt"); refining the structure
  seeds more aggressively, or a small prior for them, is the next lever.
- **Budget.** Winners use the full 160 evaluations; the refinements that win come from seed ranks 0 / 1 / 2 in
  30 / 15 / 10 of 55 cases, so K=3 earns its keep. Cost is ~+0.25 s per task (p50 0.09 → 0.37 s on the
  references, single process). `max_evals` and `CHAMELEON_OPTIMIZE_K` are the knobs; the Docker eval decides.
- **Energy vs designer.** With the regularity terms at the floor the fitted energy is mostly "keep the source's
  reading order, grouping, containment and contrast, do not drift"; the designer references are still preferred
  to the engine in only 39 % of the fitted pairs. The missing terms are compositional (bands, grids, white-space
  shape), which the structure family addresses on the generation side.
- Move set: no rotation changes, no per-member edits inside a group, no font change without a box change.
  Re-wrap applies to single texts only (a host unit's attached bars keep their offsets through scaling because
  the scale step is snapped to an integer font).
