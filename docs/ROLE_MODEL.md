# Learned role / hierarchy classifier (workstream S4)

A small gradient-boosted classifier that names every element of a source design
(headline, subhead, body, cta, badge, fine_print, logo, hero, image, background,
decorative, shape) from id-free signals, trained on real Crello templates with
DesignAsCode's distilled layer themes as labels. It is a second opinion next to the
hand-written rules in `engine/analyze.py`: off by default (`CHAMELEON_ROLE_MODEL=0`),
merged by confidence when on, and usable as the third vote next to the VLM (S1).

Files (all under `chameleon/`):

| file | role |
|---|---|
| `engine/role_features.py` | 123 per-element features (type, geometry, z, grouping, neighbours, font rank, text stats, colour/contrast); pure Python, ~2 ms per design |
| `engine/role_model.py` | numpy-only inference over the exported trees: `predict(source) -> {id: (role, confidence)}`, `predict_proba`, `text_hierarchy`, `enabled()` |
| `engine/role_merge.py` | `merged_roles(source, rule_roles)` / `apply_to_analysis(analysis, source)`: rules + model by confidence, flag-gated |
| `engine/models/roles.npz` | the shipped model (complete depth-6 trees; see size below) |
| `tools/role_labels.py` | DesignAsCode theme → role mapping and per-design resolution |
| `tools/build_role_dataset.py` | Crello train shards + DesignAsCode → `eval/data/roles/dataset.npz` |
| `tools/train_role_model.py` | grouped CV, export, tiny test fixture, `eval/data/roles/cv_report.json` |
| `tools/eval_role_model.py` | samples with ids stripped, Boynton, agreement with the rules on the 450 eval designs |
| `tools/role_model_report.py` | prints the markdown tables below from the CV report |
| `tests/test_role_model.py` | 27 offline tests (features, numpy path vs scikit-learn on a tiny fixture, merge policy, shipped model on the samples) |

Nothing in `engine/analyze.py`, `resize.py` or the other engine modules was changed.
`numpy` is the only runtime dependency and it is already in the image (skia-python
requires it); if it or the model file is missing, `predict` returns `{}` and the
rules stand.

## 1. Labels

### 1.1 Source

[DesignAsCode training data](https://huggingface.co/datasets/Tony1109/DesignAsCode-training-data)
(MIT, 19,479 designs, 151 MB JSONL). Every row is one Crello **train** template; its
`grouping` field is a GPT-4o/o3-distilled list of groups, each with the Crello layer
indices it contains and a free-text *theme* ("main title text", "call-to-action
button", "decorative lines", "contact information", "background image", …). There are
46,017 distinct themes over 206,217 layers; the 20 most common cover a third of them.
The ids are Crello ids and the layer indices are Crello layer order, which is exactly
the `el_NN` id our eval converter gives each element, so the labels join onto the
converted designs without any pixel data. All 19,479 ids are in Crello's train split
(none in validation/test, so none of the 450 eval designs or Boynton is labelled).

Crello's train metadata (31 shards, ~0.35 MB of non-pixel columns each, read with
range requests like the eval harness does) is cached in `eval/data/raw/train-*.parquet`.

### 1.2 Theme → role mapping (`tools/role_labels.py`)

Ordered keyword rules per converted element type. The first matching rule wins; the
whole group shares the theme, so a button's background shape and its label both see
"call-to-action button".

| our role | text themes | image themes | shape themes |
|---|---|---|---|
| cta | call-to-action, cta, button, swipe up, shop now, subscribe, donate, register, sign up, book/order/buy now, learn more, download | same, only when the group also has a text | same, only when the group also has a text |
| fine_print | attribution, author, signature, credit, contact, website, url, link, address, phone, e-mail, footer, copyright, legal, disclaimer, terms, social, handle, hashtag, note | – | – |
| headline | title, headline, heading, header text, main text/message, quote, announcement, promotional text, main discount/offer/number/price, large number, recipient name, certificate, slogan, key message, statement, lettering, event name, brand name, greeting … | – | – |
| subhead | subtitle, subheading, subheader, subheadline, tagline, secondary text, supporting text, subtext, caption, intro text, kicker, eyebrow, descriptor (checked **before** headline: "subtitle" contains "title") | – | – |
| badge (`chip?`) | date, time, price, discount, percent, sale, offer, badge, sticker, tag, label, number, year, day, step, ribbon, highlight, promo, limited, new, free, coupon, code, rating, award, stamp, seal, category, location, venue, season, edition; also logo/brand-name *text* | badge/tag/… when the group has a text | badge/sticker/tag/ribbon/label/… when the group has a text and the theme is not background-like |
| logo | – | logo, brand, branding, emblem, monogram, wordmark | – (a single-colour SVG logo is a shape in our schema; it stays `shape`) |
| background (`bg?`) | – | background, overlay, backdrop, base, canvas, full bleed, wash, gradient, panel, card, container, box, block, section, area, band, bar, strip, banner, sidebar, column, zone, plate, backing | same |
| decorative | – | decorat*, accent, divider, separator, line(s), underline, dot(s), pattern, texture, ornament, embellish, flourish, sparkle, confetti, star, heart, arrow, shadow, swirl, wave, blob, doodle, frame, border, stroke, outline, scatter, floating, abstract, geometric, circle, triangle, icon, bullet, glow, splash, brush, leaf, floral, stripe, dash, rule, cross … | same |
| hero / image (`hero?`) | – | everything else (main/central image, photo, product, illustration, portrait, scene, graphic, …) | – |
| body | everything else (event details, description, text content, information, list, menu, …) | – | – |
| shape | – | – | everything else (highlight bars, panels behind text, colour blocks) |

Per-design resolution after the keyword pass:

* `bg?` → `background` when the element covers ≥ 50 % of the canvas, else `shape`
  (shapes) or `hero?` (images).
* `hero?` → the largest such image with ≥ 3 % of the canvas is `hero`, the rest `image`.
* `chip?` → `badge` when the content is ≤ 40 characters and ≤ 6 words, else `body`.
* Exactly one `headline`: among headline-themed texts the largest font keeps it; the
  others become `subhead` (≥ 35 % of the headline size, a kicker or second line),
  `badge` (short) or `body`. When no theme is title-like (plain quote posters), the
  largest `subhead`/`body` text is promoted.
* A `subhead` under 35 % of the headline size that is long is `body`.
* Text hierarchy rank: sort texts by (tier, −font size) with tier headline 0,
  subhead 1, cta 2, badge/body 3, fine_print 4.

Coverage: 91 % of the 206k labelled layers match at least one keyword; the 9 % that
match none are almost all plain copy ("event details", "text content",
"description") and fall to the correct default (`body` / `shape`). Layers without any
DesignAsCode group (1.2 %) are left unlabelled and skipped.

Known label noise (accepted): split headlines ("CAREER" twice, "THAT'S / WHY") give
one headline + subheads; decorative banner images sometimes become `hero`; "header
text" is ambiguous between the top label and the title (resolved by font size).

### 1.3 Dataset

Crello train: 19,479 templates in the 31 shards, 19,219 converted (204 without text, 56 with more
than 40 elements skipped), 205,515 elements of which 2,277 have no DesignAsCode theme and are left
unlabelled. Two augmented copies of every design go into training: one with the eval converter's
normalised text boxes and one with Crello's tight boxes (the hidden tasks' box convention is
unknown, the model must not lean on box height); in half of the copies button-like shape + label
pairs get a synthetic `group_id` (Crello has none, the samples do); single-colour SVG logos, which
the converter turns into shapes, are re-typed as `contain` images because that is how the hidden
tasks ship logos. 406,476 labelled rows in total. Label counts (per original design, before
augmentation):

| role | n |
|---|---|
| headline | 18,264 |
| subhead | 11,743 |
| body | 21,353 |
| cta | 6,196 |
| badge | 20,709 |
| fine_print | 9,028 |
| logo | 2,047 |
| hero | 8,647 |
| image | 6,676 |
| background | 23,196 |
| decorative | 43,573 |
| shape | 31,806 |

`eval/data/roles/dataset.npz` + `meta.json` (gitignored, rebuilt in ~4 min).

## 2. Features (`engine/role_features.py`)

123 numbers per element, all from id-free fields:

* identity: type one-hot, shape type, image fit
* design context: canvas log-aspect and log-area, element / text / image / shape /
  group counts
* geometry: area and visible share, w/h share, log aspect, centre, margins to each
  edge, fraction inside the canvas, spans-x/-y, distance to centre, opacity, rotation,
  z rank (and topmost / bottommost)
* grouping: `group_id` size and member types, group area, text share of the group
* neighbourhood: overlaps (all / with text), elements stacked above, the nearest
  flat shape *behind* the element (its area and the area ratio = "sits in a pill"),
  behind an image, texts the element *backs* (count, area ratio, characters, font
  position of the best one), gaps to the nearest text / image / shape, image area
  rank and ratio to the largest image, reading-order position
* text: font px, font relative to √canvas area, ratio to the largest font, font rank
  (absolute and normalised), ratio to the next / previous size, same-size count,
  ratio to the median, bold, italic, letter spacing / font, line height, alignment,
  style runs, characters / words / lines / longest line, uppercase and digit ratios,
  date / time / url / e-mail / phone / price patterns, verb at the start, ends with
  "!" / ".", comma, average word length, dots-only (leader lines), estimated line
  capacity and line count, box lines, ink share, colour luminance / alpha /
  saturation, contrast against the dominant background and against the shape behind,
  colour shared with other texts, size ratio to the text above / below, first / last
  text, vertical rank among texts, biggest text, text area rank
* shape / image: fill luminance / saturation, corner radius ratio, thinness, canvas
  cover, same-fill count

Crello has no `group_id`, so the grouping features are constant in training and the
trees never split on them; on grouped inputs (the samples) they are simply ignored,
while the "behind shape" / "backs text" features capture button structure either way.

## 3. Model and export

scikit-learn `HistGradientBoostingClassifier` (dev dependency only), 12 classes,
one-vs-rest trees per iteration. The export writes every tree as a *complete* depth-6
binary tree (pads carry the parent leaf's value, threshold +inf = always left), so
`engine/role_model.py` evaluates all trees for all elements with six numpy gathers:
no Python loop over trees, no threads, bit-for-bit deterministic, < 3 ms per design.
The export is checked against `predict_proba` on 2,000 training rows at export time
(max |Δp| ≈ 2e-8) and in the tests against a 3-iteration fixture.

Parameters: 120 iterations, learning rate 0.08, max depth 6, ≤ 48 leaves, ≥ 20 samples per
leaf, L2 = 1.0, fixed seed; sample weights logo ×4, cta ×2, hero ×1.5, subhead ×1.3 (the rare
roles the layouts care about most). Fit on everything: 57.3 s.
`engine/models/roles.npz`: **0.39 MB** (1,440 trees × 63 nodes, compressed npz).
Inference: 2.78 ms for the Level 3 sample (17 elements), 1.5 ms mean over the 450 eval
designs, measured on the M-series laptop; export vs scikit-learn max |Δp| = 2.1e-08.

## 4. Results

Grouped by template title so that the same design at several sizes never straddles train and
test. "Per design" asks the question the layouts ask: is the element with the highest P(role) the
labelled one? Element-level numbers are depressed by label noise between neighbouring text roles
(subhead / body / badge are often interchangeable in the themes) and between decorative and
shape; the design-level numbers are the ones that matter.

#### 5-fold grouped cross-validation (groups = template title)

Element accuracy 0.707; text 0.669, image 0.755, shape 0.723.

| role | precision | recall | F1 | support |
|---|---|---|---|---|
| headline | 0.837 | 0.856 | 0.846 | 36528 |
| subhead | 0.518 | 0.682 | 0.589 | 23486 |
| body | 0.676 | 0.559 | 0.612 | 42706 |
| cta | 0.538 | 0.472 | 0.502 | 12392 |
| badge | 0.614 | 0.53 | 0.569 | 41418 |
| fine_print | 0.714 | 0.675 | 0.694 | 18056 |
| logo | 0.551 | 0.796 | 0.651 | 4094 |
| hero | 0.751 | 0.851 | 0.798 | 17294 |
| image | 0.654 | 0.596 | 0.624 | 13352 |
| background | 0.921 | 0.963 | 0.942 | 46392 |
| decorative | 0.692 | 0.753 | 0.721 | 87146 |
| shape | 0.688 | 0.63 | 0.658 | 63612 |

Per design (is the top-scoring element the labelled one?):

| role | accuracy | designs |
|---|---|---|
| headline | 0.873 | 36528 |
| cta | 0.897 | 6086 |
| logo | 0.975 | 3090 |
| hero | 0.922 | 17294 |

Text hierarchy: mean Spearman between the model's rank (expected tier, then font size) and the label rank = 0.736 over 26798 designs with >= 3 texts.

#### Held-out 20 % of designs (fold 1 of the grouped split)

Element accuracy 0.707 (3934 designs, 81298 elements).

| role | precision | recall | F1 | support |
|---|---|---|---|---|
| headline | 0.835 | 0.854 | 0.845 | 7414 |
| subhead | 0.525 | 0.683 | 0.593 | 4804 |
| body | 0.682 | 0.567 | 0.619 | 8162 |
| cta | 0.532 | 0.497 | 0.514 | 2514 |
| badge | 0.622 | 0.516 | 0.564 | 8502 |
| fine_print | 0.708 | 0.667 | 0.687 | 3316 |
| logo | 0.504 | 0.817 | 0.624 | 810 |
| hero | 0.751 | 0.858 | 0.801 | 3672 |
| image | 0.628 | 0.588 | 0.607 | 2856 |
| background | 0.921 | 0.96 | 0.94 | 9730 |
| decorative | 0.698 | 0.74 | 0.718 | 17484 |
| shape | 0.677 | 0.636 | 0.656 | 12034 |

Per design (is the top-scoring element the labelled one?):

| role | accuracy | designs |
|---|---|---|
| headline | 0.872 | 7414 |
| cta | 0.915 | 1218 |
| logo | 0.974 | 612 |
| hero | 0.914 | 3672 |

Text hierarchy: mean Spearman between the model's rank (expected tier, then font size) and the label rank = 0.731 over 5226 designs with >= 3 texts.

Confusion (rows = label, columns = prediction):

| label \ pred | headl | subhe | body | cta | badge | fine_ | logo | hero | image | backg | decor | shape |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| headline | 31254 | 2138 | 1012 | 159 | 1856 | 109 | 0 | 0 | 0 | 0 | 0 | 0 |
| subhead | 826 | 16011 | 2750 | 528 | 2903 | 468 | 0 | 0 | 0 | 0 | 0 | 0 |
| body | 1499 | 7476 | 23892 | 958 | 6756 | 2125 | 0 | 0 | 0 | 0 | 0 | 0 |
| cta | 685 | 793 | 803 | 5843 | 563 | 781 | 58 | 57 | 89 | 0 | 1084 | 1636 |
| badge | 2678 | 3569 | 4608 | 727 | 21971 | 1399 | 186 | 195 | 195 | 16 | 2562 | 3312 |
| fine_print | 409 | 917 | 2257 | 918 | 1372 | 12183 | 0 | 0 | 0 | 0 | 0 | 0 |
| logo | 0 | 0 | 0 | 12 | 4 | 0 | 3259 | 207 | 236 | 6 | 370 | 0 |
| hero | 0 | 0 | 0 | 9 | 6 | 0 | 243 | 14724 | 713 | 1432 | 167 | 0 |
| image | 0 | 0 | 0 | 63 | 18 | 0 | 885 | 1177 | 7955 | 58 | 3196 | 0 |
| background | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1435 | 7 | 44670 | 258 | 22 |
| decorative | 0 | 0 | 0 | 537 | 80 | 0 | 1286 | 1798 | 2965 | 1643 | 65583 | 13254 |
| shape | 0 | 0 | 0 | 1113 | 243 | 0 | 0 | 0 | 0 | 667 | 21486 | 40103 |

Top features (permutation importance, accuracy drop on 5k elements):

| feature | drop |
|---|---|
| covers_canvas | 0.1334 |
| is_text | 0.1232 |
| visible_share | 0.119 |
| is_shape | 0.0896 |
| is_image | 0.034 |
| image_area_ratio | 0.0282 |
| font_rank | 0.0282 |
| font_ratio_max | 0.022 |
| n_texts | 0.0172 |
| image_area_rank | 0.0158 |
| z_rank | 0.0144 |
| behind_shape_ratio | 0.0132 |
| dist_text | 0.013 |
| font_rel | 0.0128 |
| text_area_rank | 0.0122 |
| n_images | 0.012 |
| log_aspect | 0.0118 |
| ink_share | 0.0116 |
| canvas_log_area | 0.0114 |
| top | 0.0092 |


Reading the confusion matrix: headline is confused with subhead/badge (split headlines, big date
numbers), cta with fine_print/body (free-text calls to action without a button), logo with
decorative/image (small corner graphics), hero with background (half-canvas photos). No text is
ever predicted as an image role or vice versa, by construction of the family restriction in
`predict`.

## 5. The three samples with ids stripped, and Boynton

`tools/eval_role_model.py` strips the ids (e00, e01, … and g0, g1 for groups) before calling the
model, so nothing below comes from the descriptive sample ids. `rule` is the current
`engine/analyze.py`, `model` the classifier's best role in the element's type family with its
probability, `merged` the result of `role_merge.merged_roles(..., force=True)`; `←` marks a change.

#### chameleon_sample_level1_warmup (ids stripped)

| id | type | font | text | rule | model | p | merged | flag |
|---|---|---|---|---|---|---|---|---|
| bg | image |  |  | background | background | 0.98 | background |  |
| logo | image |  |  | logo | logo | 0.87 | logo |  |
| headline | text | 60 | Chase the Light | headline | headline | 0.93 | headline |  |
| cta | text | 30 | Shop the Summer Line | cta | subhead | 0.44 | cta |  |

#### chameleon_sample_level2_core (ids stripped)

| id | type | font | text | rule | model | p | merged | flag |
|---|---|---|---|---|---|---|---|---|
| bg | image |  |  | background | background | 0.98 | background |  |
| deco_circle_1 | shape |  |  | decorative | shape | 0.61 | decorative |  |
| deco_circle_2 | shape |  |  | decorative | shape | 0.65 | decorative |  |
| logo | image |  |  | logo | logo | 0.56 | logo |  |
| product | image |  |  | hero | hero | 0.81 | hero |  |
| headline | text | 56 | Chase the Light | headline | headline | 0.84 | headline |  |
| subhead | text | 24 | Botanical sparkling infusion… | subhead | body | 0.50 | subhead |  |
| badge_bg | shape |  |  | badge | shape | 0.80 | badge |  |
| badge_label | text | 18 | NEW FLAVOR | badge | badge | 0.75 | badge |  |
| cta_bg | shape |  |  | cta | cta | 0.50 | cta |  |
| cta_label | text | 22 | Shop the Summer Line | cta | cta | 0.85 | cta |  |

#### chameleon_sample_level3_advanced (ids stripped)

| id | type | font | text | rule | model | p | merged | flag |
|---|---|---|---|---|---|---|---|---|
| bg | image |  |  | background | background | 0.99 | background |  |
| logo | image |  |  | logo | logo | 0.88 | logo |  |
| product | image |  |  | hero | hero | 0.74 | hero |  |
| headline | text | 40 | Introducing the All-New Limi… | headline | headline | 0.89 | headline |  |
| subhead | text | 22 | Small-batch botanical infusi… | subhead | body | 0.63 | body | ← |
| badge1_bg | shape |  |  | badge | shape | 0.60 | badge |  |
| badge1_label | text | 15 | LIMITED EDITION | badge | body | 0.58 | badge |  |
| badge2_bg | shape |  |  | badge | shape | 0.82 | badge |  |
| badge2_label | text | 15 | AWARD WINNING 2026 | badge | body | 0.64 | badge |  |
| badge3_bg | shape |  |  | badge | shape | 0.54 | badge |  |
| badge3_label | text | 15 | SMALL BATCH | badge | body | 0.46 | badge |  |
| cta_bg | shape |  |  | cta | shape | 0.66 | cta |  |
| cta_label | text | 22 | Shop the Summer Line | cta | cta | 0.72 | cta |  |
| ribbon_bg | shape |  |  | badge | shape | 0.84 | badge |  |
| ribbon_label | text | 20 | SUNSET SALE | badge | body | 0.34 | badge |  |
| holiday_watermark | image |  |  | image | logo | 0.58 | image |  |
| legal_text | text | 12 | Please drink responsibly. Bo… | fine_print | body | 0.59 | fine_print |  |

#### 5928010895a7a863ddcd8e06 — Boynton conference the ocean is in danger (1190x1683)

| id | type | font | text | rule | model | p | merged | flag |
|---|---|---|---|---|---|---|---|---|
| el_00 | image |  |  | hero | hero | 0.99 | hero |  |
| el_01 | shape |  |  | cta | shape | 0.44 | cta |  |
| el_02 | shape |  |  | body | shape | 0.44 | body |  |
| el_03 | shape |  |  | hero | decorative | 0.50 | hero |  |
| el_04 | shape |  |  | badge | shape | 0.55 | badge |  |
| el_05 | shape |  |  | badge | shape | 0.87 | badge |  |
| el_06 | text | 14.13 | ............................… | fine_print | fine_print | 0.62 | fine_print |  |
| el_07 | text | 14.13 | ............................… | fine_print | fine_print | 0.47 | fine_print |  |
| el_08 | shape |  |  | subhead | decorative | 0.57 | subhead |  |
| el_09 | text | 27.3 | Over 1,000,000 seabirds are … | fine_print | body | 0.96 | body | ← |
| el_10 | text | 28.5 | EACH YEAR | cta | body | 0.55 | cta |  |
| el_11 | text | 28.5 | Learn details info@conferenc… | body | fine_print | 0.73 | fine_print | ← |
| el_12 | text | 28.5 | Book your place guests@confe… | body | fine_print | 0.72 | fine_print | ← |
| el_13 | text | 28.5 | Become a speaker speak@confe… | body | fine_print | 0.82 | fine_print | ← |
| el_14 | text | 28.5 | CONTACT US | body | body | 0.43 | body |  |
| el_15 | text | 40.09 | IS IN DANGER | subhead | subhead | 0.57 | subhead |  |
| el_16 | text | 93.17 | THE OCEAN | headline | headline | 0.45 | headline |  |
| el_17 | text | 24.67 | 1 PM - 6 PM | badge | badge | 0.86 | badge |  |
| el_18 | text | 62.99 | JULY | badge | badge | 0.80 | badge |  |
| el_19 | text | 133.89 | 17 | badge | badge | 0.93 | badge |  |
| el_20 | text | 33.09 | SAVE THE OCEAN! | badge | cta | 0.30 | badge |  |
| el_21 | text | 33.77 | CONFERENCE | body | badge | 0.44 | body |  |
| el_22 | text | 39.52 | BOYNTON | body | badge | 0.57 | badge | ← |


**Boynton (eval design 5928010895a7a863ddcd8e06, 1190×1683 poster, 16 texts).** The model calls
**"THE OCEAN" (el_16, 93 px) the headline** (highest P(headline) of all texts, 0.45 as its own best
role), with "IS IN DANGER" (el_15) a subhead and the much larger "17" (134 px) and "JULY" (63 px)
date figures as badges (0.93 / 0.80), i.e. it does not fall for the biggest font. It also corrects the
rules on the body of the poster: the 27 px paragraph "Over 1,000,000 seabirds…" is body copy, not fine
print (0.96), the three e-mail contact lines are fine print (0.72–0.82), and "BOYNTON" is a label
(badge 0.57). The rules in the current analyzer already pick "THE OCEAN" as the headline, so the
merged roles agree there; the row-by-row table is above.

**Agreement with the rules on the 450 eval designs** (text and image elements; there are no labels,
so a disagreement is not an error): the model's top P(headline) text is the rule headline in
414/450 designs (0.92); background 0.98, hero 0.71, badge 0.66, logo 0.34 (the converter's
stand-in logo asset is any wide short SVG), cta 0.20 (the rules' free-text CTA fires on bold short
lines the model reads as subhead / badge). With the merge forced on, at least one role changes in
266/450 designs, mostly body ↔ subhead / badge / fine_print.

Most common disagreements:

| rule → model | n |
|---|---|
| body → subhead | 194 |
| body → badge | 165 |
| fine_print → body | 100 |
| body → fine_print | 100 |
| subhead → body | 66 |
| fine_print → badge | 61 |
| subhead → fine_print | 52 |
| hero → background | 51 |
| subhead → badge | 42 |
| fine_print → subhead | 33 |
| decorative → hero | 32 |
| headline → badge | 31 |
| badge → body | 30 |
| cta → fine_print | 23 |
| body → headline | 21 |


## 6. Merge policy (`engine/role_merge.py`)

"Rules are the floor; the model votes on what the rules guess."

* `background`, `panel`, `decorative` are the rules' geometric facts: never changed,
  never assigned by the model. Shapes are never changed either (their rule roles now
  come from the text they hold).
* A free text / image is re-labelled only when the model's best role in the element's
  type family has probability ≥ 0.55 **and** beats the rule role's probability by
  ≥ 0.25. A text never becomes a logo, an image never a headline.
* Groups and analyzer units (holder / host units, passed by `apply_to_analysis`) vote
  with their text members and move as one; a shape + label unit the rules call
  `badge`/`cta` can only switch between those two.
* Afterwards: exactly one headline among free texts (highest P(headline); a displaced
  headline becomes subhead), at most one hero and one logo among free images, at most
  one CTA (free text or unit).
* `CHAMELEON_ROLE_MODEL=0` (default): `merged_roles` returns the rule roles unchanged
  and `apply_to_analysis` is a no-op.

Wiring (not applied, so the engine's output is unchanged for now; one line in
`engine/resize.py` after `analysis = analyze(source)`):

```python
from engine.role_merge import apply_to_analysis
apply_to_analysis(analysis, source)          # no-op unless CHAMELEON_ROLE_MODEL=1
```

`role_merge.summary(source, rule_roles)` returns the per-element rule / model /
merged view for the playground.

## 7. How to retrain

```bash
cd chameleon
.venv/bin/pip install scikit-learn                     # dev only
.venv/bin/python -c "from eval.crello_convert import fetch_shard; [fetch_shard('train', i) for i in range(31)]"
huggingface-cli download Tony1109/DesignAsCode-training-data --repo-type dataset --local-dir /tmp/dac
.venv/bin/python tools/build_role_dataset.py --dac /tmp/dac/dataset.jsonl
.venv/bin/python tools/train_role_model.py             # CV + export + fixtures
.venv/bin/python tools/eval_role_model.py              # samples, Boynton, rule agreement
.venv/bin/python tools/role_model_report.py            # tables for this file
.venv/bin/python -m pytest tests/test_role_model.py -q
```

## 8. Limits and next steps

* The labels are GPT-distilled themes, not human role labels; neighbouring text roles are noisy
  (≈ 0.6 F1 for subhead / body / badge) while headline (0.85 F1, 0.87 per design), logo (0.97 per
  design), hero (0.92) and CTA (0.90–0.92) are solid. Treat probabilities below ~0.6 as "don't know".
* Free-text CTAs without a button are the weak spot (Level 1's "Shop the Summer Line" gets
  subhead 0.44); the merge keeps the rule there. A few hundred human labels on the eval designs
  (the eval browser could collect them) would fix the calibration of exactly these cases.
* Logos are learned from re-typed SVG marks and the sample lockup; a photo-like logo would score as
  image / hero. The training logo class is still small (2 k).
* Shapes and the structural roles are never changed by the merge; the model's shape / decorative
  split (0.66 / 0.72 F1) is informative but not used.
* `text_hierarchy` is a ranking by expected tier then font size (Spearman 0.73 against the label
  rank); a pairwise ranker trained on the same data would be the next step if the layouts start
  consuming the rank directly.
* Not wired into `resize.py` (one line, §6). When S1's VLM roles land, `merged_roles(..., probs=...)`
  can take the VLM's distribution the same way, or the three votes can be averaged before the merge.
* Retraining needs the 31 Crello train shards (≈ 1 h to fetch at today's rate) and the 151 MB
  DesignAsCode file; everything else is ~5 min.
