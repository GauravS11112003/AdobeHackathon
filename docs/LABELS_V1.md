# Human labels, round 1 (2026-10-24, 109 pairs)

Decisions: 49 both bad, 23 A, 20 B, 17 tie. Calibration on the 43 decisive pairs: hand weights agree 0.51,
fitted 0.58 in-sample (too few pairs; weights NOT applied). Fit direction: contrast, presence, balance,
alignment up; read.size, layout.fill, layout.size, faith.order down.

## What "both bad" looks like (docs/labels_v1/both_bad_*.png)

Two different causes, roughly half each:

**A. Eval-data artifacts, not engine faults.** The Crello conversion replaces photos with the three brand
assets and some sources already render broken: text truncated in the source ("IENCE / LIGION"), photo
replaced by a white or orange panel (Theater, Sewing), a dark gradient where a product photo was (Shoes).
Judging our output on these is noise. Fix: the labelling sampler must skip sources whose own render fails a
self-check (source text overflow, stand-in panels covering > 40 % of the canvas, missing-asset placeholders).

**B. Genuine generation weaknesses** (the user's point that effort has gone into choosing, not creating):
1. Banners spread content to the extremes (Real Estate 728x90: bottle far left, wordmark far right, 80 %
   empty between). Need a max-gap cap / cohesion: cluster content, justify with bounded gaps.
2. Tiny strips shrink everything evenly into illegibility (Saturday eco talks 728x90, Furniture Expo
   1584x396). Need importance-based degradation: headline + CTA keep size, the rest shrinks first
   (water-filling), and rotated vertical text must be re-measured with its rotated box.
3. Tall sources into skyscrapers leave most of the strip empty with microscopic type (NY Furniture Fair
   160x600). Floors are too low relative to the canvas; a tall strip should stack at readable size.
4. Text half over an image edge (Chandelier 1080x1080, anchor candidates): contrast estimate passes because
   half the box is on white; need worst-region contrast, not 25th percentile, for text straddling an edge.
5. Overlapping texts in anchor candidates at large scale (Citation A4: "PRAY" over "When Life Is Great",
   both candidates). Possible rectifier miss on scaled-up anchor layouts. Reproduce with the design id below.
6. Intentional layered panels (Sparkling night) get re-stacked as a list of pills; layered panel groups
   should be kept as one unit when they overlapped in the source.

## The twelve cases shown (design id, preset)
(see the list printed by the commit's command output; ids are in eval/data/labels.jsonl with decision both_bad)
