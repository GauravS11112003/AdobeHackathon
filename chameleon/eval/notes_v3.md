## Observations (hand-written): v2 -> v3

Four rule upgrades borrowed from the rival engines (docs/COMPETITORS.md, "what to borrow" 1-5), all in
`chameleon/engine/`, tests in `tests/test_v3_rules.py` (19 tests) plus updated expectations in
`test_analyze.py`, `test_floorplan.py`, `test_judge.py`, `test_p1_fixes.py`.

1. **No-render contrast estimate** (`engine/contrast.py`, tailsgit). Layers under every text's painted box
   are composited from the JSON and the asset files at a 32x8 grid; the text's ratio is the 25th percentile
   of the WCAG ratios of its colour(s). Validation on 300 random v2 cases (1330 text elements, source and
   output of each, `eval/contrast_check.py`): Pearson 0.969 on log ratios, Spearman 0.973, verdict
   disagreement 3.2 % at 1.3:1, 1.9 % at 3:1, 2.4 % at 4.5:1; the hard-fail drop rule agrees on 97.9 % of
   the 376 headline / CTA elements (21 fails by estimate, 23 by render). The estimate is lower than the
   render-based number 70 % of the time (a 25th percentile against a mean colour). Cost: 1 ms per design
   against 69 ms for a text-less render. The judge now scores every candidate on the estimate and renders
   only the top 3 (`resize.TOP_RENDER`), which halves the runtime.
   The hard fail became *source-relative* (ratio < 3 and < 0.5x the same text's ratio in the source): with
   stand-in assets the old absolute rule flagged white copy that the source itself put on the white canvas.
2. **Units beyond group_id** (`engine/analyze.py`, tailsgit + gk7494): holders (label in a pill, sticker of
   short lines), photo frames, host bars attached to a heading, absorbed decorations, sibling rows. The
   Boynton poster (`5928010895a7a863ddcd8e06`, docs/sanity_v3/boynton_sheet.png) now keeps its underline
   bars under "CONTACT US" / "EACH YEAR", the divider under "IS IN DANGER" and the accent bar on the photo's
   edge in all twelve formats (`test_boynton_bars_stay_under_their_headings_in_every_format` checks the
   gap and the horizontal overlap per bar); the date block "17 / JULY / 1 PM - 6 PM" is one sticker and
   "THE OCEAN" is the headline (v2 took the 134 px "17" for it). Two lessons from the smoke runs: a shape
   holding *several* texts is a card, not a button (texts stayed readable in v2 because they were free;
   as a rigid group they shrank to 2-4 px), so only sticker-sized ones (<= 6 % of the canvas, short lines)
   merge and bigger ones become panels; and bars must be tested against the host element, not the growing
   cluster, or six far-away squares chain onto one headline.
3. **Painted text boxes and canvas-relative floors** (gk7494). Plans and the rectifier work on the glyph
   extent (`TextMeasurer.painted`), attachments keep their offset from it in font units; fonts never go
   below 0.85 % of the long side (legal 0.7x, badges 0.8x), logo / hero / stamps keep 14 / 30 / 8 % of the
   short side, the headline stays the largest text (`resize._keep_headline_largest`). Raising the floors
   exposed designs that only fit at sub-floor sizes (Level 3 on 160x600): v2 "fit" by letting the rectifier
   shrink the legal copy to 5 px; v3 has an explicit rescue mode that lowers secondary / minor floors by 0.45
   before a plan may overflow.
4. **Source-relative penalties and adaptation** (fernando-ace): overlap counts only when > 1.5 pp worse than
   the source pair (per part of a row), bleed the source had is excused, hierarchy keeps >= min(0.82, source
   ratio), a font is below the floor only if it also shrank versus the designer's size; the anchor layout on
   a ratio change >= 1.75 pays 18 points (`ADAPT_PENALTY`, so it wins only when every re-layout has a hard
   defect, which replaces the old "fallback only if all fail" sort trick), and a floor plan on a near-identity
   change pays up to 4 points (`DISRUPT_PENALTY`) so a finished design is not re-arranged for a 0.3-point
   judge preference.

### Measuring like for like
The metric definitions moved with the engine (painted boxes, per-part overlaps, higher floors, the drop
rule), so the published v2 numbers are not comparable with v3 as such. `eval/remeasure.py` re-judged the
v2 winner JSONs under the v3 metrics and scorer (run `v2_remeasured`); the tables below show v2 as
published, v2 re-measured and v3, on the same 6058 cases. The re-measured v2 overlap column is high (26 %) because v2 allowed *any* overlap between a pair
whose boxes touched in the source, and the Crello boxes touch far more often than the glyphs do; under
the "worse than the source pair" rule those are real overlaps (a stacked "mega / SHOES" lockup whose
overlap grew from 66 % to 90 %, a sticker that slid onto its photo), and v3's rectifier removes them
(0.05 % left).

### Before / after (same 6058 cases; v2 as published, v2 re-measured under the v3 rules, v3)

Common cases: **6058** (v2: 6058, v2_remeasured: 6058, v3: 6058)

| metric | v2 | v2_remeasured | v3 |
|---|---:|---:|---:|
| any hard defect (%) | 0.86 | 27.22 | 0.66 |
| any hard defect (n) | 52 | 1649 | 40 |
| text overflow (%) | 0.17 | 0.17 | 0.05 |
| text overflow (n) | 10 | 10 | 3 |
| headline/CTA below floor (%) | 0.59 | 2.72 | 0.56 |
| headline/CTA below floor (n) | 36 | 165 | 34 |
| unwanted overlap (%) | 0.10 | 26.23 | 0.05 |
| unwanted overlap (n) | 6 | 1589 | 3 |
| off canvas (%) | 0.00 | 0.00 | 0.00 |
| off canvas (n) | 0 | 0 | 0 |
| judge contrast fail (%) | 6.78 | 4.46 | 2.24 |
| judge contrast fail (n) | 411 | 270 | 136 |
| anchor fallback wins (%) | 2.94 | 2.94 | 0.71 |
| anchor fallback wins (n) | 178 | 178 | 43 |
| errors (%) | 0.00 | 0.00 | 0.00 |
| errors (n) | 0 | 0 | 0 |
| judge score mean | 5.91 | -737.62 | 51.16 |
| judge score p50 | 83.62 | 78.51 | 82.45 |
| read.size | 0.883 | 0.883 | 0.891 |
| read.lines | 0.958 | 0.935 | 0.936 |
| read.contrast | 0.744 | 0.696 | 0.693 |
| read.presence | 0.858 | 0.884 | 0.864 |
| layout.balance | 0.898 | 0.867 | 0.879 |
| layout.alignment | 0.657 | 0.553 | 0.550 |
| layout.spacing | 0.728 | 0.717 | 0.703 |
| layout.fill | 0.926 | 0.843 | 0.887 |
| layout.margins | 0.880 | 0.920 | 0.929 |
| faith.order | 0.822 | 0.831 | 0.840 |
| faith.anchors | 0.603 | 0.615 | 0.604 |
| faith.hierarchy | 0.991 | 0.988 | 0.985 |
| faith.scale | 0.698 | 0.690 | 0.737 |
| runtime p50 (s) | 0.28 | 0.28 | 0.17 |
| runtime p95 (s) | 0.85 | 0.85 | 0.43 |
| smallest font p05 (px) | 7.0 | 7.0 | 6.0 |
| gt centre error | 0.153 | 0.153 | 0.152 |
| gt reading-order tau | 0.805 | 0.805 | 0.781 |
| gt size rho | 0.801 | 0.801 | 0.784 |
| gt font ratio (median) | 0.983 | 0.983 | 1.000 |

### Defect rate by preset (%)

| preset | n | v2 any | v2_remeasured any | v3 any | v2 below floor | v2_remeasured below floor | v3 below floor | v2 overlap | v2_remeasured overlap | v3 overlap | v2 contrast | v2_remeasured contrast | v3 contrast |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A4 poster | 453 | 0.0 | 25.6 | 0.2 | 0.0 | 1.8 | 0.0 | 0.0 | 24.9 | 0.0 | 5.3 | 3.8 | 2.0 |
| Facebook cover | 453 | 1.3 | 28.7 | 0.2 | 0.2 | 2.9 | 0.0 | 0.4 | 28.5 | 0.2 | 7.5 | 4.4 | 2.4 |
| Instagram portrait | 453 | 0.0 | 30.2 | 0.0 | 0.0 | 0.2 | 0.0 | 0.0 | 30.0 | 0.0 | 4.6 | 3.3 | 2.2 |
| Instagram post | 453 | 0.0 | 28.7 | 0.0 | 0.0 | 0.2 | 0.0 | 0.0 | 28.7 | 0.0 | 4.6 | 3.1 | 2.0 |
| Leaderboard ad | 453 | 2.9 | 27.2 | 2.4 | 2.4 | 6.4 | 2.4 | 0.2 | 24.1 | 0.0 | 9.1 | 7.1 | 3.8 |
| LinkedIn banner | 453 | 0.0 | 24.3 | 0.4 | 0.0 | 4.9 | 0.4 | 0.0 | 23.4 | 0.0 | 6.8 | 5.3 | 2.2 |
| Pinterest pin | 453 | 0.0 | 25.8 | 0.0 | 0.0 | 1.8 | 0.0 | 0.0 | 25.2 | 0.0 | 5.5 | 3.3 | 2.4 |
| Skyscraper ad | 453 | 5.1 | 25.2 | 4.4 | 4.9 | 4.4 | 4.2 | 0.0 | 21.6 | 0.2 | 11.5 | 7.7 | 4.2 |
| Story / Reel | 453 | 0.0 | 23.6 | 0.2 | 0.0 | 2.2 | 0.0 | 0.0 | 22.7 | 0.2 | 5.5 | 4.0 | 2.6 |
| Twitter / X post | 453 | 0.0 | 32.0 | 0.0 | 0.0 | 2.2 | 0.0 | 0.0 | 30.9 | 0.0 | 5.7 | 3.3 | 1.1 |
| Wide web banner | 453 | 0.0 | 23.4 | 0.2 | 0.0 | 4.6 | 0.2 | 0.0 | 22.5 | 0.0 | 6.6 | 4.6 | 1.8 |
| YouTube thumbnail | 453 | 0.0 | 31.3 | 0.0 | 0.0 | 1.5 | 0.0 | 0.0 | 31.3 | 0.0 | 6.0 | 3.3 | 1.1 |
| gt (designer siblings) | 622 | 1.6 | 27.7 | 0.5 | 0.3 | 2.4 | 0.2 | 0.5 | 26.8 | 0.0 | 8.7 | 4.7 | 1.6 |


Reading of the table: every hard-defect metric improved (any defect 52 -> 40 cases, overflow 10 -> 3,
below floor 36 -> 34, overlap 6 -> 3 under the stricter rule, 1589 under that rule for the v2 outputs),
the judge's contrast fails fell 411 -> 136 (drop rule + the estimate seeing panels and assets), the anchor
fallback wins 178 -> 43 (it now competes with a penalty instead of being excluded), runtime halved (p50
0.28 -> 0.17 s, p95 0.85 -> 0.43 s: one render for the top 3 instead of one per candidate). Skyscraper
5.1 % -> 4.4 %, Leaderboard 2.9 % -> 2.4 %, Facebook cover 1.3 % -> 0.2 %, designer siblings 1.6 % -> 0.5 %.

What did not improve, against the re-measured v2 (same definitions): faith.hierarchy 0.988 -> 0.985,
faith.anchors 0.615 -> 0.604, read.presence 0.884 -> 0.864, layout.spacing 0.717 -> 0.703, and against
the designers' own versions reading-order tau 0.805 -> 0.781 and size rho 0.801 -> 0.784 (61 sibling
cases worse, 34 better; the largest drops are 2-3 matched texts where tau flips sign). The driver is the
anchor path winning more sibling cases (140 -> 186: `SMALL_CHANGE_MAX` 1.6 -> 1.75 and the disruption
penalty near identity), i.e. v3 keeps the designer's *source* arrangement where the designer's sibling
re-arranged. That is a deliberate trade (identity resizes stay the identity; fallback wins and defects
fell) and the deltas are within 0.02; it is flagged here rather than hidden. `read.contrast`,
`layout.alignment` and `layout.fill` moved between v2-published and v2-remeasured because their
definitions changed (25th-percentile estimate; visible boxes), not the layouts.

### Remaining defects (v3 worst cases, docs/eval_v3)
- 21 headline / 13 CTA fonts below the floor, almost all 160x600 and 728x90: an unbreakable single
  word (a URL in a pill: "beautyconversations.online", "WWW.WAUGH.STORE") wider than the canvas at
  the floor font; v2 labelled the same texts BODY (no floor), v3 labels the pill CTA. Nothing fits them.
- 144 contrast drops (not counted as defects, see caveat): white copy that sat on the photo and lands on
  the white canvas in a banner / tall plan. The panel system keeps text on *shapes*; text on a photo
  has no zone to follow it. Candidate for the next step: a "text stays on the hero" placement or a
  colour-aware check in the plans.
- 9 cases clean in v2 and defective in v3 (5 of them the URL pills above); 1618 the other way round under
  the stricter overlap rule.
