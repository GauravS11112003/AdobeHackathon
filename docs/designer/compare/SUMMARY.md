# Designer references vs engine

240 (design, format) pairs. Scores are the engine's own scorer (no pixels).

**Headline numbers:** designer agreement of the engine's winner **0.601** (best judged candidate 0.711); references tripping a hard fail **10/240**; designer scores higher in 65/240; engine hard fails 0/240.

| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | designer hard fails | engine hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 88.6 | 91.6 | 3/20 | 141 | 135 | 0.73 | 0.76 | 36 | 36 | 0 | 0 |
| 1080x1920 | 20 | 88.0 | 91.5 | 2/20 | 126 | 140 | 0.71 | 0.75 | 32 | 36 | 0 | 0 |
| 1000x1500 | 20 | 88.3 | 91.9 | 3/20 | 114 | 113 | 0.73 | 0.77 | 29 | 30 | 0 | 0 |
| 1080x1350 | 20 | 88.9 | 92.0 | 4/20 | 120 | 112 | 0.73 | 0.74 | 30 | 30 | 0 | 0 |
| 1600x900 | 20 | 87.6 | 89.7 | 6/20 | 114 | 117 | 0.73 | 0.77 | 32 | 30 | 0 | 0 |
| 1080x1080 | 20 | 88.7 | 90.8 | 4/20 | 106 | 96 | 0.71 | 0.71 | 28 | 26 | 0 | 0 |
| 1280x720 | 20 | 87.6 | 90.5 | 6/20 | 91 | 96 | 0.73 | 0.81 | 26 | 26 | 0 | 0 |
| 1600x400 | 20 | -13.2 | 89.8 | 6/20 | 78 | 80 | 0.73 | 0.76 | 20 | 22 | 2 | 0 |
| 1584x396 | 20 | -13.1 | 89.9 | 6/20 | 77 | 80 | 0.73 | 0.77 | 20 | 22 | 2 | 0 |
| 820x312 | 20 | -13.4 | 89.0 | 9/20 | 47 | 48 | 0.75 | 0.79 | 13 | 14 | 2 | 0 |
| 160x600 | 20 | -13.2 | 87.8 | 8/20 | 31 | 28 | 0.80 | 0.76 | 9 | 9 | 2 | 0 |
| 728x90 | 20 | -14.4 | 87.6 | 8/20 | 28 | 24 | 0.81 | 0.79 | 9 | 8 | 2 | 0 |

## Designer agreement (eval/metrics.designer_agreement; 1 = the reference itself)

| format | n | agreement (winner) | agreement (best candidate) | winner is best | centre error | within 10 % | reading-order tau | size rho | winner >= 0.7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 0.684 | 0.778 | 2/20 | 0.096 | 0.37 | 0.76 | 0.94 | 8/20 |
| 1080x1920 | 20 | 0.657 | 0.786 | 3/20 | 0.107 | 0.34 | 0.71 | 0.91 | 8/20 |
| 1000x1500 | 20 | 0.687 | 0.774 | 6/20 | 0.099 | 0.39 | 0.76 | 0.94 | 10/20 |
| 1080x1350 | 20 | 0.699 | 0.790 | 5/20 | 0.100 | 0.43 | 0.80 | 0.92 | 10/20 |
| 1600x900 | 20 | 0.551 | 0.692 | 2/20 | 0.164 | 0.16 | 0.63 | 0.90 | 5/20 |
| 1080x1080 | 20 | 0.758 | 0.823 | 10/20 | 0.078 | 0.56 | 0.78 | 0.89 | 15/20 |
| 1280x720 | 20 | 0.556 | 0.701 | 2/20 | 0.169 | 0.18 | 0.62 | 0.91 | 4/20 |
| 1600x400 | 20 | 0.503 | 0.638 | 2/20 | 0.191 | 0.13 | 0.49 | 0.92 | 4/20 |
| 1584x396 | 20 | 0.505 | 0.635 | 2/20 | 0.192 | 0.13 | 0.52 | 0.92 | 4/20 |
| 820x312 | 20 | 0.551 | 0.647 | 3/20 | 0.173 | 0.21 | 0.60 | 0.83 | 6/20 |
| 160x600 | 20 | 0.592 | 0.698 | 2/20 | 0.124 | 0.19 | 0.62 | 0.87 | 3/20 |
| 728x90 | 20 | 0.466 | 0.561 | 5/20 | 0.202 | 0.09 | 0.47 | 0.85 | 2/20 |
| **all** | 240 | 0.601 | 0.711 | 44/240 | 0.141 | 0.26 | 0.65 | 0.90 | 79/240 |

### By design

| design | n | agreement (winner) | agreement (best) | winner >= 0.7 | structure wins | designer hard fails |
|---|---:|---:|---:|---:|---:|---:|
| 58a4091695a7a863ddcc6c53 | 12 | 0.426 | 0.487 | 0/12 | 0/12 | 0 |
| 5952983995a7a863ddce040b | 12 | 0.479 | 0.717 | 2/12 | 3/12 | 0 |
| 5c346ef7048d064dbc063111 | 12 | 0.489 | 0.718 | 1/12 | 7/12 | 5 |
| 5952645b95a7a863ddcde7c9 | 12 | 0.503 | 0.616 | 2/12 | 8/12 | 0 |
| 5953611d95a7a863ddce13e0 | 12 | 0.525 | 0.649 | 1/12 | 0/12 | 0 |
| 595256d795a7a863ddcde397 | 12 | 0.529 | 0.672 | 3/12 | 7/12 | 3 |
| 5e68e28db04a3d1f19b3c3fc | 12 | 0.543 | 0.630 | 3/12 | 0/12 | 0 |
| 59b27d591350e8329300d8b3 | 12 | 0.554 | 0.638 | 3/12 | 0/12 | 0 |
| 593112f495a7a863ddcdc5a7 | 12 | 0.572 | 0.721 | 2/12 | 3/12 | 0 |
| 5e709a0f4b3890eb0783cb50 | 12 | 0.596 | 0.740 | 4/12 | 1/12 | 0 |
| 5ca7253923c829c8213e6cd2 | 12 | 0.629 | 0.739 | 6/12 | 1/12 | 0 |
| 5e8d96cb4b3890eb071c683d | 12 | 0.639 | 0.699 | 4/12 | 2/12 | 0 |
| level3_advanced | 12 | 0.639 | 0.740 | 4/12 | 1/12 | 0 |
| level2_core | 12 | 0.671 | 0.736 | 5/12 | 8/12 | 2 |
| 59b27ce91350e8329300d847 | 12 | 0.674 | 0.792 | 5/12 | 0/12 | 0 |
| 5952492d95a7a863ddcddfa0 | 12 | 0.681 | 0.791 | 5/12 | 5/12 | 0 |
| 59b26b291350e8329300d483 | 12 | 0.703 | 0.766 | 7/12 | 10/12 | 0 |
| 5888cec295a7a863ddcc24c9 | 12 | 0.704 | 0.737 | 6/12 | 2/12 | 0 |
| 59b27f4d1350e8329300daea | 12 | 0.723 | 0.776 | 7/12 | 9/12 | 0 |
| level1_warmup | 12 | 0.736 | 0.843 | 9/12 | 0/12 | 0 |

## Designer references that still trip a hard fail

- 595256d795a7a863ddcde397 160x600: el_07 cta font 7 below readable 12
- 595256d795a7a863ddcde397 728x90: el_07 cta font 6 below readable 8
- 595256d795a7a863ddcde397 820x312: el_07 cta font 9 below readable 12
- 5c346ef7048d064dbc063111 1584x396: el_02 collides with el_04 (1862px²)
- 5c346ef7048d064dbc063111 1600x400: el_02 collides with el_04 (1900px²)
- 5c346ef7048d064dbc063111 160x600: el_02 collides with el_04 (320px²)
- 5c346ef7048d064dbc063111 728x90: el_02 collides with el_04 (250px²)
- 5c346ef7048d064dbc063111 820x312: el_02 collides with el_04 (1156px²)
- level2_core 1584x396: logo collides with product (1617px²)
- level2_core 1600x400: logo collides with product (1650px²)

## Score components, mean (designer vs engine)

| component | designer | engine | gap |
|---|---:|---:|---:|
| faith.anchors | 0.609 | 0.605 | +0.004 |
| faith.hierarchy | 0.965 | 0.986 | -0.020 |
| faith.order | 0.904 | 0.893 | +0.011 |
| faith.scale | 0.751 | 0.795 | -0.044 |
| layout.alignment | 0.562 | 0.579 | -0.017 |
| layout.balance | 0.878 | 0.901 | -0.023 |
| layout.cohesion | 0.919 | 0.964 | -0.045 |
| layout.fill | 0.823 | 0.844 | -0.020 |
| layout.margins | 0.710 | 0.943 | -0.233 |
| layout.size | 0.851 | 0.869 | -0.019 |
| layout.spacing | 0.800 | 0.904 | -0.104 |
| read.contrast | 0.830 | 0.835 | -0.005 |
| read.lines | 0.928 | 0.926 | +0.002 |
| read.presence | 0.938 | 0.948 | -0.010 |
| read.size | 0.939 | 0.948 | -0.009 |

## Engine hard fails on cases where the designer reference is clean

