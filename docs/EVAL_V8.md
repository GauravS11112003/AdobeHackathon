# EVAL v8 — closing the picker gap (2026-10-25)

v6 and v7 established that the candidate set usually contains a layout close to the designer's reference
(best-candidate agreement ≈ 0.70) while the judge returns one at ≈ 0.60: *the judge, not the generator, is
the gap*. v8 works on the judge only. Nothing in the generators changed; one invariant was added to the
optimiser's refinement step. All numbers are no-pixel runs on macOS (fonts hint differently in the Linux
image, docs/DOCKER_CHECK.md).

Files: `engine/score.py` (`faith.rows`, `structure_prior` / `structure_survives`, `ROW_KEEP_*`,
`STRUCTURE_PRIOR`, `STRUCTURE_READ_MIN`, `SURVIVAL_TERMS`), `engine/resize.py` (prior wiring in `judge`,
`SCARCE_FONT` / `_spent_scarce_font` in `refine`), `engine/score_weights.json` (the fit, shipped; loaded by the
v2 `load_weights` mechanism, `CHAMELEON_SCORE_WEIGHTS=0` restores the hand weights), `eval/picker_gap.py`
(diagnosis + candidate dump), `eval/fit_judge.py` (the fit), `eval/rank_judge.py` (learned rankers),
`eval/calibrate.py` (`fit_weights(freeze=...)`), `tests/test_v8_picker.py`. Reports:
`docs/designer/compare/v8_picker_v7scorer/` (the v7 judge), `v8_picker_hand/` (v8 terms, hand weights; `FIT.md`
is the fit, `RANKER.md` the ranker comparison), `v8_picker/` (as shipped). Renders: `docs/sanity_v8/`.

## 1. Diagnosis (`eval/picker_gap.py`, the v7 judge)

One engine run per reference case (720 = 60 designs × 12 formats; the 10 sealed hold-out designs are reported
apart and were never fitted on). Every judged candidate is recorded with its breakdown, hard fails, penalty,
energy terms, seed family and designer agreement, so any re-weighting can be evaluated offline by re-ranking
(the judge's total is exactly `Σ W_k · bd_k − 1000 · |hard| − penalty`).

| | tuning (600) | hold-out (120) |
|---|---:|---:|
| winner agreement | 0.595 | 0.603 |
| best candidate agreement | 0.696 | 0.717 |
| best *clean non-fallback* candidate agreement | 0.663 | 0.652 |
| best − winner gap, mean / p50 | 0.101 / 0.067 | 0.114 / 0.086 |
| winner is the best candidate | 91 | 25 |
| judge missed by ≥ 0.02 / ≥ 0.10 | 415 / 233 | 81 / 56 |
| best candidate has a hard fail | 77 | 15 |

**Where the best candidate is.** In 293 of 600 tuning cases it is a plain anchor layout; in 105 of those it is
the anchor *fallback* (proportional copy, slid to the anchors), which only exists on ratio changes ≥ 1.75 and
pays the 18-point adaptation penalty by design. The "penalty" is the single largest vote for the judge's pick
in 104 missed cases, a hard fail in 72. By eye (renders in the session notes) the fallback is usually a tiny,
unreadable copy of the source — the agreement metric (0.35 position + 0.25 within-10 %) rewards
position-copying there, not quality — so the fallback policy stays and the honest ceiling for a re-weighting
is the best clean non-fallback candidate: **0.663 tuning / 0.652 hold-out**.

**Soft-term blame** (weight × (winner − best), mean over the missed cases; positive = the term voted for the
worse pick): read.size +1.54, layout.size +1.41, layout.fill +0.83, layout.spacing +0.56, layout.margins +0.54,
layout.alignment +0.49; faith.anchors −0.80 and faith.scale −0.32 voted for the better layout. Largest single
vote: penalty 104, hard 72, layout.spacing 53, faith.anchors 38, layout.fill 33, read.size 31, faith.order 27,
layout.size 22. By seed family of the missed pick: template+opt → anchor 91 cases (gap 0.185), template → anchor
39, anchor+opt → anchor 38 (0.082: the optimiser drifting off the designer's positions), template+opt →
structure 38 (0.149), template+opt → template 36. Banners and wide formats carry the largest gaps (0.117 /
0.111), squares the smallest (0.079).

## 2. Two new judge terms (source-relative, constants at module level)

**`faith.rows` — row integrity.** For every sibling row the analyzer found in the source (chips side by side:
badges, thumbnails, icons) the output's parts (visible boxes, one per part) must still read as one line:
consecutive parts overlap on the cross axis by ≥ `ROW_KEEP_OVERLAP` 0.5 of the smaller one (a row may become a
column on a strip), no gap wider than `ROW_KEEP_GAP` 1.5 × the larger part (or `ROW_KEEP_GROW` 1.25 × the
source's own gap ratio), cross extents within `ROW_KEEP_SPREAD` 0.25 (or the source's spread), gaps as even as
the source's plus `ROW_KEEP_CV` 0.15. A row that wraps into a *compact cluster* (2 + 1 on a banner) is kept too:
every part has a neighbour within the same gap allowance (nearest-neighbour Chebyshev gap over the parts'
thickness). Two chips pinned to opposite corners fail both tests. Per row `max(inline × gap × even, cluster) ×
spread`, importance-weighted, 1.0 with no rows; the source scores 1.0 on itself. Level 3 → 1080²: the
`chips=corner` plans score 0.00, the row plan wins (the v7 §7 follow-up).

**Structure prior.** When a preserve-structure candidate *survives* a big shape change (ratio change ≥
`ADAPT_RATIO` 1.75: no hard fail and its readability block — read.size, read.lines, read.presence — all ≥
`STRUCTURE_READ_MIN` 0.8), the template (floor plan) candidates and the structure variants that did not survive
pay `STRUCTURE_PRIOR` 3 points, like the adaptation / disruption penalties (outside the 0–100 breakdown, in
`Score.penalty`, note `structure_prior`; refined "+opt" copies and the pixel re-judging carry it through
`priors`). The survival test is what keeps it general: the first version taxed templates whenever any clean
structure candidate existed, and that let an 11 px headline (Eco-talks → 728×90, templates at 25–32 px), a
five-line headline and a 12 px product bottle (Level 3 → 728×90) win. A composition that only fits by halving
its copy has not survived; then the templates compete unpenalised.

**Refinement invariant (`resize.refine`).** A refined "+opt" layout is dropped when it shrank a headline / CTA
font that was already within `SCARCE_FONT` 1.25 × of its readable floor (the optimiser's aesthetic moves took an
8 px button to 7 px on the 728×90 banner, and the fitted judge accepted it).

Hand weights now sum to 100 with `faith.rows` 4 (read.lines 7 → 6, layout.balance 7 → 6, layout.spacing 6 → 5,
layout.fill 7 → 6).

## 3. The fit (`eval/fit_judge.py`)

Pairs from the 600 tuning cases of the hand-weight dump: the reference (scored by the same judge) beats every
non-fallback candidate with the same number of hard fails (6 877 pairs), two non-fallback candidates of one case
with the same hard count and agreement ≥ 0.05 apart (24 486), plus the 109 human labels re-scored under the
current judge (61 decisive / tie pairs; 53 "both bad" skipped). Each case's designer pairs sum to one unit of
weight and its candidate pairs to another. `eval/calibrate.py`'s pairwise logistic path (weights ≥ 1 % of the
sum, sum 100, hard fails and penalties pinned, free temperature), **L2 2.0 toward the hand weights**, and the
readability block **frozen at its hand weights** (`--freeze read.size,read.lines,read.contrast,read.presence`):
the references are legible by construction and cannot calibrate legibility against faithfulness; unfrozen, the
fit put faith.order at 23.7 and read.contrast at 12.9 (component agreement 0.50 — noise absorbing budget), and a
six-line headline beat a three-line one on the 90 px banner. L2 0.5 / 1 / 2 / 4 give hold-out 0.610 / 0.609 /
0.610 / 0.607 by offline re-ranking; L2 2 moves least for the same gain.

| component | hand | fitted | | component | hand | fitted |
|---|---:|---:|---|---|---:|---:|
| read.size | 11.0 | 10.6 | | layout.size | 8.0 | 6.5 |
| read.lines | 6.0 | 5.8 | | layout.cohesion | 4.0 | 2.8 |
| read.contrast | 8.0 | 7.7 | | faith.order | 12.0 | **17.7** |
| read.presence | 6.0 | 5.8 | | faith.anchors | 6.0 | 7.5 |
| layout.balance | 6.0 | 5.7 | | faith.hierarchy | 8.0 | 8.1 |
| layout.alignment | 7.0 | 5.1 | | faith.scale | 3.0 | 4.4 |
| layout.spacing | 5.0 | 3.9 | | faith.rows | 4.0 | 5.2 |
| layout.fill | 6.0 | 2.3 | | | | |
| layout.margins | 4.0 | 1.0 | | | | |

Pair agreement: hand 0.657 → fitted 0.701 in sample, 0.694 leave-one-design-out, hold-out pairs 0.632 → 0.683;
the 61 human pairs stay at 0.50 either way (too few, and the scorer never ordered them well). Offline re-ranking
of the dump: tuning 0.598 → 0.607 (0.606 leave-one-design-out over 25 folds), hold-out 0.603 → 0.610.

**Learned ranker (`eval/rank_judge.py`, 50 features: breakdown + 22 energy terms + family one-hot + opt /
fallback flags + penalty + log ratio change + target family; hard fails pinned, fallback policy kept).**
Leave-one-design-out on the tuning set / hold-out (final hand-weight dump, `v8_picker_hand/RANKER.md`):
linear-ext C=0.3 0.608 / 0.611, C=3 0.605 / 0.614; gbt-point depth 3 0.608 / 0.604, depth 4 0.609 / 0.608 (in
sample 0.617 / 0.623: the trees over-fit the tuning designs). The plain linear fit is 0.606 / 0.610, the hand
weights 0.598 / 0.603. Within the noise of 120 hold-out cases nothing beats the 16-weight linear judge (the
best alternative is +0.004 with 50 features and a second scoring path), so the linear weights ship and no
model file is added.

## 4. Off → on, the real runs (`v8_picker_v7scorer` → `v8_picker_hand` → `v8_picker`)

| | v7 judge | v8 terms, hand weights | **v8 shipped** |
|---|---:|---:|---:|
| **tuning (600)** agreement (winner) | 0.595 | 0.598 | **0.608** |
| best − winner gap, mean / p50 | 0.101 / 0.067 | 0.099 / 0.059 | **0.089 / 0.049** |
| winner is the best candidate | 91 | 104 | 115 |
| judge missed by ≥ 0.02 | 415 | 402 | 383 |
| winner with a hard fail | 1 | 1 | 1 |
| judge total, mean (own scale) | 89.2 | 89.1 | 88.9 |
| winner families (anchor / +opt, template / +opt, structure / +opt) | 65 / 97, 100 / 229, 48 / 61 | 65 / 98, 92 / 196, 63 / 86 | 76 / 99, 55 / 183, 94 / 93 |
| **HOLD-OUT (120)** agreement (winner) | 0.603 | 0.603 | **0.610** |
| best − winner gap, mean / p50 | 0.114 / 0.086 | 0.115 / 0.089 | **0.108 / 0.077** |
| winner is the best candidate | 25 | 25 | 22 |
| judge missed by ≥ 0.02 | 81 | 82 | 80 |
| winner with a hard fail | 1 | 1 | 1 |
| judge total, mean (own scale) | 81.2 | 81.2 | 81.0 |
| hold-out by target: tall / square / wide / banner | 0.633 / 0.758 / 0.606 / 0.497 | 0.634 / 0.758 / 0.604 / 0.497 | 0.637 / 0.758 / **0.621** / **0.507** |
| runtime p50, three samples × 12 presets, single process (s) | 0.35 (v7 report) | 0.29 | 0.29 |

The gain is where the diagnosis said it would be (wide and banner formats, structure and anchor seeds over
refined templates); squares and the tall formats are unchanged. The best-vs-chosen gap narrows by 0.012 on the
tuning set and 0.006 on the hold-out — measurable, not closed: the clean-candidate ceiling is 0.663 / 0.652.

**Eval slice** (`eval.run_eval --limit 300 --workers 4 --name v8 --no-render`, 4 198 cases in common with the v7
run, `eval.compare_runs v7 v8`):

| metric | v7 | v8 |
|---|---:|---:|
| any hard defect (n) | 23 | 23 |
| overflow / overlap / off canvas | 0 / 0 / 0 | 0 / 0 / 0 |
| headline or CTA below floor | 23 | 23 |
| judge contrast fail | 19 | 19 |
| anchor-fallback wins | 8 | 9 |
| smallest headline / CTA font p05 / p50 (px) | 12 / 57 | 12 / 55 |
| smallest font p05 (px) | 7 | 6 |
| faith.order / faith.anchors (winner mean) | 0.887 / 0.665 | 0.905 / 0.691 |
| layout.fill / spacing / margins | 0.851 / 0.923 / 0.956 | 0.822 / 0.901 / 0.928 |
| Crello designer siblings: reading-order tau / centre error | 0.772 / 0.151 | 0.790 / 0.145 |
| runtime p50 / p95 (s, 4 workers) | 0.34 / 0.93 | 0.34 / 1.05 |

No new defect; the judge-score means are not comparable across weight sets. The Crello siblings (an independent
designer signal) agree with the references. Sanity renders `docs/sanity_v8/`: Level 3 keeps its badge row in
every format (the square and Twitter post take the row plan again), Boynton takes the structure flip on the wide
and banner formats, Level 1 / 2 unchanged by eye.

## 5. Tests and goldens

`tests/test_v8_picker.py` (10): row term on a toy badge row (source scores 1, spread / scatter / lifted / uneven
lose, a tight column is kept), Level 3 square keeps the row, the prior rule and `structure_survives`, the prior
applied to templates and non-surviving variants (Level 2 → 1600×400), the shipped weights file, the fit tooling
on a toy dump. `tests/test_judge.py::test_judge_without_pixels_still_picks_a_clean_floor_plan` accepts the
structure strategy. `tests/fixtures/golden_v5`: the four Level 3 files that changed were regenerated
deliberately (flags off, optimiser off): 1080×1080 `square scale=1.3` → `anchor x1.12` and 1080×1920
`tall structure keep` → `anchor x1.25` (weights), 1200×628 `wide chips=corner` → `wide hero=stack` (row
term), 160×600 `tall scale=1.5` → `tall structure keep` (weights). Level 1 / 2 goldens and the 728×90 / 1584×396
Level 3 goldens are byte-identical to v7. Full suite: 444 passed, 0 failed, 5 skipped, 10 xfailed (one new, the
order relation of §7), 41 xpassed. The three `v8_picker*/candidates.jsonl` dumps are 47 MB each (every
candidate's design); keep the `.md` reports in git and regenerate the dumps on demand (§6, ~2 min each).

## 6. How to re-run

```
.venv/bin/python -m eval.picker_gap --workers 4 --out ../docs/designer/compare/v8_picker          # as shipped
CHAMELEON_SCORE_WEIGHTS=0 .venv/bin/python -m eval.picker_gap --workers 4 --out ../docs/designer/compare/v8_picker_hand
.venv/bin/python -m eval.fit_judge --dump ../docs/designer/compare/v8_picker_hand/candidates.jsonl \
    --freeze read.size,read.lines,read.contrast,read.presence --l2 2 --install
.venv/bin/python -m eval.rank_judge --dump ../docs/designer/compare/v8_picker_hand/candidates.jsonl
```

## 7. Known limits and follow-ups

- **The metric rewards the proportional copy.** The anchor fallback has the best agreement in 105 tuning
  cases and is unreadable in most of them; the gap figures therefore overstate what a picker can win. A
  readability-aware agreement (or human A/B on the 80 hold-out misses) is the next measurement step.
- **The fit cannot see legibility.** Readability weights are frozen; the only legibility signals in the fit are
  the hard floors and the sample tests. Human labels (61 usable pairs) are too few to fit; more labels on
  structure-vs-template pairs would let the readability block be fitted too.
- **Element-order sensitivity (fixed in v8.1).** A multi-element unit took its "primary" element from list
  position (`analyze._cluster` `ids[0]`; `engine/structure.py` reads `u.primary or u.ids[0]`), so a shuffled
  element list laid a structure candidate out differently, and with the v8 weights that candidate won on
  synthetic seed 11. `analyze._canon` now ranks elements by z, then reading position (y, x), then size (the id
  only for elements identical in all of those), and `_cluster` (member order, cluster order, holder / bar / root
  ties), `_panel_stacks` and `_merge_rows` use it. `test_element_order_does_not_matter` passes strictly for all
  12 corpus seeds; the three samples give identical output per id under three shuffles × six targets; no golden
  moved and the sanity renders are unchanged.
- **Offline re-ranking is optimistic by ≈ 0.001–0.003** against the real run (the stage-1 order decides which
  seeds the optimiser refines); the shipped column above is the real run.
- The optimiser still lowers agreement when it refines an anchor seed (anchor+opt → anchor, 39 missed cases,
  gap 0.08): `pres.drift` in the energy is the lever, not the judge.
