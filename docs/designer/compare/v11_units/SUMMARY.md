# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.608 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 199 | 200 |
| centre error, mean | 0.141 | 0.140 |
| reading-order tau, mean | 0.702 | 0.704 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 1 |
| designer wins by judge score | 163 | 162 |
| judge score, mean | 87.54 | 87.57 |
| energy, mean (lower is better) | 13.16 | 14.82 |
| refined candidate wins | 369 | 367 |
| runtime p50 (s) | 0.61 | 0.62 |
| runtime p95 (s) | 1.54 | 1.51 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 18, down in 17, unchanged in 565 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.660 | 0 | 0 | 18 | 17 |
| 1000x1500 | 50 | 0.674 | 0.671 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.697 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.578 | 0.574 | 0 | 0 | 11 | 10 |
| 1080x1080 | 50 | 0.715 | 0.709 | 0 | 0 | 9 | 10 |
| 1280x720 | 50 | 0.583 | 0.583 | 0 | 0 | 7 | 7 |
| 1600x400 | 50 | 0.537 | 0.536 | 0 | 0 | 13 | 12 |
| 1584x396 | 50 | 0.538 | 0.538 | 0 | 0 | 14 | 13 |
| 820x312 | 50 | 0.552 | 0.556 | 0 | 0 | 14 | 15 |
| 160x600 | 50 | 0.592 | 0.602 | 0 | 0 | 18 | 19 |
| 728x90 | 50 | 0.490 | 0.489 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.613 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 39 | 39 |
| centre error, mean | 0.141 | 0.142 |
| reading-order tau, mean | 0.725 | 0.720 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 5 |
| designer wins by judge score | 29 | 27 |
| judge score, mean | 77.95 | 78.13 |
| energy, mean (lower is better) | 23.26 | 56.73 |
| refined candidate wins | 74 | 71 |
| runtime p50 (s) | 0.79 | 0.79 |
| runtime p95 (s) | 1.39 | 1.34 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 3, down in 7, unchanged in 110 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.682 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.648 | 0.648 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.678 | 0.678 | 0 | 0 | 2 | 1 |
| 1080x1350 | 10 | 0.689 | 0.689 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.673 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.752 | 0.749 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.667 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.558 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.513 | 0 | 0 | 4 | 3 |
| 160x600 | 10 | 0.515 | 0.519 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.456 | 0.450 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 595256d795a7a863ddcde397 1080x1080: 0.716 -> 0.512 (square structure keep +opt -> square chips=corner +opt)
- 5889bbc295a7a863ddcc3aa3 1000x1500: 0.481 -> 0.327 (tall chips=corner, spacing=0.7 -> tall structure swap +opt)
- 593011fc95a7a863ddcdbf9a 1600x900: 0.468 -> 0.321 (wide structure keep +opt -> wide spacing=0.75)
- 5e8d96cb4b3890eb071c683d 1080x1080: 0.670 -> 0.534 (square chips=corner +opt -> square hero=left +fix:tighter )
- 5888ce7495a7a863ddcc2449 1600x900: 0.521 -> 0.398 (wide structure flip +opt -> wide structure keep +opt)
- 5e8d96cb4b3890eb071c683d 160x600: 0.618 -> 0.553 (tall scale=1.3 -> tall scale=1.3 +opt)
- 5cebeb787d4459dfe1267619 728x90: 0.435 -> 0.375 (banner scale=1.3 +fix:tighter  -> banner scale=1.5, fill +opt)
- 5888ce7495a7a863ddcc2449 728x90: 0.655 -> 0.596 (banner structure flip +opt -> banner structure flip +fix:hea)
- 5888ce7495a7a863ddcc2449 160x600: 0.571 -> 0.614 (tall structure keep +opt -> tall structure keep +opt)
- 5889bbc295a7a863ddcc3aa3 1080x1350: 0.485 -> 0.540 (tall chips=corner, spacing=0.7 -> tall chips=corner, spacing=0.7)
- 595256d795a7a863ddcde397 1280x720: 0.386 -> 0.446 (wide hero=right, chips=corner  -> wide hero=right, chips=corner )
- 5e709a0f4b3890eb0783cb50 1080x1920: 0.590 -> 0.706 (tall spacing=0.75 +opt -> tall spacing=0.75)
- 5889bbc295a7a863ddcc3aa3 1080x1080: 0.427 -> 0.566 (square chips=corner +opt -> square hero=right, chips=corne)
- 593011fc95a7a863ddcdbf9a 160x600: 0.302 -> 0.443 (tall chips=corner, spacing=0.7 -> tall structure keep)
- 5cebeb787d4459dfe1267619 820x312: 0.370 -> 0.560 (wide scale=1.5 +fix:pin to sou -> wide hero=right, chips=corner )
- 595256d795a7a863ddcde397 160x600: 0.392 -> 0.791 (tall scale=1.5 +fix:bolder, fi -> tall structure keep +opt)
