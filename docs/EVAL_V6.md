# Engine v6 — designer references as the target (2026-10-25)

The 240 hand-composed references (`docs/designer/`, 20 designs × 12 formats) said two things
(docs/designer/FINDINGS.md): our scorer rejected 68 of them, and the engine threw away the
composition of editorial sources. v6 acts on both: scorer and rectifier allowances for what the
designer does on purpose, a *designer-agreement* metric, a *preserve-structure* candidate family,
and 240 weak calibration pairs. All numbers below were measured with the v7 energy optimiser off
(`CHAMELEON_OPTIMIZE=0`; it landed in the same tree while this work was in progress) and without
pixels, like the harness.

Tests: `tests/test_v6_rules.py` (rules, metric), `tests/test_structure.py` (detection, layout,
hook). Sheets: `docs/sanity_v6/` (Level 3, Boynton, Charity Night), `docs/designer/compare/`
(240 source | designer | engine rows, `SUMMARY.md`, `results.jsonl`; the pre-v6 run is kept in
`compare/baseline_v5/`, the run after the scorer fixes but before the structure family in
`compare/v6_scorer/`).

## 1. Scorer and rectifier allowances

One shared predicate decides what two content units may overlap (`rectify.OverlapRules.conflict`,
built once per source and used by the rectifier, `score_design`, `unwanted_overlaps` and the eval
metrics). On top of the v3 rule (a pair may overlap as much as it did in the source + 1.5 pp):

| rule | what changed | why (reference) |
|---|---|---|
| graze vs lockup | a source text-on-text overlap is a lockup, not a graze, when one text's ink lies ≥ 80 % *on the other's lines* (not its hull) **and** the two differ in size ≥ 1.5× or are the same word | the skincare "NATURAL" shadow copy (same word offset 7 px) was a graze, so every reference "collided" (12/12); the PRAY case (same size, different words) stays a graze |
| text over picture / shape, role level | a text whose role the designer laid over a picture / shape (≥ 30 % of its ink) may lie on a picture / shape again when ≥ 30 % of its ink is on it, whatever the pair | Furniture Expo body on the hero (52 % → 100 %), red-dress headline on the photo (38 % → 41 %), quote lockup (96 % → 100 %) |
| hosted text | a text ≥ 80 % inside a shape / image drawn below it is never a collision (contrast + straddle rules judge it) | the brief: intentional layering is fine |
| designed non-text overlap | a pair the source layered where one side is not text may overlap up to 2× the source amount | StayAtHome figure on the wall (38 % → 44 %), red-dress block on the photo (28 % → 48 %), medical square under the heading (10 % → 17 %) |
| `layout.margins` | only text and small units (< 15 % of the source canvas); picture / shape blocks may run to the edge | designers bleed photo bands and colour panels (margins was the biggest soft-score gap, 0.60 vs 0.93) |
| off canvas | a picture / shape unit that bled ≥ 1 % in the source may bleed up to 1.5× that, capped at 25 % of itself; text keeps the +1 % rule | cropped photos stay cropped |
| text overflow | measured on the painted ink (widest line, last baseline + descender) with the DSL validator's 0.5 px slack; `max_lines` still honoured; same rule in `eval/metrics.overflow_n` | the renderer never clips: the box is a layout hint |
| `layout.spacing` | source-relative: the gap unevenness (coefficient of variation) the source's own stacks / rows had is free, only the excess is penalised | a header / band / footer source has uneven gaps by design; the structure candidate for the Charity story lost 4.8 points on this term alone |

References tripping a hard fail: **61 → 10** of 240 (FINDINGS counted 68 on an older run). The ten
that remain are explained, not excused:

- `595256d7` 160×600 / 728×90 / 820×312: the designer set a secondary CTA at 7 / 6 / 9 px, under the
  brief's own 12 px floor. Our floor stands.
- `5c346ef7` 1584×396 / 1600×400 / 160×600 / 728×90 / 820×312: the designer laid the white block over
  the photo (30–39 %); the source had them apart. A new overlap the source never had stays a
  collision (allowing it would allow any shape onto any photo).
- `level2_core` 1584×396 / 1600×400: the logo over the product photo (19 %), again a pair that never
  touched in the source.

Engine hard fails on the 240 cases: 11 → **0** (the eleven were `el_04` contrast drops that the
layering allowances no longer force the rectifier to create).

## 2. Designer agreement (`eval/metrics.designer_agreement`)

Per (design, format), on content elements matched by id (backgrounds and decoration left out), in
canvas-normalised coordinates on the drawn extents: mean centre distance (fraction of the
diagonal; `da_pos` = mean of 1 − d / 0.25), share of elements whose x / y / width / height are
all within 10 % of the canvas (`da_within10`), Kendall tau of the reading orders
(`engine.score.reading_order`), Spearman rho of linear sizes, and the mix
`da_agreement = 0.35 pos + 0.25 within10 + 0.2 (tau+1)/2 + 0.2 (rho+1)/2` (1 = the reference itself).
`tools/designer_compare.py` writes it per row (`da_*`) for the winner and the best of all judged
candidates (`da_best`, `da_best_name`, `da_best_rank`), and `SUMMARY.md` has a table per format and
per design.

| | winner agreement | best candidate | winner ≥ 0.7 | designer soft score higher | engine hard fails |
|---|---:|---:|---:|---:|---:|
| after the scorer fixes (`compare/v6_scorer/`) | 0.594 | 0.702 | 75/240 | 77/240 | 11/240 |
| + structure family, source-relative spacing (final) | **0.601** | **0.711** | 79/240 | 65/240 | 0/240 |

By format the winner agrees most on squares (0.76) and posters (0.66–0.70) and least on banners
(0.47–0.55): the designers' banner compositions (one row, header left) are furthest from what the
judge picks. The gap between the winner (0.60) and the best candidate (0.71) is the judge's, not the
generator's: in 196 of 240 cases a candidate closer to the reference exists and loses.

Regression targets (editorial designs, winner / best candidate): Charity Night `5888cec2` **0.70** /
0.74 (target ≥ 0.7 met; the story reaches 0.92), quote posters `5952492d` 0.68 / 0.79, SEO
`5e68e28d` 0.54 / 0.63, Furniture Expo `5952645b` 0.50 / 0.62 (the structure family wins 8 of its
12 formats, but the designer's "01 APRIL" lockup straddling the photo's edge and the omitted
sticker on banners keep the position error high). Three of the four targets are not met.

## 3. Preserve-structure candidate family (`engine/structure.py`)

`detect_structure(analysis)` reads the macro structure out of the analyzer's units: *zones* are
panels and big pictures / shapes (≥ 10 % of the canvas; a bleeding "decorative" photo ≥ 25 %;
never a rotated block); a content unit ≥ 30 % on a zone drawn below it is *carried* by it; a zone
≥ 80 % inside a bigger zone below it is a *card*. Zones and free units are projected on the
source's stack axis (vertical for tall / square, horizontal for wide / banner) and merged into
*bands* (overlap > 15 % of the smaller); zones side by side inside a band, on their *visible*
extents (a panel drawn over a photo hides part of it), make a *split*. Kinds: `bands` (header /
zone band / footer), `split` (one band of columns), `lockup` (one zone carrying everything).
Sources without a zone (a logo, a headline and a button on a gradient) get no structure candidate.

`structure_relayout` lays the tree out on the target: text leaves re-wrap with the floor plan's
`_TextItem` machinery (one global shrink factor k from `_largest_k`, rescue mode included); blocks
in text leaves (logo, date sticker, button) are capped at their source share of the stack length;
panels are elastic (never smaller than their content plus the source padding scaled) and flush
with the canvas edges they touched; `contain` pictures keep their aspect and take what the band
gives them; vertical texts that ran along a zone's side become rails beside its column; leftover
length goes to the zones in proportion to their source weights, the rest to spacing; a legal
footer keeps the bottom edge. On a strip (cross extent < 0.4 × the stack length) a split's leaves
stack instead (the Charity panel above its photo on 160×600). Variants (`StructureOptions`, 2–3 per
task from `candidates.generate_candidates`, strategy `"structure"`, `MAX_CANDIDATES` 21): keep the
axis, flip it when the target's orientation differs from the source's (bands ↔ columns: the SEO
banner's panel | photo becomes panel over photo on a poster), mirror the split.

The structure family wins 67 of the 240 reference cases (Furniture Expo 8/12, Level 2 8/12, the two
sparkling-night banners 19/24, Charity Night's Facebook cover and leaderboard) and, by eye
(`docs/sanity_v6/`), the Boynton poster's square, story and all four banners now keep the photo
band over the text block as the designer composed it. Cost: 2–3 more candidates per task.

## 4. Calibration pairs (`eval/data/labels.designer.jsonl`)

240 weak pairs in the `labels.jsonl` record format (side a = the reference, scored by the engine's
own scorer; side b = the engine's winner; decision "a"; kind "weak"; `source_file` points at the
designer source). `python -m eval.calibrate --dry-run --weak eval/data/labels.designer.jsonl`:

- the hand weights agree with the designer in **31 %** of the decisive pairs (the perturbation weak
  labels: 71 % human-only agreement after fitting); the fit degenerates (temperature 0.001,
  leave-one-design-out 0.34): no linear reweighting of the fifteen components expresses the
  designer's preference;
- per component, the ones that side most with the designer are `faith.anchors` (0.54) and
  `faith.order` (0.51); the ones that side against her are `layout.margins` (0.13; designers bleed),
  `faith.hierarchy` (0.23) and `layout.cohesion` (0.30). The only weights the fit raises are the
  floor-bound ones (`faith.scale`, `margins`, `cohesion` to 5 %).

So the designer pairs push *nothing in particular*: what the designer prefers is composition
(structure kept, columns aligned, panels full-bleed), which the breakdown does not measure. That is
the case for the relational energy the follow-up session adds; these pairs are its training data.
The weights file is not written (dry run only).

## 5. Full eval v6 vs v5 (6058 common cases, `eval/compare_runs.py v5 v6`)

Both runs without pixels, 4 workers, `CHAMELEON_OPTIMIZE=0`. Note that `overflow_n` and `overlap_n`
are measured with the v6 rules in both columns' *scorer* but the v5 column's outputs were produced
by the v5 engine, so the overlap / overflow rows mix a metric change with an engine change; the
below-floor, off-canvas, contrast and runtime rows are like for like.

| metric | v5 | v6 |
|---|---:|---:|
| any hard defect | 38 (0.63 %) | **30 (0.50 %)** |
| headline / CTA below floor | 34 | 28 |
| unwanted overlap | 4 | 1 |
| text overflow | 1 | 1 |
| off canvas | 0 | 0 |
| judge contrast fail | 124 (2.05 %) | **44 (0.73 %)** |
| anchor fallback wins | 39 | 14 |
| judge score mean / p50 | 58.5 / 86.9 | 75.8 / 88.6 |
| layout.spacing (source-relative in v6) | 0.767 | 0.915 |
| read.presence / faith.order / faith.anchors | 0.886 / 0.843 / 0.595 | 0.918 / 0.867 / 0.627 |
| layout.fill | 0.862 | 0.843 |
| gt centre error / reading-order tau | 0.156 / 0.771 | 0.151 / 0.775 |
| smallest font p05 / headline-CTA p05 | 7 / 12 px | 7 / 12 px |
| runtime p50 / p95 | 0.25 / 0.55 s | 0.25 / 1.04 s |

Winners by strategy in v6: floor plan 3546, anchor 1620, **structure 892** (14.7 %); the structure
winners carry 8 harness defects and 11 judge hard fails among them (mean judge score 73.6). The
judge mean rises mostly because far fewer winners carry a hard fail (collisions the layering
allowances no longer flag, and the contrast drops the rectifier used to create by shoving layered
text off its picture). No preset got worse on any defect column; the skyscraper (3.8 %) and the
leaderboard (2.4 %) keep the below-floor cases they had. Runtime p95 doubled with the 2–3 extra
candidates; p50 is unchanged.

## 6. Known gaps / follow-ups

- Banners are the weak format for agreement (0.47–0.55): designers compose header-left rows; the
  flipped structure variant does that but rarely wins against the banner floor plan.
- The judge, not the generator, is the bottleneck: a candidate closer to the reference exists in
  82 % of cases. Human A/B on the structure vs floor-plan winners, or the energy optimiser, decide it.
- `detect_structure` ignores rotated blocks and treats piled zones as cards of the biggest; a wide
  source whose photo is only a background (cover, ≥ 85 %) has no zone and no structure candidate.
- The remaining reference "defects" are design choices we do not want to copy (a 7 px CTA, a new
  overlap). They stay.
- `tests/fixtures/golden_v5` was regenerated from the v6 tree (flags off, optimiser off); the S1
  byte-identity contract is "flags off = this tree", not "= the v5 tree".
