# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 199 | 198 |
| centre error, mean | 0.141 | 0.140 |
| reading-order tau, mean | 0.702 | 0.702 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 168 | 164 |
| judge score, mean | 87.54 | 87.58 |
| energy, mean (lower is better) | 13.15 | 13.12 |
| refined candidate wins | 369 | 273 |
| runtime p50 (s) | 0.59 | 0.63 |
| runtime p95 (s) | 1.46 | 1.55 |

references with a hard fail under the current judge: 44; under the energy: 44; reference energy mean 105.08

agreement up in 117, down in 130, unchanged in 353 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.677 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.660 | 0 | 0 | 18 | 17 |
| 1000x1500 | 50 | 0.674 | 0.669 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.697 | 0 | 0 | 14 | 13 |
| 1600x900 | 50 | 0.578 | 0.571 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.715 | 0.709 | 0 | 0 | 10 | 10 |
| 1280x720 | 50 | 0.583 | 0.582 | 0 | 0 | 8 | 9 |
| 1600x400 | 50 | 0.537 | 0.532 | 0 | 0 | 13 | 11 |
| 1584x396 | 50 | 0.538 | 0.538 | 0 | 0 | 14 | 15 |
| 820x312 | 50 | 0.552 | 0.555 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.592 | 0.599 | 0 | 0 | 19 | 18 |
| 728x90 | 50 | 0.490 | 0.493 | 0 | 0 | 20 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.615 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 39 | 38 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.725 | 0.727 |
| engine cases with a hard fail (judge) | 1 | 0 |
| engine cases with a hard fail (energy) | 1 | 0 |
| designer wins by judge score | 32 | 28 |
| judge score, mean | 77.95 | 86.46 |
| energy, mean (lower is better) | 23.21 | 14.70 |
| refined candidate wins | 74 | 50 |
| runtime p50 (s) | 0.77 | 0.78 |
| runtime p95 (s) | 1.31 | 1.43 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 123.69

agreement up in 26, down in 32, unchanged in 62 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.683 | 0 | 0 | 2 | 1 |
| 1080x1920 | 10 | 0.648 | 0.656 | 0 | 0 | 1 | 2 |
| 1000x1500 | 10 | 0.678 | 0.674 | 0 | 0 | 2 | 3 |
| 1080x1350 | 10 | 0.689 | 0.691 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.669 | 0 | 0 | 4 | 2 |
| 1080x1080 | 10 | 0.752 | 0.749 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.670 | 0.667 | 0 | 0 | 3 | 2 |
| 1600x400 | 10 | 0.558 | 0.567 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.514 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.517 | 1 | 0 | 3 | 2 |
| 728x90 | 10 | 0.456 | 0.462 | 0 | 0 | 4 | 3 |

## Largest agreement changes (on - off)

- 5e68e28db04a3d1f19b3c3fc 160x600: 0.558 -> 0.318 (tall default -> tall chips=corner, scale=1.3 +)
- 593011fc95a7a863ddcdbf9a 728x90: 0.443 -> 0.211 (banner spacing=0.75 +opt -> banner structure flip +opt)
- 595256d795a7a863ddcde397 1080x1080: 0.716 -> 0.512 (square structure keep +opt -> square chips=corner +opt)
- 5889bbc295a7a863ddcc3aa3 1000x1500: 0.481 -> 0.327 (tall chips=corner, spacing=0.7 -> tall structure swap +opt)
- 593011fc95a7a863ddcdbf9a 1280x720: 0.468 -> 0.321 (wide structure keep +opt -> wide compose=bleed +solve)
- 593011fc95a7a863ddcdbf9a 1600x900: 0.468 -> 0.321 (wide structure keep +opt -> wide compose=bleed +solve)
- 5e8596d64b3890eb078227f9 1584x396: 0.675 -> 0.532 (banner text=inline +opt -> banner text=column, scale=1.3 )
- 592fbce195a7a863ddcdb82e 160x600: 0.785 -> 0.653 (tall structure keep -> tall scale=1.5 +opt)
- 5e709a0f4b3890eb0783cb50 1080x1920: 0.590 -> 0.706 (tall spacing=0.75 +opt -> tall spacing=0.75)
- 59b27ce91350e8329300d847 728x90: 0.494 -> 0.627 (banner text=inline, spacing=0. -> banner text=inline, spacing=0.)
- 5889bbc295a7a863ddcc3aa3 1080x1080: 0.427 -> 0.566 (square chips=corner +opt -> square hero=right, chips=corne)
- 593011fc95a7a863ddcdbf9a 160x600: 0.302 -> 0.451 (tall chips=corner, spacing=0.7 -> tall spacing=0.75, rescue +opt)
- 5cebeb787d4459dfe1267619 820x312: 0.370 -> 0.560 (wide scale=1.5 +fix:pin to sou -> wide hero=right, chips=corner )
- 592c21ac95a7a863ddcd9611 1280x720: 0.563 -> 0.804 (wide scale=1.5 -> wide structure keep +opt)
- 5ca7253923c829c8213e6cd2 728x90: 0.372 -> 0.729 (banner scale=1.5 +fix:tighter  -> banner hero=right, text=column)
- 595256d795a7a863ddcde397 160x600: 0.392 -> 0.795 (tall scale=1.5 +fix:bolder, fi -> tall structure keep +solve)
