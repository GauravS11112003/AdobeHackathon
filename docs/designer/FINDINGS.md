# Designer references vs the engine (v5) — findings, 2026-10-24

240 hand-composed layouts (20 designs × 12 formats) in `docs/designer/out/`, sheets `<name>__SHEET.png`,
side-by-side with the engine in `docs/designer/compare/<name>__COMPARE.png`, numbers in
`compare/results.jsonl` and `compare/SUMMARY.md`.

## 1. Our scorer rejects designer work

68 of the 240 references trip at least one of our **hard fails**; four designs fail in all 12 formats.
73 of the 88 failures are "collides with": text deliberately layered over the hero or a panel (the skincare
"30 % OFF" lockup over the bottle, the Party Dresses headline straddling the photo edge, the StayAtHome
figures in front of the wall panels). The brief says intentional layering is fine; our rule says it is a
defect. Also: 5 off-canvas (photos/panels bleeding on purpose), 3 CTA-below-floor on 160×600 (designer
chose 7 px for a secondary CTA), 5 text overflow (box-based measurement vs ink).

Consequence: **the engine cannot produce these layouts even if it generated them** — the judge would throw
them away. Fixing the scorer comes before fixing the generator.

Soft score with hard fails removed: designer 86.0 vs engine 87.2, designer higher in only 74/240. The soft
score does not recognise composition either: by eye the designer wins most wide/banner formats and every
editorial case.

## 2. Where the engine actually differs (by eye, sheets)

- **Editorial structure is thrown away.** Charity Night: the designer keeps header / red-panel-plus-photo band /
  footer in every format; the engine recomposes it as a product ad (giant red panel, misplaced copy on
  1080×1920, lost band on 1600×900). Same for Furniture Expo and the quote posters. The source's
  composition is the prior; the engine's templates ignore it on big ratio changes.
- **Panels and photos bleed.** Designers run image bands and colour panels to the canvas edge; our
  `layout.margins` term (designer 0.59 vs engine 0.93) punishes exactly that. Margins should apply to text,
  not to full-bleed blocks.
- **Lockups stay lockups.** Designers keep rules/underlines/figures attached and keep layered groups
  (text over panel, text over hero) as one unit. Engine v5 units help but rows of shapes + text still split.
- **Size is NOT the gap any more.** Headline px and hull coverage are within a few percent of the references
  after v4/v5. Composition is.

## 3. What this unlocks

1. **Scorer fixes (first):** allow text over an image/panel when the source layered the same text over an
   image/panel (role-level, not pair-level); never count text fully inside its hosting panel as a collision;
   margins only for text and small units; off-canvas allowed for full-bleed images/panels that bled in the
   source.
2. **240 automatic preference pairs** (designer > engine for the same case) for scorer calibration, on top of
   the human labels. Plus a *designer-agreement* metric (position/size/order similarity to the reference)
   as an eval column, like the Crello `gt_*` metrics.
3. **A preserve-structure candidate family:** read the source's bands (header / band / footer, or column
   split), keep them, and re-proportion per family. The references show this is what a designer does for
   editorial sources. Templates remain for product ads and extreme strips.
4. **The references as regression targets:** the engine should get within a tolerance of the reference on
   the 20 designs × 12 formats without being tuned to them (the rules changed must be general).
