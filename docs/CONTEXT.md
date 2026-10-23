# CHAMELEON — Project Context

> Paste this file at the start of a new Claude Code session. It captures everything researched and decided so far for the Adobe University Hackathon 2026 "CHAMELEON" challenge. Dates: research done 2026-10-19. Treat anything marked **TBD** as unconfirmed by the organizers.

---

## 0. How to use this file

- Sections 1–6 are facts (brief, rules, schema, repo). Trust them; re-verify against the live repo if something looks off.
- Sections 7–9 are the research map and the three candidate strategies, with scores.
- Section 10 is the recommended architecture to build. Section 11 is the implementation plan.
- Section 12 lists open questions to confirm with organizers before relying on them.

---

## 1. The challenge in one paragraph

Adobe Express can make a poster, but a brand needs the same poster as an Instagram square, a phone story, a wide web banner, a YouTube thumbnail, etc. Today a designer rebuilds the layout by hand for each shape, and Express's built-in Resize crops/stretches (the brief shows a 1080×1350 "Solstice — Chase the Light" poster losing its logo and CTA when resized to 1080×1080). **CHAMELEON asks for an engine that takes a finished design + a target canvas size and returns the same elements re-laid-out so it still looks designed: nothing overlapping that shouldn't, text readable, brand intact, everything intentional.** The brief's analogy: don't stretch a photo of the old room — move the furniture into the new room.

Brief: "Adobe University Hackathon: North America 2026 — Project CHAMELEON, Any Design. Every Canvas." Starter repo: https://github.com/jhaaj08/chameleon

## 2. Competition structure

- **Stage 1 (automated, what we're building now):** every team submits an engine. Organizers run it offline against a large hidden set of designs × target sizes across 3 difficulty levels and score automatically. Top ~6–7 teams advance.
- **Engineering session:** finalists walk Adobe engineers through their approach and trade-offs.
- **Stage 2 (live finale at Adobe Founders office):** turn the engine into a real Adobe Express add-on; judged by a cross-functional jury (research/product/design/engineering). Open-ended: multiple options to choose from, user steering/locking, letting less-important elements drop, adaptive copy/typography are all welcome *here* (not scored in Stage 1).

### Difficulty levels (same task, harder input)
- **Level 1 — Warm-up:** few elements, nearby aspect ratio. Sample: 4 elements, 1080×1080 → 1080×1350.
- **Level 2 — Core:** many elements, groups, overlapping and semi-transparent shapes, very different ratio. Sample: 11 elements, 1080×1080 → 1600×400. "The main discriminator." Already beyond what Adobe's tools do reliably.
- **Level 3 — Advanced:** arbitrary number of text boxes/images, deliberately awkward content (e.g. an intentionally missing asset), extreme unseen ratio. Sample: 17 elements, 1080×1350 → 728×90.

Organizers say a thoughtful partial solution is valuable; they are measuring how far a team climbs.

## 3. Hard rules (Stage 1)

- **Runs offline in Docker with `--network none`** on the organizers' machine. Everything (packages, model weights) must be installed/baked at build time via `requirements.txt` / Dockerfile. `docker build --platform linux/amd64`.
- **Reference hardware:** Apple M5 Pro — exact CPU/RAM/disk and whether a GPU is available are **TBD** (RULES.md literally says placeholder). Assume CPU-only to be safe.
- **Local models allowed** with a size cap and an approved open-model list — both **TBD**. No calling outside APIs. If using fine-tuned/LoRA weights, they must be publicly hosted (e.g. public HF repo).
- **Disqualifying:** regenerating, redrawing, or replacing the pixel content of any asset, including backgrounds and decorative elements, including with GenAI. Reposition and resize only.
- **Stage 1 treats text content and font family as fixed.** Changing `font_size` to fit is expected and core. Rewriting copy or swapping fonts is finale-only creativity.
- **No hand-tailoring** to specific designs/sizes; hidden cases punish it.
- **Fixed materials you may rely on:** brand colors, fonts (Solstice Serif, Solstice Sans), logo, and a catalogue of common canvas sizes described as real platform formats ("Instagram Post", "YouTube Thumbnail"…) with exact resolutions. Specific hidden targets are unseen but will look like real formats, not arbitrary rectangles.
- **No hard time limit;** "speed and reliability" is a rubric row but a slower, better result is not thrown out. Optimize quality first.
- **Deliverables (Stage 1):** engine code + Dockerfile + short README explaining approach and how to run. Submission location/form to be announced.

## 4. Scoring (what the automated scorer checks)

Both outputs are evaluated:
1. **Output JSON — structural checks:** same element ids as source (none added/removed), required fields present, nothing off-canvas, images kept in proportion, etc.
2. **Rendered PNG — AI evaluator against a rubric.** Your JSON is run through the official renderer, then judged.

Rubric qualities (from the brief):
- No unwanted collisions (intentional layering is fine; text never sits on a busy image)
- Everything readable (text large enough, enough contrast, nothing cut off)
- Stays on brand (colors, fonts, logo intact and in proportion)
- Looks intentional (alignment, even spacing, hierarchy preserved, image proportions kept)
- Holds up everywhere (many designs/shapes, not one lucky example)
- Speed and reliability (minor row)

Plausible JSON that renders illegibly gets no credit; a nice-looking PNG from a dishonest JSON gets no credit.

## 5. Starter repo (jhaaj08/chameleon) — layout and workflow

As of 2026-10-19: 2 commits, 0 stars, 0 forks. No public solutions or forks exist.

```
chameleon/
├── Dockerfile
├── README.md / RULES.md / FAQ.md
├── requirements.txt
├── chameleon_design_schema_v0.9.json   # field-by-field spec (see §6)
├── engine/
│   ├── main.py      # orchestrator: load input -> resize() -> write JSON+PNG, run self-check. Don't edit.
│   └── resize.py    # THE ONLY FILE YOU EDIT: def resize(source: dict, target_canvas: dict) -> dict
├── renderer/        # vendored transformer-convertor wrapping cr-renderer (CyberAgent's Crello renderer)
├── brand_kit/
│   ├── assets/      # image files referenced by asset_id (bg, logo, product art)
│   └── fonts/       # Solstice Serif / Solstice Sans
├── input/           # task JSONs (3 samples, one per level)
└── output/          # <task>_output.json + <task>_output.png
```

Workflow:
```
git clone https://github.com/jhaaj08/chameleon.git && cd chameleon
pip install -r requirements.txt     # Python 3.10+, installs cr-renderer
python -m engine.main                # processes every input/*.json
docker build --platform linux/amd64 -t my-chameleon-engine .
docker run --rm --network none -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output my-chameleon-engine
```

Notes:
- Baseline `resize()` is a deliberate uniform stretch. Replace the body, not just constants.
- `main.py` self-check (ids, required fields, off-canvas) is a sanity net, not the official scorer. A warning doesn't block output. The Level 2 sample's corner-bleeding decorative circle is an *expected* warning.
- If the output PNG shows labeled boxes instead of real text/images, cr-renderer failed to import — fix the install.
- Renderer handles real glyph-width text wrapping, rotation, shape rasterization, and missing assets as placeholders (Level 3's `holiday_watermark` → `solstice_holiday_badge_2025.png` is intentionally missing; don't add it).
- Organizers convert their schema to Crello's format right before rendering; we never touch that.

## 6. Input / output schema (chameleon_design_schema_v0.9.json, exact)

Task file wrapper (what sits in `input/`):
```json
{ "task_id": "...", "difficulty": "...", "notes": "...",
  "source": { "canvas": {...}, "elements": [...] },
  "target_canvas": { "width": W, "height": H } }
```
`resize()` receives `source` and `target_canvas`; returns a `source`-shaped dict with the new canvas and updated elements.

Top level: `canvas {width:int, height:int}` (px), `elements[]` (min 1). `additionalProperties: false` at top level only.

Common element fields: `id` (string, opaque; return each exactly once), `type` ∈ {text, image, shape}, `x`, `y` (px from top-left; may be negative), `width`, `height` (px ≥ 0), `rotation` (deg clockwise about center, default 0), `opacity` (0–1, default 1), `z_index` (int, higher on top), `group_id` (string|null; shared id = designer-intended unit that must travel together; meaning not given).

Text: `content` (literal string — don't change), `font_family`, `font_size` (px; **may change to fit**), `font_weight` ∈ {regular, bold}, `font_style` ∈ {normal, italic}, `color` (CSS `rgba()` string), `text_align` ∈ {left, center, right}, `line_height` (multiplier, default 1.2), `letter_spacing` (px), `max_lines` (int|null), `style_runs[]` ({start, end, color?, font_weight?, font_style?}; 0-based, end-exclusive indices into content). Renderer wraps within width×height regardless.

Image: `asset_id` (file in brand_kit/assets), `fit` ∈ {contain, cover, fill} (default contain). **No crop rect / focal point field.**

Shape: `shape_type` ∈ {rectangle, ellipse, line}, `fill_color`, `stroke_color` (string|null), `stroke_width`, `corner_radius` (rectangles).

Required: text → content, font_family, font_size, color; image → asset_id; shape → shape_type, fill_color.

### Level 2 sample (1080×1080 → 1600×400), abbreviated but exact values
- `bg` image 0,0 1080×1080 z0 `solstice_bg_gradient.png` fit cover
- `deco_circle_1` ellipse −100,−100 500×500 z1 white opacity 0.15 (intentional bleed + intentional overlap with product)
- `deco_circle_2` ellipse 700,700 300×300 z1 white opacity 0.12
- `logo` image 380,60 320×110 z4 `solstice_logo_lockup.png` contain
- `product` image 290,260 500×500 z3 `solstice_bottle.png` contain
- `headline` text 90,780 900×140 z4 "Chase the Light" Solstice Serif 56 bold white center, style_run {6,16} gold rgba(240,178,66,1)
- `subhead` text 140,920 800×70 z4 "Botanical sparkling infusions, crafted for golden hour." Solstice Sans 24 rgba(255,255,255,0.85) center
- `badge_bg` rect 40,40 220×56 z3 orange rgba(232,106,58,1) corner_radius 28 group "badge"
- `badge_label` text 40,52 220×32 z4 "NEW FLAVOR" Solstice Sans 18 bold white center group "badge"
- `cta_bg` rect 330,950 420×90 z3 orange corner_radius 45 group "cta"
- `cta_label` text 330,975 420×44 z4 "Shop the Summer Line" Solstice Sans 22 bold white center group "cta"

Sample files: `input/chameleon_sample_level1_warmup.json`, `..._level2_core.json`, `..._level3_advanced.json`.

### Gotchas derived from the schema + samples
- Sample ids are descriptive (`headline`, `logo`) but the FAQ says hidden tasks give only id/type/geometry — **treat ids as opaque; infer roles from signals.**
- "Nothing off-canvas" is really "nothing important off-canvas": low-opacity decorative shapes may bleed (sample does it on purpose). Keep text, logo, product, CTA fully inside.
- Group inset must be preserved (badge label sits 12px inside badge bg; label height 32 inside 56).
- `style_runs` indices must stay valid → never alter `content`.
- Only two fonts; all colors are `rgba()` → contrast checks are easy.
- Asset files are on disk: you may *read* pixels (bounding box of the bottle inside its PNG, busy regions of the background) — you may never write new pixels.
- Image boxes with `contain` must keep aspect ratio when resized.

## 7. Research map (with one-line takeaways)

### Directly about resizing/retargeting designs
- **O'Donovan, Agarwala, Hertzmann — "Learning Layouts for Single-Page Graphic Designs" (TVCG 2014, Adobe Research).** Energy model of good layout (alignment, balance, importance, segmentation); retargets a design to a new size using the previous layout as a prior. Project page has retargeting data + 98 human/automatic retargets. https://www.dgp.toronto.edu/~donovan/layout/index.html · PDF https://www.dgp.toronto.edu/~donovan/layout/designLayout.pdf
- **DesignScape (CHI 2015, same authors)** — interactive layout suggestions (refine vs brainstorm). The finale's "offer several options" idea, built by Adobe a decade ago. https://www.dgp.toronto.edu/~donovan/design/designscape.pdf
- **Adobe patent US10606925 — Responsive grid layouts for graphic design (O'Donovan).** Generate grid layouts, map cells to elements, score grids on aesthetic criteria; on ratio change swap grid and move contents to new cells by rules. https://patents.google.com/patent/US10606925
- **Adobe patent US11320975 — Semantic-aware resize constraints.** Detect element semantics → auto-generate resize constraints via heuristics. https://patents.justia.com/patent/11320975
- **Bylinskii et al. — Learning Visual Importance for Graphic Designs (2017).** Importance maps → retargeting keeps the most important regions. https://arxiv.org/pdf/1708.02660
- **Attribute-conditioned LayoutGAN (TVCG 2021, Adobe).** Adjusts layouts to new sizes while preserving reading order. https://arxiv.org/abs/2009.05284
- **Graphic-Design-Bench (LICA, 2026)** — has a "Multi-Aspect Ratio Adaptation" task; frontier image models fail (GPT-Image-1.5: text 1.0 but asset recall 0.23; Gemini: recall 1.0, text 0.92). Confirms unsolved; useful for the pitch. https://arxiv.org/pdf/2604.04192 · code https://github.com/purvanshi-lica/lica-bench
- **"One Figure, Every Canvas" (Oct 2026)** — agentic Parse→Style→Layout pipeline with a critic per stage for aspect-ratio-adaptive flowchart relayout; notes image models fail beyond ~3:1. https://arxiv.org/pdf/2610.06852

### Adobe MDSR (the team most likely behind the judge)
- **DesignSense (Feb 2026, Adobe MDSR).** 10,235 human preference pairs of *relayouts across aspect ratios* built from Crello (Stretching-2x and Inverse-Ratio variants). 5-stage pipeline: grouping (GPT-4o one-shot, ARI ≈ 0.69 vs humans) → prediction (AesthetiQ at group level, 10 samples by temperature) → filtering (overlaps/overflows) → IoU clustering for diversity → refinement (o3 fixes overlaps/alignment). Judge = InternVL3-8B fine-tuned, 4-class (left/right/both good/both bad), beats GPT-5/o3/Gemini by large margins; judge prompt attends to visual appeal, spacing & alignment, element clarity, design principles, with tie-break = absence of visual defects. Perturbation augmentation: perturb ~70% of elements (20–50% shift or 0.8–1.2× scale) → auto-label bad (+12.3% Macro F1). Inference-time scaling (generate 10, rank) gives +3.6% win rate; RL with the judge +~3%. **No public code/weights/data found.** https://arxiv.org/html/2602.23438v1
- **AesthetiQ (CVPR 2025, Adobe MDSR).** MLLM layout generator (1B–8B), DPO-aligned to MLLM aesthetic preferences (AAPA), with layout-quality heuristic filtering; takes grouped element images + target ratio → boxes. No public weights found. https://openaccess.thecvf.com/content/CVPR2025/html/Patnaik_AesthetiQ_Enhancing_Graphic_Layout_Design_via_Aesthetic-Aware_Preference_Alignment_of_CVPR_2025_paper.html
- **mdsrLab's fork of Awesome-Layout-Generation** — the team's reading list. https://github.com/mdsrLab/Awesome-Layout-Generation

### Data
- **Crello dataset (CyberAgent, HF `cyberagent/crello`)** — ~19k real design templates (canvas size, elements, text boxes, images), many designs in multiple sizes, CDLA-Permissive-2.0. Same renderer family as the hackathon (`cr-renderer`). https://huggingface.co/datasets/cyberagent/crello · renderer https://github.com/CyberAgentAILab/cr-renderer
- **DesignAsCode training data (HF `Tony1109/DesignAsCode-training-data`, MIT)** — 19,479 Crello designs with GPT-4o/o3-distilled *layer groupings* with thematic labels + layout reasoning. Free grouping labels. Planner model `Tony1109/DesignAsCode-planner` is Qwen3-8B (16 GB fp16; likely over any size cap). https://huggingface.co/datasets/Tony1109/DesignAsCode-training-data
- Others: PKU PosterLayout, CGL v1/v2, Magazine, SciPostLayout (see awesome list).

### Layout generation / LLM-based (code public unless noted)
- **LayoutPrompter (NeurIPS 2023, MSR)** — in-context LLM layout gen: serialization + dynamic exemplar selection + **layout ranker picks best of N**. https://github.com/microsoft/LayoutGeneration/tree/main/LayoutPrompter
- **PosterO (CVPR 2025)** — layouts as SVG trees; in-context with intent-aligned example selection; shows adaptability across aspect ratios. https://arxiv.org/pdf/2505.07843
- **LGGPT "Smaller But Better" (IJCV 2025)** — 1.5B LLM beats 7B/175B on unified layout gen; argues 1.5B is a sweet spot. https://github.com/NiceRingNode/LGGPT
- **PosterLlama (ECCV 2024)** — HTML-as-layout with LLM. https://github.com/jaepoong/PosterLlama
- **PosterLLaVa (2024)** — unified MLLM layout generator (JSON). https://github.com/posterllava/PosterLLaVA
- **Graphist (ByteDance 2024)** — hierarchical layout gen from layered inputs. https://github.com/graphic-design-ai/graphist
- **RALF (CVPR 2024 oral, CyberAgent)** — retrieval-augmented layout transformer: retrieve similar layouts, then generate. https://github.com/CyberAgentAILab/RALF
- **FlexDM (CVPR 2023 highlight, CyberAgent)** — masked-field prediction over multimodal design elements, trained on Crello. https://github.com/CyberAgentAILab/flex-dm
- **Uni-Layout (2025, JD)** — unified generation + evaluation with human feedback. https://github.com/JD-GenX/Uni-Layout
- **Qwen2.5-VL (3B/7B)** — local VLM with stable JSON bbox output; candidate ranker/role-classifier if on the approved list. https://qwenlm.github.io/blog/qwen2.5-vl/

### Refinement / optimization / scoring
- **LayoutRectifier (CGF 2025)** — optimization post-processor: discrete grid search for alignment, then a box-containment cost removing unwanted overlap while minimizing deviation; aspect-ratio-preservation term; no training. https://arxiv.org/abs/2508.11177
- **LACE (ICLR 2024, Adobe Research)** — differentiable alignment & overlap losses. https://github.com/puar-playground/lace
- **Aesthetics++ (TVCG 2022, MSR)** — refine designs via design principles + human preference. https://github.com/microsoft/LayoutGeneration
- **Minkowski Penalties (SIGGRAPH 2024, Crane lab)** — robust differentiable penalties for no-overlap/containment/padding. https://history.siggraph.org/?p=164147
- **Optimizing UI layouts via gradient descent (2020)** — ReLU penalties for overlap/out-of-bounds with per-constraint weights. https://arxiv.org/pdf/2002.10702
- **Ngo, Teo & Byrne — A Mathematical Theory of Interface Aesthetics (2000/2003)** — closed-form 0–1 measures: balance, equilibrium, symmetry, sequence, cohesion, unity, proportion, simplicity, density, regularity, economy, homogeneity, rhythm, order & complexity. https://www.mi.sanu.ac.rs/vismath/ngo/index.html (formulas summarized in https://arxiv.org/pdf/1101.1606)
- **LTSim (CyberAgent 2024)** — transport-based layout similarity metric ("how far did we drift from the source"). https://arxiv.org/abs/2407.12356
- **Predicting Visual Attention in Graphic Design Documents (2024)** — attention model for designs. https://arxiv.org/pdf/2407.02439

### Practical libraries
- **`stretchable`** — Python bindings for Taffy (Rust CSS Flexbox/Grid/Block); wheels for macOS arm64/Linux/Windows. Use for "floor plan" archetypes. https://pypi.org/project/stretchable
- **Pillow / HarfBuzz** — measure text with brand fonts; binary-search font_size until wrapped text fits.
- **kiwisolver (Cassowary)** / **scipy.optimize** / **PyTorch** — constraint or gradient-based rectifier.
- **Katna** (OpenCV saliency + smartcrop.js rules) / **smart-crop-ai** — saliency focal point. Limited use: schema has no crop rect; only `fit`.

### Commercial behavior (for context/pitch)
- Adobe Express Resize shipped "new layout variations"/"updated algorithms" (Nov–Dec 2025 release notes); its AI resize uses generative expand (disqualifying here); the non-generative path still crops.
- Creatopy/Bannersnack Smart Resize: designer defines reference layouts per orientation; algorithm adapts sizes from nearest reference ("floor plans" idea).
- Canva Magic Resize: mostly scale + clip.
- InDesign Liquid Layout / Adjust Layout: object-based rules (pin to edges, scale), font-size adjustment on page-size change.

## 8. Competitive assumptions (who does what)

- ~50% of teams: crude scale-and-anchor heuristics, no role inference, no real text measurement.
- ~30%: a local LLM/VLM asked to output coordinates directly → noisy, overlaps, off-canvas.
- ~10%: attempt fine-tuning on Crello (risky given TBD model rules/hardware).
- ~5%: a generate → rectify → rank loop. Almost nobody: retrieval from Crello.

## 9. The three strategies (scored)

Scores: Quality = soundness for this problem (1–10). Win = chance of topping Stage 1 if executed flawlessly, given the field (1–10).

### Idea 1 — "Move the furniture by its rules" (deterministic constraint-preserving relayout)
Read the invisible rules out of the source (roles, which edge each element hugs, size hierarchy, reading order, groups). Small ratio change → InDesign-Liquid-Layout style: slide and scale toward anchors. Big change → pick a floor plan (tall stack / wide row / square centered) as a flex tree and pour the elements into slots. Then fit text by measuring real fonts.
- Basis: Adobe patents US11320975 & US10606925, O'Donovan 2014 (previous layout as prior), Creatopy reference layouts, LayoutGAN reading-order preservation, Taffy.
- Quality 8 · Win 6 · Risk low · ~25% of teams do it well. Necessary floor; low ceiling on Level 3 alone.

Flow: Source design → Read the rules (roles, anchors, order) → How big is the shape change? → [small: slide & scale to anchors | big: pour into a floor plan] → Fit the text (measure fonts, shrink) → Resized design (same ids).

### Idea 2 — "Judge-in-the-loop" (generate many → fix defects → rank like Adobe's judge)
Generate ~10 candidates (floor plans × spacing/scale variants), run each through a defect-fixing optimizer (overlap, off-canvas, margins, grid snap, aspect, min font size), **render each with cr-renderer** (my twist: judge the real PNG, since the scorer does), score with defects → Ngo balance/alignment → similarity-to-source (LTSim-style), optionally a small VLM ranker, ship the best.
- Basis: DesignSense pipeline + inference-time scaling (+3.6%), judge tie-break = zero visual defects; LayoutPrompter ranker; LayoutRectifier/LACE/Minkowski penalties; Ngo measures; RULES.md "both JSON and PNG checked".
- Quality 9 · Win 8 · Risk medium (compute on M5 Pro; VLM availability) · ~5% of teams. Works with zero models (heuristic ranker).

Flow: Make 10 candidates → Fix defects → Render for real → Judge each one → Ship the winner.

### Idea 3 — "Borrow from 19,000 designers" (retrieval of real layouts at the target ratio)
Convert Crello templates to the Chameleon schema; compute a role signature for the source (which roles exist + size hierarchy); retrieve Crello templates with the same signature at the target ratio; copy their slot geometry onto our elements; hand to Idea 2's fixer/ranker. Grouping validated on DesignAsCode labels.
- Basis: RALF (retrieve-then-generate), Crello (same renderer family), PosterO/LayoutPrompter exemplar selection, O'Donovan learning from examples, DesignAsCode grouping data.
- Quality 8.5 · Win 7 · Risk high (data engineering, role mapping, domain mismatch) · ~0–5% of teams. Highest ceiling for "looks designer-made"; retrieved variants double as finale "options".

Flow: [Crello library + Describe your design] → Find look-alikes at target size → Copy their positions → Hand to the judge loop.

### Recommendation
Build 1 (week 1) → add 2 on top (it only needs candidates) → add 3 once the eval harness exists. 1+2 ≈ top-3 Stage-1 engine; 1+2+3 is the finale story ("Adobe's own judge-in-the-loop recipe, seeded by real designer layouts").

## 10. Recommended architecture (combined engine)

```
resize(source, target)
  1. analyze(source)            -> roles, groups, anchors, reading order, hierarchy
  2. plan(target)               -> ratio-change class, candidate floor plans (Idea 1) [+ retrieved layouts (Idea 3)]
  3. generate(candidates)       -> N layouts via flex trees (stretchable) with text fitting (Pillow/HarfBuzz)
  4. rectify(each)              -> penalty optimizer: overlap, off-canvas, margins, grid snap, aspect, min font, group inset
  5. render(each)               -> cr-renderer PNG (reuse renderer/converter/convert.py)
  6. score(each)                -> hard defects (fail) -> readability/contrast -> Ngo measures -> similarity to source [-> VLM tie-break]
  7. return best (same ids, new canvas, updated x/y/width/height/font_size)
```

### Role inference (no labels available)
- background: image covering ≥ ~90% of canvas, lowest z, often `fit: cover`
- logo: small `contain` image, high on canvas / in a corner, low area ratio
- product/hero: largest `contain` image, central
- headline: largest font_size text; subhead: next text below headline; body: smaller
- button/CTA: text sharing `group_id` with a shape (badge, cta)
- decorative: opacity < ~0.3, or partially off-canvas, or huge ellipse behind others
- Reading order: sort by y then x (text roles). Hierarchy: font_size order and area order.
- Validate the grouper/role inference against DesignAsCode grouping labels (ARI; DesignSense's GPT-4o got ~0.69).

### Floor plans (archetypes), by target ratio family
- tall (≤ 0.8): column stack — logo top, product middle, headline/subhead, CTA bottom; decorative bleed at corners
- square (0.8–1.25): centered stack or product-left/text-right
- wide (1.25–3): row — logo | product | headline+subhead | CTA
- banner (> 3, e.g. 728×90): single row, tiny logo, headline + CTA, product small or omitted-sized (must keep all ids; shrink, don't remove)
Implement as Taffy flex trees; slots sized from role hierarchy; images keep aspect (contain).

### Text fitting
- Load brand fonts; measure wrapped text width/height at a given font_size with the renderer's assumptions (line_height multiplier, letter_spacing).
- Binary-search font_size in [min_readable, original] until it fits the slot; keep headline > subhead > body ratios; min font size by canvas height (e.g. ≥ ~12px at 90px tall banners is impossible — prioritize CTA/headline).
- Never change `content`, `font_family`, or style_run indices.

### Rectifier (penalties, PyTorch or scipy)
loss = w_overlap·Σ(unwanted overlap area) + w_oob·Σ(important-element area outside canvas) + w_margin·margin violations + w_align·distance to grid/alignment lines + w_aspect·(image aspect deviation) + w_group·(group inset deviation) + w_dev·(deviation from proposal). Unwanted overlap excludes: decorative (low opacity) under others, elements in the same group, element-on-background.

### Scorer (ordered)
1. Hard fails: any text/logo/product/CTA off-canvas; text overflow (measured); text over busy region (local variance/entropy of background under text box); contrast below threshold; image aspect distorted; ids mismatch.
2. Ngo measures (balance, equilibrium, symmetry, alignment/regularity, density).
3. Similarity to source (relative positions/reading order; LTSim-like).
4. Optional VLM pairwise ranker (if allowed) as tie-break.

### Eval harness (the real moat)
- Convert Crello → Chameleon schema (reverse of organizers' converter). Use Crello's multi-size templates as ground-truth pairs.
- Generate perturbed negatives (DesignSense trick) to calibrate the scorer.
- Run the full loop on hundreds of designs × catalogue sizes; track defect rate, scorer distributions, runtime.

## 11. Implementation plan (suggested)

1. Clone starter; run baseline; inspect the 3 samples and PNGs.
2. Write `analyze()` (roles, groups, anchors, hierarchy) + unit tests on the 3 samples.
3. Text measurement module with brand fonts; verify against cr-renderer wrapping.
4. Idea 1 small-change path (anchors) → Level 1 sample looks right.
5. Floor plans via `stretchable` → Level 2 and Level 3 samples look right.
6. Rectifier + scorer; generate N candidates; pick best (Idea 2).
7. Render-and-verify loop using the vendored renderer.
8. Crello converter + eval harness; iterate on failures.
9. Docker build with `--network none`; time it; write README.
10. (Stretch) Idea 3 retrieval; (Finale) options UI, locks, adaptive copy.

## 12. Open questions to confirm with organizers

- Exact reference hardware (cores, RAM, GPU?) and any wall-clock budget.
- Model size cap and approved open-model list; whether a VLM ranker is permitted.
- Tolerance for decorative bleed off-canvas in the structural check (sample implies some).
- Whether `fit` may be changed on images (e.g. contain ↔ cover) and whether `rotation`/`opacity` may change.
- The target-size catalogue (exact list) — "fixed materials".
- Whether reading asset pixels for analysis is acceptable (it isn't regeneration, but confirm).
- Submission form/location and code-freeze date.

## 13. Key links

- Starter repo: https://github.com/jhaaj08/chameleon
- RULES.md: https://raw.githubusercontent.com/jhaaj08/chameleon/main/RULES.md
- Schema: https://raw.githubusercontent.com/jhaaj08/chameleon/main/chameleon_design_schema_v0.9.json
- Level 2 sample: https://raw.githubusercontent.com/jhaaj08/chameleon/main/input/chameleon_sample_level2_core.json
- DesignSense: https://arxiv.org/html/2602.23438v1
- AesthetiQ: https://openaccess.thecvf.com/content/CVPR2025/html/Patnaik_AesthetiQ_Enhancing_Graphic_Layout_Design_via_Aesthetic-Aware_Preference_Alignment_of_CVPR_2025_paper.html
- O'Donovan layout work: https://www.dgp.toronto.edu/~donovan/layout/index.html
- LayoutRectifier: https://arxiv.org/abs/2508.11177
- LACE: https://github.com/puar-playground/lace
- Ngo aesthetics: https://www.mi.sanu.ac.rs/vismath/ngo/index.html
- Crello: https://huggingface.co/datasets/cyberagent/crello
- DesignAsCode data: https://huggingface.co/datasets/Tony1109/DesignAsCode-training-data
- RALF: https://github.com/CyberAgentAILab/RALF
- LayoutPrompter: https://github.com/microsoft/LayoutGeneration/tree/main/LayoutPrompter
- stretchable: https://pypi.org/project/stretchable
- Graphic-Design-Bench: https://arxiv.org/pdf/2604.04192
- Awesome Layout Generation (mdsrLab): https://github.com/mdsrLab/Awesome-Layout-Generation
