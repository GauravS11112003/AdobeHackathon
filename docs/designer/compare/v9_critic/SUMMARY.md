# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.608 | 0.608 |
| designer agreement >= 0.7 | 197 | 198 |
| centre error, mean | 0.140 | 0.140 |
| reading-order tau, mean | 0.704 | 0.702 |
| engine cases with a hard fail (judge) | 1 | 0 |
| engine cases with a hard fail (energy) | 1 | 0 |
| designer wins by judge score | 167 | 165 |
| judge score, mean | 85.74 | 87.53 |
| energy, mean (lower is better) | 14.67 | 13.12 |
| refined candidate wins | 375 | 373 |
| runtime p50 (s) | 0.33 | 0.34 |
| runtime p95 (s) | 0.74 | 0.85 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 49, down in 41, unchanged in 510 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.682 | 0.684 | 0 | 0 | 13 | 13 |
| 1080x1920 | 50 | 0.658 | 0.657 | 0 | 0 | 18 | 18 |
| 1000x1500 | 50 | 0.677 | 0.677 | 0 | 0 | 14 | 14 |
| 1080x1350 | 50 | 0.695 | 0.695 | 0 | 0 | 13 | 13 |
| 1600x900 | 50 | 0.574 | 0.575 | 0 | 0 | 12 | 12 |
| 1080x1080 | 50 | 0.714 | 0.715 | 0 | 0 | 10 | 9 |
| 1280x720 | 50 | 0.578 | 0.579 | 0 | 0 | 8 | 8 |
| 1600x400 | 50 | 0.531 | 0.537 | 0 | 0 | 13 | 13 |
| 1584x396 | 50 | 0.535 | 0.538 | 0 | 0 | 14 | 14 |
| 820x312 | 50 | 0.557 | 0.552 | 0 | 0 | 15 | 14 |
| 160x600 | 50 | 0.596 | 0.594 | 1 | 0 | 18 | 18 |
| 728x90 | 50 | 0.497 | 0.490 | 0 | 0 | 19 | 19 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.610 | 0.614 |
| designer agreement >= 0.7 | 36 | 38 |
| centre error, mean | 0.142 | 0.140 |
| reading-order tau, mean | 0.734 | 0.727 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 33 | 29 |
| judge score, mean | 77.59 | 77.97 |
| energy, mean (lower is better) | 22.87 | 23.13 |
| refined candidate wins | 77 | 74 |
| runtime p50 (s) | 0.42 | 0.42 |
| runtime p95 (s) | 0.68 | 0.77 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 13, down in 9, unchanged in 98 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.666 | 0.678 | 0 | 0 | 2 | 2 |
| 1080x1920 | 10 | 0.635 | 0.634 | 0 | 0 | 2 | 1 |
| 1000x1500 | 10 | 0.679 | 0.690 | 0 | 0 | 2 | 2 |
| 1080x1350 | 10 | 0.678 | 0.689 | 0 | 0 | 2 | 1 |
| 1600x900 | 10 | 0.686 | 0.686 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.758 | 0.753 | 0 | 0 | 1 | 0 |
| 1280x720 | 10 | 0.670 | 0.670 | 0 | 0 | 2 | 2 |
| 1600x400 | 10 | 0.532 | 0.558 | 0 | 0 | 4 | 3 |
| 1584x396 | 10 | 0.534 | 0.528 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.506 | 0.513 | 0 | 0 | 4 | 4 |
| 160x600 | 10 | 0.527 | 0.519 | 1 | 1 | 3 | 3 |
| 728x90 | 10 | 0.454 | 0.456 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 5ca7253923c829c8213e6cd2 728x90: 0.729 -> 0.372 (banner hero=right, text=column -> banner scale=1.5 +fix:tighter )
- 5cebeb787d4459dfe1267619 820x312: 0.617 -> 0.370 (wide hero=right +opt -> wide scale=1.5 +fix:pin to sou)
- 5889910495a7a863ddcc341b 160x600: 0.583 -> 0.424 (tall chips=corner, scale=1.3 -> tall chips=corner, scale=1.3 +)
- 5e8d96cb4b3890eb071c683d 1584x396: 0.564 -> 0.465 (banner spacing=0.75 -> banner default +fix:pin to sou)
- 5e8d96cb4b3890eb071c683d 1600x400: 0.611 -> 0.518 (banner scale=1.5, fill -> banner scale=1.5, fill +fix:pi)
- 5d5ec02dcf657b21effed4f3 1080x1920: 0.462 -> 0.380 (tall structure keep +opt -> tall scale=1.5, fill +fix:tigh)
- 59b26b3c1350e8329300d498 1240x1754: 0.543 -> 0.470 (tall scale=1.5 +opt -> tall scale=1.15 +fix:pin to so)
- 5914233995a7a863ddcd7772 160x600: 0.617 -> 0.546 (tall structure keep +opt -> tall structure keep +fix:cta o)
- 5947c25e95a7a863ddcdda6b 1080x1350: 0.421 -> 0.526 (tall scale=1.5, fill +opt -> tall scale=1.5 +fix:pin to sou)
- level3_advanced 820x312: 0.512 -> 0.622 (wide scale=1.5, fill -> wide scale=1.5, fill +fix:pin )
- 5947c25e95a7a863ddcdda6b 1000x1500: 0.405 -> 0.516 (tall scale=1.5, fill +opt -> tall scale=1.5 +fix:pin to sou)
- 5947c25e95a7a863ddcdda6b 1240x1754: 0.411 -> 0.528 (tall scale=1.5, fill +opt -> tall scale=1.5 +fix:pin to sou)
- 5952645b95a7a863ddcde7c9 1240x1754: 0.658 -> 0.799 (tall structure keep +opt -> anchor x1.12 scale=1.637 +opt)
- level3_advanced 1584x396: 0.494 -> 0.689 (banner text=column +opt -> banner text=column, scale=1.3 )
- level3_advanced 1600x400: 0.498 -> 0.696 (banner text=column +opt -> banner text=column, scale=1.3 )
- 5947c25e95a7a863ddcdda6b 1600x400: 0.447 -> 0.703 (banner text=inline, spacing=0. -> banner chips=stack +fix:tighte)
