# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 199 | 200 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.702 | 0.701 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 163 | 163 |
| judge score, mean | 87.54 | 87.57 |
| energy, mean (lower is better) | 13.16 | 13.22 |
| refined candidate wins | 369 | 266 |
| runtime p50 (s) | 0.63 | 0.63 |
| runtime p95 (s) | 1.60 | 1.58 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 69, down in 63, unchanged in 468 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.674 | 0.673 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.578 | 0.578 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.715 | 0.715 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.583 | 0.582 | 0 | 0 | 7 | 7 |
| 1600x400 | 50 | 0.537 | 0.536 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.541 | 0 | 0 | 14 | 14 |
| 820x312 | 50 | 0.552 | 0.552 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.592 | 0.592 | 0 | 0 | 18 | 18 |
| 728x90 | 50 | 0.490 | 0.488 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.614 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 39 | 38 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.725 | 0.723 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 29 | 28 |
| judge score, mean | 77.95 | 77.96 |
| energy, mean (lower is better) | 23.26 | 23.32 |
| refined candidate wins | 74 | 52 |
| runtime p50 (s) | 0.82 | 0.85 |
| runtime p95 (s) | 1.50 | 1.47 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 10, down in 14, unchanged in 96 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.682 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.648 | 0.648 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.678 | 0.678 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.689 | 0.688 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.686 | 0 | 0 | 3 | 2 |
| 1080x1080 | 10 | 0.752 | 0.752 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.558 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.511 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.515 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.456 | 0.456 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- level3_advanced 728x90: 0.538 -> 0.447 (banner scale=1.5, fill -> banner structure flip +solve)
- 5888d00b95a7a863ddcc269a 1000x1500: 0.609 -> 0.584 (tall scale=1.15 +opt -> tall scale=1.15 +opt +solve)
- level3_advanced 1000x1500: 0.770 -> 0.749 (anchor x1.25 scale=1.111 -> anchor x1.25 scale=1.111 +solv)
- 5909cf8595a7a863ddcd37aa 820x312: 0.650 -> 0.630 (wide structure keep +opt -> wide structure keep +opt +solv)
- 5914237f95a7a863ddcd77ce 1584x396: 0.428 -> 0.412 (banner text=column, scale=1.5, -> banner text=column +solve)
- 592c21ac95a7a863ddcd9611 1600x900: 0.562 -> 0.547 (wide scale=1.5, fill +opt -> wide scale=1.5, fill +opt +sol)
- 59b268f51350e8329300d285 1584x396: 0.500 -> 0.487 (banner text=column, scale=1.5, -> banner text=column, scale=1.5,)
- 599ecb061350e83293007738 1000x1500: 0.600 -> 0.587 (tall chips=corner, scale=1.3 + -> tall chips=corner, scale=1.3 +)
- 5952983995a7a863ddce040b 728x90: 0.322 -> 0.327 (banner text=inline +opt -> banner text=inline +opt +solve)
- 5cebeb787d4459dfe1267619 1600x400: 0.438 -> 0.444 (banner scale=1.3 +opt -> banner scale=1.3 +opt +solve)
- 59526a6495a7a863ddcdead9 1240x1754: 0.678 -> 0.685 (tall chips=corner, scale=1.3 + -> tall chips=corner, scale=1.3 +)
- level2_core 1000x1500: 0.753 -> 0.767 (anchor x1.4 scale=1.296 -> anchor x1.25 scale=1.157 +solv)
- 59525fbb95a7a863ddcde543 728x90: 0.382 -> 0.397 (banner text=inline, spacing=0. -> banner text=inline, spacing=0.)
- 5889bae595a7a863ddcc391f 1080x1920: 0.419 -> 0.448 (tall scale=1.5 +fix:headline o -> tall scale=1.5 +fix:tighter pl)
- 5889bae595a7a863ddcc391f 1600x900: 0.836 -> 0.893 (anchor x1.4 scale=5.040 +opt -> anchor x1.25 scale=4.500 +opt )
- 5ca7253923c829c8213e6cd2 1584x396: 0.523 -> 0.703 (banner structure keep +opt -> banner hero=right +fix:bolder,)
