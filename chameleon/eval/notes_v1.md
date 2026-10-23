## Observations (hand-written, from the contact sheets and the per-case data)

### What holds up
- **Structure is solid.** 0 crashes, 0 id/field/immutable violations, 0 important units off canvas, 1 image
  aspect drift in 6058 cases. The uniform-scale safety net was never needed.
- **Nine of the twelve presets are nearly defect-free** (≤ 1.5 % of cases with a measurable hard defect;
  A4 poster 0 %, Story/Reel 0.2 %). The square / tall / wide social formats are in good shape.
- **Reading order and hierarchy survive.** Against the designers' own versions of the same template
  (608 cases): reading-order Kendall tau 0.82 (72 % of cases ≥ 0.5), font-size-hierarchy Spearman 0.78,
  our type scale is 0.99× the designer's (median, canvas-normalised).
- **Speed is fine.** 0.21 s median per case in a single process (0.42 s with 4 workers competing for
  the CPU), 1.9 s p95, 9.9 s worst (a 1080×1920 render-heavy case).

### Failure patterns, most important first

1. **Zero-size text boxes crash the official renderer (fixed in this session).** 23 cases (0.4 %, all
   728×90) ended with a text element at width 0 × height 0 (font 1 px). cr-renderer's `TextElement`
   model requires width/height > 0 and rejects the *whole* design, so the task would produce no PNG and
   score nothing. Guard added in `resize._finalize` (text boxes ≥ 1 px, kept on canvas) and a regression
   test (`tests/test_eval.py::test_no_zero_size_text_elements_reach_the_official_renderer`,
   fixture `tests/fixtures/zero_size_text_regression.json`). Root cause still open: the banner plan
   squeezes a short uppercase line that `analyze` labels CTA ("THE OCEAN", the real headline) to nothing.

2. **Letter spacing is not scaled with the font.** Of the 146 overflow cases, ~50 overflowing elements
   carry positive `letter_spacing`. The wrap ignores letter spacing (as the renderer does) but the fit
   check adds it to the line width; when the font shrinks the px spacing stays, so the line never fits
   and `fit_font_size` runs down to the floor (1 px fonts appear in the outputs). Crello uses letter
   spacing on 40 % of text layers, so hidden tasks will too. **Suggestion:** scale `letter_spacing`
   with the font (same factor as `font_size`); the schema treats it as a px value, not a fixed one.

3. **Rotated text is fitted as if upright.** Vertical labels (rotation ±90°) have narrow boxes; the fitter
   wraps the words into that narrow width and collapses the font. 18 overflowing elements, every one
   ends at the floor. **Suggestion:** fit rotated text in its own frame (swap width/height for
   |rotation| near 90°, use the rotated AABB only for collisions, which `rectify` already does).

4. **Colour panels are treated as chips.** Crello designs are built from flat colour rectangles
   (single-colour SVGs → `shape` here): split backgrounds, side bars, text panels. The floor plans
   size shapes as badge-like chips, so a half-canvas panel becomes a 30 px square and the text that
   sat on it lands on the bare canvas (see worst #13 "Corporate Charity Night", #15 "Red college",
   #10 "Eco-consciousness"). This is the biggest *visual* weakness; the hard metrics barely see it,
   the ground-truth centre error (0.15 of the diagonal, 0.18 for big ratio changes) does.
   **Suggestion:** in `analyze`, a shape that covers ≥ ~15 % of the canvas or spans an edge to edge is a
   *panel*, not a chip; panels may be stretched (flat colour has no aspect) and should be laid out
   like backgrounds/zones, carrying the text that overlapped them in the source.

5. **Tiny canvases: 160×600 and 728×90 are where the engine fails.** Skyscraper: 18.8 % of cases with a
   hard defect (11.9 % overflow, 13.5 % headline/CTA font below the readable floor); Leaderboard 9.9 %;
   Facebook cover 4.6 %. Causes in the data: a single word wider than the slot (`content` cannot be
   broken, 24 elements), headline slots ≤ 130 px wide on a 160 px canvas, CTA labels squeezed below
   12 px. The ground truth agrees the type is too small on banners: our banner fonts are 0.77× the
   designer's (median) while every other family is ≈ 1.0×. **Suggestions:** (a) size the headline slot
   from its longest word at the floor font before shrinking anything else; (b) on banners give the text
   column more of the width (designers' text boxes are 1.3–1.7× wider than ours relative to the
   canvas, `gt_width_ratio`); (c) let the headline take 2–3 lines on skyscrapers before dropping below
   the floor; (d) drop fine print / badges to their minimum first (prio already exists, the floor
   search still ends at k where the headline is below floor).

6. **The anchor safety net wins 5.4 % of the time (327 cases), and 213 of those were "clean".** Every
   real candidate had a hard fail (often only a contrast fail from the stand-in assets, but in 30 cases
   a layout defect) so the fallback, which merely slides things to their anchors, was returned. It is
   defect-free but unpolished: big empty areas, shrunken content (worst #7/#8 "Origami"). **Suggestion:**
   make the anchor-fit layout a first-class candidate for big ratio changes (rectified, scored like the
   others) and let the judge pick it on merit, or feed it through the floor-plan spacing pass.

7. **The judge barely separates candidates.** Runner-up gap median 0.78 points; in 57 % of cases the
   top two candidates are within 1 point. Soft components with the least spread dominate
   (`faith.hierarchy` 0.98, `layout.fill` 0.91, `layout.balance` 0.90); the discriminating ones are
   `faith.anchors` (0.42 on banners), `faith.scale`, `layout.spacing`, `layout.alignment` (0.66).
   **Suggestion:** calibrate the weights with perturbed negatives (DesignSense: shift 20–50 % / scale
   0.8–1.2× of ~70 % of the elements and label bad) — the harness has every output JSON to perturb.

8. **Contrast hard fails (11.2 %) are mostly the dataset, but they hide an engine gap.** 45 of 453
   designs fail contrast in ≥ 50 % of their cases: white text whose photo was replaced by a small
   stand-in or whose colour panel shrank to a chip. The engine never reacts: it cannot recolour, but
   it could keep text on the unit it sat on. **Suggestion:** record "text over image/panel" relations
   in `analyze` and preserve them in the plans (same fix as pattern 4).

9. **Tight source boxes shrink the type silently.** Crello sizes a text box as lines × font ×
   line-height; `textfit.fits()` wants ascent + descent, so 90 % of raw Crello boxes count as
   overflowing and the engine shrinks their fonts (run `full_rawboxes`: defect rate 4.0 % vs 3.5 %,
   but `read.size` 0.853 vs 0.881, median smallest font 22 px vs 24 px, p10 of font-scale-vs-canvas
   0.60). The converter now normalises boxes (`--raw-boxes` keeps them). If the hidden tasks are drawn
   tight, the engine will under-size type. **Suggestion:** accept the renderer's own convention in
   `fits()` (height ≥ lines × font × line_height) or always grow the box before shrinking the font.

10. **Render budget under load.** With 4 worker processes, 615 cases lost pixel checks because a render
    exceeded the 2.5 s budget (CPU contention); single-process runs never hit it. Harmless for the
    judges' single run, but the budget is a function of machine load, not of the design.

### Prioritised list for the next engine session
- P0 (done here) zero-size text guard; still find why the banner plan collapses a CTA-labelled headline.
- P1 scale `letter_spacing` with `font_size` (pattern 2).
- P1 fit rotated text in its own frame (pattern 3).
- P1 panels: large flat shapes become stretchable zones that carry their text (patterns 4, 8).
- P2 tiny canvases: longest-word-aware slot widths, wider text column on banners, more headline lines
  before dropping below the floor (pattern 5).
- P2 anchor-fit as a real candidate for big ratio changes; polish or retire the raw fallback (pattern 6).
- P3 judge calibration with perturbed negatives generated from `eval/data/runs/full/outputs/` (pattern 7).
- P3 `fits()` convention for tight boxes (pattern 9); render budget independent of load (pattern 10).

### Harness caveats
- Assets are stand-ins chosen by shape (photo → gradient panel, wide → logo, else bottle); illustrations
  become bottle stickers. Fonts are Solstice Serif/Sans by serif-likeness. Both change the look, not the
  geometry. The original fonts/types are in each design's sidecar.
- Crello has no `group_id`, so grouped units (buttons, badges) are only exercised by the three samples.
- Ground-truth siblings are matched by title + shared text; the designer's version is at a slightly
  different canvas (same family), so `gt_*` numbers are canvas-normalised and approximate.
