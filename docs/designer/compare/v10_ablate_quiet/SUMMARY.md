# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.604 | 0.603 |
| designer agreement >= 0.7 | 198 | 198 |
| centre error, mean | 0.143 | 0.143 |
| reading-order tau, mean | 0.695 | 0.695 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 166 | 166 |
| judge score, mean | 87.30 | 87.30 |
| energy, mean (lower is better) | 13.38 | 13.38 |
| refined candidate wins | 360 | 360 |
| runtime p50 (s) | 0.41 | 0.41 |
| runtime p95 (s) | 0.99 | 0.98 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 0, down in 1, unchanged in 599 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.673 | 0.673 | 0 | 0 | 12 | 12 |
| 1080x1920 | 50 | 0.651 | 0.651 | 0 | 0 | 19 | 19 |
| 1000x1500 | 50 | 0.674 | 0.673 | 0 | 0 | 16 | 16 |
| 1080x1350 | 50 | 0.689 | 0.689 | 0 | 0 | 14 | 14 |
| 1600x900 | 50 | 0.576 | 0.576 | 0 | 0 | 12 | 12 |
| 1080x1080 | 50 | 0.708 | 0.708 | 0 | 0 | 8 | 8 |
| 1280x720 | 50 | 0.579 | 0.579 | 0 | 0 | 8 | 8 |
| 1600x400 | 50 | 0.533 | 0.533 | 0 | 0 | 14 | 14 |
| 1584x396 | 50 | 0.537 | 0.537 | 0 | 0 | 15 | 15 |
| 820x312 | 50 | 0.547 | 0.547 | 0 | 0 | 12 | 12 |
| 160x600 | 50 | 0.589 | 0.589 | 0 | 0 | 19 | 19 |
| 728x90 | 50 | 0.487 | 0.487 | 0 | 0 | 17 | 17 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.611 | 0.610 |
| designer agreement >= 0.7 | 38 | 38 |
| centre error, mean | 0.140 | 0.140 |
| reading-order tau, mean | 0.707 | 0.704 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 33 | 33 |
| judge score, mean | 77.68 | 77.64 |
| energy, mean (lower is better) | 23.23 | 23.32 |
| refined candidate wins | 74 | 74 |
| runtime p50 (s) | 0.50 | 0.50 |
| runtime p95 (s) | 0.84 | 0.84 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 2, down in 2, unchanged in 116 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.676 | 0.676 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.646 | 0.646 | 0 | 0 | 3 | 3 |
| 1000x1500 | 10 | 0.660 | 0.651 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.683 | 0.683 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.672 | 0.672 | 0 | 0 | 4 | 4 |
| 1080x1080 | 10 | 0.758 | 0.758 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.667 | 0.667 | 0 | 0 | 3 | 3 |
| 1600x400 | 10 | 0.544 | 0.544 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.546 | 0.546 | 0 | 0 | 3 | 3 |
| 820x312 | 10 | 0.509 | 0.509 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.511 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.457 | 0.457 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 5ea00c67499b85dcc778413e 1000x1500: 0.570 -> 0.475 (tall scale=1.15 +opt -> tall spacing=1.3 +opt)
- 58aeb3f395a7a863ddcc8457 160x600: 0.408 -> 0.371 (tall structure flip +fix:headl -> tall structure keep +fix:headl)
- 5952645b95a7a863ddcde7c9 1000x1500: 0.792 -> 0.765 (anchor x1.12 scale=1.400 +fix: -> anchor x1.12 scale=1.400 +opt)
- 5888cec295a7a863ddcc24c9 1000x1500: 0.954 -> 0.954 (anchor fit scale=1.361 -> anchor fit scale=1.361)
- 5888cec295a7a863ddcc24c9 1080x1080: 0.843 -> 0.843 (anchor x1.12 scale=1.098 +opt -> anchor x1.12 scale=1.098 +opt)
- 5888cec295a7a863ddcc24c9 1080x1350: 0.927 -> 0.927 (anchor x1.12 scale=1.372 -> anchor x1.12 scale=1.372)
- 5888cec295a7a863ddcc24c9 1080x1920: 0.949 -> 0.949 (anchor fit scale=1.469 +opt -> anchor fit scale=1.469 +opt)
- 5888cec295a7a863ddcc24c9 1240x1754: 0.953 -> 0.953 (anchor x1.12 scale=1.687 -> anchor x1.12 scale=1.687)
- 5fa50e1ea637ee11e399a87f 1584x396: 0.531 -> 0.531 (banner spacing=1.3 +opt -> banner spacing=1.3 +opt)
- 5fa50e1ea637ee11e399a87f 1600x400: 0.531 -> 0.531 (banner spacing=1.3 +opt -> banner spacing=1.3 +opt)
- 5fa50e1ea637ee11e399a87f 1600x900: 0.528 -> 0.528 (wide structure keep -> wide structure keep)
- 5fa50e1ea637ee11e399a87f 160x600: 0.463 -> 0.463 (tall scale=1.15 +opt -> tall scale=1.15 +opt)
- 5fa50e1ea637ee11e399a87f 728x90: 0.528 -> 0.528 (banner scale=1.5 +fix:tighter  -> banner scale=1.5 +fix:tighter )
- 5fa50e1ea637ee11e399a87f 820x312: 0.416 -> 0.416 (wide structure flip -> wide structure flip)
- 5ea00c67499b85dcc778413e 1080x1080: 0.608 -> 0.609 (square hero=right +fix:bolder, -> square hero=right +fix:tighter)
- 5ea00c67499b85dcc778413e 1600x400: 0.722 -> 0.723 (banner text=column +fix:tighte -> banner text=column, scale=1.5,)
