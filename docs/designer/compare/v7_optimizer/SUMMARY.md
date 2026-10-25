# Designer references: optimiser off vs on (v7)

720 (design, format) cases; 120 belong to the sealed hold-out designs and are reported separately below. Scores are the engine's own judge (no pixels); agreement is eval/metrics.designer_agreement (1 = the reference itself).

## Tuning set (batch one + batch two without the hold-out) (600 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.587 | 0.595 |
| designer agreement >= 0.7 | 172 | 179 |
| centre error, mean | 0.148 | 0.145 |
| reading-order tau, mean | 0.651 | 0.665 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 167 | 127 |
| judge score, mean | 88.22 | 89.18 |
| energy, mean (lower is better) | 17.93 | 15.44 |
| refined candidate wins | 0 | 387 |
| runtime p50 (s) | 0.09 | 0.38 |
| runtime p95 (s) | 0.33 | 0.83 |

references with a hard fail under the current judge: 47; under the energy: 47; reference energy mean 110.10

agreement up in 219, down in 153, unchanged in 228 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.671 | 0.676 | 0 | 0 | 15 | 12 |
| 1080x1920 | 50 | 0.625 | 0.647 | 0 | 0 | 15 | 13 |
| 1000x1500 | 50 | 0.660 | 0.666 | 0 | 0 | 14 | 9 |
| 1080x1350 | 50 | 0.672 | 0.678 | 0 | 0 | 13 | 11 |
| 1600x900 | 50 | 0.554 | 0.568 | 0 | 0 | 12 | 11 |
| 1080x1080 | 50 | 0.696 | 0.694 | 0 | 0 | 11 | 7 |
| 1280x720 | 50 | 0.554 | 0.562 | 0 | 0 | 11 | 8 |
| 1600x400 | 50 | 0.505 | 0.512 | 0 | 0 | 13 | 11 |
| 1584x396 | 50 | 0.509 | 0.520 | 0 | 0 | 13 | 11 |
| 820x312 | 50 | 0.551 | 0.555 | 0 | 0 | 13 | 9 |
| 160x600 | 50 | 0.579 | 0.579 | 1 | 1 | 18 | 12 |
| 728x90 | 50 | 0.470 | 0.487 | 0 | 0 | 19 | 13 |

## HOLD-OUT (10 sealed designs, never tuned on) (120 cases)

| metric | optimiser off | optimiser on |
|---|---:|---:|
| designer agreement, mean | 0.595 | 0.603 |
| designer agreement >= 0.7 | 34 | 35 |
| centre error, mean | 0.148 | 0.146 |
| reading-order tau, mean | 0.688 | 0.716 |
| engine cases with a hard fail (judge) | 1 | 1 |
| engine cases with a hard fail (energy) | 1 | 1 |
| designer wins by judge score | 31 | 27 |
| judge score, mean | 79.93 | 81.15 |
| energy, mean (lower is better) | 26.10 | 23.18 |
| refined candidate wins | 0 | 78 |
| runtime p50 (s) | 0.12 | 0.46 |
| runtime p95 (s) | 0.35 | 0.83 |

references with a hard fail under the current judge: 12; under the energy: 12; reference energy mean 132.05

agreement up in 41, down in 35, unchanged in 44 cases

| format | n | agreement off | agreement on | hard off | hard on | designer wins off | designer wins on |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.653 | 0.666 | 0 | 0 | 1 | 1 |
| 1080x1920 | 10 | 0.597 | 0.621 | 0 | 0 | 2 | 2 |
| 1000x1500 | 10 | 0.634 | 0.662 | 0 | 0 | 1 | 1 |
| 1080x1350 | 10 | 0.660 | 0.669 | 0 | 0 | 2 | 0 |
| 1600x900 | 10 | 0.652 | 0.662 | 0 | 0 | 3 | 3 |
| 1080x1080 | 10 | 0.751 | 0.758 | 0 | 0 | 1 | 1 |
| 1280x720 | 10 | 0.652 | 0.654 | 0 | 0 | 3 | 2 |
| 1600x400 | 10 | 0.518 | 0.520 | 0 | 0 | 4 | 4 |
| 1584x396 | 10 | 0.518 | 0.520 | 0 | 0 | 4 | 4 |
| 820x312 | 10 | 0.501 | 0.502 | 0 | 0 | 4 | 3 |
| 160x600 | 10 | 0.545 | 0.545 | 1 | 1 | 2 | 2 |
| 728x90 | 10 | 0.461 | 0.451 | 0 | 0 | 4 | 4 |

## Largest agreement changes (on - off)

- 5952975a95a7a863ddce0319 728x90: 0.922 -> 0.533 (banner structure flip -> banner spacing=0.75 +opt)
- 595298a695a7a863ddce047c 1584x396: 0.780 -> 0.506 (banner structure flip -> banner scale=1.15 +opt)
- 595298a695a7a863ddce047c 1600x400: 0.780 -> 0.508 (banner structure flip -> banner scale=1.15 +opt)
- 5ca7253923c829c8213e6cd2 1600x400: 0.729 -> 0.518 (banner hero=right -> banner structure keep +opt)
- 5ca7253923c829c8213e6cd2 1584x396: 0.729 -> 0.523 (banner hero=right -> banner structure keep +opt)
- 59b27ce91350e8329300d847 1080x1350: 0.652 -> 0.457 (tall scale=1.3 -> tall structure keep +opt)
- 599ecb061350e83293007738 1080x1080: 0.696 -> 0.533 (square structure keep -> square chips=corner +opt)
- 5d4ab742cf657b21ef933c97 1000x1500: 0.804 -> 0.647 (tall structure keep -> tall scale=1.5 +opt)
- 5952645b95a7a863ddcde7c9 1080x1350: 0.505 -> 0.751 (tall chips=corner -> anchor x1.12 scale=1.260 +opt)
- 593011fc95a7a863ddcdbf9a 728x90: 0.211 -> 0.460 (banner structure flip -> banner scale=1.15 +opt)
- 59b27ce91350e8329300d847 1600x400: 0.501 -> 0.769 (banner text=inline, spacing=0. -> banner scale=1.15 +opt)
- 59b27ce91350e8329300d847 1584x396: 0.499 -> 0.769 (banner text=inline, spacing=0. -> banner scale=1.15 +opt)
- 59526a6495a7a863ddcdead9 1080x1350: 0.413 -> 0.688 (tall scale=1.5 -> tall chips=corner, spacing=0.7)
- 59526a6495a7a863ddcdead9 1584x396: 0.611 -> 0.901 (banner structure keep -> anchor x1.4 scale=2.640 +opt)
- 5914233995a7a863ddcd7772 1080x1920: 0.635 -> 0.930 (tall structure keep -> anchor fit scale=2.000 +opt)
- 5eec925b499b85dcc7e50220 728x90: 0.419 -> 0.912 (banner default -> anchor x1.25 scale=0.589 +opt)
