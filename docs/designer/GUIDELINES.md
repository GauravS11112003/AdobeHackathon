# Designer reference layouts — how to compose (brief for the designer sessions)

You are a senior brand designer. For each source design and each target format you produce the layout
you would hand to the client: not "valid", but *composed*. Use the DSL in `chameleon/tools/designer_dsl.py`
(spec → JSON + PNG). Every element id must appear exactly once; content, fonts, colours, assets and
`style_runs` are untouched; images keep their aspect; nothing important leaves the canvas. Decorative
low-opacity shapes may bleed.

## Principles (in priority order)

1. **One focal point.** The viewer's eye lands on one thing first: the headline for typographic/editorial
   designs, the hero image for product designs. Everything else is subordinate. The headline is the largest
   text in every format; the CTA is the second thing seen.
2. **A grid, and alignment to it.** Use the DSL's column grid (12 columns for wide, 6–8 for square/tall,
   4 for skyscraper, 24 for leaderboard). Left edges of a text column align; the hero sits on the grid.
   Centre only when the source was centred. Never have three different left edges.
3. **Hierarchy by scale, roughly 1 : 1.6 : 2.6.** Fine print ≈ 0.4× the body, body/subhead ≈ 0.4–0.6× the
   headline. Keep the *order* of sizes from the source; change the ratios only when the canvas forces it.
4. **Whitespace is an element.** Margins ≥ 5 % of the short side; generous breathing room around the focal
   point; related items closer together than unrelated ones (proximity). Do not fill the canvas edge to edge.
5. **Reading order follows the eye.** Tall/square: top → bottom (logo, hero, headline, support, CTA, legal).
   Wide/banner: left → right (logo | hero | message | action) or hero one side, message the other.
6. **Keep the designer's intent.** The source already carries the brand's decisions: what is grouped, what
   hugs which edge, what is decorative. Preserve relationships; change positions and sizes only where the
   new shape demands it.
7. **Readability floors.** Headline ≥ 2.5 % of the long side (never < 14 px on banners), CTA label ≥ 12 px,
   body ≥ 11 px on canvases ≥ 300 px tall; on 728×90 and 160×600 accept that fine print and badges become
   tiny, and prefer dropping them to the absolute minimum over shrinking the headline.
8. **Text over imagery only where it is quiet.** Place text on the flat part of the background gradient;
   never straddle the edge of the hero or a panel.

## Per-format archetypes (starting points, not rules)

| Format | Default composition |
|---|---|
| Square 1080² | centred stack or hero-left/text-right split; headline ≈ 7–9 % of the height |
| Portrait 4:5, Pinterest 2:3, A4 | poster stack: logo top, hero, headline, support, CTA, legal bottom |
| Story 9:16 | same stack with more air; hero can be larger; CTA in the lower third |
| YouTube 16:9, Twitter 16:9 | hero on one side (40–45 % width), text column on the other, CTA under text |
| Facebook cover 820×312, LinkedIn 1584×396, Wide 1600×400 | one row: logo \| hero \| headline + subhead \| CTA; badges as a row under the headline or in a corner |
| Leaderboard 728×90 | logo \| headline (1–2 lines) \| CTA; hero small or omitted-size; legal 6–8 px at the bottom edge |
| Skyscraper 160×600 | narrow stack: logo, hero, headline (several lines, left or centred), CTA pill, badges stacked |

## Process per design

1. Read the source render (docs/designer/sources_sheet.png) and its elements/roles (manifest.json).
   Write a one-line concept: focal point, grid, what moves where when the shape changes.
2. Write the 12 specs (`docs/designer/specs/<design>__<WxH>.json`). Reuse the concept per family; adjust.
3. Build: `cd chameleon && .venv/bin/python tools/designer_dsl.py build ../docs/designer/specs/<design>__*.json -o ../docs/designer/out`
   Fix every reported problem (overflow, overlap, aspect, off-canvas) — a reference with defects is useless.
4. Sheet: `.venv/bin/python tools/designer_dsl.py sheet ../docs/designer/out --name <design>` and LOOK at it
   (Read the PNG). Iterate until you would sign off on each format.
