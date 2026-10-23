## Engine failures found by the synthetic corpus, prioritised (for the engine owners)

Scope: 200 generated designs x 12 presets (2400 cases) + 29 nasty cases with their own targets (74 cases),
plus the metamorphic suite (12 corpus designs x 7 relations, 29 nasty cases x 3 targets). Numbers are from
run `synth` (engine snapshot of 2026-10-23 14:18; `engine/*.py` and `eval/metrics.py` did not change during
the run, verified by hash). The engine was being edited by sibling sessions all afternoon: an identical run
40 minutes earlier had 11.2 % below-floor cases, this one has 6.9 % after the source-relative font floor
landed in `engine.score.below_floor`. Re-run `--synthetic 200 --seed 1` before acting on a number. Nothing in
`engine/` was changed by this session.

### Crashes

None. 0 of 2474 harness cases raised, 0 of 87 nasty `resize()` calls raised, and the uniform-scale safety
net (`resize failed`) never fired (`test_nasty_inputs_do_not_hit_the_uniform_fallback`). Empty content,
font 0.5 / 400, 0x0 elements, negative coordinates, every asset missing, one element, everything in one
group, required fields only, rotation 725, unicode / newlines, letter_spacing 40 / line_height 0, 45
elements, six identical stacked texts, a 900 px watermark, 1x1 / 4000x4000 / 4000x100 / 100x4000 targets and
a 50x50 source all return a design with the right ids in the right order and no immutable field touched.

### P1 — would fail the organizers' structural pass or the PNG step

1. **Negative sizes on a degenerate target** (`nasty_target_1x1`): the logo comes back as x=2, y=1, w=-3,
   h=-1 and the hero as w=-1, h=-1 (the only `fields` fail in the run). Schema says width/height >= 0 and
   cr-renderer rejects the design, so the task scores nothing. 1x1 is absurd, but an 88x31 micro-bar is a
   real IAB size and the same arithmetic (margins larger than the canvas) applies. Suggestion: `_finalize`
   clamps text boxes to >= 1 px; clamp every element's width/height to >= 0 (images >= 1 px, aspect kept)
   and cap margins at a fraction of the canvas. Only text is guarded today.
2. **A full-bleed image without a `fit` key is stretched** (`nasty_required_fields_only`: aspect drift 25 %
   at 1080x1080, 30 % at 1080x1920, 911 % at 728x90). The schema default for `fit` is `contain` and the rules
   say contain images keep their aspect; the engine treats the element as a cover background and stretches
   it. If a hidden task omits optional keys (the schema allows it), this is a structural fail on the
   background of every case. Suggestion: when `fit` is missing on a background-sized image, scale it
   uniformly to *cover* the canvas and let it bleed (off-canvas background is tolerated) instead of changing
   its aspect.
3. **Letter-spaced text is drawn wider than the box the engine fitted** (visible in worst #22, #9, #10, #21):
   the wrap ignores `letter_spacing` (as cr-renderer's wrap does) but the glyphs are drawn with it, so a
   letter-spaced line is wider than its box and runs off the right canvas edge in the render. Measured as
   overflow in 15 cases (0.6 %), but the slice says it is the single biggest risk factor in the corpus:
   **cases with letter spacing have an 11.9 % defect rate vs 1.6 % without** (1464 vs 936 cases). Crello uses
   tracking on 40 % of text layers. All 15 overflow cases are `long` / `medium` headlines with 1-6 px tracking,
   8 of them also rotated 5-12 degrees, and 3 end at a 1 px font (Skyscraper 160x600); in 7 of them every real
   candidate hard-fails on the overflow and the un-designed anchor fallback ships (worst #23-#27).
   Suggestions: make the fitter's width check consistent with the wrap *and* give the box the tracked width
   (wrap at `width - tracking x chars_per_line`, or widen the box to the tracked line width), and fit rotated
   text in its own frame. This is the same mechanism EVAL_V1 listed as P1; the synthetic corpus shows it
   also costs whole layouts, not only font size.

### P2 — hard defects by the engine's own definition (the judge gives them -1000)

4. **Headline / CTA below the readable floor: 6.9 % of cases** (166; 147 headline, 100 CTA elements), the only
   frequent defect. By target: Skyscraper 20 %, Facebook cover 11.5 %, Leaderboard 9.5 %, Story 7.5 %; by
   headline length: `long` (140-190 chars) 22 % vs 1-2 % for `short` / `two_words`; `unbreakable` 8 %.
   Two mechanisms:
   - the plan starves the primary text when there is a lot of other content: `syn_1_0026` (36 elements, 6
     badges, 4 subheads, 1024x512 -> 1080x1920) could keep its headline at 63 px by uniform scaling and the
     floor is 16 px, yet every one of the 9 floor plans puts it at 5-11 px (`square hero=right`: 5 px), so the
     only clean candidate is the anchor fallback (worst #4, and the three `syn_1_0026` fallback wins). Chips
     and subheads should give way before the headline / CTA drop under the source-scaled size;
   - small canvases: a Level-1-like design drawn at 500x500 has a 9 px CTA label; the floor at 160x600 is 12
     px, so `Reserve a Bottle` ends at 7 px. The floor is already source-relative in the metric; the plans
     still shrink below uniform scale (median output / floor 0.64 in the earlier run).
5. **Unwanted overlaps: 16 cases (0.6 %), all floor-plan winners, 9 on Leaderboard, 3 LinkedIn, 2 Wide web
   banner, 2 Skyscraper, every one a design with 28-39 elements and 4-6 badges.** Every pair involves the
   badge row (`row:group:...`) colliding with the text column, the CTA, a second badge row or the ribbon; 3
   sources were themselves overfull. Median overlap 2 % of the canvas (worst #4-#6, #11-#20). Suggestion: the
   banner chip cluster should re-flow to two rows / drop to its floor *before* the row is placed, and the
   rectifier should be allowed to split a row (or hide chips behind the fold) when pushing does not help.
6. **An unbreakable headline collapses the whole layout** (worst #7, `syn_1_0191` 1584x396 -> 160x600): a
   52-character URL headline cannot wrap, so the fitter runs it to 1 px and the column is mostly empty;
   `unbreakable` sources have an 8.3 % defect rate (vs 1.4 % `short`). Suggestion: break at `-`, `/`, `.`
   and `#` when a word is wider than the column (cr-renderer will still draw the unbroken word, so the
   honest option is to let the word bleed horizontally at a readable size rather than shrink to nothing),
   or rotate-free vertical stacking of that unit.
7. **Everything in one group** (`nasty_all_one_group`): 6 CTA-labelled texts below the floor at 728x90
   (-5920) and 1080x1920. A group that spans the whole canvas (background included) is not a unit;
   suggestion: dissolve a group whose bbox covers > 85 % of the canvas or that contains the background.
8. **A grid of 44 small texts to 728x90** (`nasty_forty_five_elements`): fallback with 39 overflows and 21
   overlaps (14.8 % of the canvas). No floor plan has a notion of a grid. Unrealistic for an ad, but an
   editorial design with many small texts is not: an XY-cut / grid re-flow candidate (docs/COMPETITORS.md,
   gk7494) would cover it.
9. **Source canvases below 300 px lose their roles, and the tall plan then leads with the legal text**
   (worst #3, `syn_1_0167` 728x90 -> 160x600: "Please drink responsibly" in large type at the top of the
   column, the headline tiny below it). `FINE_PRINT_MAX_PX = 16` is absolute source px, so on a 728x90 or
   970x250 source every text under 16 px is fine print, the real CTA becomes `fine_print` and a badge label
   becomes `cta` (see 11). Banner sources make up a quarter of the Crello catalogue.

### P3 — metamorphic relations the engine breaks (see "Metamorphic tests" above)

10. **Identity is not a no-op** (`banner-11`, and `tall-13` / `square-13` on the 14:05 snapshot): with target
    == source a floor plan beats the identity candidate by < 1 point (93.2 vs 92.7) and moves the headline
    400 px, or the identity candidate is *hard-failed* because the source's own CTA label is below the floor.
    Suggestion: for ratio_change < ~1.05 require a clear soft-score margin before accepting a re-layout, and
    never hard-fail a candidate for a floor the source itself violates (partly done since).
11. **Output depends on the source's absolute resolution** (4 of 12 designs differ when the source is drawn
    at 2x): on the 1584x396 source three 9-14 px subheads are fine print and the badge label is the CTA,
    while at 2x they are subhead / body / cta; on other designs the same plan wins but fonts come out ~6 %
    larger from the 2x source. Suggestion: express px thresholds relative to the canvas (16 px on a
    1080-wide canvas = 1.5 % of the long side) and derive plan sizes from canvas fractions only.

### Properties that did *not* matter (good news)

Missing hero asset (11.1 % vs 7.0 % defect rate, all of it explained by the designs' other properties),
style_runs (7.9 % either way), max_lines (5.6 % vs 8.3 %), shadow headline duplicates (6.3 % vs 8.1 %), text
panels (10.8 % vs 6.9 %, mostly the 36-element designs), decorative bleed, z-index ties (3.6 % with ties vs
10.4 % without — worth a look: designs whose content shares one z have *fewer* defects, which suggests the
paint-order-based unit clustering treats distinct z as separation), tiny elements, any logo position.

### What held up

- Off-canvas: 0 of 2474 cases, including rotated ribbons at 45 degrees, decorative ellipses bleeding 70 %,
  negative source coordinates and a shape 3000 px outside the source canvas.
- Image aspect: 0 drift on every `contain` image that carried its `fit` key; missing assets are laid out like
  any image (placeholder box in the render, as the Level 3 sample expects).
- ids / order / immutables: 0 violations; opaque-id renaming and element-list shuffling give identical output;
  two runs give identical output; group translation keeps the members' internal layout on every grouped
  design; +3 % width moves nothing by more than 4 % of the diagonal on all 12 corpus designs.
- Runtime: p50 0.14 s per case with 4 workers competing, p95 0.42 s, max 1.7 s (4000x4000).
