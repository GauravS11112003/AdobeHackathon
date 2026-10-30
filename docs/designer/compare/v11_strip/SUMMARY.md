# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.607 |
| best candidate agreement, mean | 0.670 | 0.670 |
| designer agreement >= 0.7 | 199 | 197 |
| centre error, mean | 0.141 | 0.141 |
| reading-order tau, mean | 0.702 | 0.703 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 163 | 162 |
| judge score, mean | 87.54 | 87.58 |
| energy, mean (lower is better) | 13.16 | 13.13 |
| refined candidate wins | 369 | 380 |
| runtime p50 (s) | 0.70 | 0.70 |
| runtime p95 (s) | 1.98 | 1.99 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 46, down in 57, unchanged in 497 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.678 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.674 | 0.674 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.578 | 0.578 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.715 | 0.715 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.583 | 0.583 | 0 | 0 | 7 | 7 |
| 1600x400 | 50 | 0.537 | 0.537 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.538 | 0 | 0 | 14 | 15 |
| 820x312 | 50 | 0.552 | 0.552 | 0 | 0 | 14 | 14 |
| 160x600 | 50 | 0.592 | 0.589 | 0 | 0 | 18 | 19 |
| 728x90 | 50 | 0.490 | 0.489 | 0 | 0 | 19 | 16 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.615 | 0.614 |
| best candidate agreement, mean | 0.668 | 0.668 |
| designer agreement >= 0.7 | 39 | 39 |
| centre error, mean | 0.141 | 0.140 |
| reading-order tau, mean | 0.725 | 0.723 |
| engine cases with a hard fail (judge) | 1 | 0 |
| engine cases with a hard fail (energy) | 1 | 0 |
| designer wins by judge score | 29 | 27 |
| judge score, mean | 77.95 | 86.29 |
| energy, mean (lower is better) | 23.26 | 14.89 |
| refined candidate wins | 74 | 74 |
| runtime p50 (s) | 0.95 | 0.94 |
| runtime p95 (s) | 1.76 | 1.71 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 7, down in 12, unchanged in 101 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.682 | 0.682 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.648 | 0.648 | 0 | 0 | 1 | 1 |
| 1000x1500 | 10 | 0.678 | 0.678 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.689 | 0.689 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.686 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.752 | 0.752 | 0 | 0 | 0 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.558 | 0.558 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.528 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.513 | 0.513 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.515 | 0.507 | 1 | 0 | 3 | 2 |
| 728x90 | 10 | 0.456 | 0.457 | 0 | 0 | 4 | 3 |

## Largest agreement changes (on - off)

- 5e68e28db04a3d1f19b3c3fc 160x600: 0.558 -> 0.318 (tall default -> tall chips=corner, scale=1.3 +)
- 592fbce195a7a863ddcdb82e 160x600: 0.785 -> 0.653 (tall structure keep -> tall scale=1.5 +opt)
- 5ea97608499b85dcc7d2ec78 160x600: 0.714 -> 0.586 (tall structure keep -> tall spacing=0.75, rescue +opt)
- 5909cf8595a7a863ddcd37aa 160x600: 0.553 -> 0.440 (tall structure keep +fix:headl -> tall spacing=0.75, rescue +opt)
- 5d4ab742cf657b21ef933c97 728x90: 0.513 -> 0.434 (banner scale=1.15 +opt -> banner scale=1.5 +opt)
- 5889bae595a7a863ddcc391f 728x90: 0.448 -> 0.373 (banner chips=stack +fix:pin to -> banner chips=stack +fix:pin to)
- 59b27d591350e8329300d8b3 728x90: 0.506 -> 0.445 (banner scale=1.3 +fix:pin to s -> banner scale=1.3, rescue +fix:)
- level1_warmup 160x600: 0.787 -> 0.735 (tall scale=1.5 +opt -> tall scale=1.5 +opt)
- 595256d795a7a863ddcde397 160x600: 0.392 -> 0.452 (tall scale=1.5 +fix:bolder, fi -> tall spacing=0.75 +opt)
- 5ea00c67499b85dcc778413e 160x600: 0.432 -> 0.499 (tall spacing=0.75 +fix:bolder, -> tall default +opt)
- 58a4091695a7a863ddcc6c53 160x600: 0.567 -> 0.646 (tall chips=corner, scale=1.3 + -> tall chips=corner, spacing=0.7)
- 58aed3c795a7a863ddcc88e4 160x600: 0.402 -> 0.484 (tall chips=corner, scale=1.3 + -> tall scale=1.5 +fix:tighter pl)
- 5952975a95a7a863ddce0319 160x600: 0.706 -> 0.788 (tall structure keep -> tall structure keep)
- 595298a695a7a863ddce047c 160x600: 0.706 -> 0.789 (tall structure keep -> tall structure keep)
- 5ea97608499b85dcc7d2ec78 728x90: 0.453 -> 0.546 (banner scale=1.5, fill +fix:ti -> banner default +opt)
- 5952983995a7a863ddce040b 728x90: 0.322 -> 0.484 (banner text=inline +opt -> banner structure keep +opt)
