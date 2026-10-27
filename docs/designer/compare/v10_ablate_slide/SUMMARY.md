# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.603 | 0.603 |
| designer agreement >= 0.7 | 196 | 198 |
| centre error, mean | 0.143 | 0.143 |
| reading-order tau, mean | 0.694 | 0.695 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 168 | 166 |
| judge score, mean | 87.29 | 87.30 |
| energy, mean (lower is better) | 13.40 | 13.38 |
| refined candidate wins | 360 | 360 |
| runtime p50 (s) | 0.38 | 0.40 |
| runtime p95 (s) | 0.97 | 0.99 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 8, down in 6, unchanged in 586 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.677 | 0.673 | 0 | 0 | 12 | 12 |
| 1080x1920 | 50 | 0.651 | 0.651 | 0 | 0 | 19 | 19 |
| 1000x1500 | 50 | 0.674 | 0.673 | 0 | 0 | 16 | 16 |
| 1080x1350 | 50 | 0.688 | 0.689 | 0 | 0 | 14 | 14 |
| 1600x900 | 50 | 0.574 | 0.576 | 0 | 0 | 13 | 12 |
| 1080x1080 | 50 | 0.708 | 0.708 | 0 | 0 | 8 | 8 |
| 1280x720 | 50 | 0.578 | 0.579 | 0 | 0 | 9 | 8 |
| 1600x400 | 50 | 0.533 | 0.533 | 0 | 0 | 14 | 14 |
| 1584x396 | 50 | 0.537 | 0.537 | 0 | 0 | 15 | 15 |
| 820x312 | 50 | 0.547 | 0.547 | 0 | 0 | 12 | 12 |
| 160x600 | 50 | 0.589 | 0.589 | 0 | 0 | 19 | 19 |
| 728x90 | 50 | 0.487 | 0.487 | 0 | 0 | 17 | 17 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.610 | 0.610 |
| designer agreement >= 0.7 | 37 | 38 |
| centre error, mean | 0.140 | 0.140 |
| reading-order tau, mean | 0.709 | 0.704 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 33 | 33 |
| judge score, mean | 77.69 | 77.64 |
| energy, mean (lower is better) | 23.22 | 23.32 |
| refined candidate wins | 75 | 74 |
| runtime p50 (s) | 0.48 | 0.50 |
| runtime p95 (s) | 0.83 | 0.83 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 2, down in 2, unchanged in 116 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.676 | 0.676 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.633 | 0.646 | 0 | 0 | 3 | 3 |
| 1000x1500 | 10 | 0.665 | 0.651 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.683 | 0.683 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.672 | 0.672 | 0 | 0 | 4 | 4 |
| 1080x1080 | 10 | 0.753 | 0.758 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.667 | 0.667 | 0 | 0 | 3 | 3 |
| 1600x400 | 10 | 0.544 | 0.544 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.546 | 0.546 | 0 | 0 | 3 | 3 |
| 820x312 | 10 | 0.509 | 0.509 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.511 | 0.511 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.457 | 0.457 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 5e68e28db04a3d1f19b3c3fc 1000x1500: 0.476 -> 0.318 (tall scale=1.5 -> tall scale=1.5 +fix:tighter pl)
- 5e68e28db04a3d1f19b3c3fc 1240x1754: 0.481 -> 0.327 (tall scale=1.3 +fix:tighter pl -> tall scale=1.3 +fix:tighter pl)
- 5d5ec02dcf657b21effed4f3 1000x1500: 0.528 -> 0.385 (tall chips=corner +opt -> tall scale=1.3)
- 59b26b3c1350e8329300d498 1280x720: 0.508 -> 0.450 (wide scale=1.3 +fix:badges to  -> wide scale=1.3 +fix:badges to )
- 58aed3c795a7a863ddcc88e4 1000x1500: 0.577 -> 0.538 (tall scale=1.5 +opt -> tall scale=1.5 +fix:tighter pl)
- 58aed3c795a7a863ddcc88e4 160x600: 0.433 -> 0.402 (tall structure flip -> tall chips=corner, scale=1.3 +)
- 593112f495a7a863ddcdc5a7 1600x900: 0.682 -> 0.677 (wide scale=1.5, fill +fix:bold -> wide chips=corner +fix:bolder,)
- 5ea00c67499b85dcc778413e 1240x1754: 0.470 -> 0.469 (tall spacing=0.75 +opt -> tall scale=1.5, fill +fix:tigh)
- 5e68e28db04a3d1f19b3c3fc 1080x1920: 0.316 -> 0.319 (tall chips=corner, scale=1.3 + -> tall chips=corner, scale=1.3)
- 593112f495a7a863ddcdc5a7 1280x720: 0.650 -> 0.677 (wide spacing=0.75 +opt -> wide chips=corner +fix:bolder,)
- 58aed3c795a7a863ddcc88e4 1080x1350: 0.411 -> 0.450 (tall scale=1.5 +opt -> tall chips=corner, scale=1.3)
- 5ea00c67499b85dcc778413e 1080x1080: 0.555 -> 0.609 (square hero=right +opt -> square hero=right +fix:tighter)
- 58a4091695a7a863ddcc6c53 1600x900: 0.635 -> 0.750 (wide chips=corner +opt -> wide chips=corner +opt)
- 58a4091695a7a863ddcc6c53 1280x720: 0.643 -> 0.759 (wide chips=corner +opt -> wide chips=corner +opt)
- 5ea00c67499b85dcc778413e 1080x1920: 0.614 -> 0.752 (tall spacing=0.75 +opt -> tall default +opt)
- 591429a395a7a863ddcd7e39 1000x1500: 0.460 -> 0.631 (tall scale=1.15 +opt -> tall structure flip +opt)
