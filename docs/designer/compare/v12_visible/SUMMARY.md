# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 198 | 198 |
| centre error, mean | 0.140 | 0.140 |
| reading-order tau, mean | 0.702 | 0.700 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 164 | 164 |
| judge score, mean | 87.58 | 87.58 |
| energy, mean (lower is better) | 13.12 | 13.15 |
| refined candidate wins | 273 | 270 |
| runtime p50 (s) | 0.58 | 0.59 |
| runtime p95 (s) | 1.37 | 1.42 |

references with a hard fail under the current judge: 44; under the energy: 44; reference energy mean 105.08

agreement up in 1, down in 5, unchanged in 594 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.677 | 0.677 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.660 | 0.660 | 0 | 0 | 17 | 17 |
| 1000x1500 | 50 | 0.669 | 0.669 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.697 | 0.697 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.571 | 0.571 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.709 | 0.709 | 0 | 0 | 10 | 10 |
| 1280x720 | 50 | 0.582 | 0.582 | 0 | 0 | 9 | 9 |
| 1600x400 | 50 | 0.532 | 0.531 | 0 | 0 | 11 | 11 |
| 1584x396 | 50 | 0.538 | 0.538 | 0 | 0 | 15 | 15 |
| 820x312 | 50 | 0.555 | 0.555 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.599 | 0.599 | 0 | 0 | 18 | 18 |
| 728x90 | 50 | 0.493 | 0.493 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.615 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 38 | 38 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.727 | 0.727 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 28 | 28 |
| judge score, mean | 86.46 | 86.45 |
| energy, mean (lower is better) | 14.70 | 14.71 |
| refined candidate wins | 50 | 50 |
| runtime p50 (s) | 0.70 | 0.69 |
| runtime p95 (s) | 1.31 | 1.29 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 123.69

agreement up in 0, down in 0, unchanged in 120 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.683 | 0.683 | 0 | 0 | 1 | 1 |
| 1080x1920 | 10 | 0.656 | 0.656 | 0 | 0 | 2 | 2 |
| 1000x1500 | 10 | 0.674 | 0.674 | 0 | 0 | 3 | 3 |
| 1080x1350 | 10 | 0.691 | 0.691 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.669 | 0.669 | 0 | 0 | 2 | 2 |
| 1080x1080 | 10 | 0.749 | 0.749 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.667 | 0.667 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.567 | 0.567 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.514 | 0.514 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.517 | 0.517 | 0 | 0 | 2 | 2 |
| 728x90 | 10 | 0.462 | 0.462 | 0 | 0 | 3 | 3 |

## Largest agreement changes (on - off)

- 5888d6c095a7a863ddcc2826 1600x400: 0.453 -> 0.416 (banner structure flip +opt -> banner structure flip)
- 5888d6c095a7a863ddcc2826 820x312: 0.459 -> 0.435 (wide structure flip +opt -> wide structure flip +solve)
- 5888d6c095a7a863ddcc2826 160x600: 0.443 -> 0.436 (tall structure keep +opt +solv -> tall structure keep +solve)
- 59158aee95a7a863ddcd861e 160x600: 0.434 -> 0.433 (tall chips=corner, scale=1.3 + -> tall chips=corner, scale=1.3 +)
- 59b27f4d1350e8329300daea 1600x400: 0.775 -> 0.775 (anchor x1.25 scale=1.000 +opt -> anchor x1.25 scale=1.000 +opt)
- 5888cec295a7a863ddcc24c9 1000x1500: 0.954 -> 0.954 (anchor fit scale=1.361 -> anchor fit scale=1.361)
- 5888cec295a7a863ddcc24c9 1080x1080: 0.843 -> 0.843 (anchor x1.12 scale=1.098 +opt -> anchor x1.12 scale=1.098 +opt)
- 5888cec295a7a863ddcc24c9 1080x1350: 0.927 -> 0.927 (anchor x1.12 scale=1.372 -> anchor x1.12 scale=1.372)
- 5fa50e1ea637ee11e399a87f 1280x720: 0.528 -> 0.528 (wide structure keep +solve -> wide structure keep +solve)
- 5fa50e1ea637ee11e399a87f 1584x396: 0.531 -> 0.531 (banner spacing=1.3 +opt -> banner spacing=1.3 +opt)
- 5fa50e1ea637ee11e399a87f 1600x400: 0.487 -> 0.487 (banner scale=1.15 +opt -> banner scale=1.15 +opt)
- 5fa50e1ea637ee11e399a87f 1600x900: 0.528 -> 0.528 (wide structure keep +solve -> wide structure keep +solve)
- 5fa50e1ea637ee11e399a87f 160x600: 0.454 -> 0.454 (tall scale=1.5 +opt -> tall scale=1.5 +opt)
- 5fa50e1ea637ee11e399a87f 728x90: 0.528 -> 0.528 (banner scale=1.5 +fix:tighter  -> banner scale=1.5 +fix:tighter )
- 5fa50e1ea637ee11e399a87f 820x312: 0.657 -> 0.657 (wide scale=1.3, compose=bleed  -> wide scale=1.3, compose=bleed )
- 5888d6c095a7a863ddcc2826 728x90: 0.439 -> 0.450 (banner structure flip -> banner structure flip)
