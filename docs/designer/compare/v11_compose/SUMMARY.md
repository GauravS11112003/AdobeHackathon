# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.671 |
| designer agreement >= 0.7 | 199 | 198 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.702 | 0.703 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 163 | 163 |
| judge score, mean | 87.54 | 87.56 |
| energy, mean (lower is better) | 13.16 | 13.16 |
| refined candidate wins | 369 | 368 |
| runtime p50 (s) | 0.70 | 0.71 |
| runtime p95 (s) | 1.61 | 1.74 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 9, down in 9, unchanged in 582 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.674 | 0.674 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.578 | 0.576 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.715 | 0.715 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.583 | 0.584 | 0 | 0 | 7 | 7 |
| 1600x400 | 50 | 0.537 | 0.538 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.539 | 0 | 0 | 14 | 14 |
| 820x312 | 50 | 0.552 | 0.550 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.592 | 0.592 | 0 | 0 | 18 | 18 |
| 728x90 | 50 | 0.490 | 0.485 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.614 |
| best candidate agreement, mean | 0.668 | 0.667 |
| designer agreement >= 0.7 | 39 | 38 |
| centre error, mean | 0.141 | 0.143 |
| reading-order tau, mean | 0.725 | 0.730 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 29 | 30 |
| judge score, mean | 77.95 | 77.90 |
| energy, mean (lower is better) | 23.26 | 23.40 |
| refined candidate wins | 74 | 74 |
| runtime p50 (s) | 0.84 | 0.83 |
| runtime p95 (s) | 1.34 | 1.51 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 3, down in 2, unchanged in 115 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.682 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.648 | 0.648 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.678 | 0.678 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.689 | 0.689 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.686 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.752 | 0.752 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.549 | 0 | 0 | 3 | 4 |
| 1584x396 | 10 | 0.528 | 0.538 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.510 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.515 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.456 | 0.456 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 593011fc95a7a863ddcdbf9a 728x90: 0.443 -> 0.211 (banner spacing=0.75 +opt -> banner structure flip +opt)
- 5947c25e95a7a863ddcdda6b 1600x400: 0.703 -> 0.506 (banner chips=stack +fix:tighte -> banner hero=right, compose=boo)
- 595298a695a7a863ddce047c 820x312: 0.760 -> 0.590 (wide structure flip +opt -> wide compose=bleed)
- 593112f495a7a863ddcdc5a7 1600x900: 0.677 -> 0.574 (wide chips=corner +fix:bolder, -> wide compose=bleed +opt)
- 59158aee95a7a863ddcd861e 728x90: 0.495 -> 0.415 (banner hero=right, text=column -> banner hero=right, text=column)
- 5947c25e95a7a863ddcdda6b 820x312: 0.441 -> 0.411 (wide hero=left +fix:pin to sou -> wide compose=bleed +opt)
- 59158aee95a7a863ddcd861e 1584x396: 0.562 -> 0.538 (banner hero=right, text=column -> banner hero=right, text=column)
- 59b27ce91350e8329300d847 1280x720: 0.744 -> 0.742 (wide scale=1.3 -> wide scale=1.3, compose=bleed)
- 593112f495a7a863ddcdc5a7 728x90: 0.437 -> 0.458 (banner structure keep +opt -> banner compose=bleed +fix:bold)
- 5f34ddbfa637ee11e32f6bf0 728x90: 0.296 -> 0.321 (banner text=inline, spacing=0. -> banner compose=twotier +opt)
- 59b27ce91350e8329300d847 1600x900: 0.703 -> 0.739 (wide scale=1.3 -> wide scale=1.3, compose=bleed)
- 5cebeb787d4459dfe1267619 1280x720: 0.365 -> 0.417 (wide spacing=0.75 +fix:pin to  -> wide compose=header +opt)
- 5888cec295a7a863ddcc24c9 1584x396: 0.460 -> 0.528 (banner hero=right +opt -> banner hero=right, compose=boo)
- 5888cec295a7a863ddcc24c9 1600x400: 0.455 -> 0.529 (banner hero=right, text=inline -> banner hero=right, compose=boo)
- 5889915e95a7a863ddcc3491 1584x396: 0.368 -> 0.468 (banner text=inline, spacing=0. -> banner compose=twotier +opt)
- 5889915e95a7a863ddcc3491 1600x400: 0.368 -> 0.471 (banner text=inline, spacing=0. -> banner compose=twotier +opt)
