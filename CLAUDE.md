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

## Playground (dev tool, not shipped)
- `chameleon/tools/playground.py` serves a local UI at http://localhost:8765: pick a sample, upload or paste a
  design, pick a preset or custom size; shows source / stretch-baseline / output renders (fit or 1:1, optional
  role-colored element boxes), every judged candidate with score breakdown (click one to inspect it), inferred
  roles, self-check warnings, output JSON, downloads, and a "Run all formats" gallery across every preset.
  Reloads `engine/*` on every run. Start with the "playground" entry in `.claude/launch.json` (preview_start)
  or `cd chameleon && .venv/bin/python tools/playground.py`. It depends on `resize_with_candidates` /
  `Judged.summary()` and `engine.render.render_design(design, max_size)`; keep those stable.
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
