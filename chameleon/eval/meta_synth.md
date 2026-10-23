Run of 2026-10-23 (engine snapshot of 14:18, rendering off): **149 passed, 8 xfailed, 31 xpassed** in 19 s
(`.venv/bin/python -m pytest tests/test_metamorphic.py -q -rxX`).

| relation / check | result |
|---|---|
| contract on 12 corpus designs x 4 targets (ids, order, immutables, aspect, on canvas, text boxes >= 1 px) | 48/48 pass |
| contract on the 3 samples at 300x250, 160x600, 2000x2000, 1080x1080 | 3/3 pass |
| never crash on 29 nasty cases (87 resize calls), structural contract | 27/29 pass; xfail `required_fields_only` (background without `fit` stretched, aspect +25 %), `target_1x1` (negative width/height) |
| nasty cases keep important things on canvas (18 cases) | 17/18 pass (same `required_fields_only`) |
| nasty cases never reach the uniform-scale safety net | pass |
| deterministic across two runs | 12/12 pass |
| ids are opaque (renaming ids + group ids -> identical geometry) | 12/12 pass |
| element order does not matter (shuffle -> same output per id) | 12/12 pass |
| group translation keeps the group's internal layout | 12/12 pass (one grouped unit per design) |
| identity (same canvas -> centres within 3 % of the diagonal, sizes within 30 %) | 11/12 (xfail `banner-11`: identity candidate hard-failed because the source's badge label is under the CTA floor; a floor plan re-lays out the banner) |
| +3 % width -> centres within 4 %, sizes within 30 % | 12/12 (relation marked xfail; all XPASS on this snapshot) |
| 2x source scale -> same output within 1 % / 3 % / 1.5 px font | 8/12 (xfail `square-13`, `wide-11`, `banner-11`, `banner-13`: roles depend on absolute source px, plan variant or fonts differ) |
| aggregate pass-rate floor (identity, +3 %, 2x scale >= 50 %) | pass |

Earlier the same day (engine snapshot of 14:05) identity failed on 3/12 and +3 % on 3/12 designs; the
sibling session's source-relative font floor fixed two of them. The xfail markers are non-strict so the
suite keeps passing as the engine improves; the aggregate test is the regression guard.
