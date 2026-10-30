# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 199 | 198 |
| centre error, mean | 0.141 | 0.140 |
| reading-order tau, mean | 0.702 | 0.700 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 163 | 164 |
| judge score, mean | 87.54 | 87.48 |
| energy, mean (lower is better) | 13.16 | 13.13 |
| refined candidate wins | 369 | 372 |
| runtime p50 (s) | 0.69 | 0.70 |
| runtime p95 (s) | 1.70 | 1.70 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 30, down in 50, unchanged in 520 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.674 | 0.673 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 12 |
| 1600x900 | 50 | 0.578 | 0.575 | 0 | 0 | 11 | 12 |
| 1080x1080 | 50 | 0.715 | 0.713 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.583 | 0.589 | 0 | 0 | 7 | 9 |
| 1600x400 | 50 | 0.537 | 0.531 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.537 | 0 | 0 | 14 | 14 |
| 820x312 | 50 | 0.552 | 0.552 | 0 | 0 | 14 | 13 |
| 160x600 | 50 | 0.592 | 0.592 | 0 | 0 | 18 | 18 |
| 728x90 | 50 | 0.490 | 0.498 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.616 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 39 | 38 |
| centre error, mean | 0.141 | 0.139 |
| reading-order tau, mean | 0.725 | 0.727 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 29 | 27 |
| judge score, mean | 77.95 | 78.02 |
| energy, mean (lower is better) | 23.26 | 23.07 |
| refined candidate wins | 74 | 74 |
| runtime p50 (s) | 0.86 | 0.91 |
| runtime p95 (s) | 1.56 | 1.57 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 12, down in 11, unchanged in 97 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.683 | 0 | 0 | 2 | 1 |
| 1080x1920 | 10 | 0.648 | 0.645 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.678 | 0.674 | 0 | 0 | 2 | 3 |
| 1080x1350 | 10 | 0.689 | 0.691 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.681 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.752 | 0.752 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.557 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.534 | 0 | 0 | 4 | 3 |
| 820x312 | 10 | 0.513 | 0.516 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.531 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.456 | 0.463 | 0 | 0 | 4 | 3 |

## Largest agreement changes (on - off)

- 591429a395a7a863ddcd7e39 1080x1080: 0.677 -> 0.404 (square structure flip -> square scale=1.3, air +opt)
- 5e8596d64b3890eb078227f9 1584x396: 0.675 -> 0.531 (banner text=inline +opt -> banner text=column, scale=1.3 )
- 593112f495a7a863ddcdc5a7 1600x900: 0.677 -> 0.547 (wide chips=corner +fix:bolder, -> wide chips=corner +opt)
- 5e8d96cb4b3890eb071c683d 1600x400: 0.518 -> 0.421 (banner scale=1.5, fill +fix:pi -> banner spacing=1.3 +fix:pin to)
- level3_advanced 728x90: 0.538 -> 0.447 (banner scale=1.5, fill -> banner structure flip)
- 5f34ddbfa637ee11e32f6bf0 1280x720: 0.455 -> 0.366 (wide chips=corner +opt -> wide spacing=0.75 +opt)
- 59b27ce91350e8329300d847 1280x720: 0.744 -> 0.663 (wide scale=1.3 -> anchor x1.4 scale=1.279 +opt)
- 5953611d95a7a863ddce13e0 1600x400: 0.405 -> 0.326 (banner scale=1.5 +opt -> banner structure swap)
- 59b27ce91350e8329300d847 728x90: 0.494 -> 0.627 (banner text=inline, spacing=0. -> banner text=inline, spacing=0.)
- 5cebeb787d4459dfe1267619 1600x900: 0.400 -> 0.536 (wide chips=corner +fix:pin to  -> wide hero=right, scale=1.3 +fi)
- 5889910495a7a863ddcc341b 160x600: 0.424 -> 0.583 (tall chips=corner, scale=1.3 + -> tall chips=corner, scale=1.3)
- 5889bbc295a7a863ddcc3aa3 1080x1080: 0.427 -> 0.619 (square chips=corner +opt -> square structure keep +opt)
- 5947c25e95a7a863ddcdda6b 1584x396: 0.394 -> 0.598 (banner text=column, scale=1.3  -> banner hero=right, text=inline)
- 5cebeb787d4459dfe1267619 1280x720: 0.365 -> 0.590 (wide spacing=0.75 +fix:pin to  -> wide hero=right, scale=1.3 +op)
- 592c21ac95a7a863ddcd9611 1280x720: 0.563 -> 0.804 (wide scale=1.5 -> wide structure keep +opt)
- 5ca7253923c829c8213e6cd2 728x90: 0.372 -> 0.729 (banner scale=1.5 +fix:tighter  -> banner hero=right, text=column)
