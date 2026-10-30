# Engine v11: the five roadmap implementations (2026-10-29)

The five ideas from `docs/NEXT_STEPS.md`, each behind its own switch in `chameleon/engine/flags.py`
(`CHAMELEON_V11=0` restores v10 byte for byte; `CHAMELEON_V11_<PIECE>=0|1` toggles one piece). Code details are in
`CLAUDE.md` ("v11").

| Piece | What it does | Default |
|---|---|---|
| COMPOSE | Designer compositions as floor-plan variants. Wide: `bleed` (the hero flush with its edge at full height) and `header` (the headline across the top, the hero beside the rest). Banner: `bookend` (logo and CTA at the two ends), `twotier` (one-line headline above a row of copy, chips and CTA) and `bleed`. | on |
| SOLVE | A joint minimal-move constraint pass (`engine/solve.py`): near-aligned edges are aligned exactly and nearly even gaps made exactly even, while every pair keeps its order and gap and content stays on the canvas. It only translates units, solved with Dykstra projections, and polishes the winner as "+solve". | on |
| TYPESCALE | Secondary copy stays between 1/2.6 and 1/1.25 of the headline's size, or the source's own ratio when that falls outside. Long copy wraps at 75 characters. | on |
| AIR | Reserves 12 % of the column as whitespace before the size search (variants). | **opt-in** (measured worse) |
| UNITS | Pictures of at least 6 % of the canvas get their own slot beside the hero instead of a badge chip. Split phrases on one row become one unit. A paragraph in a box is no longer a CTA. | on |
| STRIP | The tiny-format composer. Tall strips get tighter margins. Letter spacing gives way before font size (also inside buttons). Attached bars are clipped to the slot. Units sliding past the edge are moved back. A box grows rather than halving a planned font. Strips get triage (rescue) variants, which alone tighten the leading on short banners. On short banners a headline beyond 3 lines pays a 3-point prior. | on |

## Results

Eval slice: 300 designs, 4,198 cases, no pixels, `eval/data/runs/bg_on_np` vs `v11_final_np`.

| | v10 | v11 |
|---|---:|---:|
| any hard defect | 13 | **0** |
| headline / CTA below the readable floor | 13 | **0** |
| overflow / unwanted overlap / off canvas | 0 / 0 / 0 | 0 / 0 / 0 |
| judge contrast fails / fallback wins | 10 / 5 | 10 / 5 |
| judge score mean (p50) | 80.64 (86.49) | **83.79** (86.61) |
| Skyscraper 160×600 / Leaderboard 728×90 defect rate | 3.0 % / 1.3 % | **0 % / 0 %** |
| ground-truth reading-order tau / size rho | 0.787 / 0.782 | 0.780 / 0.778 |

Designer references: 720 cases, `eval.compare_optimize --flag CHAMELEON_V11`, `docs/designer/compare/v11_final`.

| | tuning off | tuning on | hold-out off | hold-out on |
|---|---:|---:|---:|---:|
| designer agreement | 0.607 | 0.607 | 0.615 | 0.615 |
| best candidate agreement | 0.670 | 0.670 | 0.668 | 0.668 |
| engine hard fails | 0 | 0 | 1 | **0** |
| judge score mean | 87.54 | 87.58 | 77.95 | **86.46** |
| runtime p50 / p95 (s, 9 workers) | 0.59 / 1.46 | 0.63 / 1.55 | 0.77 / 1.31 | 0.78 / 1.43 |

Per format (tuning), the strips gain: 160×600 0.592 → 0.599, 728×90 0.490 → 0.493, 1080×1920 0.657 → 0.660,
820×312 0.552 → 0.555. 1600×900 (0.578 → 0.571) and 1080×1080 (0.715 → 0.709) lose a little. The per-piece ablation
(`docs/designer/compare/v11_<piece>`, each piece alone against v10, run before the two fixes below) puts all five within ±0.001 of v10 in the mean.
UNITS explains most of the 1600×900 / 1080×1080 dip but is net neutral over the 600 cases (21 up, 24 down, total
+0.04). SOLVE moves 60–70 cases each way by pixels.

Single-process runtime, the three samples × 6 targets with pixels on: p50 0.61 s → 0.54 s, max 1.40 s → 1.54 s.

## What this does and does not show

- The clear gain is robustness where the brief says "holds up everywhere". Every remaining hard defect was a
  headline or CTA under the readable floor on a skyscraper or leaderboard, and all are gone. The causes were tracked
  one by one in the composer: headline bars widening the footprint past a 160 px canvas, letter-spaced lines that
  the renderer wraps on glyph widths and then paints wider, tracked button labels, and six-line headlines with hard
  line breaks in a 90 px strip.
- Designer agreement does not move, and the best candidate in the pool did not get closer either (0.670). The
  metric rewards the proportional copy (NEXT_STEPS.md said composition work needs human eyes), and the new
  compositions win few cases under the fitted judge. They are now in the pool for a human A/B round (/label) to
  judge fairly.
- Two near-tie flips were found and fixed before shipping. The solver on the top 3 lifted a six-line Level 3
  headline at 728×90 over the best layout by 0.1, so it now polishes the winner only. The AIR variant won 13 cases
  at −0.022 agreement (a BBQ poster with its lines reordered by the optimiser), so it is opt-in.
- Not run in Docker yet, like v7–v10. The S5 freeze (in-container eval, Linux text widths) is still open.

## Reproduce

```bash
cd chameleon
.venv/bin/python -m eval.run_eval --limit 300 --workers 9 --no-render --name v11_final_np
.venv/bin/python -m eval.compare_runs bg_on_np v11_final_np
.venv/bin/python -m eval.compare_optimize --flag CHAMELEON_V11 --workers 9 --out ../docs/designer/compare/v11_final
for p in COMPOSE SOLVE TYPESCALE UNITS STRIP; do .venv/bin/python -m eval.compare_optimize --flag CHAMELEON_V11_$p --workers 9 --out ../docs/designer/compare/v11_$(echo $p | tr A-Z a-z); done
```
