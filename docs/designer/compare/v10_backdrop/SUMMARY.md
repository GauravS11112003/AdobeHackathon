# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.608 | 0.607 |
| designer agreement >= 0.7 | 198 | 199 |
| centre error, mean | 0.140 | 0.141 |
| reading-order tau, mean | 0.702 | 0.702 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 165 | 163 |
| judge score, mean | 87.53 | 87.54 |
| energy, mean (lower is better) | 13.12 | 13.16 |
| refined candidate wins | 373 | 369 |
| runtime p50 (s) | 0.45 | 0.47 |
| runtime p95 (s) | 2.35 | 2.50 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 9, down in 7, unchanged in 584 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.684 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.677 | 0.674 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.575 | 0.578 | 0 | 0 | 12 | 11 |
| 1080x1080 | 50 | 0.715 | 0.715 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.579 | 0.583 | 0 | 0 | 8 | 7 |
| 1600x400 | 50 | 0.537 | 0.537 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.538 | 0 | 0 | 14 | 14 |
| 820x312 | 50 | 0.552 | 0.552 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.594 | 0.592 | 0 | 0 | 18 | 18 |
| 728x90 | 50 | 0.490 | 0.490 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.614 | 0.615 |
| designer agreement >= 0.7 | 38 | 39 |
| centre error, mean | 0.140 | 0.141 |
| reading-order tau, mean | 0.727 | 0.725 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 29 | 29 |
| judge score, mean | 77.97 | 77.95 |
| energy, mean (lower is better) | 23.13 | 23.26 |
| refined candidate wins | 74 | 74 |
| runtime p50 (s) | 0.49 | 0.52 |
| runtime p95 (s) | 0.93 | 0.91 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 2, down in 4, unchanged in 114 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.678 | 0.682 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.634 | 0.648 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.690 | 0.678 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.689 | 0.689 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.686 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.753 | 0.752 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.558 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.513 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.519 | 0.515 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.456 | 0.456 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 5e68e28db04a3d1f19b3c3fc 1000x1500: 0.476 -> 0.318 (tall scale=1.5 -> tall scale=1.5 +fix:tighter pl)
- 5e68e28db04a3d1f19b3c3fc 1240x1754: 0.481 -> 0.327 (tall scale=1.3 +fix:tighter pl -> tall scale=1.3 +fix:tighter pl)
- 5952645b95a7a863ddcde7c9 1240x1754: 0.799 -> 0.658 (anchor x1.12 scale=1.637 +opt -> tall structure keep +opt)
- 58aed3c795a7a863ddcc88e4 160x600: 0.490 -> 0.402 (tall scale=1.5 +fix:tighter pl -> tall chips=corner, scale=1.3 +)
- 5ea00c67499b85dcc778413e 1000x1500: 0.620 -> 0.533 (tall scale=1.15 +opt -> tall scale=1.15 +fix:tighter p)
- 58aeb3f395a7a863ddcc8457 160x600: 0.408 -> 0.371 (tall structure flip +fix:headl -> tall structure keep +fix:headl)
- 5e8596d64b3890eb078227f9 1000x1500: 0.640 -> 0.604 (anchor x1.4 scale=1.296 -> tall scale=1.3 +opt)
- 5952645b95a7a863ddcde7c9 1000x1500: 0.748 -> 0.720 (anchor x1.25 scale=1.562 +fix: -> anchor x1.25 scale=1.562)
- 59b26b3c1350e8329300d498 1600x900: 0.487 -> 0.508 (wide scale=1.5 +fix:badges to  -> wide scale=1.5 +fix:badges to )
- 593112f495a7a863ddcdc5a7 1280x720: 0.650 -> 0.677 (wide spacing=0.75 +opt -> wide chips=corner +fix:bolder,)
- 58aed3c795a7a863ddcc88e4 1080x1350: 0.411 -> 0.447 (tall scale=1.5 +opt -> tall chips=corner, scale=1.3 +)
- 5e8596d64b3890eb078227f9 1240x1754: 0.604 -> 0.646 (tall scale=1.3 +opt -> anchor x1.4 scale=1.607)
- 59b26b3c1350e8329300d498 1280x720: 0.483 -> 0.538 (wide scale=1.5 +fix:badges to  -> wide scale=1.5 +fix:pin to sou)
- 58a4091695a7a863ddcc6c53 1600x900: 0.635 -> 0.749 (wide chips=corner +opt -> wide chips=corner)
- 58a4091695a7a863ddcc6c53 1280x720: 0.643 -> 0.757 (wide chips=corner +opt -> wide chips=corner)
- 5ea00c67499b85dcc778413e 1080x1920: 0.654 -> 0.797 (tall scale=1.15 +opt -> tall default +opt)
