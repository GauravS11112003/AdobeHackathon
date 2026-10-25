# S1 — VLM perception as one vote among three (2026-10-24)

Workstream S1 of docs/PLAN_VLM.md: the vision model looks at the rendered source and votes on what each
piece of the design *is* (its role), what kind of design it is (archetype) and what matters most; the
engine merges that vote with the rule analyzer (engine/analyze.py) and the learned classifier (S4,
engine/role_model.py), then lays the design out as before. Model: Qwen3-VL-4B-Instruct Q4_K_M + mmproj
Q8_0 through engine/vlm.py (S0). Code: `engine/perceive.py`, the three-voter part of
`engine/role_merge.py`, `resize.understand()`, the archetype prior in `engine/candidates.py`. Tests:
`tests/test_perceive.py` (45). Tools: `tools/eval_perception.py`, `eval/s1_sheet.py`. Raw results:
`chameleon/eval/data/perception/` (gitignored), eval runs `eval/data/runs/s1_{off,model,vlm}`.

## TL;DR

- **It works and it is safe.** One VLM call per source (≈ 9 s native p50, 12 s p95; the three samples take
  10–11 s each), cached per source hash; off by default; with the flags off the output is byte-identical
  to v5 (golden test). 303/303 eval designs answered, no timeouts, no crashes; 404 tests pass.
- **As a perceiver the 4B is not better than the rules.** On 60 DesignAsCode-labelled Crello designs with
  ids stripped: coarse agreement rules 0.713, VLM 0.687, classifier 0.825 (in-sample: these are training
  designs of S4), rules + classifier 0.745, all three 0.747. The VLM beats the rules exactly where S0 said
  it would (headline 52/58 vs 46/58, picture 38/40 vs 29/40, CTA 9/19 vs 6/19, badge 15/59 vs 3/59) and
  loses on body copy (secondary 55/100 vs 86/100: it calls body lines badge / headline) and decoration.
  On the three samples the VLM is 23/23 coarse; the merge changes one fine role (Level 3 subhead → body).
- **The merge is net positive on labels but small**: of 72 units whose role it changes, 23 go from wrong
  to right at the coarse level, 7 from right to wrong, 42 are fine-split or wrong-to-wrong.
- **In the 300-design eval the effect is mixed.** Judge-internal: hard-failing cases 108 → 97 (classifier)
  → 82 (VLM + classifier), judge contrast fails 75 → 66 → 58, fallback wins 22 → 12 → 13, clean-case mean
  flat (86.6). Harness view (roles from the rule analyzer): "headline / CTA below floor" 29 → 44 → 84,
  because the vote re-labels the headline / CTA in ~1 in 10 designs and the old one then shrinks; the
  designer-sibling reading-order tau drops 0.762 → 0.734 while size rho rises 0.784 → 0.795. On the twelve
  "both bad" cases 6 outputs change, none into a hard fail, judge totals −5 to +3; visually the changes are
  plausible but not a clear win (docs/sanity_s1).
- **Recommendation: no-go for VLM on by default** at this deadline (§4). Keep the plumbing: it costs
  nothing when off, and the classifier vote (`CHAMELEON_ROLE_MODEL=1`, 3 ms) is the part worth a human
  A/B before the freeze.

## Results

### (a) Role agreement, ids stripped

Per analyzer unit, coarse classes; "exact" is the fine role. `tools/eval_perception.py samples|dac`.

**Three samples** (23 labelled units from the sample ids; hidden tasks will not have them):

| voter | coarse | exact | headline | cta | logo | hero top-1 |
|---|---:|---:|---|---|---|---|
| rules | 1.000 | 1.000 | 3/3 | 3/3 | 3/3 | 2/2 |
| classifier | 0.826 | 0.609 | 3/3 | 2/3 | 3/3 | 2/2 |
| VLM | 1.000 | 0.783 | 3/3 | 3/3 | 3/3 | 0/2 (calls the hero "image": the coarse class is right) |
| rules + classifier | 1.000 | 1.000 | 3/3 | 3/3 | 3/3 | 2/2 |
| all three | 1.000 | 0.957 | 3/3 | 3/3 | 3/3 | 2/2 |

**60 DesignAsCode-labelled Crello designs** (train shards 0–2, seeded, 3–14 elements, ≥ 60 % of the elements
labelled; 463 labelled units). Caveat: S4's classifier was trained on these designs' labels, so its row is
an upper bound; the rules and the VLM have never seen them.

| voter | coarse | exact | minor | secondary | badge | headline | picture | cta | logo | headline top-1 | cta top-1 | logo top-1 | hero top-1 |
|---|---:|---:|---|---|---|---|---|---|---|---|---|---|---|
| rules | 0.713 | 0.454 | 157/183 | 86/100 | 3/59 | 46/58 | 29/40 | 6/19 | 3/4 | 46/58 | 6/13 | 3/4 | 20/28 |
| classifier (in-sample) | 0.825 | 0.747 | 177/183 | 74/100 | 32/59 | 48/58 | 34/40 | 13/19 | 4/4 | 47/58 | 9/13 | 4/4 | 24/28 |
| VLM | 0.687 | 0.445 | 147/183 | 55/100 | 15/59 | 52/58 | 38/40 | 9/19 | 2/4 | 43/58 | 9/13 | 2/4 | 6/28 |
| rules + classifier | 0.745 | 0.492 | 157/183 | 84/100 | 15/59 | 47/58 | 29/40 | 9/19 | 4/4 | 47/58 | 9/13 | 4/4 | 20/28 |
| all three | 0.747 | 0.514 | 157/183 | 83/100 | 16/59 | 46/58 | 32/40 | 9/19 | 3/4 | 46/58 | 9/13 | 3/4 | 19/28 |

Where the three-voter merge moves a unit's coarse class (30 of 463): wrong → right 23 (13 secondary → badge,
3 logo → picture, 3 secondary → cta, 3 cta → secondary, 1 secondary → headline), right → wrong 7 (5
secondary → badge, 1 secondary → cta, 1 headline → secondary). 20 units where the VLM alone was right and
the merge kept the rules: 7 headlines the rules called body (the classifier sided with the rules), 5
pictures the rules froze as decorative / panel (hard structure, by design), 2 CTAs. Dropping `RULE_BONUS`
(0.5 for the unit the rules gave a unique role, in the one-headline pass) costs two headlines (44/58), so
it stays. Archetypes on this set: product_ad 20, event_poster 18, editorial 16, quote 6; on the 303 eval
designs event_poster 157, quote 65, product_ad 41, editorial 39, other 1 (Crello's catalogue is mostly
invitations and posters; "grid" was never chosen).

### (b) 300-design eval, three arms

`eval.run_eval --limit 300 --workers 4`: 300 Crello designs + the 3 samples × 12 presets + 562 designer
siblings = 4198 cases per arm, rendering on. Perception came from the precomputed cache
(`tools/eval_perception.py precompute --limit 300`, one 4B call per design, 48 min), so the runtime
columns are the engine without the VLM call; add the call cost of §3 for the VLM arm.
`eval.compare_runs s1_off s1_model s1_vlm`:

| metric | VLM off (v5) | classifier only | VLM + classifier |
|---|---:|---:|---:|
| any hard defect, harness (%) | 0.79 | 1.17 | 2.05 |
| headline / CTA below floor, harness (n) | 29 | 44 | 84 |
| unwanted overlap (n) | 4 | 5 | 2 |
| text overflow / off canvas (n) | 1 / 0 | 1 / 0 | 1 / 0 |
| judge contrast fail (n) | 75 | 66 | 58 |
| anchor fallback wins (n) | 22 | 12 | 13 |
| judge: cases with any hard fail (n) | 108 | 97 | 82 |
| judge score mean (all cases) | 59.49 | 62.33 | 66.64 |
| judge score mean (clean cases) | 86.64 | 86.60 | 86.58 |
| judge score p50 | 86.83 | 86.78 | 86.87 |
| read.contrast | 0.709 | 0.709 | 0.715 |
| layout.spacing / cohesion | 0.759 / 0.935 | 0.755 / 0.933 | 0.770 / 0.944 |
| faith.order | 0.847 | 0.840 | 0.838 |
| faith.anchors | 0.612 | 0.615 | 0.606 |
| faith.hierarchy | 0.989 | 0.986 | 0.985 |
| faith.scale | 0.789 | 0.789 | 0.792 |
| runtime p50 / p95 (s, engine only) | 0.26 / 0.52 | 0.25 / 0.51 | 0.25 / 0.51 |
| gt centre error | 0.157 | 0.156 | 0.159 |
| gt reading-order tau | 0.762 | 0.761 | 0.734 |
| gt size rho | 0.784 | 0.788 | 0.795 |
| gt font ratio p50 | 1.050 | 1.054 | 1.055 |

Reading it: the engine's own judge sees fewer defects with the votes (hard-failing cases −24 %, contrast
fails −23 %), and the clean-case quality is unchanged. The harness, which labels roles with the rule
analyzer, sees three times as many "headline / CTA below floor" cases: in those designs the vote gave the
headline or CTA role to another element, the former one became secondary and was allowed to shrink. Both
views are true; which one the official judge shares depends on whether the vote's re-labelling is right.
Spot checks of the designs with the most new below-floor cases (`eval/data/perception/`): "NO APPOINTMENT
NECESSARY" in a 4 px pill demoted cta → badge (defensible), "Listen and Donate" promoted body → cta and an
address pill demoted cta → badge (right), a car photo the rules called logo → hero (right), "ST. ANTHONY
CHURCH" → body and "YOUTH CAMP" → headline (right), "7 PM" headline → badge with "DRESSCODE: BLACK DRESS"
promoted to headline by the classifier alone while the VLM's pick "SPARKLING" was outvoted (wrong). The
reading-order tau drop (−0.03 against designer siblings) comes from the same re-labelling: column plans
order by role. Per preset, the extra below-floor cases concentrate on Facebook cover (0.3 → 4.6 %),
leaderboard (3.6 → 5.9 %) and skyscraper (4.6 → 5.6 %).

### (c) The twelve "both bad" cases (docs/LABELS_V1.md), VLM + classifier on vs off

`eval/s1_sheet.py docs/sanity_s1`: source | VLM off | VLM + classifier on, one row per case
(docs/sanity_s1/s1_sheet.png and one PNG per case).

| design → preset | archetype | roles changed by the vote | winner off → on | judge total off → on |
|---|---|---|---|---|
| Corporate Charity Night → 1080×1350 | event_poster | cta → subhead (consistency) | tall chips=corner → tall scale=1.5 | 87.8 → 84.2 |
| Valley Brooks apartments → 1600×900 | product_ad | cta → badge | anchor ×1.25 → wide hero=right | 82.7 → 81.6 |
| Religious choir → 820×312 | event_poster | fine_print → cta (vlm) | same plan | 89.0 → 87.5 |
| Real Estate → 728×90 | editorial | logo → hero | same | 84.9 → 84.8 |
| Origami classes → 1080² | event_poster | 2 × body → badge | square scale=1.5 → square chips=corner | 91.3 → 86.0 |
| Prayer invitation → 1080² | event_poster | none | identical | 92.7 |
| Sewing day → 1600×900 | product_ad | none | identical | 93.6 |
| Citation (quote) → 1080² | quote | subhead → fine_print | identical | 84.3 → 87.0 |
| Healthy food → 1600×900 | editorial | body → subhead | wide scale=1.15 → wide hero=stack | 93.4 → 93.0 |
| Peak hike → 1080² | event_poster | none | identical | 90.4 |
| Corporate Charity Day → 1080² | event_poster | subhead → badge, body → badge | same plan | 80.5 → 77.2 |
| Shoes sale → 1584×396 | product_ad | body → subhead | same | 87.9 → 88.0 |

No case gains or loses a hard fail. Six outputs change; the archetype prior is visible in two (the two
*editorial* designs move to text-column plans: Healthy Food's wide canvas now stacks the hero under the
column, Real Estate keeps its banner). The badge re-labels put dates and taglines into pills / corners
(Origami, Charity Day), which reads as intentional but costs cohesion points. None of the six is the
kind of change that would have moved a "both bad" label: the weaknesses those labels found were
generation problems (fixed in v5), not perception problems.


## 1. What the model is asked

One call per source design (cached by a hash of the source JSON, so every target of the same source
reuses it):

1. `engine.render.render_design(source, 896)`; one numbered magenta box per analyzer unit (groups,
   holders, hosts and sibling rows are one box; the background is skipped), reading order, number tag at
   the top-left corner. This is the set-of-marks overlay that reached 0.75 coarse agreement in
   docs/VLM_BENCH.md; the image goes to the model at 448 px.
2. The *hinted* prompt: the role vocabulary with one-line definitions, then every box's element types and
   text ("3: shape + text \"Shop the Summer Line\""), then the archetype definitions. The model answers
   `{"roles": {"1": role, ...}, "archetype": ..., "importance": [box numbers, most important first]}`;
   the JSON-schema grammar makes every key present and every value an enum member, so a wrong choice is
   the only failure mode.
3. `interpret()` maps the answer onto units: the fine role is kept (`Perception.fine`) and mapped onto
   the **coarse classes** the merge acts on (`perceive.COARSE`): picture (hero / image), headline, cta,
   logo, badge, secondary (subhead / body / fine_print), minor (decorative / panel / shape). An answer
   that contradicts the box's element type (an image called "headline", a text called "logo") is dropped.
   **Confidence is derived, not a model probability** (grammar-constrained decoding gives none without
   `logits_all`, which would cost ~2 GB of logits per call): the bench's accuracy on that class
   (`BASE_CONF`: logo / headline / picture 0.85, cta 0.8, badge 0.7, secondary 0.6, minor 0.5), divided
   among the boxes that share a role that should be unique (headline / cta / logo), except the one the
   model ranked most important, which keeps the full value. So a second "headline" has 0.425 and cannot
   break a tie (threshold 0.6); one headline has 0.85 and can.

Gating and safety: `CHAMELEON_VLM` must be **explicitly** on (`1`/`true`); unset or `0` means the
perceiver is not even imported from `resize.py` (the test suite asserts `engine.vlm` is never imported
by default) and the output is byte-identical to the pre-S1 engine (`tests/fixtures/golden_v5/`, three
samples × six targets, compared byte for byte). Per-task budget `CHAMELEON_VLM_BUDGET_S` (default 20 s)
covers model load + render + call; with less than 1.5 s left the call is skipped (`status="budget"`).
Two timeouts or two backend errors switch the adapter off for the process (S0). `perceive()` never
raises; every failure returns an empty Perception with a `status` (`off`, `no_model`, `no_render`,
`budget`, `no_answer`, `error`) and the engine proceeds with the rules.

## 2. The vote (`role_merge.vote_roles`)

Per analyzer unit, three voters: rules (always), classifier (its coarse-class probability mass over the
members that name the unit, voting when ≥ `MIN_CONF` 0.55), VLM (coarse role, voting when confidence
≥ `VLM_MIN` 0.4 and the class is allowed for the unit's element family: text → headline / cta / badge /
secondary, image → logo / picture / badge, a shape + label unit the rules call badge / cta → badge / cta).

| situation | decision | recorded as |
|---|---|---|
| background, panel, decorative, shape-only unit | rules | `rules` |
| classifier and VLM agree against the rules | theirs | `model+vlm` |
| one of them agrees with the rules | rules | `rules+model` / `rules+vlm` |
| three-way split | VLM if conf ≥ `VLM_TIEBREAK` 0.6, else rules | `vlm` / `rules` |
| VLM abstains, classifier disagrees | S4 policy: P ≥ max(0.55, `STICKY`[rule]) and margin ≥ 0.25 | `model` / `rules` |
| classifier abstains, VLM disagrees | VLM if conf ≥ 0.6, else rules | `vlm` / `rules` |
| fine split inside the class (subhead / body / fine_print, hero / image) | rules, unless both models name the same other fine role | `model+vlm` |
| afterwards: one headline, one CTA, one logo, one hero | strongest unit keeps the role (classifier P + VLM conf + importance bonus 0.3/rank + 0.5 if the rules had it); a displaced headline → subhead, CTA → body (free text) / badge (pill), logo / hero → image | `consistency` |

Unit membership, anchors, reading order and panel carry are never touched. `apply_votes` rewrites
`analysis.roles`, the units' role / importance and `headline_font_size`, and stores the record in
`analysis.perception` (`archetype`, `vlm` status, `decisions` per unit with `rule` / `model` / `vlm` /
`by`, voter counts, number of changed roles). `Judged.summary()["roles"]` carries the compact form into
the eval rows; `resize.LAST_ANALYSIS` the full one; the playground's analysis table shows "Decided by"
and the votes per unit, and a Perception line with the archetype.

Archetype → candidates: `plan_variants(family, archetype)` puts the variants that suit the archetype
first (that decides which three floor plans a *small* ratio change tries) and every floor-plan candidate
carries a `prior` of `ARCHETYPE_PENALTY` (3 points, applied in `judge` like the adaptation penalty) when
it fights the archetype: editorial / quote designs tax hero-first plans (wide `hero_side ≠ stack`, square
left / right, banner `text_flow=column`), grid designs tax `chips ≠ row`. Without a perception the
prior is 0 and the order is the v5 order.

## 3. Cost

Qwen3-VL-4B Q4_K_M + mmproj Q8_0, CPU only, 8 threads, Apple M3 Pro (the reference M5 Pro should be
faster). One perception call per source; every further target of that source is a cache hit (≈ 1 ms).

| where | VLM off | VLM + classifier on (uncached, incl. 2.4–3 s model load in the first task) |
|---|---|---|
| native, three samples (`python -m engine.main`) | 0.3–1.0 s per task | 12–15 s per task (15.0 / 12.4 / 12.0) |
| arm64 container, `--network none` (`my-chameleon-engine:arm64-s1`, built from this tree) | 0.5–1.1 s per task | **11.4–13.2 s per task** (budget 20 s and 60 s give the same numbers: nothing hit the budget) |
| 303 eval designs, native, uncached call only | – | p50 9.0 s, p95 12.3 s, max 16.6 s (8 units per design p50; 48 min for the set) |
| 60 DesignAsCode designs | – | p50 9.1 s, max 16.1 s |

The container is **not** 3× slower than native here: about 1× (S0 measured ~2× on the 672 px bench calls;
at 448 px with the ARMv8.2 llama.cpp build the prefill is short enough that the Docker VM's share
matters less). The default 20 s budget covers the p95 with room; a design with ~15 units at the max
(16.6 s) still fits, and a timeout only skips perception for that task. The image is 7.3 GB on disk
(3.25 GB compressed) against 1.24 GB without weights; the size cap is still unstated
(docs/ORGANIZER_QUESTIONS.md). The amd64 image cannot be timed on this machine (skia segfaults under
QEMU, docs/DOCKER_CHECK.md); on an x86 host the AVX2 wheel is used and the call cost is unknown.

All three sample outputs are written with the VLM on in the container and are **identical** to the
VLM-off outputs: on Levels 1 and 2 the vote agrees with the rules on every unit, on Level 3 the only
change (subhead → body, both models) does not alter the plan (same tier, same floor).

## 4. Recommendation

**No-go for `CHAMELEON_VLM=1` by default at the stage-one freeze; keep it shipped and off.** Reasons:

1. *It does not perceive better than what we have.* 0.69 coarse agreement with labels vs 0.71 for the rules;
   its wins (headline, CTA, pictures, badges) are real but the merge can only pass them through when the
   classifier does not side with the rules, which on labelled data leaves +0.2 pp of coarse agreement
   (0.745 → 0.747) for a 10 s call. S0's 0.75 "coarse agreement" was agreement with the analyzer, not with
   ground truth; against ground truth the two are about equally often wrong, in different places.
2. *The measurable effect on outputs is mixed, not positive.* The engine's judge is happier (−24 % hard
   fails) but the harness and the designer siblings are not (reading-order tau −0.03, three times as many
   rules-view below-floor cases), and the sheet of the twelve hardest cases shows plausible but not
   better layouts. The official judge looks at pixels; the only evidence that would settle it is a human
   A/B on the VLM-on vs VLM-off outputs, which the label page can serve directly (`eval/labeling.py`
   "two harness runs" mode on `s1_off` vs `s1_vlm`; 150 pairs ≈ 1 h). Ship it on only if that A/B
   prefers VLM-on by a clear margin (≥ 60 % of decisive pairs).
3. *Cost and risk.* +10–13 s per task on an otherwise sub-second engine, a 7.3 GB image under an unknown
   size cap, and a native-code path (llama.cpp) in the scoring run; the fallbacks are tested but every
   extra second and gigabyte is a submission risk with no demonstrated gain.

What to keep and what to do with the budget:

- Keep `engine/perceive.py`, the three-voter merge and the archetype prior: off they cost nothing, the
  golden test guards the identity, and the voter record in the playground is useful on its own.
- The **classifier vote** (`CHAMELEON_ROLE_MODEL=1`, 3 ms, no weights beyond 0.4 MB) carries most of the
  judge-side gain (hard-failing cases 108 → 97, fallback wins 22 → 12) with a smaller harness-side cost
  (below floor 29 → 44). It should go into the same human A/B (`s1_off` vs `s1_model`); if humans prefer
  it, turn it on by default — it needs no Docker change.
- If a VLM stays in the plan, its best use is not perception: the four classes it is good at are the
  ones the rules already get right on the samples. The honest alternatives are (a) a *second opinion only
  on low-confidence rule decisions* (text-heavy designs where the rules' headline is a guess: the 7
  headlines the VLM had right and the merge lost were all "body" by the rules and the classifier), i.e.
  ask only when the rules' headline is not the largest text or several texts are within 15 % of it, which
  would cut the calls to a fraction and remove the re-labelling noise everywhere else; or (b) S2's judge
  role, which S0 measured as marginal. Both are post-deadline experiments unless the human A/B says the
  perception is already worth it.
- The archetype came back `event_poster` / `quote` for most Crello designs and `grid` never; the prior
  moved two of twelve both-bad cases to text-column plans. It is harmless, but it is not evidence either
  way until the A/B.

Open points: the 20 s budget is right for the 4B at 448 px (p95 12.3 s native, 13.2 s in the container);
if the organizers' machine is slower than 1.5× this one, set `CHAMELEON_VLM_BUDGET_S=30`. The harness
measures roles with the rule analyzer (`eval/metrics.py` runs its own `analyze`): with a vote on, read its
"below floor" column as "the rules' headline / CTA shrank", not as a defect count, or add an
engine-view column that uses `resize.LAST_ANALYSIS` (not done here, to keep the arms comparable with
the v2–v5 runs).
