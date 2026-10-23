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
- `geometry.py` — `Box` helpers. Tests: `chameleon/tests/` (`.venv/bin/python -m pytest tests -q`, pytest is
  dev-only, not in requirements.txt). `tests/test_judge.py` covers the judge loop (winner defect-free,
  perturbed layout scores worse, rectifier removes an injected overlap, < 10 s per task).
- Judge renders: `docs/judge_v1/` (three samples + Level 2 → 1080×1920, 160×600, 1200×628). Make them with
  `tools/compare.py compare <dir> [--target WxH] [task.json]`; `tools/compare.py sheet <dir>` writes a
  contact sheet of every candidate with its score breakdown.
- Renderer facts: text is NOT vertically centered or clipped in its box; a single over-wide word overflows;
  drawing uses int(font_size). Comparison renders of each milestone go in `docs/<milestone>/`.

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

## Docker status (see docs/DOCKER_CHECK.md)
- The shipped `linux/amd64` image builds but **hangs at run time on Apple Silicon without Rosetta**: skia
  segfaults under QEMU, inside the organizers' own renderer. A native arm64 build of the same Dockerfile
  runs the three samples offline in 4 s. Open question for organizers; guard any in-engine rendering with
  a fallback so resize() still returns a layout if the renderer dies.

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
