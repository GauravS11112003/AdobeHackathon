# Competitive landscape — CHAMELEON public repos (updated 2026-10-26; sweep 3 at the end)

Full clones in `reference/competitors/` (read-only, untrusted). Nothing here is official; READMEs are
claims and several were found to overstate what the code does. File:line pointers refer to the clones.

## No "India" version exists

Adobe India Hackathon 2025 (same organizer handle, jhaaj08) was PDF outline extraction. Its Round 1A
limits are the best hint for this year's unpublished rules: **8 CPUs, 16 GB RAM, CPU only, ≤ 10 s per
task, model ≤ 200 MB, --network none, linux/amd64, open source only.** India 2026 is unrelated.

## Who is serious (as of 2026-10-23)

| Repo | Last commit | State | ML | Candidates | Judging |
|---|---|---|---|---|---|
| **tailsgit/chameleon** | 10-19 | complete, calibrated | none (OR-Tools CP-SAT) | 12–130 | 19-term scorer fitted on 185 hand labels; renders top 10 for contrast |
| **gk7494/chameleon** | 10-22 | complete, single file | none | 1 (global-scale search, ~1,600 layout evals) | geometric proxies only, no render |
| **fernando-ace** | 10-19 | complete + Express add-on | none | 6–18, repair top 2 | heuristic score, lexicographic hard rules; contrast proxy from background only |
| **benso10-uw** | 10-16 | working presets; LLM path dev-only | LLM via API/Ollama, **not baked in Docker** | 1 preset (+LLM attempts offline) | priority-weighted rule cost |
| rsingh135, 4rd2, Joonseomoon, fashton28, annniedong, anubhav-gupta, justacoderq, LakshyaDhingra, AngeloLandiza | — | scaffolds / plans | — | — | — |

**Nobody ships a model.** benso10's own notes: in every Gemini/Qwen trial the preset was retained; the
LLM never beat it, 93.5 % of tokens were reasoning, one Level 3 trace spent 618 s in model calls.

## Best techniques, by rival

### tailsgit (the one to beat) — `engine/analyze.py, recipes.py, preserve.py, fit.py, select.py, eval/score.py`
- **Units via union-find**: group_id, containment in a "holder" (shape < 25 % canvas or flat image), photo-in-frame,
  decorations ≥ 80 % inside a unit absorbed. Tightest holder wins.
- **Grids and sibling rows** become one rigid unit that can re-flow to any column count (badge rows re-stack
  when unreadable). `_merge_grids`, `score.siblings`.
- **Floating units**: corner-pinned or rotated badges keep their corner / host and can mirror their tilt.
- **Roles** with confidences: headline = largest font (conf from lead over runner-up); CTA = shape+text with an
  action verb (0.9) else lowest-widest shape+text in bottom 40 % (0.6); logo = topmost image < 8 % with aspect
  ≥ 1.3; fineprint = font ≤ 0.6× median or smallest ≥ 60 chars in bottom 15 %. Importance adds **colour
  emphasis** (CIELAB chroma ≥ 30, far from palette).
- **Recipes × knob grids**: stack (48 with hero), split (16), split_grid, anchor, strip (16), overlay (stack in the
  2 quietest of 5 background regions), compact (primaries only; rest floats). Shared-scale bisection; demote the
  least-important unit to floating when nothing fits; 2–3 newspaper columns when wide; rescue mode to 1 px.
- **Preserve-first CP-SAT**: per item x, y, integer scale; hard: inside canvas, readable, big items keep ≥ 0.7
  share, non-overlapping pairs stay disjoint (4-way BoolOr); objective: displacement (weighted by share),
  scale deviation (shrink costs 3× growth), broken order 2000, broken shared edge 2/px. 4 variants (share, fit,
  edges, between), 0.5 s deterministic time each. Wins 61/161 moderate changes, only 12/148 extreme.
- **Retrieval**: 1,494 Crello layouts (aspect + units{role, kind, box} + role counts). Match |ln aspect| ≤ 0.2,
  L1 on role counts, top 30; Hungarian assignment on role/kind/size/shape cost; dummy slot cost 2.5 so bad
  fits float. **By eye retrieval was mostly worse (28/30 bad)** until guarded: dropped if headline or main image
  share < 0.7× the best recipe's.
- **Text**: renderer's own layout; invisible slack line (12 % of lines) for macOS/Linux metric drift; letter-spaced
  text fitted by narrowing width ×0.97 steps; floating text searches maximal-empty-rectangles.
- **Scorer** `total = 100(1 − Σw·p/Σw)`, 19 terms; pinned heavy ones: text_over_image 3.0, coverage 3.0,
  key_size 2.0, legibility 2.0; others fitted by pairwise logistic regression on good/okay/bad labels
  (agreement 0.866). **No-render contrast estimate** (composite layers under text at 32×8 points, 25th pct WCAG)
  correlates 0.99 with the rendered one.
- **Selection**: dedupe → drop violations → tiered safety (legible, not on busy image, big things keep ≥ 0.5 share)
  → score → render top 10 for contrast. Adaptive 14.5 s budget measured on the live machine.
- Weaknesses they admit: English verb list, headline = biggest font, text in groups never re-wraps, hairlines,
  no photo crop/focal, text-heavy designs → banners still fail, Crello-derived library is a licensing grey area.

### gk7494 — `engine/resize.py` (single 1,967-line file)
- **Tight painted text boxes** (re-wrap at source width, ascent − 0.78·fs top offset) instead of declared boxes.
- **XY-cut tree**: binary split at the widest whitespace band (tol 0.5 % of the axis), flatten same-axis nesting,
  overlapping clusters become reading-order stacks. Panels (opaque shapes holding ≥ 2 things) form subtrees.
- **Re-orientation** by target aspect (h if ≥ 1.3): legal pruned to a footer; consecutive text rows merged into
  one column; rows of ≤ 4 small items restacked; **every consecutive 2- and 3-column partition tried** (≤ 24).
- **Global scale search**: 56 log-spaced k in [k_hi/40, k_hi] + 6 bisection steps; score = log k − 0.35·penalties
  − fill/imbalance terms; penalties: extra wrapped lines × importance, below-floor 0.6·importance, rigid block
  shrunk < 0.6, wrapped row 0.4 + 0.1·rows. Floors: font max(5, 0.85 % of max side); logo 14 %, hero 30 %,
  image 20 %, stamp 8 % of min side.
- **Background-aware shift**: BgMap of the cover-cropped background (luminance + edge density, 48 cells);
  cost = busyness + contrast shortfall, weighted by importance, + 0.25 displacement; 15×15 translation grid;
  applied only if gain ≥ 0.015. One global translation.
- Byte-identical Docker vs local output; 0.04 s per task.
- Weaknesses: single candidate, no rendering, button labels can win "headline", only one subhead, panels and
  decor excluded from its own overlap test, README claims tests that are not in the repo.

### fernando-ace — `engine/chameleon/*.py`, `tools/stress_corpus.py`, `chameleon-express/`
- Roles: area/position thresholds plus a **date/time regex** for event metadata and a 29-word CTA verb list.
- **Source-relative penalties**: overlap only if worse than the source by > 1.5 pp; hierarchy ratio must stay
  ≥ min(0.82, source ratio); bleed excused when the source had it.
- **Lexicographic rank** (contract, hard-valid, clipping, aspect, off-canvas, …) before the soft score.
- **Target adaptation penalty**: source_fit/stack on wide targets +18, banner on tall +14, so the engine is
  forced to actually re-layout.
- **Very-wide banded layout** (≥ 4.5:1, ≥ 300 px tall): hard-coded bands for logo/headline/narrative/badges/CTA/
  legal/hero rail.
- **Adversarial corpus**: 64 synthetic designs (2–45 elements, missing assets, negative positions, rotations,
  opacities) × 9 targets + 45 sample mutations (headline ×2/×4, hero ×1.25, moved logo, rotated shape, +3 %
  width, missing asset) with metamorphic assertions (identity, no new overlap, no hierarchy regression).
- **Express add-on** prototype: local HTTPS server, 6 presets, one-element lock (engine does not re-plan around
  it), apply as a new page (shapes become rectangles, font ×0.75). Never verified inside Express.
- Weaknesses: computed alpha bounds and luminance **never used**; fonts never grow above source; only 6
  candidates for tall targets; repair only translates and only on 2 candidates; contrast ignores shapes.

### benso10-uw — `engine/analyze/understand.py`, `engine/resize/preset.py`, `hard_path.py`, `check/checker.py`
- **Space pressure** = area needed at minimum readable size / target area; routes easy vs hard.
- Presets: column (binary search of one global scale over 40 steps, text floors 10 → 6 → none), hero beside
  column ≤ 42 % width (1.4–4.5), strip with lowest-priority cells squeezed first; leftover space shared in
  proportion to the source's gaps; edge-hugging blocks stay on their edge.
- LLM contract worth noting even if unused: model places **groups by (x, y, scale)** and code expands members;
  model gets measured `fit_options` (width share × font size → height) instead of estimating; silent
  restoration of every non-geometry field; image boxes are placement boxes with source aspect fitted inside.
- Checker ranks violations by severity × priority; new-overlap signal skips pairs that overlapped in the source.

## Where we stand (engine v2, 2026-10-23)

Ahead: evaluation scale (6,058 cases vs 945 / ~112 / 13-format stress), speed (0.4 s median), rendering every
candidate, eval browser + playground, learned-component plan.
Behind on specific techniques listed below.

## What to borrow, prioritised

1. **No-render contrast estimate** (tailsgit): composite the layers under each text box from the JSON and the
   assets; 0.99 correlation with rendering at a fraction of the cost. Lets us judge all candidates on contrast.
2. **Units beyond group_id** (tailsgit, gk7494): holders, panels, photo-in-frame, grids, sibling rows, floating
   corner badges with hosts. Our Boynton failure (scattered underline bars) is exactly a missing "host" relation.
3. **Tight painted text boxes + per-role floors** (gk7494): geometry from glyphs, not declared boxes; logo 14 %,
   hero 30 % of min side so brand elements never vanish.
4. **Preserve-first optimisation** (tailsgit CP-SAT): a "move as little as possible" candidate family with
   no-new-overlap constraints; our faithfulness score (0.60) is our weakest component. scipy LP first;
   OR-Tools only if needed (adds ~30 MB).
5. **Source-relative penalties + target-adaptation penalty** (fernando): penalise only what got worse; punish
   non-adapted layouts on big ratio changes.
6. **Pairwise calibration of scorer weights on hand labels** (tailsgit): we have 6k rendered cases; label
   ~150 pairs good/okay/bad in the eval browser and fit weights.
7. **Adversarial corpus + metamorphic tests** (fernando, gk7494): synthetic generator feeding our harness.
8. **XY-cut re-orientation with text-run merging and legal footer** (gk7494) as another candidate family for
   text-heavy editorial designs (our Boynton case).
9. **Retrieval**: tailsgit found it mostly loses by eye; keep as low priority, guard it if built.
10. **Colour emphasis as an importance signal** (tailsgit): cheap and we already parse rgba.

## Things to avoid (evidence from rivals)
- LLM writing coordinates (benso10: never beat presets, token blowups).
- Hard-coded band percentages per format (fernando): brittle on unseen designs.
- Single-candidate engines with no visual check (gk7494).
- Trusting README numbers: fernando's 17.08 px headline is 16.58 in the committed output; gk7494's synthetic
  tests are not in the repo.

---

# Sweep 2 — 2026-10-24 (code-level reads, not READMEs)

## Movement since 2026-10-23
- **No new commits** on tailsgit, fernando-ace, gk7494, benso10-uw, AngeloLandiza.
- **Joonseomoon/chameleon went private** (clone now fails). It had a team workflow (PRs, CI, iteration plans).
  Assume a serious private entry.
- 12 further repos triaged by cloning and measuring engine code (scratch, not kept): 7 are untouched
  starters (PolymorphicTrio, preetham-ven, shivraj-jadeja, 4rd2, LakshyaDhingra, justacoderq, AngeloLandiza);
  anishraj836 is a different challenge (brand-audit skill, India round); 4 have real code, below.

## New entries with real code

| Repo | Last commit | Size | ML | Candidates | Judging | Threat |
|---|---|---|---|---|---|---|
| **annniedong/chameleon** (kept in reference/) | 10-23, active | ~2k engine + tools | none, **plans a "vision-model reranker"** (comment in score.py) | 3–10 templates × minor-multiplier; **top 3 refined with z3** | hand-weighted geometric score, no render | high |
| **anubhav-gupta-software/chameleon** (kept) | 10-16 | 1,702-line single file | none | ≤ 2 templates | box-only cost | medium-low |
| fashton28/adobe-hacks | 10-16 | ~1.5k | none | a few dozen (DP row breaks × γ font exponent × splits) | lexicographic + hand score, no render | low ("slop", 6 px text at 728×90) |
| rsingh135/chameleon | 10-19 | 1.3k eval only | none | **engine still the starter stretch** | plate-render contrast, 14 metrics, holdout synthetic families | unknown (engine elsewhere?) |

### annniedong — techniques (engine/understand.py, templates.py, layout.py, solve.py, textmetrics.py)
- Units: group_id, or text inside a shape/non-cover image < 25 % canvas (15 % slack, smallest host wins);
  separator texts ("x", "+", "|") excluded. **Logo lockups vs sponsor strips**: small images on a row chained
  by height ratio ≤ 1.8 and gap ≤ 3×height; "presented by / sponsored by" labels absorbed; primary logo chosen.
- Roles: action-verb regex → CTA; rotated / > 70 % caps / ≤ 3 words → badge; legal regex or smallest-and-dim-or-low.
- Templates by ratio (strip ≥ 2.6, split > 1.25, else column) × minor multipliers {1, 0.7, 0.45} (trade minor
  units' size for the headline's). Flexbox-like tree (Rigid/Text/Column/Row/Wrap); one global k by bisection.
- **z3 Optimize refinement** of the top 3: per unit x, y, scale ∈ [0.35, 1.6]; non-overlap pairs keep the side
  the template chose (stays linear); text width modelled as `bw·s + A·(1−s)` with a per-glyph allowance;
  **readability floors as tracked assumptions, unsat core → drop the least important unit's floor and re-solve**;
  objective 100·imp·s − 40·imp·drift; 2.5 s timeout.
- **Hinting-safe glyph widths**: width = max(platform width, unhinted linear width + 1 px) because FreeType on
  Linux renders small bold text up to ~23 % wider than macOS skia measures. Quantise boxes up / fonts down
  before the hard gate.
- Four-layer fallback (reflow → letterbox+repair → clamp-only → pass-through), never raises.
- Weak: overlap is never a hard gate, decorations unchecked, tall targets get only the column template, no
  contrast term, no measured results.

### anubhav-gupta — techniques (engine/resize.py)
- **Water-filling allocation** when minimums don't fit: everyone gets 45 % of its minimum, the rest handed out
  by importance (`_priority_allocate`).
- Text height from real ascent + descent, not size × line_height (display serifs ≈ 1.4× size).
- **Busy-background dodge on max-over-small-blocks** of the cover-cropped asset (catches a dot under one word),
  scans a row at 5 offsets, accepts if gain > 0.2, then widens the box into free space.
- Label-min → group-height conversion via the label's share of the group.
- Weak: no tests, scorer inconsistent with fitter, dims secondary content to 32–60 % opacity (arguably a style
  change the rubric may punish), slides text along rows breaking alignment.

### fashton28 — techniques
- Font exponent γ: `peak·k·(fs/peak)^γ` compresses hierarchy as a search axis; hierarchy penalty keeps ≥ √(source ratio).
- Preserve-arrangement prior `3·exp(−2|log r|)` decaying with aspect change, weighed against layout shift.
- Choppy-wrap penalty (< 14 chars/line); inflation cap so pills/logos don't outgrow the headline.

### rsingh135 — eval ideas
- Source-mined intentional overlaps/containment (only *new* collisions count); plate render (text stripped) for
  contrast + busyness; synthetic generator with **holdout families and holdout targets** to measure
  seen-vs-unseen gap; CI runs the offline Docker build.

## Action items for us (new from this sweep)
1. **Verify text metrics inside the Linux container.** Measure every sample's wrapped widths in the arm64 image vs
   macOS; if Linux is wider, adopt max(hinted, linear+1 px) like annniedong or a slack margin like tailsgit.
   Must happen before freeze (S5). Potential silent overflow on the judges' machine.
2. Unsat-core style degradation order for floors (which floor to give up first) in our rescue mode.
3. Water-filling allocation for the "nothing fits" regime in floor plans.
4. Busy-background check on small blocks (we sample 32×8 points; add a max-over-blocks term).
5. Choppy-wrap penalty and γ-style hierarchy compression as candidate knobs.
6. Holdout families/targets in the synthetic corpus to report seen-vs-unseen gap.
7. Someone else is planning a VLM reranker; our S1/S2 lead is real but not unique. Ship it.

---

# Sweep 3 (2026-10-26)

Method: `git fetch` of every clone and `git log --all --since=2026-10-23`; the 19 forks of jhaaj08/chameleon by push
date (`gh api repos/jhaaj08/chameleon/forks`); repo search for "chameleon" / "adobe hackathon" created since
2026-09-20; code search for `cr-renderer`, `chameleon_design_schema`, `solstice_holiday_badge_2025` and
`target_canvas` in a `resize.py`. Everything below is from the code, with paths and line counts; README claims are
marked as such. New clones went into `reference/competitors/` (read-only, untrusted). Our own engine for scale:
14,654 lines in `chameleon/engine/`, 284 tests.

## Gone private or deleted since sweep 2

| Repo | State on 2026-10-26 | What our clone keeps |
|---|---|---|
| AngeloLandiza/Adobe-26-University-Hackathon | **404 (private)** | branches through 10-23: `offline-priority` (the real engine, 2,894 lines, 200 tests) and `angelo/distill` (3.3 GB of distillation data + a 12,217-line research engine) — see below |
| Joonseomoon/chameleon | still gone | nothing |
| shivraj-jadeja/chameleon, anishraj836/chameleon | 404 | nothing (scaffolds in sweep 2) |
| justacoderq/chameleon | 404; `justacoderq/chameleon-main` (10-24) is the starter + the brief PDF | — |

## Known rivals: what changed since 2026-10-23

| Repo | Last commit | Approach delta | Model / weights | Eval | Strength now |
|---|---|---|---|---|---|
| **tailsgit/chameleon** | main 10-19 (v5, unchanged); branches `gen-integration` / `team-docs` 10-23 | main untouched. Branches, **none merged**: `critic` (10-19) learned layout critic; `diagnose` (10-20) label CV harness + tag server; `rules` (10-21) *tight groups* (label+value, shadow copy, text+underline, logo+name, small image next to a text; `eval/score.py tight_relations`, `TIGHT_MAX_AREA` 0.25) held rigid, generated *alternately* with the free analysis (`engine/resize.py _alternate`), new scorer terms `groups` 2.0 / `related_order` 1.0 / `fill` 1.15, `COVER_SRC` 0.9 → 0.2; `generator` (10-22) CVAE; `gen-integration` (10-23) `engine/candidate_budget.py` (path-coverage counts replace wall-clock cutoffs, byte-deterministic), `engine/gen_candidates.py` (ONNX, `GEN_ON=1` only) | **Critic**: 1.84M-param transformer over element tokens (`critic/model.py` 61 lines, `critic/features.py` 210: 30+ per-element features incl. colour, texture, panel_kept), ONNX; val pair accuracy 0.883 but **0.578 on 245 human labels vs the hand scorer's 0.830** → parked. **Generator**: CVAE transformer (`generator/model.py` 85 lines, d 192, 3 layers, latent 16, 16 fixed latents) on 18,108 campaign-deduped Crello designs, **6 MB ONNX**; human recall 15/40 = no gain, 0 cases where only it was acceptable → **off by default**. `requirements.txt` adds `onnxruntime==1.20.1`; Dockerfile has a `CRITIC_URL` build-arg download. | 245 hand labels (41 good / 33 okay / **171 bad**); candidate recall 17/39 acceptable; rules branch hand score 91.49 → 89.41 on dev (46 drops > 10); 600 dev cases CPU p50 / p95 / max 1.29 / 3.49 / 6.82 s; tests 71 (main) → 117 (integration). `docs/TEAM_OVERVIEW.md`: ship `submission-fallback` (v4, `14ea0dc`) if experiments fail; working deadline "around Nov 2, unconfirmed"; image 331 MB | **still the strongest shipped engine**, but the learned work went nowhere and main is 7 days old. Own weak list: collages, icon rows, CVs/invoices → banners, 160×600 |
| **annniedong/chameleon** | **10-26** (active) | `engine/understand.py` +108: `_compound_texts` union-find joins texts that read as one phrase: geometry (layered ≥ 10 % overlap; same line gap ≤ 0.8 em, 2.0 em when the words link; stacked ≤ 0.35 em, more when linked, ≤ 3 / 6 words) widened by *language cues* (`_text_link`: number + unit, currency + number, lone & / +, trailing/leading connector words, unfinished sentence into lowercase). Since 10-20: `tools/crello.py` (Crello → tasks, every non-text layer saved as a **rendered RGBA crop asset**, fonts mapped to the two brand families), `tools/judge_set.py` (100-item hand-judging set in 4 shape buckets) | none; `score.py` still calls itself "a stand-in until the vision-model reranker exists" | 20 tests (+3 for compounds); no committed numbers | medium-high on structure, still no contrast / render / overlap gate |
| **fernando-ace** | submission branch 10-19 (unchanged); branch `goal-2-extreme-format-generalization-rebuild` 10-20 | not on the submission branch: `engine/chameleon/allocation.py` 245 lines ("content-measured semantic lanes with disjoint rotation-aware unit cells": 1–3 line widths × 7 width fractions per text, whole groups in reserved cells), hierarchy protection, collision feasibility ranked above aesthetics | none | 1,600-case synthetic corpus in 13 buckets (dev / holdout / blind 300 / 300 / 1000, fixed seeds): collision pairs 3,307 → 0, hierarchy 675 → 0, headline p5 15.7 → 21.7 px, **but important-text minimum fell 8.0 → 6.3 px** on the legacy 112; 38 tests; Docker 11/11 (`evidence/rebuild/report.md`, unusually honest) | medium: clean but small type; still one brand kit, no pixels |
| benso10-uw | main 10-16; `feat/design-analysis` 10-19 | the LLM is now shown the rendered source (`source_image`) for the understanding call; `temp_main.py`, PowerShell runners | hosted / Ollama only, nothing baked | 58 tests on the branch | unchanged: presets ship, LLM is dev-only |
| gk7494, anubhav-gupta | 10-22 / 10-16 | nothing | — | — | unchanged |
| rsingh135, fashton28, LakshyaDhingra, 4rd2 | 10-19 / 10-16 / 10-19 / 10-05 | nothing; rsingh135's and LakshyaDhingra's `engine/resize.py` are still the 3.6 KB starter | — | — | — |

## New repos with real code (cloned this sweep)

| Repo (clone dir) | Last commit | Engine | Candidates | Model | Judge / scoring | Tests | Threat |
|---|---|---|---|---|---|---|---|
| **vedanth2406/chameleon** (fork; `vedanth2406_chameleon/`) | 10-26 | 1,311 lines in 11 modules (`layout.py` 272, `horizontal.py` 280, `quality.py` 187) | 40–120: anchor, contain, 4 weighted stacks, 6 BSP partitions, ≤ 24 "editorial bands", column splits, footer variants; banners: media-rail × hero/row/column × 1–3 label rows with an 8-step binary search on one *shared readability level* | none | hard gates (protected fields, rotated bounds, measured overflow, ink off canvas, label detached from pill, rigid-group change, new overlap > 1.5 %) then 10 geometric costs; skia ink metrics; `repair()` refits; **no contrast, no render** | 28; `tools/evaluate.py` renders with sockets blocked; Dockerfile pins base image by sha256 + `constraints-linux-amd64.txt` | **medium** |
| **preetham-ven/chameleon** (fork; `preetham-ven_chameleon/`) | 10-25 | 879 + `packing.py` 87; **modified the vendored converter** (style-run end exclusive, new `renderer/converter/textlayout.py`) so they test fit under both | ≈ 150 (2 spacings × 3 type scales × 5 families × 2 orders × 3 splits + grids + image panel), then if min font < 12 px a `_compact_candidates` scan of integer floors 12 → 1 × rails × label rows × columns (hundreds per floor) | none | `_valid` (ids, inside, fits under both converters, aspect, **zero AABB overlap between units**) then 5-term rank; image prominence and overlap from the asset's **alpha bounding box** (`_asset_bounds`) | 33; nothing committed | **medium**: rigorous fit, but no contrast and text may never touch a picture; Level 2 circle pulled on canvas (judge-visible) |
| EbrahimHimayoun/PolymorphicTrio (fork) | 10-26 | 794 | 10–60: anchored copy + 1…8 equal columns with a DP reading-order partition, "visual / copy / controls" lanes, pressure search, greedy `_grow_text` into free rectangles | none | overflow, size ratio, hierarchy, 80× overlap; absolute text targets 14 / 11 / 9 / 7 px regardless of canvas; no contrast / render | 12 + a Level 1 golden; `VALIDATION.md` numbers point at an uncommitted folder; Docker never run | medium-low |
| Preeyam183/AdobeHackathon (starter copy) | 10-25 | 1,606 (≈ 900 engine, rest self-checks + VLM) | 19: preserved copy + 3 families × 6 parameter sets, 5 of them **seeded-random** | `_LocalVLM` → **Ollama** `qwen3-vl:4b-instruct-q4_K_M` over HTTP: grammar roles + pairwise judge with order-swap confirmation; off unless `CHAMELEON_VLM=auto`; not in the Dockerfile, no weights → dead offline (commit: "broken VLM judge") | structural vs defect split; readability × contrast (background asset sampled 32×32 + shapes) 0.4, hierarchy 0.25, kept alignments 0.2, occupancy 0.15; **renders up to 4 finalists and writes diagnostics inside `resize()`** | 0 pytest (internal `_check_*`) | medium-low |
| ankita320/adobe-h (starter nested) | 10-21 | 1,157, single file | ≤ 60 column assignments × 40-step global-scale search | none | priority-weighted scale, PIL background-luminance contrast grid (WCAG 3 / 4.5 by font size), coverage; logo by **regex on id / asset_id**; **blocks that cannot fit are collapsed to an invisible speck** (ids survive, content hidden) | 0 (8 JSON cases) | medium-low; the hidden-content trick is a rubric risk |
| Revan-dev/chameleon (fork) | 10-24 | 473 | 1 | none | none; per-axis text box scaling, `font_size = max(12, ×s)` unmeasured, rewrites `fit` to cover and `z_index`, logo = "logo" in id | 0 | low |
| Jdeww/chameleon (fork) | 10-18 | 1,011 | 3–45 (stack / split / 4–7 column templates × alpha ∈ {1, .65, .4}) | none | legibility, hero/logo floors, AABB overlap, coverage, fidelity; no contrast | 0 | low |
| amanadhav/chameleon (starter copy) | 10-05 | 1,612 | ≤ 10 (stack, split, two-column × hero share, banner with tier waterfall) | none | 6 terms incl. source-relative new overlaps; PIL metrics, not skia | 4 | low |
| **Parinagpal11/Project-Chameleon-Adobe_Hackathon** (Iowa State; not on the starter) | 10-25 | 4,815 lines in `backend/engine/` (`adapt.py` 2,394, `subject.py` 874, `understand.py` 753) + a web Studio deployed on Render | several per target, tiered (keep / re-flow / rebuild) | **ships weights**: `backend/engine/models/` YuNet face 232 KB, U2-Net-P saliency 4.5 MB, YOLOX-nano 3.6 MB (ONNX, onnxruntime + opencv) for photo subjects | 5 parts (content, legibility, faithfulness, composition, subject) vs stretch / crop / letterbox baselines; own pydantic schema (`fontSize`, `hidden`, `pinned`), **drops low-priority elements and crops photos around subjects** | 94 (incl. Playwright) | low for stage 1 (not schema-compatible, hides elements); the only team with photo-focal detection, relevant to the finale |
| **AngeloLandiza** (private; clone branch `offline-priority`) | 10-23 | 2,894 in `chameleon/engine/pipeline/` (priority / layout / grading nodes) | 5–37 (templates by aspect class × `PARAM_GRID` 4 / 12 / 36 + proportional reflow) | node 1 calls Claude / Gemini (`anthropic`, `google-genai` in requirements) → **offline it is the rule ranker** (their note: "the scored engine today is the rules", rules τ 0.75 vs hosted 0.83–0.98 on 10 designs) | 9 hard gates (incl. `G9_hidden`: element fully under an opaque later one) + 10 geometry terms, then **text-less render of the top 6** for WCAG contrast at p10 / p90, Sobel busyness, placeholder share (0.7 geometry + 0.3 pixels) | 200 | medium as shipped; **medium-high if the research engine is ported** (below) |

**Angelo's research branch (`angelo/distill`, `distil-research/`, "not our submission")** is the most ambitious
learned-component programme in the field and the clearest negative result: a 12,217-line "v5" engine (567 tests)
with bisection / anchored / design-grid strategies, a scipy-HiGHS LP geometry pass (`layout/solver.py`, 47 KB, off
by default and scipy is not in its requirements), a retrieval module and `grading/picker_weights.json` (a linear
picker over grader terms × family × aspect fitted on Claude Opus pairwise judgements, 282 cells). Their own numbers
(`docs/research/2026-10-23-offline-node1.md`, commit messages 10-21/22): v5 beats their shipped layout node **70–17
on 50 unseen Crello ads**; a Qwen3-4B LoRA student emitting layouts lost 11–13 to v5 (8B tied 8–8, DPO made it worse
7–15), ran 23 s per layout as Q4 GGUF on CPU; "learned pickers and graders were coin flips"; learned Sonnet
proportions lost 36–27 on real ads; their Crello role heuristic got ~80 % of headlines but 25–30 % CTA / logo
precision. Their next plan (`beating-v5-offline.md`): a CP-SAT / LP geometry pass behind every candidate, then a
tiny *plan* predictor (region / order / keep / anchor), never coordinates. Also: 7 adversarial dev designs
(ghost word at opacity 0.08 as the biggest font, plain-text CTA, "SAVE 20%" read as a button) that break
first-word-verb and largest-font rules — worth copying as test ideas.

Not rivals: kelechi-c, tomosh22, GoranKim0518, umairkhalidx, amosrnb, ricardohbin, roos103, dallas8000-ops,
Master-Roshi-Ultra, rie10170521-boop (unrelated projects named chameleon); chitrangad-ram-sapate and Gahlawat-9
(India round, brand-audit skill); the 13 forks last pushed 2026-09-24 are untouched starters.

## Field ranking on the rubric (what the code can do, 2026-10-26)

| Rubric row | Us (v9) | tailsgit v5 | annniedong | vedanth2406 | preetham-ven | fernando | Angelo (shipped) |
|---|---|---|---|---|---|---|---|
| No unwanted collisions | source-relative `OverlapRules`, rectifier + hard fail, verified in eval (0 / 4,198) | hard rules + local repair, tiered safety | **scored only**, never gated | hard gate (> 1.5 % new overlap) | zero-overlap gate (too strict: dismantles layering) | hard feasibility, 0 on 1,600 synthetic | gate (overlap beyond source) |
| Readable text | measured skia fit, role floors, contrast estimate + text-less render, straddle rule | renderer fit, legibility tier, no-render contrast (0.99 corr.) | measured + hinting-safe widths, no contrast | measured ink, shared readability level, no contrast | measured under two converters, floor scan, no contrast | measured, 3×3 sampled contrast; min type fell to 6.3 px | floors by role, render contrast on top 6 |
| Brand fidelity | roles (rules + classifier), logo / hero floors, one headline / CTA / logo | roles with confidences, colour emphasis, key_size pinned | lockup / sponsor-strip logic, compound texts | coarse roles (no CTA / logo) | no roles beyond button / dominant image | roles + date regex | rule ranker (verb list) |
| Intentional look | judge fitted on 720 designer refs, energy optimiser, critic loop | hand scorer fitted on 185 labels, CP-SAT preserve-first | drift / order / balance terms | 10 geometric costs | 5-term rank | lexicographic + proxy score | 10 terms + fitted picker only in research |
| Holds up everywhere | 21 candidates in 4 families, structure family, rescue mode | 12–130 candidates, 7 recipes, retrieval guarded | 3–10 templates × minor multipliers, z3 refine | 40–120, banner search | ≈ 150 + exhaustive floor scan | lanes + families, 13 synthetic buckets | 5–37 |
| Speed | 0.3 s p50 native | 1.3 s p50 CPU, 6.3 s median in Docker | fast (z3 2.5 s cap) | unknown (large pool) | likely seconds (hundreds per floor) | 0.4–0.9 s | unknown |

**Who is strongest now:** tailsgit v5 remains the only rival with a fitted judge, a preserve-first solver and
human-labelled recall, but its main branch has not moved in a week and its three learned experiments (critic,
generator, tight-group rules) all failed to beat the hand scorer on human labels, which is the same thing we found
with the VLM (S1) and the text LLM (S6). annniedong is the most active and the most careful about *what belongs
together* (lockups, sponsor strips, compound phrases) but still has no collision gate or contrast signal.
vedanth2406 and preetham-ven arrived in the last two days with large measured candidate pools and strict gates;
both are blind to pixels and roles, so they will produce clean but generic layouts. Angelo's team has the deepest
evidence that LLM-emitted coordinates and learned pickers lose to rules, and the most plausible next step (LP
geometry pass + discrete plan), but their public engine is gone and the strong version is a research copy.
**Nobody ships a layout model that is on by default; the only shipped weights in the field are Parinagpal's photo
subject detectors (not schema-compatible) and our 391 KB role classifier.**

## What to borrow (general rules, in words) and what to ignore

Borrow:
1. **Compound-phrase units with language cues** (annniedong `_compound_texts`): a number next to its unit, a
   currency sign before a number, a lone "&" / "+" between two words, a line ending in "of / the / and" above the
   next, a mid-sentence lowercase continuation — join them into one unit so "50" never parts from "%". Our units
   are geometric only; this is cheap, id-free and English-light.
2. **Tight relations held rigid, generated alternately with the free analysis** (tailsgit `rules`): label + value,
   shadow copy, text + underline, logo + name as one rigid unit *and* the free version, both in the pool, the judge
   picks. tailsgit's hand score dropped when rigid-only; the alternation is the general form of our holder / host
   logic.
3. **Alpha-bounding-box visible bounds for images** (preetham-ven `_asset_bounds`): prominence, overlap and
   centring from the asset's opaque pixels, not its padded box. Directly fixes our known "logo looks small because
   of transparent padding" gap and the transparent product hero on Level 3.
4. **Hidden-under-opaque gate** (Angelo `G9_hidden`) and **content collapsed to a speck** (ankita320) as a *defect
   to detect*: an element fully covered by a later opaque element, or shrunk below a few pixels, is content removal
   in disguise. Add both to our hard fails and to the eval metrics.
5. **Path-coverage candidate budgets** (tailsgit `candidate_budget.py`): guarantee every family / mode a feasible
   representative before spending the shared budget, counts not wall-clock, so output is byte-identical on a slower
   machine. We cap by `MAX_CANDIDATES`; a per-family floor is the same idea.
6. **Adversarial role cases** (Angelo dev designs 05–09): ghost word at opacity 0.08 as the largest font, "SAVE 20%"
   as a non-button, CTA starting with "find", plain-text CTA, numbered steps in reading order, wordmark-as-logo.
   Add as role-classifier / analyzer tests (opacity-weighted size for headline choice is a one-line rule).
7. **Judge order-swap consistency** (Preeyam183, Angelo's note): when a model judges pairs, present both orders
   and count disagreement as a tie. Only matters if we ever re-enable a VLM tie-break.
8. **Shared readability level across all banner text** (vedanth2406 `horizontal.py`): one binary search on a
   readability level that every text and label row must meet, rejecting a layout rather than shrinking one piece
   below it. Our `_largest_k` does this for floors; the rejection (instead of rescue) is a stricter variant worth
   trying as a candidate.

Ignore / traps:
- Absolute pixel text targets (Ebrahim 14 / 11 / 9 / 7 px) and `fit = "cover"` forced on backgrounds: hand-tuned
  to small banners, wrong at 1080×1920 and alters the design.
- Zero-overlap gates (preetham-ven, Ebrahim's 80× penalty): dismantle every layered design; our source-relative
  rule is right.
- Hiding content (ankita320 speck, Parinagpal `hidden`), rewriting `z_index` / `fit` (Revan-dev), modifying the
  vendored converter (preetham-ven): rubric or rule violations a judge will see.
- Logo by id / asset-name regex (ankita320, Revan-dev): hidden tasks have opaque ids.
- Learned layout generators and critics at this data scale: tailsgit (CVAE 15/40, critic 0.578), Angelo (student
  loses 11–13, pickers coin flips), us (S1, S6). Three independent teams, same answer. Spend the remaining days on
  rules + judge, not weights.
- Rendering and disk writes inside `resize()` by default (Preeyam183): our render is budgeted and optional for
  the QEMU reason in docs/DOCKER_CHECK.md.

## Housekeeping
- Organizer-side signals seen in rival docs: tailsgit works to "around November 2, unconfirmed" and a 13.5 CPU-s
  self-imposed budget; Angelo's team still lists network-during-scoring, image size limit and reference hardware as
  open questions. Nobody has a confirmed model cap.
- Clones added: `vedanth2406_chameleon`, `preetham-ven_chameleon`, `EbrahimHimayoun_PolymorphicTrio`,
  `Preeyam183_AdobeHackathon`, `ankita320_adobe-h`, `Revan-dev_chameleon`, `Jdeww_chameleon`,
  `amanadhav_chameleon`, `Parinagpal11_Project-Chameleon-Adobe_Hackathon`. AngeloLandiza's clone is now the only
  copy of that work.
