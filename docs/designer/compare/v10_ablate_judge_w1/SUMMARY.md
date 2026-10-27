# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.607 | 0.606 |
| designer agreement >= 0.7 | 199 | 199 |
| centre error, mean | 0.141 | 0.142 |
| reading-order tau, mean | 0.702 | 0.698 |
| engine cases with a hard fail (judge) | 0 | 0 |
| engine cases with a hard fail (energy) | 0 | 0 |
| designer wins by judge score | 164 | 166 |
| judge score, mean | 87.54 | 87.44 |
| energy, mean (lower is better) | 13.16 | 13.26 |
| refined candidate wins | 369 | 369 |
| runtime p50 (s) | 0.52 | 0.53 |
| runtime p95 (s) | 1.28 | 1.29 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 9, down in 16, unchanged in 575 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.678 | 0.671 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.657 | 0.653 | 0 | 0 | 18 | 19 |
| 1000x1500 | 50 | 0.674 | 0.672 | 0 | 0 | 15 | 15 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 14 |
| 1600x900 | 50 | 0.578 | 0.576 | 0 | 0 | 11 | 11 |
| 1080x1080 | 50 | 0.714 | 0.714 | 0 | 0 | 9 | 9 |
| 1280x720 | 50 | 0.583 | 0.579 | 0 | 0 | 7 | 7 |
| 1600x400 | 50 | 0.537 | 0.534 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.538 | 0.536 | 0 | 0 | 14 | 15 |
| 820x312 | 50 | 0.552 | 0.552 | 0 | 0 | 13 | 14 |
| 160x600 | 50 | 0.592 | 0.593 | 0 | 0 | 19 | 18 |
| 728x90 | 50 | 0.490 | 0.493 | 0 | 0 | 19 | 18 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.611 | 0.609 |
| designer agreement >= 0.7 | 38 | 38 |
| centre error, mean | 0.142 | 0.143 |
| reading-order tau, mean | 0.713 | 0.706 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 28 | 30 |
| judge score, mean | 78.07 | 77.91 |
| energy, mean (lower is better) | 23.42 | 23.50 |
| refined candidate wins | 71 | 72 |
| runtime p50 (s) | 0.65 | 0.67 |
| runtime p95 (s) | 1.13 | 1.14 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 1, down in 3, unchanged in 116 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.676 | 0.676 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.643 | 0.635 | 0 | 0 | 2 | 2 |
| 1000x1500 | 10 | 0.658 | 0.658 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.683 | 0.683 | 0 | 0 | 1 | 1 |
| 1600x900 | 10 | 0.686 | 0.675 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.758 | 0.758 | 0 | 0 | 0 | 1 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.555 | 0.555 | 0 | 0 | 3 | 3 |
| 1584x396 | 10 | 0.525 | 0.525 | 0 | 0 | 3 | 4 |
| 820x312 | 10 | 0.507 | 0.507 | 0 | 0 | 3 | 3 |
| 160x600 | 10 | 0.515 | 0.511 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.457 | 0.457 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 591429a395a7a863ddcd7e39 1240x1754: 0.627 -> 0.404 (tall structure flip +opt -> tall scale=1.5)
- 59b26b3c1350e8329300d498 1000x1500: 0.514 -> 0.292 (tall scale=1.5 +fix:pin to sou -> tall structure keep +fix:pin t)
- 59b26b3c1350e8329300d498 1080x1920: 0.499 -> 0.287 (tall scale=1.5 +fix:pin to sou -> tall structure keep +fix:pin t)
- 59b26b3c1350e8329300d498 1240x1754: 0.470 -> 0.291 (tall scale=1.15 +fix:pin to so -> tall structure keep +fix:pin t)
- 5df213199fea0cc374af016c 1584x396: 0.539 -> 0.421 (banner chips=stack +fix:tighte -> banner chips=stack +fix:pin to)
- 59b26b3c1350e8329300d498 1280x720: 0.538 -> 0.421 (wide scale=1.5 +fix:pin to sou -> wide chips=corner +opt)
- 5947c25e95a7a863ddcdda6b 1600x900: 0.932 -> 0.824 (anchor fit scale=3.125 +opt -> anchor x1.12 scale=3.500 +opt)
- 5952998195a7a863ddce0560 1600x400: 0.760 -> 0.663 (anchor x1.25 scale=1.000 +opt -> banner structure keep)
- 5cebeb787d4459dfe1267619 160x600: 0.463 -> 0.469 (tall scale=1.15 +opt -> tall spacing=0.75 +opt)
- 592fbd6095a7a863ddcdb859 1600x900: 0.486 -> 0.493 (wide hero=stack, scale=1.3 +op -> wide structure keep +opt)
- 592fbd6095a7a863ddcdb859 1280x720: 0.486 -> 0.493 (wide hero=stack, scale=1.3 +op -> wide structure keep +opt)
- 5889bae595a7a863ddcc391f 1600x400: 0.477 -> 0.522 (banner chips=stack +fix:headli -> banner scale=1.5, fill +fix:he)
- 5952645b95a7a863ddcde7c9 1000x1500: 0.720 -> 0.765 (anchor x1.25 scale=1.562 -> anchor x1.12 scale=1.400 +opt)
- 5952645b95a7a863ddcde7c9 1240x1754: 0.658 -> 0.799 (tall structure keep +opt -> anchor x1.12 scale=1.637 +opt)
- 5952983995a7a863ddce040b 1000x1500: 0.355 -> 0.501 (tall scale=1.5 +opt -> tall structure flip +opt)
- 5952983995a7a863ddce040b 728x90: 0.322 -> 0.497 (banner text=inline +opt -> banner structure keep)
