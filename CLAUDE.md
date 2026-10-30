# AdobeHack — Project CHAMELEON

Adobe University Hackathon: North America 2026, challenge "CHAMELEON — Any Design. Every Canvas."
Build an engine that takes a finished design (JSON of text/image/shape elements) plus a target canvas size
and returns the same elements re-laid-out so the result still looks designed. "Move the furniture, don't
stretch the photo."

## Read these first
- `docs/CONTEXT.md` — full digested context: brief, rules, schema, starter repo, research map, three
  strategies with scores, recommended architecture, implementation plan, open questions. **Source of truth.**
- `docs/BRIEF_PDF_TEXT.md` — verbatim text of the official brief PDF (`docs/Final Chameleon Challenge.pdf`).
- Starter repo cloned at `chameleon/` (https://github.com/jhaaj08/chameleon). Work happens there.
- `docs/baseline/` — rendered source-vs-baseline comparisons for the three samples (stretch baseline, 2026-10-19).
- `docs/NEXT_STEPS.md` — **where to resume** (2026-10-26): the S5 freeze checklist, the five next engine
  implementations in priority order, and the dead ends already measured (do not re-propose them).

## Non-negotiable rules (Stage 1, automated scoring)
- Edit **only** `engine/resize.py`: `def resize(source: dict, target_canvas: dict) -> dict`.
- Output must contain **exactly the same element ids** as the source, none added or removed.
- **Never regenerate, redraw, or replace asset pixels** (incl. backgrounds/decoration, incl. GenAI). Disqualifying.
- Treat **text `content` and `font_family` as fixed**. Changing `font_size` to fit is expected and core.
  Never alter `content` (it would break `style_runs` indices).
- Images (`fit: contain`) must keep aspect ratio. Nothing important off-canvas (low-opacity decorative
  bleed is tolerated; the Level 2 sample does it on purpose).
- Runs offline in Docker: `docker build --platform linux/amd64` then `docker run --network none`.
  Everything (packages, model weights) must be baked at build time via `requirements.txt` / Dockerfile.
- No hand-tailoring to specific designs or sizes. Hidden cases punish it.
- Element ids in hidden tasks are opaque (id/type/geometry only). Infer roles from signals, not names.
- Reference hardware: Apple M5 Pro, exact spec TBD. Assume CPU-only. No hard time limit; quality first.
- Model size cap and approved open-model list are **TBD**. Fine-tuned weights must be publicly hosted.
- Level 3 sample's `holiday_watermark` asset is intentionally missing. Don't add it.

## Scoring
1. JSON structural checks (ids, required fields, off-canvas, image proportions).
2. Rendered PNG (via official cr-renderer) judged by an AI evaluator against the rubric: no unwanted
   collisions, readable, on brand, looks intentional, holds up everywhere, speed/reliability (minor).
Both must pass; a nice PNG from dishonest JSON or plausible JSON that renders badly gets no credit.

## Decided architecture (see docs/CONTEXT.md §10)
analyze(roles/groups/anchors/hierarchy) → plan(ratio class, floor plans) → generate N candidates
(flex trees via `stretchable`, text fitting with real brand fonts) → rectify (penalty optimizer) →
render each with cr-renderer → score (hard defects → readability/contrast → Ngo measures → similarity
to source → optional VLM tie-break) → return best. Build Idea 1 (deterministic relayout) first, then
Idea 2 (generate-fix-rank), then Idea 3 (Crello retrieval) as stretch.

## Engine layout (chameleon/engine/, all shipped by the Dockerfile's `COPY engine/`)
- `resize.py` — orchestrator (judge loop, "judge_v1"): analyze → `candidates.generate_candidates` →
  for each: `materialize` (`_fit_text`) → `rectify` → `_finalize` → `score_design` (renders) → best wins.
  `resize_with_candidates()` returns every judged candidate with its score (playground); env
  `CHAMELEON_DUMP_DIR` writes each candidate's JSON/PNG/scores, `CHAMELEON_NO_RENDER=1` (or
  `CHAMELEON_RENDER=0`) judges on geometry only. Still wrapped in a uniform-scale fallback so it never
  crashes. ~1 s per task with pixels, ~0.3 s without; the winners are the same on all three samples.
  `_finalize` clamps text boxes to ≥ 1 px: cr-renderer's `TextElement` rejects width/height 0 and the
  whole PNG fails (found by the eval run on 728×90 banners, regression test in `tests/test_eval.py`).
- `candidates.py` — 4–12 candidates per task: ratio_change ≤1.6 → anchor variants with content scale
  min(sx,sy)×{1, 1.12, 1.25} (capped at max(sx,sy)) plus 3 floor plans; bigger changes → the family's
  `PlanOptions` variants (hero left/right/stack, chips row/corner/beside_cta, spacing 0.75/1.3,
  scale_bias 0.85/1.15, banner text stacked/inline) plus an anchor "fallback" that is only chosen when
  every real candidate has a hard fail. Identical placements are deduped.
- `rectify.py` — deterministic defect fixer on materialized elements, at unit level (groups move/scale
  as one): image aspect, push apart unwanted overlaps (visible boxes: text = measured ink, rotated =
  AABB; overlaps present in the source are allowed), shrink the less important unit when nothing can
  move, keep content on canvas with a margin, snap near-aligned edges/centres, even out nearly-even
  gaps in stacks/rows. Max 6 passes, stops when nothing changes. `unwanted_overlaps()` is shared with
  the scorer and tests.
- `score.py` — `score_design()` → `Score(total, hard, breakdown)`. Hard fails (−1000 each): content off
  canvas, measured text overflow, image aspect drift >5 %, headline/CTA font below
  `floorplan.Metrics.min_font`, unwanted collision, unreadable contrast. Soft (0–100, weights in
  `WEIGHTS`): readability (size vs src×√area-ratio, line counts, WCAG contrast + busyness sampled on a
  no-text render, hero/logo presence), layout (Ngo balance, alignment, even spacing, fill, margins),
  faithfulness (reading order via rows/stacks, anchors, size hierarchy, scale uniformity).
- `render.py` — `render_design(design, max_size=800, with_text=True)` → PIL image in memory via the
  vendored renderer (`_get_renderer` + `convert_chameleon_to_crello`); returns None if the renderer is
  unavailable (scorer then skips pixel checks). **Pixels are a bonus signal, never a dependency**: skia
  segfaults under QEMU (docs/DOCKER_CHECK.md) and `main.py` writes the JSON only after `resize()`
  returns, so `policy()` turns rendering off when the process looks emulated (platform.machine() family
  ≠ /proc/cpuinfo family; `CHAMELEON_RENDER=1` forces it on), a render slower than
  `PER_RENDER_BUDGET_S` (2.5 s) or two exceptions switch it off for the process, and each task may spend
  at most `TASK_RENDER_BUDGET_S` (6 s) rendering. No threads, subprocesses or extra native code.
- `analyze.py` — roles (background/decorative/logo/hero/image/headline/subhead/body/cta/badge/fine_print/shape),
  groups as single `Unit`s, edge anchors, reading order, importance. Thresholds are module constants.
- `relayout.py` — `anchor_relayout` (sizes × min(sx,sy), positions by per-axis anchor), `resolve_vertical_collisions`.
- `floorplan.py` — big-ratio-change path (`floorplan_relayout`). Picks a plan by the target's ratio family
  (tall ≤0.8 / square ≤1.25 / wide ≤3 / banner >3): tall+square = centered column (logo, hero, headline,
  subhead, badges row, CTA, fine print at bottom); wide = hero on one side, column on the other; banner =
  one row logo | hero | text column | badge cluster | CTA. Every slot's size is a function of one global
  shrink factor k∈[0,1] (ideal → readable floor) with per-role shrink speeds (headline/logo/CTA last, badges
  and legal first); a binary search finds the largest k that fits, leftover becomes spacing. Text is fitted
  with `TextMeasurer`; banners wrap the headline on the fewest lines that keep k comfortable (`BANNER_LINE_POLICY`).
  Minimum fonts scale with canvas height below 300px (`Metrics.min_font`). Explicit sizes travel in
  `Placement.font_size` and win over `font_scale` in `resize._fit_text`. Plain arithmetic, no `stretchable`.
  `PlanOptions` (hero_side, spacing, scale_bias, chips, text_flow) parameterize the variants that
  `candidates.py` enumerates; defaults reproduce v1. A button-like group (shapes + one label) whose
  uniform scale would push the label under the role's min font is *squeezed*: label at the floor font,
  pill re-shaped around it (`_Scaled._squeeze`; this is how a 160×600 skyscraper gets a 12px CTA).
  Column plans bottom-anchor a CTA that hugged the bottom in the source and keep the logo's height share.
  Tests: `tests/test_floorplan.py`. Renders: `docs/floorplan_v1/`. Known gaps: text-only groups and
  secondary images are sized as badge-like "chips"; the logo asset's transparent padding makes logos look small.
- `textfit.py` — `TextMeasurer` mirrors cr-renderer: skia glyph widths, greedy wrap at spaces (no letter spacing),
  lines at font_size×line_height from box top, no clipping. `fit_font_size` binary-searches integer sizes.
- `vlm.py` — local VLM adapter (llama-cpp-python 0.3.36, Qwen3-VL GGUF in `models/`, baked into the image by
  the Dockerfile's weights stage with sha256 checks). `describe(image|[images], prompt, schema, max_tokens,
  timeout_s, max_side)` → dict valid against the schema or None; never raises; grammar-constrained JSON,
  temperature 0, fixed seed; cached by image+prompt hash (memory, plus disk with `CHAMELEON_VLM_CACHE_DIR`);
  cooperative timeout; `CHAMELEON_VLM=0` switches it off (resize() does not import it yet, so output is
  unchanged). Bench: `tools/vlm_bench.py` (set-of-marks roles vs analyzer, good-vs-perturbed judge probes);
  numbers, model choice and the Docker/wheel findings in `docs/VLM_BENCH.md`. Weights are not in git;
  `python -m engine.vlm input/*.json` is the smoke test. Tests: `tests/test_vlm.py` (stub backend).
- `perceive.py` — **S1 VLM perception (2026-10-24, docs/S1_PERCEPTION.md, tests/test_perceive.py)**: `perceive(source,
  analysis)` renders the source once (896 px), draws one numbered magenta box per analyzer unit (set of marks, the
  bench's overlay), asks the VLM with the *hinted* prompt (box types + text) for every box's role (the analyzer's
  fine enum, grammar-constrained), a design `archetype` (product_ad | event_poster | editorial | quote | grid |
  other) and the 5 most important boxes → `Perception(roles={unit_key: (coarse, conf)}, fine, archetype,
  importance, status)`. Coarse classes (`COARSE`: picture / headline / cta / logo / badge / secondary / minor) are
  what the merge acts on; confidence is *derived* (bench accuracy per class, divided among boxes sharing a
  unique role, 0 on a type conflict), not a model probability. Off unless `CHAMELEON_VLM=1` **explicitly**
  (default off; then `engine.vlm` is never imported), per-task budget `CHAMELEON_VLM_BUDGET_S` (20 s, covers
  load + render + call), cache by source hash (memory + `CHAMELEON_VLM_CACHE_DIR`), never raises.
  `python -m engine.perceive input/*.json` shows what the model sees. ~9 s p50 / 12 s p95 per uncached call
  natively (4B, 8 boxes p50), 11–13 s per task in the arm64 container (≈ native, not 3×), 2.4 s model load.
  **Verdict (docs/S1_PERCEPTION.md): no-go for VLM on by default** — against DesignAsCode labels the 4B's coarse
  role agreement (0.69) is below the rules (0.71); the three-voter merge gains +0.2 pp over rules+classifier; the
  300-design eval is mixed (judge hard fails −24 %, but designer reading-order tau −0.03 and the rules' headline
  / CTA shrinks 3× as often). Next: human A/B of `s1_off` vs `s1_model` / `s1_vlm` on the label page.
- `role_merge.py` — S4's two-voter `merged_roles` / `apply_to_analysis` plus the **S1 three-voter vote**
  (`vote_roles` / `apply_votes(analysis, source, perception)`), called from `resize.understand()` before
  candidate generation: background / panel / decorative / shape-only units and unit membership stay with the
  rules; the coarse class is the majority of rules, classifier (≥ `MIN_CONF`) and VLM (≥ `VLM_MIN`), a
  three-way split goes to the VLM at confidence ≥ `VLM_TIEBREAK` (0.6) else the rules; classifier alone keeps
  S4's `STICKY` / margin policy, VLM alone needs 0.6; fine splits (subhead / body / fine_print, hero / image)
  change only when both models agree against the rules; then one headline / CTA / logo / hero (strength =
  classifier P + VLM conf + importance bonus + `RULE_BONUS`). Every unit's decision is recorded with its
  voter in `analysis.perception["decisions"]` (`by` ∈ rules, rules+model, rules+vlm, model+vlm, model, vlm,
  consistency); `Judged.summary()["roles"]` carries archetype / VLM status / voter counts, `resize.LAST_ANALYSIS`
  the full record (the playground's analysis table shows "Decided by"). `candidates.py`: the archetype reorders
  `plan_variants` and taxes plans that fight it by `ARCHETYPE_PENALTY` (3, `Candidate.prior`, applied in
  `judge` like the adaptation penalty): editorial / quote → hero-first plans (wide hero_side ≠ stack, square
  left / right, banner text_flow column) pay, grid → chips ≠ row pay. With both flags off nothing changes:
  `tests/fixtures/golden_v5/` holds the three samples × 6 targets from the pre-S1 tree and
  `test_output_is_byte_identical_to_v5_with_the_flags_off` compares byte for byte (macOS only: Linux text
  widths differ). Measurement tools: `tools/eval_perception.py` (samples / dac / precompute / report, results
  in `eval/data/perception/`), `eval/s1_sheet.py` (source | VLM off | VLM on rows for the both-bad cases,
  docs/sanity_s1).
- `geometry.py` — `Box` helpers. Tests: `chameleon/tests/` (`.venv/bin/python -m pytest tests -q`, pytest is
  dev-only, not in requirements.txt). `tests/test_judge.py` covers the judge loop (winner defect-free,
  perturbed layout scores worse, rectifier removes an injected overlap, < 10 s per task).
- Judge renders: `docs/judge_v1/` (three samples + Level 2 → 1080×1920, 160×600, 1200×628). Make them with
  `tools/compare.py compare <dir> [--target WxH] [task.json]`; `tools/compare.py sheet <dir>` writes a
  contact sheet of every candidate with its score breakdown.
- Renderer facts: text is NOT vertically centered or clipped in its box; a single over-wide word overflows;
  drawing uses int(font_size). Comparison renders of each milestone go in `docs/<milestone>/`.
- **v3 rule upgrades (2026-10-23, docs/EVAL_V3.md, tests/test_v3_rules.py)**, borrowed from the rivals in
  docs/COMPETITORS.md:
  - `contrast.py` — no-render contrast estimate: the layers under each text's painted box are composited
    from the JSON (canvas white, shapes with fill alpha × opacity, ellipses inside only, image assets sampled
    through their `fit`, missing asset = the renderer's grey placeholder) at a 32×8 grid; a text's ratio is the
    25th percentile of the WCAG ratios of its colour (and style-run colours covering ≥ 10 %) at those points,
    `busy` the spread of the composited colours. numpy (ships with skia) does the arithmetic; without it the
    estimate is empty and the scorer stays neutral. ~1 ms per design vs ~70 ms for a render; log-ratio
    correlation with the render-based check 0.97 on 300 eval cases (`eval/contrast_check.py`).
  - Judge loop is two-stage (`resize.judge`): every candidate scored without pixels (estimate), then the top
    `TOP_RENDER` (3) re-scored with a text-less render that refines ratio / busyness. Contrast hard fail is the
    *drop rule*: headline / CTA ratio < 3 **and** < 0.5 × the same text's ratio in the source (`Analysis.
    source_contrast`), so stand-in assets and loosely built sources are not our fault.
  - `analyze.py` units beyond `group_id` (union-find): *holder* (text ≥ 80 % inside a shape / flat image
    drawn below it: one label in a pill ≤ 12 % of the canvas, or several short lines in a sticker ≤ 6 %;
    a bigger shape holding text becomes a PANEL), *frame* (shape of about a photo's size behind it, unit keeps
    the photo's role), *host* (a thin bar or a shape inside the box of a single text / image, ≤ 3 per host,
    tested against the host element itself so bars never chain), absorbed decorations, *sibling rows*
    (≥ 2 chip-like units of one role, similar height, side by side → one `kind="row"` unit with `parts`).
    `Unit.kind/primary/attachments/parts`; `is_group` now means "more than one element". One CTA per design:
    a one-label pill at least as wide as tall beats a free text that looked like one. Reading order, panel
    carry and anchors unchanged.
  - `floorplan.py`: `_TextItem` footprints are the *painted* extent (`TextMeasurer.painted`: caps start
    ascent − 0.78·fs below the box top, last baseline + descender only when the text has descenders) plus
    the attachments, which keep their offset from the painted top/bottom in font units; a letter-spaced line
    wider than its budget at the floor widens its box so the planned font really fits. Floors:
    `Metrics.min_font` = max(old rule, 0.85 % of the long side × {legal 0.7, badge 0.8}); logo ≥ 0.14,
    hero ≥ 0.30, stamp ≥ 0.08 of the short side (`*_FLOOR_FRAC`, on the unit's larger dimension, capped by the
    slot); chips keep up to 18 % of the canvas height when they were big in the source. *Rescue mode*
    (`_Item.relax`, `RESCUE_FACTOR`): when even the floors do not fit, secondary / minor floors drop to 0.55×
    (headline, logo, CTA keep theirs) before the plan is allowed to overflow. Button squeeze allows 3 lines at
    the floor and a last resort at the floor whatever the height. Row parts in `chips=corner` alternate the two
    corners of their edge. `resize._keep_headline_largest` caps any text that was smaller than the headline in
    the source at the headline's output size.
  - `rectify.py` / `score.py` source-relative rules: `unwanted_overlaps` flags a pair only when its overlap
    (fraction of the smaller visible box, per part of a row) exceeds the source's by > `OVERLAP_TOL` (1.5 pp);
    off-canvas is excused up to the bleed the source had (+1 %); a headline / CTA is below the floor only if it
    also shrank below 0.98 × source font × canvas scale (`score.below_floor`, shared with eval/metrics);
    `faith.hierarchy` adds the role-rank rule (higher role keeps ≥ min(0.82, source ratio) of the lower one).
    Penalties outside the 0–100 breakdown (`Score.penalty`): anchor strategy on ratio change ≥ 1.75 pays
    `ADAPT_PENALTY` (18; it still wins when it is the only clean candidate), a floor plan on ratio change
    < 1.25 pays up to `DISRUPT_PENALTY` (4, linear to 0) so an identity resize stays the identity.
    `SMALL_CHANGE_MAX` is 1.75. Layout metrics (balance, alignment, fill, margins) use visible boxes.
  - Dev tools in `eval/`: `sanity_sheet.py <design> <dir>` (all-preset contact sheet, docs/sanity_v3),
    `contrast_check.py`, `remeasure.py` (re-judge an old run's outputs under the current metrics, used for
    the v2 baseline), `compare_runs.py` (before/after table on common cases).
- **v4 size ambition (2026-10-24, docs/EVAL_V4.md, tests/test_v4_size.py)**: the engine uses the canvas when
  it has room. `candidates.py` adds `scale_bias` 1.3 / 1.5 (`BOLD` / `BOLDER`) and a `fill` variant
  (`PlanOptions.fill`: one shrink speed for everything, so the k search is a global-scale search from
  1.5× proportional down) to every family, anchor boost 1.4, `MAX_CANDIDATES` 18; banners also try
  `text_flow="column"` (the wide plan on a banner ≥ `BANNER_COLUMN_MIN_H` = 160 px tall: hero beside one
  column with logo, text, chip row, CTA, legal) and keep the v3 stacked chips as `chips="stack"`.
  `floorplan.py`: a scaled unit's ideal is at least `Metrics.prop` (sqrt of the area ratio) × `Metrics.bias`
  (share-of-canvas ideals alone left a 6 % CTA at its floor on banners); the wide plan keeps the hero at full
  size and tries `HERO_SHARES` (0.45/0.36/0.28 of the width), its fit test also requires the headline on
  ≤ `HEAD_MAX_LINES` (3) lines; `_Chips` direction `"auto"` packs rows first and columns only when the rows
  do not fit the height (banner default); a text line wider than the canvas shrinks below its floor instead
  of overflowing (`_TextItem.hard_w`; the fitter would shrink it anyway but attached bars kept the bigger
  font's offsets); `K_SEARCH_STEPS` 10. `score.py`: new `layout.size` (weight 8: headline / CTA font and
  hero / logo linear size vs `AMBITION` (1.2) × proportional, clamped, so nothing past the cap is rewarded;
  read.size 12, read.lines 7, balance 7, faith.scale 3 to keep the sum at 100), `layout.fill` is 60 % hull
  + 40 % ink density (`GOOD_DENSITY` 0.30), fine print is left out of the spacing chains (a bottom-anchored
  legal line is a convention). Hard fails, the drop rule and the source-relative rules are unchanged.
  Level 3 → 1584×396: headline 16 → 28 px, product 165 → 356 px, badges in one row, 0 hard fails.
  Cost: ~2× the v3 runtime (more candidates, up to 3 share searches in the wide plan).
- **v5 generation fixes from human labels (2026-10-24, docs/EVAL_V5.md, docs/LABELS_V1.md,
  tests/test_v5_labels.py)**, one mechanism per "both bad" pattern; the eval design ids are regression cases only:
  - *Banner cohesion*: `_plan_banner` caps each gap at max(`MAX_GAP_MULT` 3 × gap, `MAX_GAP_FRAC` 8 % of the
    width) and centres the clustered row; `score.layout.cohesion` (weight 4; read.size 11, layout.fill 7) is
    the widest empty stretch between the runs of visible boxes along either axis, free up to the same cap, 0 at
    half the span (fine print excluded).
  - *Importance tiers / water-filling*: every `_Item` has a `tier` (primary / hero / secondary / minor, from the
    nominal shrink speed, so `fill` variants keep it). When even the floors do not fit, `_largest_k` relaxes
    floors by `RESCUE_STEPS` (minor ×0.55, secondary ×0.55, minor, hero, secondary), never the primary tier and
    never below `ABS_MIN_FONT` (4 px); the k search then hands the room to the headline / logo / CTA first.
    The banner `_TextColumn` *flows* into several columns (reading order kept) when one column cannot fit the
    strip at the floors (`_flow`), and an attachment never makes a text's footprint taller than its slot (a bar
    that ran along a list is capped at the room left). Eco-talks → 728×90: headline 10 → 32 px, 0 hard fails.
  - *Rotated text*: a vertical text in a column runs along at most `VERTICAL_LEN_SHARE` (0.5) of the column and
    wraps beyond (spine-label style); vertical texts that ran along the hero's sides in the source become *rails*
    (`_HeroRails`, `_beside`): one line each, sized against the hero's height (up to `RAIL_LEN_SHARE` 0.6 of the
    column), hero gets the width they leave. Column plans keep the hero in its source reading position (texts
    that preceded it stay above, the rest below). NY Furniture Fair → 160×600: rails 5 → 10 px beside the photo.
  - *Tall strips* (w/h ≤ `STRIP_MAX_RATIO` 0.5): font floors also relative to the width (`STRIP_FONT_FRAC`:
    headline 4.5 %, CTA 3.5 %, other 3 %; the absolute 12 px still wins on 160 px); `_absorb_leftover` grows the
    hero (`_Scaled.grow`, capped by the builder's `cap_s` and `HERO_MAX_SHARE` 0.55 of the height) when the
    width-bound text leaves the column short.
  - *Straddles*: `contrast.estimate` also reports the 25th-percentile ratio per `SLICES` (4) along the long side
    and caps `ratio` by the worst slice; `rectify.is_straddle` = one slice < 3, another ≥ 4.5 and ≥ 4× the worst
    (a sharp edge, not a gradient's glow). A straddling text that did not straddle in the source
    (`Analysis.source_straddle`) is a hard fail in `score_design` (notes["straddles"]) and `rectify.fix_straddles`
    (first 2 passes) slides the unit fully onto the side where the estimate reads, when free and on canvas.
  - *Graze rule*: `rectify.text_graze`: a source text-on-text overlap thinner than `GRAZE_EM` (0.9) × the smaller
    font in either direction (lines that ran into each other after font substitution) is left out of the
    source-overlap table, so the output must not keep it (a lockup overlaps by a full line and is kept).
  - *Layered panels*: `analyze._panel_stacks`: rectangular panels of about the same size (areas within 0.7, the
    smaller ≥ 0.6 inside the larger, same fill or ≥ 0.85 inside) are one `kind="stack"` PANEL unit (top member
    first); `relayout.stack_boxes` keeps each layer's inset from the hull (scaled by the padding scale) in
    `place_panels` and `grow_panels`.
  - Also: text boxes in floor plans hug their wrapped lines (`_TextItem._size_at`: widest line + one space, glyph
    width for negative letter spacing: wrap-safe under the renderer's character-based wrap), the pre-judge
    `resolve_vertical_collisions` compares a sibling row per part, and `_finalize` shrinks a rotated shape /
    image whose extent is larger than the canvas. `eval/compare_runs.py` reports `layout.cohesion` and the
    smallest font p50 / headline-CTA p05 / p50.

- **v6 designer references as the target (2026-10-25, docs/EVAL_V6.md, tests/test_v6_rules.py,
  tests/test_structure.py)**; measured with `CHAMELEON_OPTIMIZE=0`:
  - `rectify.OverlapRules` (`overlap_rules(analysis, m).conflict(a, b, pa, pb, gap, tol)`) is the one predicate the
    rectifier, scorer, eval metrics and tests share. Beyond v3's source-relative rule: a text whose role the source
    laid over a picture / shape (≥ `LAYER_SRC_MIN` 0.3 of its ink) may lie on one again (≥ `LAYER_MIN` 0.3 on it);
    a text ≥ `HOSTED_INSIDE` 0.8 inside a shape / image drawn below it is never a collision; a source-layered pair
    with a non-text side may overlap up to `LAYER_GROW` 2× the source amount; text on text stays at +1.5 pp. The
    graze rule exempts lockups: ink ≥ `GRAZE_CONTAINED` 0.8 on the other text's *lines* (`ink_lines`) and the two
    differ ≥ `LOCKUP_FONT_RATIO` 1.5× in size or are the same word (a shadow copy).
  - `score.py`: `text_overflows` (painted ink + `OVERFLOW_SLACK` 0.5 px, also eval's `overflow_n`); `layout.margins`
    skips picture / shape blocks ≥ `BIG_UNIT_FRAC` 0.15 of the source canvas (`margin_judged`); `bleed_allowance`
    lets a picture / shape that bled ≥ 1 % bleed up to 1.5× (cap 25 %); `layout.spacing` is source-relative
    (`source_spacing_cv`: the source's own gap unevenness is free); strategy `"structure"` pays the disruption
    penalty like a floor plan. Breakdown keys, hard-fail strings and `Score` fields are unchanged.
  - `engine/structure.py` — preserve-structure family: `detect_structure` (zones = panels + pictures / shapes
    ≥ `ZONE_MIN_AREA` 0.10, bleeding photos ≥ 0.25, never rotated; carried content ≥ `CARRY_MIN` 0.3 on a zone
    below it; cards ≥ 0.8 inside a zone; bands on the source's stack axis, splits on visible extents; kinds
    bands / split / lockup, None without a zone) and `structure_relayout(analysis, target, elements, m,
    StructureOptions(flip, swap, spacing), structure)`: text leaves re-wrap with floorplan's `_TextItem` and one
    global k, blocks capped at their source share of the stack length, elastic full-bleed panels, aspect-kept
    pictures, rails for vertical texts in zones, leftover to zones by source weight, splits stack on strips
    (`UNSPLIT_RATIO` 0.4). `candidates.generate_candidates` adds 2–3 variants (strategy `"structure"`,
    `MAX_CANDIDATES` 21): keep / flip (orientation change) / swap (split).
  - `eval/metrics.designer_agreement(ours, ref, analysis)` → `da_*` (centre error, within-10 %, reading-order tau,
    size rho, `da_agreement` mix); `tools/designer_compare.py` reports winner + best-candidate agreement per
    format / design (`--out <sub>`, `--labels <jsonl>` writes the 240 weak pairs `eval/data/labels.designer.jsonl`,
    gitignored). Numbers: references with hard fails 61 → 10 (3 CTAs the designer set under the 12 px floor, 7
    overlaps the source never had), engine hard fails on the 240 cases 11 → 0, winner agreement 0.594 → 0.601
    (best candidate 0.711; the judge, not the generator, is the gap), structure wins 67/240. The designer pairs do
    not fit a linear reweighting (hand weights side with the designer in 31 %): the preference is compositional.
    `tests/fixtures/golden_v5` regenerated from this tree (flags off, optimiser off).

## v9: critic loop, defect-driven regeneration (2026-10-25, docs/CRITIC_LOOP.md, tests/test_critic.py)
- `engine/critic.py` — the judge's verdict feeds back into generation. `diagnose(judged, analysis, source,
  target)` names the *shared* failures: when no real candidate is clean, every hard fail of the best one and
  every kind ≥ `SHARE_MIN` (50 %) of the pool shows (`below_floor`, `contrast_drop`, `straddle`, `collision`,
  `off_canvas`, `overflow`, parsed from the judge's hard-fail strings); when one is clean, a term the top
  `TOP_SOFT` (3) clean candidates all score under `TYPICAL[term]` (p25 of the v8 winners) and that has a repair.
  Each `Diagnosis` carries `Recipe`s: PlanOptions overrides (`rescue`, spacing, scale_bias, chips, fill) and / or
  *directives* that `resize.realize(..., directives)` applies to the materialized elements before the rectifier
  (`apply_directives`): `floor` (raise a headline / CTA to its floor, re-wrapped on ≤ 3 lines / 1 for a CTA;
  tracking is given up before size; a vertical spine that cannot run along the canvas is levelled; a pill label
  reshapes its pill; over-tall attached bars are trimmed; the unit is `protect`ed), `backing` (the plate / panel
  whose fill the text read against in the source covers it again; an occluding card is slid off or cut back),
  `onto` (the text goes back onto the picture it was layered on, fitted inside), `off`, `pin`, `shrink`, `widen`,
  `refit`, `cap_floor` (the headline-largest cap never pushes a text under its own floor). Recipes are keyed on
  roles / relations, never ids or sizes.
- `candidates.generate_repairs(analysis, source, target, diagnoses, seeds, already)` → ≤ `MAX_REPAIRS` (6)
  `Candidate`s named `<seed> +fix:<label>` (seed's strategy and prior, `Candidate.directives` / `.fix` /
  `.structure`), plan recipes re-running the floor plan of ≤ 2 floor-plan seeds, directive recipes reusing the
  seed's placement, deduped on (placement key, directives) against everything judged.
- `resize.repair()` runs after the stage-1 sort and **before** the optimiser (one refinement pass, on repaired
  seeds): up to `critic.settings()` rounds (`CHAMELEON_CRITIC_ROUNDS` 2) of diagnose → regenerate → judge (priors
  included), stopping when the best is clean and ≥ `CHAMELEON_CRITIC_TARGET` (88, p60 of the v8 clean winners),
  when nothing is diagnosed or a round adds nothing new; round 2 seeds from repairs that removed their defect.
  `resize.LAST_CRITIC` and the winner's `notes["critic_rounds"]` record the rounds; each repair's
  `notes["critic"]` names round, recipe and directives (the playground lists "+fix:" candidates).
  `CHAMELEON_CRITIC=0` is byte-identical to the loop without it (test); `floorplan.PlanOptions.rescue` and
  `rectify(..., protect=)` are the two knobs added for the recipes (default off, no effect otherwise).
- Numbers (docs/CRITIC_LOOP.md): eval slice of 300 designs (4198 cases) judge-hard winners 42 → 24, fallback
  wins 9 → 7, no new hard fails, judge mean 75.9 → 80.4, runtime p50 +0.015 s (p95 +0.15 s); designer
  agreement 0.608 → 0.608 tuning, 0.610 → 0.614 hold-out; a "+fix" candidate wins 16 % of cases, mostly soft
  recipes (pin / bolder / tighter). **Default on** (`critic.DEFAULT_ON`). Measurement tools:
  `eval.compare_runs critic_off critic_on3`, `eval.compare_optimize --flag CHAMELEON_CRITIC` (the v7 tool
  generalised to any switch), sanity sheets in `docs/sanity_critic/`. Two judgement calls inside the
  recipes: a tracked display word gives up letter spacing before size, and a vertical / diagonal headline that
  cannot fit a strip at the floor is set horizontal.

## S6: text-only LLM reading of the design JSON (2026-10-26, docs/LLM_S6.md, docs/LLM_BENCH.md, tests/test_llm.py)
- **Benched and rejected; nothing wired.** `engine/llm.py` (the engine/vlm.py pattern without the image: an
  id-free, order-free element listing → grammar-constrained JSON with a role per element, semantic groups,
  archetype / focal / importance and per-family `PlanOptions` preferences; cached by source hash; off unless
  `CHAMELEON_LLM=1`, and then the engine still never imports it: `resize.py` / `candidates.py` / `role_merge.py`
  are untouched, so the output is byte-identical by construction). `Reading.perception()` is a
  `perceive.Perception`, i.e. the hook into `role_merge.apply_votes` exists but is not called.
- Numbers (`tools/llm_bench.py roles|groups|report`, 60 DesignAsCode designs ids stripped = S1's set, 60
  designer designs × 12 formats; raw results + 360 cached answers in `eval/data/llm_bench/`): coarse role
  agreement alone Qwen3-1.7B 0.581, Qwen3-4B-Instruct-2507 0.618, Gemma-3-4B-it 0.674 vs rules 0.713 and the
  classifier 0.825 (in-sample); logo 0/4 for all; as a third voter at best +0.9 pp (Gemma); groups weakly
  above chance (members adjacent in ≥ 80 % of the designer's formats 0.45–0.48 vs 0.31 random, 0.88 for the
  analyzer's units); plan prior constant (hero left / chips row / keep true on 59–60 of 60). Latency native
  p50 / p95 6.6 / 9.8 s (1.7B), 14.4 / 22.4 s (Qwen3-4B, plus two stalls > 100 s), 12.1 / 19.1 s (Gemma).
- Weights (gitignored, 6.1 GB, sha256 + repos in docs/LLM_BENCH.md) in `models/`; no Dockerfile change
  (docs/LLM_S6.md §6 has the args a second weights set would need). Gotchas: llama.cpp's JSON-schema grammar
  ignores integer min / max (element numbers are string enums), the grammar's property order is the answer
  order (never build it from a `sort_keys` dump), and a plain roles array lets a small model lose its place
  (the answer is keyed by element number). The only idea left open: ask the model just where the rules'
  headline is a guess (docs/LLM_S6.md §7).

## v10: backdrop awareness (2026-10-26, docs/EVAL_V10.md, tests/test_v10_backdrop.py)
- `engine/backdrop.py` — the background as a composition. `BackdropMap` (24×24 cells × 3×3 samples of
  luminance / colour with summed-area tables) `from_json` (engine/contrast.py's layer compositing, ~1–2 ms) or
  `from_image` (a text-less render; pixels are a bonus, never a dependency); a text's `Signature` under its ink
  (lightness = luminance^0.45, busyness, *glow* = lightness − canvas median, hue / sat, `over` = the element it
  lies on); `source_signatures(analysis)` cached per task. Three uses, all behind `CHAMELEON_BACKGROUND`
  (=0 byte-identical to v9; `tests/test_perceive.py` pins it off for the v5 goldens) with per-piece switches
  `CHAMELEON_BACKDROP_SLIDE / _QUIET / _PATTERNS` (default on) and `_JUDGE` (**default off**):
  - *slide* (`slide_texts`, called by `floorplan.slide_backdrop` at the end of `floorplan_relayout` /
    `structure_relayout`): `_place_column` records a slot per text item in `Placement.slots` (column width, the
    room down to the neighbours' gaps); each headline / subhead / body / CTA text moves inside its slot to where
    the target's map (built from the placement's non-text elements) looks most like its source signature, only
    when ≥ `MIN_GAIN` (0.12) closer, never onto another unit; moves in `Placement.notes["slide"]`.
  - *quiet area* (`quiet_position`, critic directive `quiet`, recipe "<role> onto the quiet area"): replaces the
    v9 `onto` move on `cover` pictures (the crop changes with the box) and follows it on `contain` ones; samples
    the text's own contrast estimate at 5×5 positions over the picture, best ratio then shortest move.
  - *judge term* `read.backdrop` (`score.active_weights`: `BACKDROP_WEIGHT` 3 taken proportionally from the
    layout block, `CHAMELEON_BACKDROP_WEIGHT` dev knob; `CHAMELEON_BACKDROP_PIXELS=1` compares pixels with
    pixels in stage 2 at the cost of one source render, ~70 ms). Off by default: on the 720 designer references
    it never paid (tuning −0.004 / −0.003 / −0.001 at weight 3 / 2 / 1, hold-out within noise).
- `engine/patterns.py` — the free decorations (role decorative, on-canvas area < 20 % of the canvas: bleeding
  photos are backdrops) as one arrangement: `analyze()` fills `Analysis.patterns` (`detect_patterns`: corners /
  edge / diagonal / mirrored / scatter from geometry) and `relayout.decorative_boxes` → `place_pattern` places it
  as a whole in all three strategies (corners keep inset ratios, edge runs their edge, mirrored pairs their axis,
  diagonals their angle and spacing ratio, scatters their centre fractions; sizes × min(sx, sy) as before).
  Census: 15 of 450 corpus designs (3 corners, 1 mirrored, 11 scatter) and Level 2 (corners). Goldens: the 5
  Level 2 files in `tests/fixtures/golden_v10` (only the two circles move); everything else byte-identical.
- Numbers (docs/EVAL_V10.md §4): no-pixel slice (300 designs, 4198 cases) judge contrast fails 11 → 10, fallback wins 7 → 5,
  hard defects 13 → 13; pixel slice (150 designs) defects 7 → 7, terms within 0.003; designer references tuning
  0.608 → 0.607 (up 9 / down 7), hold-out 0.614 → 0.615; runtime p50 0.626 → 0.645 s single process. The slide acts
  in 8.6 % of plan / structure candidates but rarely in the winner (4 of 2152). Tools: `eval/backdrop_report.py` (census, by-eye `moves` sheet of
  texts that landed on a different backdrop, single-process `runtime`), sheets in `docs/sanity_v10/`,
  designer comparisons in `docs/designer/compare/v10_backdrop` and `v10_ablate_*`.

## v11: the five roadmap implementations (2026-10-29, docs/EVAL_V11.md)
- `engine/flags.py`: `CHAMELEON_V11=0|1` master, `CHAMELEON_V11_<PIECE>` per piece (COMPOSE, SOLVE, TYPESCALE, UNITS,
  STRIP on by default; AIR opt-in only, the master never turns it on). `CHAMELEON_V11=0` is byte-identical to v10
  (`tests/test_perceive.py` / `tests/test_v10_backdrop.py` pin it for their goldens).
- COMPOSE (`floorplan.PlanOptions.compose`, `candidates.compose_variants`): designer compositions as plan variants.
  Wide: `bleed` (hero flush with its side edge at full height, wider gutter), `header` (`_plan_header`: headline
  across the top on <= 2 lines, hero beside a `_Stack` of the rest). Banner: `bookend` (logo / CTA pinned to the two
  ends, rest centred with the cohesion cap), `twotier` (one-line headline above a `_Row` of copy / chips / CTA),
  `bleed` (hero full strip height at one end), and `bleed` + `text_flow=column` on strips >= 160 px. New generic item
  `_Stack`. The candidate `limit` grows by the variants added, so the fallback is never truncated.
- SOLVE (`engine/solve.py`, `resize.solve_pass`): joint minimal-move pass per axis, Dykstra projections (numpy):
  near-aligned edges / centres (`ALIGN_FRAC` 1.2 % of the short side) exactly aligned, nearly even stack gaps
  (`EVEN_RATIO` 1.6) exactly even, order + min(gap, rectifier gap) kept, layered pairs move together, canvas margin;
  translations only (no font change), any move > `MAX_MOVE_FRAC` 4 % drops the solution; contradictory families
  are retried alone. Runs on the winner only (`SOLVE_TOP_K` 1: on the top 3 its tenths of a point lifted a worse
  seed) as "<seed> +solve", dropped on a new hard fail.
- TYPESCALE (`floorplan._Builder._type_scale`): every horizontal secondary text keeps its distance under the
  headline (`TYPE_RATIO_MIN` 1.25 / `TYPE_RATIO_MAX` 2.6, or the source's ratio when outside) via `_TextItem.lead`
  in `font_at`; copy longer than `MEASURE_MAX_CHARS` (75) wraps at that measure (`measure_w`). `PlanOptions.air`
  (reserve `AIR_SHARE` 12 % of the column as whitespace) exists but is AIR-gated: 13 wins, agreement -0.022.
- UNITS: `analyze` d2 compound phrases (two single-line texts on one row <= `PHRASE_GAP_EM` apart, <= 30 chars:
  the bigger hosts the other as an attachment; 5 of 450 corpus designs), a button label must be <= 64 chars and
  <= 2 lines (a paragraph in a box is not a CTA); `floorplan._collect` moves pictures >= `SECONDARY_IMAGE_MIN`
  (6 %) of the canvas out of the chips into `_Slots.images`, sized from their own source share
  (`_Builder.images`, a `_Row` gallery for several) right after the hero in column plans; banners keep them as
  chips (`chips(with_images=True)`). 53 of the corpus's 95 secondary images are that big.
- STRIP (tiny formats, `floorplan.is_strip`: w/h <= 0.5 or a banner <= `STRIP_MAX_H` 120 px): tall strips get
  `STRIP_MARGIN` 3.5 % / `STRIP_GAP` 3 % margins; tracking gives way before size (`_Builder._tracking`,
  `TRACKING_STEPS`, measured on the wrapped lines at 0.9 of the inner width because the renderer wraps on glyph
  widths and paints the spacing on top; also in the button squeeze), carried as `Placement.tracking` and applied in
  `resize.materialize`; attachments are clipped to the slot width (`_TextItem.clip_att`: a headline's bars pushed it
  off a 160 px canvas and the rectifier halved it); `_keep_inside` slides units poking past the edge back in;
  `_fit_text` grows a box (<= 1.6x) instead of halving a planned font; rescue variants (`rescue=True`, + bold,
  + tight) on strips, and only those set multi-line headlines tighter on short banners (`_leading`,
  `LEADING_MIN` 0.95, `Placement.leading`: on every plan it pushed a clean leaderboard into a collision);
  `resize.strip_prior`: on a short banner a headline wrapped beyond `STRIP_HEAD_LINES` (3) pays
  `STRIP_LINES_PENALTY` (3) unless its own line breaks make it longer.
- Eval tooling: `eval/compare_optimize.py --workers N` (spawned pool) and a "best candidate agreement" row.

## v12: nothing the source showed is hidden (2026-10-29, docs/EVAL_V11.md "v12", tests/test_v12_visible.py)
- Found by competitor sweep 4: a rival cites an Oct 21 info-session ruling that every element must be *visible in
  the render*, not just present in the JSON. Ours hid content in 107 of 4,198 slice outputs (37 heroes, 19 logos, 7
  images, 1 headline, 77 free shapes), also in v10, e.g. a white card blown up to a story's full height drawn above
  the photo it used to sit beside.
- `engine/visibility.py`: `coverage` samples a 9×9 grid over each element's visible box (text = ink) against
  opaque elements drawn above it from other units (`is_cover`: rectangle / ellipse shapes with fill alpha × opacity
  >= 0.95, `cover` images, unrotated); `hidden_content(analysis, elements)` = content (not background / panel /
  decorative) >= `HIDDEN_FRAC` 0.9 covered while the source had it < `SOURCE_FRAC` 0.75 covered (one entry per
  unit; a unit's shapes count only when it has no text / picture). `reveal` repairs in place, up to 3 passes: a
  covering panel / background / decorative shape is cut back to the largest side clearing the element when that
  keeps >= `MIN_PANEL_KEEP` 25 %, else the hidden unit is drawn just above its cover and every `z_index` is
  renumbered to integers (the schema's type; the renderer paints by z, stable).
- Wiring (flag `CHAMELEON_V11_VISIBLE`, on; the master `CHAMELEON_V11=0` turns it off with the rest):
  `resize.realize` calls `reveal` after `grow_panels`; `score_design` adds the hard fail "<id> hidden under <id>
  (n%)"; `eval/metrics` reports `hidden_n` / `hidden_ids` (a defect count), `compare_runs` a "content hidden under
  a panel" row. 0 of the 720 designer references trip the rule.
- Numbers: slice hidden content 107 -> 0, every other defect still 0, judge mean 83.79 -> 83.77, runtime unchanged;
  designer agreement 0.607 / 0.615 unchanged (`docs/designer/compare/v12_visible`).

## Playground (dev tool, not shipped)
- `chameleon/tools/playground.py` serves a local UI at http://localhost:8765: pick a sample, upload or paste a
  design, pick a preset or custom size; shows source / stretch-baseline / output renders (fit or 1:1, optional
  role-colored element boxes), every judged candidate with score breakdown (click one to inspect it), inferred
  roles, self-check warnings, output JSON, downloads, and a "Run all formats" gallery across every preset.
  Reloads `engine/*` on every run. Start with the "playground" entry in `.claude/launch.json` (preview_start)
  or `cd chameleon && .venv/bin/python tools/playground.py`. It depends on `resize_with_candidates` /
  `Judged.summary()` and `engine.render.render_design(design, max_size)`; keep those stable.
- **Design picker** (next to the sample dropdown, "Browse designs"): filter by title / id / format / archetype,
  family chips, "designer refs only", ↓/↑ + Enter in the filter box; a click loads the design's source into the
  JSON textarea, keeps the current target and runs. `GET /api/designs` → compact list (id, title, w, h, family,
  n, nt, format, kind eval | sample | docs, arch, refs = number of designer formats, batch, holdout), built once
  and cached (`?refresh=1` rebuilds) from `eval/data/index.json` (falls back to scanning `eval/data/designs/`)
  plus the designer folders: `docs/designer{,2}/out/<id>__<WxH>.json` give the refs, `manifest.json` /
  `picks.json` titles and archetypes, `designer2/holdout_ids.json` the hold-out flag, `src_NN_<id>.json` the
  sources of designs that are not in eval/data (the three samples, or everything when eval/data is absent:
  60 rows from docs alone, `[]` when neither exists). `GET /api/design?id=` → `{id, title, source, meta,
  target (samples only), holdout, refs: [{size, w, h, batch}]}` (404 `{error}` for an unknown id; ids are
  `[A-Za-z0-9_-]+`). When the loaded design has designer layouts, `POST /api/resize` takes the page's `design_id`
  and adds `designer` (`{size, available, holdout, batch, canvas, png}`, `png` null when the current target is
  not one of the 12 designer formats; rendered in the same request) and the page shows a "Designer's version"
  row under the output with the available formats as chips (click = set that target and run, click the image =
  enlarge). The id is dropped when the JSON is edited by hand or uploaded; the sample dropdown and the eval
  browser's "Open in playground" (which now also sends `id`) keep it. A stale response from an earlier run is
  ignored (`runSeq`).
- The same server has an **eval browser** at http://localhost:8765/eval: filters every case of a harness run
  (`eval/data/runs/<run>/results.jsonl`) by format, shape family, defect type, strategy, text search; detail
  view renders source, our output and the designer's own version (ground-truth siblings) with defects and the
  judge's component bars; "Open in playground" hands the case over via localStorage. j/k step through cases.

## Docker status (see docs/DOCKER_CHECK.md, docs/VLM_BENCH.md)
- The Dockerfile has three stages: weights download (sha256-pinned, `--build-arg VLM_BASE_URL=` for a local
  mirror), an arm64-only rebuild of llama-cpp-python for ARMv8.2 (the prebuilt aarch64 wheel is generic
  ARMv8 and 8x slower), and the engine image. `.dockerignore` keeps `models/`, `.venv/`, `eval/data/` out
  of the context. Local arm64 build: `sed 's#^FROM --platform=linux/amd64 #FROM #' Dockerfile > /tmp/D &&
  docker build --platform linux/arm64 -f /tmp/D --build-arg VLM_BASE_URL=http://host.docker.internal:8787 .`
  with `python3 -m http.server 8787 --directory models` running.
- The shipped `linux/amd64` image builds but **hangs at run time on Apple Silicon without Rosetta**: skia
  segfaults under QEMU, inside the organizers' own renderer. A native arm64 build of the same Dockerfile
  runs the three samples offline in 4 s. Open question for organizers; guard any in-engine rendering with
  a fallback so resize() still returns a layout if the renderer dies.
- Text widths measured inside the Linux image are up to 18 % wider than on macOS (hinting, small bold text
  worst). Engine is self-consistent in the container, but **macOS eval numbers are optimistic: run the full eval
  inside the arm64 image before freeze** (docs/DOCKER_CHECK.md).

## Competitors (reference only)
- `docs/COMPETITORS.md` compares public rival repos; full clones live in `reference/competitors/` (read-only,
  untrusted, never copy code or run their scripts from here). Strongest rival: tailsgit (CP-SAT + retrieval).
- Best hint for the unpublished model cap: the same organizer's 2025 India round allowed <= 200 MB models,
  <= 10 s per task, 8 CPUs / 16 GB. Keep any learned component small.

## Version control
- Git repo rooted at AdobeHack/, remote https://github.com/GauravS11112003/AdobeHackathon (private), branch main.
  The starter's own .git was removed; upstream commit noted in chameleon/UPSTREAM.md.
- Worker sessions do NOT commit or switch branches; the coordinating session commits verified work with
  descriptive messages. .gitignore excludes .venv, eval/data, models/, output, reference/, .claude/.
- Keep the repo private until after the stage-one deadline (2026-10-30).

## Conventions
- System `python3` is 3.9 and too old for cr-renderer. Use the venv: `chameleon/.venv` (Python 3.11 from
  `~/.local/bin/python3.11`). Run everything from inside `chameleon/` as `.venv/bin/python -m engine.main`.
- Renderer entry point for ad-hoc previews: `renderer.converter.convert.render_design_to_png(design, Path('brand_kit/assets'), png_path)`.
- Python 3.10+. Sample tasks: `input/chameleon_sample_level{1_warmup,2_core,3_advanced}.json`.
- Local run: `python -m engine.main` writes `output/<task>_output.{json,png}` and runs a self-check
  (sanity net, not the official scorer).
- If output PNG shows labeled boxes instead of real text/images, cr-renderer failed to import.
- Keep TBD items (hardware, model cap, catalogue, submission form) in docs/CONTEXT.md §12 until confirmed.

## Eval harness (dev tool, not shipped; `chameleon/eval/`, results in docs/EVAL_V1.md)
- `eval/crello_convert.py` downloads a slice of the Crello dataset (HF `cyberagent/crello`; only the
  metadata columns, ~0.3 MB per shard via HTTP range requests, cached in `eval/data/raw/`) and converts
  templates to schema v0.9: pixels + degrees (the v5 parquet already stores both), z_index = layer order,
  opaque ids (`el_07`), no groups; text keeps content/font_size/color/align/line_height/letter_spacing +
  style_runs; fonts → Solstice Serif (serif/script families) or Sans, original font in the sidecar;
  image layers → the three brand-kit assets by shape (full bleed or big photo → gradient `cover`, wide
  → logo, else bottle); single-colour SVGs and ColoredBackground → shape rectangles. Text boxes are
  normalised to the engine's fit model (Crello's box = lines × font × line_height, the measurer needs
  ascent + descent; `--raw-boxes` keeps them). Skips >25 elements or no text. Writes
  `eval/data/designs/<id>.json` (source + meta + sidecar), `index.json`, `pairs.json` (same template at
  several sizes = designer ground truth). `eval/data/` is gitignored.
  `.venv/bin/python -m eval.crello_convert --target 450` (defaults: validation 0-2 + test 0-1).
- `eval/run_eval.py` runs `resize_with_candidates` over every design × the playground PRESETS (parsed
  from tools/playground.py) + one case per designer sibling, computes `eval/metrics.py` (ids, fields,
  immutables, important units on canvas, image aspect, measured overflow, min font vs floor, unwanted
  overlap area, judge breakdown, runtime, `gt_*` agreement with the designer's version: centre error,
  reading-order tau, size-hierarchy rho, font ratio) and writes `results.jsonl` (+ `outputs/*.json`),
  `results.csv`, `summary.json`, `summary.md` under `eval/data/runs/<name>/`. Resumable (done keys are
  skipped), `--workers N` (spawned processes), `--limit N`, `--presets a,b`, `--no-render`,
  `--summarize-only`. ~0.25 s per case; the full 6k-case run takes ~10 min with 4 workers.
  Smoke: `.venv/bin/python -m eval.run_eval --limit 20` (~90 s).
- `eval/report.py --run full --worst 30 [--notes file.md]` renders source/output contact sheets of the
  worst cases into `docs/eval_v1/` and writes `docs/EVAL_V1.md` (summary tables, auto patterns,
  hand-written notes). Tests: `tests/test_eval.py`.
- **Synthetic adversarial corpus** (`eval/synth.py`, results in docs/EVAL_SYNTH.md): a seeded generator of
  schema-valid designs with controllable properties (2-45 elements, all four source families, image/shape/no
  background, text panels, logo in any corner, hero present/absent/missing asset, headlines from two words to
  140+ chars incl. unbreakable words, 0-4 subheads, free or grouped CTA with insets, 0-6 badges in rows, rotated
  ribbons/badges/headlines, decorative ellipses bleeding off canvas, letter spacing, line height, style_runs,
  max_lines, text_align, z ties, tiny elements, shadow headlines) plus `nasty_cases()` (empty content, font
  0.5/400, zero-size, negative coords, all assets missing, one element, one group, required fields only,
  rotation 725, unicode, 45 elements, targets 1x1 / 4000x4000 / identical / +3 %). Every property is recorded
  in `props` so the report slices defect rates by it. Text boxes are sized with the engine's measurer so the
  sources fit (except deliberate `src_overflow` / `src_overfull`). ids are opaque hex, no role hints.
  `.venv/bin/python -m eval.run_eval --synthetic 200 --seed 1 --workers 4 --name synth` writes the corpus to
  `eval/data/synth/` and runs it through the same metrics (nasty cases use their own `targets` instead of
  the presets, `own:<name>`); `.venv/bin/python -m eval.synth_report --run synth --worst 30 --notes
  eval/notes_synth.md --meta <file>` writes docs/EVAL_SYNTH.md (per-property tables, nasty table, failure
  groups, worst-30 sheets in docs/eval_synth/). ~3 min with 4 workers.
- **Metamorphic tests** (`tests/test_metamorphic.py`, rendering off): contract on the corpus and the nasty cases
  (never crash, ids/order, immutables, aspect, on canvas, text boxes >= 1 px, no uniform-scale fallback),
  determinism, opaque ids (renaming), element-order shuffle, group translation. Identity, +3 % width and 2x
  source scale are *xfail* today (reasons in the file / docs/EVAL_SYNTH.md) with an aggregate pass-rate floor
  (`test_relation_pass_rate_does_not_regress`) so regressions still fail. ~25 s.

## Labelling fairness filter (eval/labeling.py `source_quality`)
- The /label sampler skips sources the Crello conversion broke: text overflowing its own box, missing
  assets, an uncovered blank panel >= 55 % of the canvas, or a primary text with contrast < 1.6 in the
  source. 293 of the 450 eval designs pass (151 have unreadable primary text in the source because a photo
  became a flat stand-in). Text-box overlap is deliberately not a criterion. Round-1 labels
  (docs/LABELS_V1.md) predate the filter.

## Learned role classifier (S4, dev + shipped; docs/ROLE_MODEL.md)
- `engine/role_features.py` (123 id-free per-element features, ~2 ms), `engine/role_model.py`
  (`predict(source) -> {id: (role, confidence)}`, `predict_proba`, `text_hierarchy`; numpy-only traversal
  of complete depth-6 trees in `engine/models/roles.npz`, < 3 ms per design, deterministic; returns `{}` if
  numpy or the file is missing) and `engine/role_merge.py` (`merged_roles` / `apply_to_analysis`: rules +
  model by confidence, background/panel/decorative and all shapes stay with the rules, groups and analyzer
  units vote with their texts, one headline / hero / logo / CTA afterwards). Gated by `CHAMELEON_ROLE_MODEL`
  (default 0 = rule roles untouched); **not wired into resize.py yet**, the one-liner is in the docs §6.
- Labels: DesignAsCode themes (HF `Tony1109/DesignAsCode-training-data`, Crello train split only) mapped by
  `tools/role_labels.py`; data via `tools/build_role_dataset.py` (needs `eval/data/raw/train-*.parquet`,
  ~10 min per shard to fetch, run workers in parallel), training/export `tools/train_role_model.py`
  (scikit-learn, dev only; checks the numpy path against `predict_proba`), evaluation
  `tools/eval_role_model.py` (samples with ids stripped, Boynton, agreement with the rules),
  tables `tools/role_model_report.py`. Tests: `tests/test_role_model.py` (offline, tiny fixture in
  `tests/fixtures/roles_tiny*`). Changing `FEATURE_NAMES` requires rebuilding the dataset and retraining.

## Scorer calibration on human labels (S2, dev tool; docs/CALIBRATION.md)
- `tools/playground.py` serves **/label**: two renders (A / B) of the same source and target, source
  thumbnail, buttons + keys `a` / `b` / `t` (tie) / `x` (both bad) / `s` (skip) / `z` (undo), `r` reveals names
  and scores; the next pair is pre-rendered. Sampling in `eval/labeling.py`: balanced over target and source
  families, two non-fallback candidates with close totals, never a pair where only one side has a hard fail;
  mode "two harness runs" compares two runs' outputs for the same case. Labels → `eval/data/labels.jsonl`
  (one line per pair with both breakdowns **and both designs**, decision, timestamp). `--port` / `PORT`
  pick another port (launch.json has `playground-8766`).
- `eval/calibrate.py`: pairwise logistic regression on the labels (weights ≥ 5 % of the sum, sum 100,
  hard fails + adaptation penalty pinned, free temperature, tie = soft 0.5, `both_bad` skipped, weak labels
  × 0.3, L2 toward the hand weights, components with < 5 differing pairs frozen at their hand weight);
  reports in-sample and leave-one-design-out agreement plus per-component agreement with the labels; writes
  `engine/score_weights.json`. `engine/score.py` loads that file at import when present and complete
  (`load_weights`, `HAND_WEIGHTS` keeps the defaults; `CHAMELEON_SCORE_WEIGHTS=0` ignores it, `=<path>`
  reads another). **The file is not checked in**: the only fit so far is on 300 perturbation weak labels
  (`python -m eval.labeling --n 300`, `eval/data/labels_weak.jsonl`), kept at
  `eval/data/score_weights.weak.json`; while a weights file exists in `engine/`, hand edits to `WEIGHTS` are
  overridden. Tests: `tests/test_calibrate.py`.

## v7: relations, energy, optimiser (2026-10-25, docs/EVAL_V7.md, tests/test_v7_optimize.py)
- The engine no longer only picks a template: after the no-pixel judging the top `OPTIMIZE_TOP_K` (3,
  `CHAMELEON_OPTIMIZE_K`) seeds are walked down a design-principle energy and each refined layout competes
  as "<seed> +opt" (same strategy / prior; dropped if the judge finds a hard fail the seed did not have).
  `CHAMELEON_OPTIMIZE=0` leaves the output byte-identical to the unrefined loop (test); same-shape targets
  (`ratio_change` ≤ `resize.SAME_SHAPE_MAX` 1.02) are never refined.
- `relations.py` — O'Donovan-style perceptual graph of a design on visible boxes: alignment groups / pairs /
  near misses, proximity neighbours (gap ≤ max(0.6 × smaller extent, 2.5 % span)), containment and panel
  carry, axis symmetry and mirror pairs, importance, reading order, size, fonts. `source_relations(analysis)`
  is cached; `lost_alignments` / `broken_proximity` (graded) / `order_discordance` / `lost_containment` /
  `lost_symmetry` compare source and output; `Relations.to_dict()` serialises.
- `energy.py` — `Layout` (unit-level state on `rectify._Rectifier`, element dicts kept in sync, cached text
  layouts and per-text contrast estimates) and `Layout.evaluate()` → `Energy(total, hard, terms)`: hard terms
  mirror the judge rule for rule (uses the v6 helpers `score.text_overflows` / `bleed_allowance` /
  `margin_judged` and `rectify.OverlapRules` when present), `pres.*` terms keep the source's relations
  (incl. `pres.drift`: displacement against the proportional copy, fading out at `ADAPT_RATIO`), `aes.*`
  terms reuse score.py's component functions (`aes.spacing` judges white space *between* proximity groups,
  `aes.margins` excludes fine print). `WEIGHTS` in one place; `engine/energy_weights.json` (fit, shipped)
  overrides; `CHAMELEON_ENERGY_WEIGHTS=0|<path>`. One evaluation 0.3–1.5 ms.
- `optimize.py` — greedy best-improvement local search per unit (snap to another unit's line, nudge ± 2 %,
  grow / shrink 10 % about the anchored point, re-wrap a single text, swap with the next unit of its stack /
  row, never two text-bearing units); accepts a move only if the energy drops by more than `EPS` (0.1) and
  neither a new hard fail nor a new sub-gap near-touch (`Energy.near`, the rectifier's minimum gap) appears;
  scale steps are snapped so the unit's largest font stays an integer; budget `max_evals` 160 (deterministic),
  `time_cap_s` safety net; `Result.summary()` lands in `Score.notes["optimize"]`.
- Fitting: `eval/perturb_designer.py` writes PRISM-style one-principle perturbation pairs of the designer
  references (`eval/data/labels_designer_perturb.jsonl`) and designer > engine pairs
  (`eval/data/labels_designer_engine.jsonl`; `tools/designer_compare.py --labels` owns `labels.designer.jsonl`,
  which the calibration prefers when present); `eval/calibrate.py --energy [--install]` fits
  the energy weights on human + weak + designer + perturbation pairs with the sealed hold-out designs
  (`docs/designer2/holdout_ids.json`) reported, never fitted; pairs whose hard-fail counts differ are excluded
  (pinned terms, they only collapse the temperature). `eval/compare_optimize.py` compares optimiser off vs on
  on every reference (hold-out in its own table) → `docs/designer/compare/v7_optimizer/`.
- Finding: designer references lose to the engine on the regularity terms (even spacing, margins, line count,
  uniform scale, symmetry) and win on reading order, containment, contrast and presence; the fit moves the
  weight there. 71 of 600 tuning references trip a hard rule (mostly deliberate layering / bleed).

## v8: the picker (2026-10-25, docs/EVAL_V8.md, tests/test_v8_picker.py)
- Judge-only release: the candidate set holds a layout at designer agreement ≈ 0.70 while the judge returned
  ≈ 0.60; the clean non-fallback ceiling is 0.663 / 0.652 (tuning / hold-out), the rest is the anchor fallback,
  which the agreement metric likes and the eye does not (the fallback policy stays). Real runs: tuning
  0.595 → 0.608, hold-out 0.603 → 0.610, best-vs-chosen gap 0.101 → 0.089 / 0.114 → 0.108, eval defects
  unchanged (23 / 23 on 4 198 cases, 0 overflow / overlap / off canvas), runtime p50 unchanged (0.29 s on the
  samples single-process, 0.34 s in the harness).
- `score.py`: **`faith.rows`** (source-relative row integrity: a sibling row's parts stay one line or a compact
  cluster: cross overlap ≥ `ROW_KEEP_OVERLAP`, gaps ≤ `ROW_KEEP_GAP` × the larger part or `ROW_KEEP_GROW` × the
  source's ratio, spread ≤ `ROW_KEEP_SPREAD`, evenness within `ROW_KEEP_CV` of the source's; nearest-neighbour
  gap for clusters; corner scatter scores 0) and the **structure prior**: `structure_survives(score)` = no hard
  fail and `SURVIVAL_TERMS` (read.size, read.lines, read.presence) ≥ `STRUCTURE_READ_MIN` 0.8; when a structure
  candidate survives a ratio change ≥ `ADAPT_RATIO`, templates and non-surviving structure variants pay
  `STRUCTURE_PRIOR` 3 (`structure_prior`, applied in `resize.judge` before the sort, carried by `priors` into
  "+opt" copies and the pixel re-judging). Hand weights re-balanced to keep the sum at 100.
- `resize.refine`: a refined layout is dropped when it shrank a headline / CTA already within `SCARCE_FONT`
  1.25 × of its floor (`_spent_scarce_font`).
- **`engine/score_weights.json` is now shipped** (the v2 loader; `CHAMELEON_SCORE_WEIGHTS=0` → hand weights):
  `eval/fit_judge.py` fits the pairwise logistic on the picker dump (reference > candidate, candidate pairs
  ordered by agreement with margin 0.05, the human labels re-scored), readability block frozen
  (`calibrate.fit_weights(freeze=...)`), L2 2.0, floor 1 %; faith.order 12 → 17.7, fill / margins to 2.3 / 1.0.
  `eval/rank_judge.py`: linear-ext and gradient-boosted rankers over breakdown + energy + family do not beat
  the 16 weights on the hold-out (gbt 0.600–0.602 < hand 0.605), so no model file.
- Tools / data: `eval/picker_gap.py` (720-case diagnosis + candidate dump, `--report-only`), reports in
  `docs/designer/compare/v8_picker{,_hand,_v7scorer}/`, renders `docs/sanity_v8/`. Goldens: four Level 3 files
  regenerated deliberately (1080², 1080×1920, 1200×628, 160×600).
- v8.1: element order is canonical. `analyze._canon` ranks elements by z, then (y, x), then size (id only as
  the last resort), and `_cluster` / `_panel_stacks` / `_merge_rows` order members, clusters and every tie
  with it, so a unit's first id (a pill's background, a group's key, what `structure.py` reads as
  `u.primary or u.ids[0]`) no longer depends on the task's element list. `test_element_order_does_not_matter`
  is strict again; no golden moved.
