# Critic loop — defect-driven regeneration (v9, 2026-10-25)

Until v8 the judge loop generated a fixed set of candidates (anchor variants, floor-plan
templates with `PlanOptions`, the preserve-structure family, the optimiser's refinements) and
kept the best. Its verdict never fed back into generation: when every candidate shared a
failure, the engine shipped the least bad. On the 6058-case v7 eval run 67 winners carried a
hard fail and 13 were the anchor fallback; every one of those was a *shared* failure, i.e. a
defect of the generator, not of one template:

| shared failure (v7 run, winner has it) | cases | typical cause |
|---|---:|---|
| headline / CTA contrast collapsed | 39 | the text sat on a plate, a card or the hero in the source; the plans put it on the white canvas, or a card grew over it |
| headline below the readable floor | 21 | a letter-spaced display word (tracking 1–1.6 em) on a 160 px strip; a vertical spine headline on a 90 px banner; the headline-largest cap then drags every other text down with it |
| CTA below the floor | 7 | a pill label on a strip, or an unbreakable URL label |

`engine/critic.py` closes the loop: it reads the judged candidates, names the shared failure
(`diagnose`) and turns it into *repair recipes* — knob overrides for the generator and
*directives* that `resize.realize` applies to the materialized elements before the rectifier.
`candidates.generate_repairs` builds up to 6 new candidates per round from them; `resize.repair`
runs up to 2 rounds; the judge scores the repairs with the rest and still has the last word.

## 1. Design

```
stage 1: generate_candidates -> realize -> score                      (as before)
critic : for round in 1..CRITIC_ROUNDS:
             stop if best is clean and total >= CRITIC_TARGET
             diagnoses = critic.diagnose(judged)                      shared hard fails (none clean) | weak terms (best clean)
             repairs   = candidates.generate_repairs(diagnoses, seeds) <= 6, deduped against everything judged
             realize(placement, directives) -> score -> judged += repairs
             seeds for the next round: repairs that removed what they were built for, then the best
optimiser: refine the top-3 seeds (repairs included)                  (v7, unchanged)
pixels   : re-judge the top-3 with a render                           (v3, unchanged)
```

Why before the optimiser: the critic fixes what the generator got wrong everywhere (a
structural defect no local move repairs); the optimiser then refines the top seeds locally and
runs once, on better seeds. Diagnosing after the optimiser would cost a second refinement pass
for the repairs and the optimiser never changes which defects are shared.

### 1.1 Diagnosis (`critic.diagnose`)

* Pool = the real (non-fallback) candidates. When none is clean, every hard fail of the best
  candidate and every kind at least `SHARE_MIN` (50 %) of the pool shows is a diagnosis
  (`below_floor`, `contrast_drop`, `straddle`, `collision`, `off_canvas`, `overflow`, keyed by
  the units in the judge's hard-fail string). When at least one is clean, the `TOP_SOFT` (3) best
  clean candidates are checked term by term: a term that all three score below `TYPICAL[term]`
  (the 25th percentile of the v7 winners) is a `weak:<term>` diagnosis — only for terms that
  have a repair mechanism.
* Each diagnosis carries the candidates showing it; a hard recipe is applied to those seeds only.

### 1.2 Recipes (general rules on roles and relations, never ids or sizes)

| diagnosis | recipe (label) | plan knobs | directive |
|---|---|---|---|
| below_floor (headline / CTA) | *to floor* | — | `floor`: raise the text to its role floor, re-wrapped on ≤ 3 lines (CTA: 1) within the content width; tracking is given up (down to 0) before size; a vertical spine that cannot run along the canvas lies down (`level`); a pill label reshapes its pill (source padding scaled, trimmed to the room); attached bars taller than the canvas are trimmed; the unit is `protect`ed in the rectifier; `cap_floor`: the headline-largest cap never pushes another text under its own floor |
| | *secondary copy yields* | `rescue=True` | the same directives |
| | *tight, shy plan* | `spacing=0.75, scale_bias=0.85` | the same directives |
| contrast_drop / straddle | *on its plate* | — | `backing`: the flat shape / panel whose fill the text read against in the source (ink ≥ 50 % on it, WCAG ≥ 3) covers the text again with the source's padding; an occluding panel between them is slid off or cut back |
| | *on the picture* | — | `onto`: the text moves to where it sat on the hero / picture it was layered on (≥ 30 % of its ink), fitted inside it |
| | *off the <unit>* | — | `off`: slide the text off a picture / plate it did not sit on in the source, shortest on-canvas move |
| straddle | *tighter column* | `spacing=0.75` | — |
| collision (a, b) | *colliders apart* | `spacing=0.75` | `shrink`: the less important unit ×0.8 |
| | *badges to the corners* (a badge involved) | `chips=corner` | — |
| off_canvas | *unit back on canvas* | — | `shrink` ×0.85 |
| overflow | *text refitted* | — | `refit` |
| weak:faith.anchors | *pin to source edges* | — | `pin`: units that hugged an edge in the source move back to it |
| | *badges to the corners* | `chips=corner` | — |
| weak:read.contrast | the contrast recipes for the worst headline / CTA / subhead | | |
| weak:read.lines | *headline on fewer lines* | — | `widen` |
| weak:read.presence, weak:layout.size | *bolder, fill* | `scale_bias=1.3, fill=True` | — |
| weak:layout.spacing, weak:layout.cohesion | *tighter plan* | `spacing=0.75` | — |
| weak:faith.rows (v8 term) | *badges in a row* | `chips=row` | — |

Plan-knob recipes re-run the floor plan of up to two floor-plan seeds with the knobs replaced
(`dataclasses.replace`); directive-only recipes reuse the seed's placement. Repairs are named
`<seed> +fix:<label>`, keep the seed's strategy and prior, and are deduped on (placement key,
directives) against everything the judge has seen. Round 2 seeds from the repairs that removed
the diagnosed defect first, so a repair that traded a floor fail for a collision gets the
collision recipe next.

### 1.3 Two judgement calls

* **Tracking.** A letter-spaced display word keeps its tracking while the line fits and gives
  it up (down to none) before it gives up the readable size. Letter spacing is not among the
  brief's fixed properties (content, font family, asset pixels); a designer drops the tracking
  of a display word on a narrow strip. The judge only sees the result.
* **Levelling.** A vertical spine headline whose line cannot run along a 90 px banner at the
  floor is set horizontal. Rotation is geometry ("move the furniture"); the alternative was a
  2 px headline.

## 2. Numbers

All runs on macOS, no pixels (`--no-render`), optimiser on, the v8 judge with its shipped weights. "off" is
`CHAMELEON_CRITIC=0`, which is byte-identical to the loop without the repair step (tests/test_critic.py; the
18 golden flags-off fixtures pass with the flag pinned to 0 in `tests/test_perceive.py`).

### 2.1 Eval slice: 300 designs × 12 presets + designer siblings (4198 cases)

`eval/run_eval.py --limit 300 --workers 4 --no-render` as `critic_off` / `critic_on3`;
`.venv/bin/python -m eval.compare_runs critic_off critic_on3` for the full table.

| metric | critic off | critic on |
|---|---:|---:|
| winner with a judge hard fail | 42 | **24** |
| cases with no clean candidate (judge) | 42 | 24 |
| anchor-fallback wins | 9 | **7** |
| eval metric: headline / CTA below floor (n) | 23 | 13 |
| eval metric: judge contrast fail (n) | 19 | 11 |
| text overflow / unwanted overlap / off canvas | 0 / 0 / 0 | 0 / 0 / 0 |
| new hard-fail winners introduced | – | **0** |
| judge score mean / p50 | 75.91 / 86.47 | 80.41 / 86.54 |
| faith.anchors / layout.spacing / layout.size | 0.691 / 0.901 / 0.831 | 0.702 / 0.908 / 0.834 |
| read.contrast | 0.686 | 0.688 |
| Crello designer siblings (562): reading-order tau / centre error | 0.790 / 0.145 | 0.790 / 0.144 |
| smallest headline-CTA font p05 / p50 (px) | 12 / 55 | 12 / 56 |
| a "+fix" candidate is the winner | – | 672 (16.0 %) |
| runtime p50 / p95 / mean (s, 4 workers) | 0.328 / 0.856 / 0.381 | 0.343 / 1.002 / 0.408 |
| runtime p50 / p95 (s, single process, 3 samples × 12 presets) | 0.293 / 1.012 | 0.315 / 1.064 |

Transitions of the winner's state: 18 cases fail → clean, 2 fallback → clean, none the other way. Among the
682 cases where the winner changed and both winners are clean, the judge total moved by +1.21 on average
(median +0.70, max +17.0); in 75 of them the on-winner scores *lower* than the off-winner (min −6.9). Those are
not the critic's candidates losing: the repairs enter the top three that the optimiser refines and the off-run's
refined winner is then not generated. `resize.refine` now always keeps the best plain seed among the refined ones
(one extra optimisation at most), which halved that count; the rest is the K = 3 budget.

Recipes behind the 672 repair winners: pin to source edges 241, bolder / fill 198, tighter plan 173, headline on
fewer lines 67, headline on the picture 50, headline on its plate 23, headline to floor 13, badges to the corners
5, tight / shy plan 3, subhead on the picture 3, subhead / headline off a panel, shape or decorative 9. The soft
recipes win often because the loop runs on every case whose best candidate is under the target (about 60 % of
cases, 1–6 cheap extra candidates each); the hard-fail recipes win rarely but each one turns a −900 winner into a
clean one.

**What is left** (24 judge-hard winners): 13 headline / CTA below the floor, all on the 160 × 600 and 728 × 90
strips — unbreakable words (`WWW.UNWILDLIFEDAY.COM`, `ORIGAMICLASS` with 1.6 em tracking) that no font of 12 px
fits into 150 px even at zero tracking, or a pill label that collides with everything at the floor; 11 contrast
drops: `58ac689d` (4 formats) and `599fef44`, a white headline the source laid on a `cover`-fit hero whose crop
moves with the box so the same relative position lands on light pixels, and `5f562c10` (7 formats), a headline
that read against a full-bleed *decorative* photo the plans do not keep under it. The 7 remaining fallback wins
are 5 of these contrast cases plus 2 judge preferences (`5a21a1ec` Pinterest, `59526907` Story: 7–20 clean
candidates exist, the fallback's soft score still wins by 2–4 points).

### 2.2 Designer references: 720 cases, hold-out apart

`.venv/bin/python -m eval.compare_optimize --flag CHAMELEON_CRITIC --out docs/designer/compare/v9_critic`
(the v7 comparison tool, generalised to any on/off switch; both batches, same code, flag 0 vs 1 per case).

| metric | tuning 600: off → on | HOLD-OUT 120 (never tuned on): off → on |
|---|---:|---:|
| designer agreement, mean (winner) | 0.608 → 0.608 | 0.610 → **0.614** |
| cases with agreement ≥ 0.7 | 197 → 198 | 36 → 38 |
| centre error / reading-order tau | 0.140 / 0.704 → 0.140 / 0.702 | 0.142 / 0.734 → 0.140 / 0.727 |
| engine cases with a judge hard fail | 1 → **0** | 1 → 1 |
| designer wins by judge score | 167 → 165 | 33 → 29 |
| judge score, mean | 85.74 → 87.53 | 77.59 → 77.97 |
| agreement up / down / unchanged | 49 / 41 / 510 | 13 / 9 / 98 |
| runtime p50 / p95 (s, one process) | 0.33 / 0.74 → 0.34 / 0.85 | 0.42 / 0.68 → 0.42 / 0.77 |

Designer agreement does not fall: flat on the tuning set, +0.004 on the sealed hold-out, with more cases going
up than down in both. The largest moves are both ways and all come from *soft* repairs the judge preferred:
`5ca72539` → 728 × 90 drops 0.73 → 0.37 (a "tighter plan" repair of a bolder seed beat the hero-beside-column
layout the designer also chose), `5cebeb78` → 820 × 312 0.62 → 0.37 (pin), `5947c25e` rises 0.41 → 0.53 in three
tall formats and Level 3 → 820 × 312 0.51 → 0.62 (pins of the logo and badge corners). As in v7 and v8 the
judge, not the generator, decides those; the critic only adds the option.

### 2.3 Sanity sheets (`docs/sanity_critic/`, critic on; `off/` for Level 3 and Boynton)

Level 1, Level 2 and the Charity poster: no change in any format. Level 3: identical in 9 formats; the three
banner / wide formats (820 × 312, 1584 × 396, 1600 × 400) now take `+fix:pin to source edges` (logo back to its
corner, the sale ribbon top-right, the badges in one row beside the copy). Boynton: Skyscraper 160 × 600 is the
one case where a repair still fails (`+fix:cta to floor` lifts the date label from 4 to 9 px, the floor is 12;
every template fails it), LinkedIn / wide banners pin the logo, the rest unchanged.

### 2.4 Cost

The loop runs on every case whose best candidate is below the target (≈ 60 %); a round is at most 6 candidates
at 2–12 ms each (no pixels), so the eval-slice p50 moves +0.015 s and the single-process sample p50 +0.022 s; the
p95 moves +0.15 s on the slice (the two-round banner cases). Within the +0.3 s budget.

## 3. Recommendation: default on

`CHAMELEON_CRITIC` defaults to on (`critic.DEFAULT_ON`). Judge-hard winners −43 % and fallback wins 9 → 7 on the
eval slice without a single new hard fail, designer agreement flat / up on the sealed hold-out, runtime p50
+0.02 s. The two judgement calls (tracking relaxed before size, a spine or diagonal headline levelled when no wrap
fits the strip) are what makes the strip repairs work; `CHAMELEON_CRITIC=0` restores the v8 engine byte for byte.

## 4. Known limits, follow-ups

- **Cover-fit pictures.** `onto` puts a text back where it sat on the hero, but a `cover` crop changes with the
  box, so the pixels under it are not the source's; the estimate (and the judge) say no. A contrast-seeking move
  (sample the picture, place the text on its darkest / lightest band) would fix `58ac689d` and `599fef44`.
- **Cards that swallowed a heading.** When `place_panels` grew a card over the heading that sat above it, the
  plate recipe slides the text off or cuts the card back; `grow_panels` then regrows the card around its carried
  content and covers the heading again (`589b41f6`, 12 cases). The fix belongs in the panel carry, not here.
- **Unbreakable words on strips.** A 21-character URL label cannot be 12 px in 150 px; the honest output is the
  7–10 px the fitter finds. The judge's floor could take the longest word into account.
- **The optimiser's K.** Repairs that enter the top three displace plain seeds from the refinement; keeping the
  best plain seed covers most of it, a K of 4 the rest (+0.1 s).
- Soft recipes are judge-driven: a "tighter plan" or "bolder, fill" repair wins on the judge's terms and can lose
  designer agreement (§2.2). Their thresholds (`TYPICAL`) are the v8 p25; raising them to the p10 would halve the
  soft rounds and their cost at the price of the +1.2 points they bring.
