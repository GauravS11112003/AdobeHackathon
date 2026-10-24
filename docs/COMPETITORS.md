# Competitive landscape — CHAMELEON public repos (updated 2026-10-23)

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
