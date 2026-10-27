# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.603 |
| designer agreement >= 0.7 | 199 | 198 |
| centre error, mean | 0.141 | 0.143 |
| reading-order tau, mean | 0.702 | 0.695 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 156 | 166 |
| judge score, mean | 87.54 | 87.30 |
| energy, mean (lower is better) | 13.16 | 13.38 |
| refined candidate wins | 369 | 360 |
| runtime p50 (s) | 0.40 | 0.41 |
| runtime p95 (s) | 0.97 | 0.98 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 29, down in 41, unchanged in 530 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.673 | 0 | 0 | 14 | 12 |
| 1080x1920 | 50 | 0.657 | 0.651 | 0 | 0 | 16 | 19 |
| 1000x1500 | 50 | 0.674 | 0.673 | 0 | 0 | 15 | 16 |
| 1080x1350 | 50 | 0.695 | 0.689 | 0 | 0 | 13 | 14 |
| 1600x900 | 50 | 0.578 | 0.576 | 0 | 0 | 11 | 12 |
| 1080x1080 | 50 | 0.714 | 0.708 | 0 | 0 | 10 | 8 |
| 1280x720 | 50 | 0.583 | 0.579 | 0 | 0 | 7 | 8 |
| 1600x400 | 50 | 0.537 | 0.533 | 0 | 0 | 11 | 14 |
| 1584x396 | 50 | 0.538 | 0.537 | 0 | 0 | 13 | 15 |
| 820x312 | 50 | 0.552 | 0.547 | 0 | 0 | 12 | 12 |
| 160x600 | 50 | 0.592 | 0.589 | 0 | 0 | 17 | 19 |
| 728x90 | 50 | 0.490 | 0.487 | 0 | 0 | 17 | 17 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.611 | 0.610 |
| designer agreement >= 0.7 | 38 | 38 |
| centre error, mean | 0.142 | 0.140 |
| reading-order tau, mean | 0.713 | 0.704 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 30 | 33 |
| judge score, mean | 78.07 | 77.64 |
| energy, mean (lower is better) | 23.42 | 23.32 |
| refined candidate wins | 71 | 74 |
| runtime p50 (s) | 0.49 | 0.50 |
| runtime p95 (s) | 0.85 | 0.84 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 8, down in 9, unchanged in 103 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.676 | 0.676 | 0 | 0 | 1 | 2 |
| 1080x1920 | 10 | 0.643 | 0.646 | 0 | 0 | 2 | 3 |
| 1000x1500 | 10 | 0.658 | 0.651 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.683 | 0.683 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.672 | 0 | 0 | 3 | 4 |
| 1080x1080 | 10 | 0.758 | 0.758 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.670 | 0.667 | 0 | 0 | 3 | 3 |
| 1600x400 | 10 | 0.555 | 0.544 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.525 | 0.546 | 0 | 0 | 4 | 3 |
| 820x312 | 10 | 0.507 | 0.509 | 0 | 0 | 3 | 4 |
| 160x600 | 10 | 0.515 | 0.511 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.457 | 0.457 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 591429a395a7a863ddcd7e39 1080x1080: 0.677 -> 0.396 (square structure flip -> square structure keep)
- 5fa50e1ea637ee11e399a87f 820x312: 0.656 -> 0.416 (wide scale=1.5 +opt -> wide structure flip)
- 593011fc95a7a863ddcdbf9a 728x90: 0.443 -> 0.211 (banner spacing=0.75 +opt -> banner structure flip +opt)
- 59b26b3c1350e8329300d498 1080x1080: 0.516 -> 0.284 (square scale=1.5 +fix:pin to s -> square structure flip +opt)
- 59b26b3c1350e8329300d498 1000x1500: 0.514 -> 0.287 (tall scale=1.5 +fix:pin to sou -> tall structure flip +fix:pin t)
- 591429a395a7a863ddcd7e39 1240x1754: 0.627 -> 0.402 (tall structure flip +opt -> tall scale=1.5, fill)
- 591429a395a7a863ddcd7e39 1080x1350: 0.630 -> 0.406 (tall structure flip +opt -> tall structure keep +opt)
- 59b26b3c1350e8329300d498 1080x1350: 0.506 -> 0.292 (tall scale=1.5 +fix:pin to sou -> tall structure flip +opt)
- 5ea00c67499b85dcc778413e 1080x1920: 0.663 -> 0.752 (tall default -> tall default +opt)
- 5ca7253923c829c8213e6cd2 1080x1350: 0.436 -> 0.550 (tall chips=corner, scale=1.3 + -> tall structure flip +opt)
- 5952645b95a7a863ddcde7c9 1240x1754: 0.658 -> 0.799 (tall structure keep +opt -> anchor x1.12 scale=1.637 +opt)
- 5952983995a7a863ddce040b 1000x1500: 0.355 -> 0.501 (tall scale=1.5 +opt -> tall structure flip +opt)
- 5952983995a7a863ddce040b 1240x1754: 0.346 -> 0.498 (tall scale=1.5 +opt -> tall structure flip +opt)
- 599ecb061350e83293007738 1080x1080: 0.533 -> 0.696 (square chips=corner +opt -> square structure keep)
- 5952983995a7a863ddce040b 728x90: 0.322 -> 0.497 (banner text=inline +opt -> banner structure keep)
- 5947c25e95a7a863ddcdda6b 1584x396: 0.394 -> 0.598 (banner text=column, scale=1.3  -> banner hero=right, text=inline)
