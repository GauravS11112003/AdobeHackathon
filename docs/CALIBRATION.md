# Scorer calibration on human labels (workstream S2, 2026-10-24)

The judge in `engine/score.py` ranks candidates with hand-set component weights (`WEIGHTS`). S0 found that
no local VLM ≤ 2B can tell a good render from a bad one (docs/VLM_BENCH.md), so the scorer is calibrated
the way tailsgit did it (docs/COMPETITORS.md): humans label pairs, a pairwise logistic regression fits the
weights. Everything here is a dev tool; the engine only gains an optional weights file.

## Pieces

| file | what |
|---|---|
| `chameleon/tools/playground.py` → **http://localhost:8765/label** | the labelling page |
| `chameleon/eval/labeling.py` | pair sampling, the label store, the perturbation weak labels |
| `chameleon/eval/calibrate.py` | the fit, agreement reports, writes `engine/score_weights.json` |
| `chameleon/engine/score.py` `load_weights()` | loads the file at import when present and complete |
| `chameleon/eval/data/labels.jsonl` | human labels (gitignored with the rest of eval/data) |
| `chameleon/eval/data/labels_weak.jsonl` | 300 weak labels from the perturbation bootstrap |
| `chameleon/eval/data/score_weights.weak.json` | weights fitted on the weak labels alone (see "Status") |
| `chameleon/tests/test_calibrate.py` | 13 offline tests |

## Labelling page

Start the playground (`cd chameleon && .venv/bin/python tools/playground.py`, or `--port 8766`; the
`.claude/launch.json` entries `playground` / `playground-8766`) and open `/label`.

- Each screen: the source thumbnail, the case (title, source shape → preset, shape change), and two renders
  **A** and **B** of the same source at the same target. Names and scores are hidden until you decide
  (checkbox or key `r` reveals them, with the per-component differences).
- Decide with the buttons or keys **a** / **b** (A or B better; arrow keys work too), **t** tie, **x** both
  bad, **s** skip, **z** undo. The next pair is fetched while you look at the current one, so a decision
  shows the next pair at once (a fresh pair costs ~0.3–1.5 s: engine run + three renders).
- Progress on the top right: labels, designs, how often the scorer agreed with you, labels per target
  family, decisions by kind. The line under the buttons reveals what you just labelled and whether the
  scorer agreed.
- Mode **two candidates of the engine** (default): a random eval design (the 450 Crello conversions plus the
  three samples) × a preset, with the target family and the source family that have the fewest labels so
  far favoured. The engine runs (`resize_with_candidates`, engine modules reloaded first), and two
  non-fallback candidates are drawn with probability ∝ exp(−|Δtotal| / 5): close scores are the informative
  ones. Pairs where only one side has a hard fail are never offered (the scorer already orders those);
  clean–clean pairs are preferred 85:15 over pairs where both sides have hard fails. A/B order is random.
- Mode **two harness runs**: the same case from two runs under `eval/data/runs/` (for example `v2` vs
  `v3`), outputs read from `outputs/`, breakdowns from `results.jsonl`, same exclusion and closeness rules.
  Use it to label an engine change against the previous version.
- Every label is one JSON line in `eval/data/labels.jsonl`: `case_key`, `design_id`, `preset`, `target`,
  families, `ratio_change`, both sides (`id`, `name`, `strategy`, `total`, `hard`, `penalty`, `breakdown`,
  and the full `design` so the pair can be re-scored under future metrics), `decision`
  (`a` / `b` / `tie` / `both_bad`), `kind` (`human` / `weak`), `seconds` to decide, timestamps. Undo removes
  the last line.

What to look for when labelling (the brief's rubric): no unwanted collisions, everything readable, on brand,
looks intentional for *this* canvas. Prefer **tie** when you honestly cannot tell and **both bad** when
neither is shippable; both are kept but do not enter the weight fit.

## Calibration

```
cd chameleon && .venv/bin/python -m eval.calibrate            # fit, report, write engine/score_weights.json
.venv/bin/python -m eval.calibrate --dry-run                  # report only
.venv/bin/python -m eval.calibrate --no-weak                  # human labels only
```

Model: the scorer's total is `T = Σ_k W_k · bd_k − 1000 · |hard| − penalty`, so for a pair
`T_A − T_B = W · Δbd − 1000 · Δhard − Δpenalty`, and the fit is

`P(A better) = σ( s · ( W · Δbd − 1000 · Δhard − Δpenalty ) )`

- weighted logistic regression (L-BFGS on the analytic gradient, scipy; dev only);
- `W ≥ 0`, sum fixed at 100 like the hand weights, every weight floored at `--floor` 5 % of the sum
  (`w = floor + span · softmax(z)` makes both exact);
- hard fails and the adaptation / disruption penalties are **pinned** (not fitted);
- one free temperature `s`;
- decisions: `a` → y = 1, `b` → y = 0, `tie` → y = 0.5 (soft target), `both_bad` → skipped;
- weak labels count `--weak-weight` 0.3 each, human labels 1.0;
- `--l2` 0.5 pulls toward the hand weights (stability with few labels);
- a component that differs in fewer than `--min-pairs` 5 decisive pairs is **frozen at its hand weight**:
  no evidence, no change (otherwise the sum constraint would quietly shrink terms the labels never touched);
- labels whose breakdown predates a component (older harness runs) count that component as "no difference".

Reported: agreement of the hand weights and of the fitted weights with the decisive labels (in sample),
**leave-one-design-out** agreement (each design's pairs held out in turn; `--max-folds` 60 groups designs
when there are more), and per component the number of decisive pairs where it differs and how often the
side with the higher value is the labelled winner (the "agrees with label" column: the component's own
vote, independent of the weights).

Output `engine/score_weights.json`: `{"weights": {...}, "temperature": s, "meta": {counts, agreements,
per-component table, hand weights, parameters}}`. `engine/score.py` loads it at import when every component
has a finite non-negative value (`WEIGHTS.update(...)`; `HAND_WEIGHTS` keeps the defaults);
`CHAMELEON_SCORE_WEIGHTS=0` ignores the file, `CHAMELEON_SCORE_WEIGHTS=<path>` reads another one. A missing
or malformed file leaves the hand weights untouched, so the shipped engine is unchanged until the file is
copied into `engine/` (the Dockerfile's `COPY engine/` then ships it).

## Weak labels (bootstrap)

`.venv/bin/python -m eval.labeling --n 300 --seed 0 --fresh` writes `eval/data/labels_weak.jsonl` in ~45 s
(rendering off): for a balanced sample of design × preset, the engine's winner (clean, non-fallback) against
the same layout with 40 % of the content units shifted by 30 % of the canvas (the probe from
`tools/vlm_bench.py`; a unit moves as far as the canvas allows, groups move as one). Up to five seeds are
tried to find a perturbation that adds no hard fail, because the soft terms are what the fit learns from; the
last try is kept anyway. Both sides are scored without pixels; A/B order is random; the decision is the
unperturbed side. Corpus written: 300 pairs over 226 designs, targets tall 78 / banner 78 / wide 72 /
square 72; 137 perturbed sides still ended with a hard fail (a collision), 163 differ in soft terms only.

## Status (2026-10-24)

Fit on the weak labels alone (`eval/data/score_weights.weak.json`, 300 pairs, 0 human):

| | hand weights | fitted (in sample) | fitted, leave-one-design-out |
|---|---|---|---|
| agreement with the 300 weak labels | 0.957 | 0.967 | 0.967 |

| component | hand | fitted | pairs where it differs | agrees with label |
|---|---|---|---|---|
| read.size | 12.0 | 11.7 (frozen) | 0 | – |
| read.lines | 7.0 | 6.8 (frozen) | 0 | – |
| read.contrast | 8.0 | 5.0 | 109 | 0.77 |
| read.presence | 6.0 | 5.8 (frozen) | 0 | – |
| layout.balance | 7.0 | 5.0 | 297 | 0.73 |
| layout.alignment | 7.0 | 13.8 | 230 | 0.80 |
| layout.spacing | 6.0 | 5.0 | 217 | 0.65 |
| layout.fill | 9.0 | 5.0 | 110 | **0.37** |
| layout.margins | 4.0 | 5.0 | 96 | 0.95 |
| layout.size | 8.0 | 7.8 (frozen) | 0 | – |
| faith.order | 12.0 | 11.4 | 208 | 0.83 |
| faith.anchors | 6.0 | 5.0 | 221 | 0.74 |
| faith.hierarchy | 8.0 | 7.8 (frozen) | 0 | – |
| faith.scale | 3.0 | 5.0 (frozen, at the floor) | 0 | – |

(The hand weights sum to 103 at the time of writing, so the frozen ones are scaled by 100/103.)

Reading: the perturbation only moves things, so the six size / line / presence terms never differ and stay
at their hand weights. Among the position terms, *alignment* and *margins* are the most reliable single
signals of "the designer's layout" vs "the shifted one", *fill* votes the wrong way (a shifted unit often
spreads the content hull wider, so fill rewards the perturbed side), and the fit moves weight from fill /
balance / contrast to alignment. The hand weights already agree with 95.7 % of these pairs; the weak labels
are a sanity floor, not the calibration. **The real calibration needs the ~150 human pairs**; the page is
ready for them.

**The fitted file is not in `engine/`** on purpose: with weak labels only, it would change the engine's
ranking (fill 9 → 5, alignment 7 → 14) on evidence from one perturbation type, and while it exists it
silently overrides every hand edit to `WEIGHTS` (the size-ambition work was editing them at the same
time). Activate with `cp eval/data/score_weights.weak.json engine/score_weights.json` or, after labelling,
by running `eval.calibrate` without `--dry-run`. `CHAMELEON_SCORE_WEIGHTS=eval/data/score_weights.weak.json`
tries it without copying.

## Procedure for the 150 human labels

1. `cd chameleon && .venv/bin/python tools/playground.py`, open http://localhost:8765/label.
2. Label ~150 pairs in the default mode (about 20–30 min; the sampler balances formats on its own; use
   `t` and `x` freely). Optionally 30–50 more in "two harness runs" mode comparing the latest run with the
   previous one.
3. `.venv/bin/python -m eval.calibrate --dry-run` and read the report: fitted LODO agreement must beat the
   hand weights' agreement on the human pairs (`human labels only` line) before the weights are worth
   shipping. If a component's "agrees with label" is below 0.5 on ≥ 30 pairs, the metric itself is wrong,
   not its weight: fix the metric in `score.py` first.
4. `.venv/bin/python -m eval.calibrate` writes `engine/score_weights.json`; re-run `tests/` and a
   `eval.run_eval` smoke to see what changed; commit the file with the labels' summary in the message.
5. Re-run the calibration whenever a scorer component is added or renamed: labels keep both designs, so
   `eval/remeasure.py`-style re-scoring can refresh the breakdowns (not automated yet).

## Known gaps

- Candidate pairs can look identical at thumbnail size when the two placements differ by a few pixels; the
  closeness sampling makes that more likely. `t` or `s` and move on; a minimum visual-difference filter
  would be the next improvement.
- Labels from the "two runs" mode carry the run's component set (older runs lack `layout.size`); the fit
  treats the missing component as no difference.
- `label_stats()` re-reads the whole file on every call; fine for thousands of labels.
- The temperature `s` is reported but unused by the engine (only the ordering matters).
