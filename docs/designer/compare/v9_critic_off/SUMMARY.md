# Designer references vs engine

240 (design, format) pairs. Scores are the engine's own scorer (no pixels).

**Headline numbers:** designer agreement of the engine's winner **0.615** (best judged candidate 0.715); references tripping a hard fail **10/240**; designer scores higher in 65/240; engine hard fails 0/240.

| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | designer hard fails | engine hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 87.3 | 90.3 | 4/20 | 141 | 137 | 0.73 | 0.75 | 36 | 36 | 0 | 0 |
| 1080x1920 | 20 | 86.7 | 89.5 | 4/20 | 126 | 133 | 0.71 | 0.74 | 32 | 35 | 0 | 0 |
| 1000x1500 | 20 | 87.0 | 90.8 | 3/20 | 114 | 117 | 0.73 | 0.75 | 29 | 30 | 0 | 0 |
| 1080x1350 | 20 | 87.4 | 90.8 | 4/20 | 120 | 112 | 0.73 | 0.73 | 30 | 30 | 0 | 0 |
| 1600x900 | 20 | 85.7 | 87.2 | 6/20 | 114 | 120 | 0.73 | 0.72 | 32 | 30 | 0 | 0 |
| 1080x1080 | 20 | 87.6 | 89.6 | 4/20 | 106 | 96 | 0.71 | 0.69 | 28 | 25 | 0 | 0 |
| 1280x720 | 20 | 85.7 | 87.7 | 3/20 | 91 | 97 | 0.73 | 0.77 | 26 | 26 | 0 | 0 |
| 1600x400 | 20 | -16.0 | 86.9 | 6/20 | 78 | 79 | 0.73 | 0.78 | 20 | 21 | 2 | 0 |
| 1584x396 | 20 | -15.8 | 86.6 | 7/20 | 77 | 77 | 0.73 | 0.79 | 20 | 21 | 2 | 0 |
| 820x312 | 20 | -15.1 | 86.6 | 9/20 | 47 | 49 | 0.75 | 0.81 | 13 | 13 | 2 | 0 |
| 160x600 | 20 | -14.9 | 86.0 | 8/20 | 31 | 28 | 0.80 | 0.85 | 9 | 9 | 2 | 0 |
| 728x90 | 20 | -17.8 | 84.4 | 7/20 | 28 | 25 | 0.81 | 0.78 | 9 | 8 | 2 | 0 |

## Designer agreement (eval/metrics.designer_agreement; 1 = the reference itself)

| format | n | agreement (winner) | agreement (best candidate) | winner is best | centre error | within 10 % | reading-order tau | size rho | winner >= 0.7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 0.670 | 0.785 | 1/20 | 0.105 | 0.36 | 0.75 | 0.94 | 8/20 |
| 1080x1920 | 20 | 0.673 | 0.794 | 3/20 | 0.111 | 0.40 | 0.77 | 0.91 | 10/20 |
| 1000x1500 | 20 | 0.687 | 0.784 | 4/20 | 0.101 | 0.40 | 0.77 | 0.94 | 9/20 |
| 1080x1350 | 20 | 0.703 | 0.795 | 5/20 | 0.102 | 0.45 | 0.81 | 0.93 | 11/20 |
| 1600x900 | 20 | 0.603 | 0.695 | 3/20 | 0.145 | 0.25 | 0.74 | 0.89 | 6/20 |
| 1080x1080 | 20 | 0.775 | 0.824 | 8/20 | 0.072 | 0.59 | 0.86 | 0.89 | 15/20 |
| 1280x720 | 20 | 0.609 | 0.704 | 4/20 | 0.143 | 0.26 | 0.72 | 0.90 | 7/20 |
| 1600x400 | 20 | 0.518 | 0.639 | 4/20 | 0.190 | 0.16 | 0.49 | 0.91 | 4/20 |
| 1584x396 | 20 | 0.511 | 0.635 | 2/20 | 0.194 | 0.14 | 0.51 | 0.92 | 4/20 |
| 820x312 | 20 | 0.547 | 0.650 | 1/20 | 0.166 | 0.15 | 0.70 | 0.86 | 5/20 |
| 160x600 | 20 | 0.614 | 0.704 | 1/20 | 0.124 | 0.26 | 0.72 | 0.85 | 4/20 |
| 728x90 | 20 | 0.467 | 0.567 | 1/20 | 0.205 | 0.09 | 0.44 | 0.86 | 2/20 |
| **all** | 240 | 0.615 | 0.715 | 37/240 | 0.138 | 0.29 | 0.69 | 0.90 | 85/240 |

### By design

| design | n | agreement (winner) | agreement (best) | winner >= 0.7 | structure wins | designer hard fails |
|---|---:|---:|---:|---:|---:|---:|
| 58a4091695a7a863ddcc6c53 | 12 | 0.473 | 0.505 | 0/12 | 0/12 | 0 |
| 5c346ef7048d064dbc063111 | 12 | 0.502 | 0.722 | 1/12 | 7/12 | 5 |
| 5952645b95a7a863ddcde7c9 | 12 | 0.539 | 0.620 | 3/12 | 10/12 | 0 |
| 5952983995a7a863ddce040b | 12 | 0.540 | 0.718 | 4/12 | 4/12 | 0 |
| 595256d795a7a863ddcde397 | 12 | 0.550 | 0.673 | 3/12 | 7/12 | 3 |
| 5953611d95a7a863ddce13e0 | 12 | 0.551 | 0.649 | 3/12 | 5/12 | 0 |
| 5e68e28db04a3d1f19b3c3fc | 12 | 0.553 | 0.630 | 3/12 | 2/12 | 0 |
| 59b27d591350e8329300d8b3 | 12 | 0.562 | 0.638 | 4/12 | 0/12 | 0 |
| 5ca7253923c829c8213e6cd2 | 12 | 0.599 | 0.740 | 4/12 | 3/12 | 0 |
| 593112f495a7a863ddcdc5a7 | 12 | 0.605 | 0.722 | 2/12 | 2/12 | 0 |
| 5e709a0f4b3890eb0783cb50 | 12 | 0.610 | 0.746 | 4/12 | 2/12 | 0 |
| 59b27ce91350e8329300d847 | 12 | 0.629 | 0.828 | 5/12 | 8/12 | 0 |
| 5e8d96cb4b3890eb071c683d | 12 | 0.653 | 0.700 | 4/12 | 2/12 | 0 |
| level3_advanced | 12 | 0.663 | 0.743 | 5/12 | 1/12 | 0 |
| level2_core | 12 | 0.678 | 0.740 | 5/12 | 8/12 | 2 |
| 5952492d95a7a863ddcddfa0 | 12 | 0.690 | 0.792 | 6/12 | 5/12 | 0 |
| 59b26b291350e8329300d483 | 12 | 0.702 | 0.766 | 7/12 | 10/12 | 0 |
| 59b27f4d1350e8329300daea | 12 | 0.720 | 0.778 | 7/12 | 9/12 | 0 |
| 5888cec295a7a863ddcc24c9 | 12 | 0.723 | 0.743 | 6/12 | 3/12 | 0 |
| level1_warmup | 12 | 0.756 | 0.843 | 9/12 | 0/12 | 0 |

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
| faith.anchors | 0.609 | 0.671 | -0.062 |
| faith.hierarchy | 0.965 | 0.987 | -0.021 |
| faith.order | 0.904 | 0.917 | -0.012 |
| faith.rows | 1.000 | 1.000 | +0.000 |
| faith.scale | 0.751 | 0.807 | -0.056 |
| layout.alignment | 0.562 | 0.601 | -0.039 |
| layout.balance | 0.878 | 0.894 | -0.016 |
| layout.cohesion | 0.919 | 0.965 | -0.046 |
| layout.fill | 0.823 | 0.832 | -0.009 |
| layout.margins | 0.710 | 0.918 | -0.209 |
| layout.size | 0.851 | 0.869 | -0.018 |
| layout.spacing | 0.800 | 0.872 | -0.072 |
| read.contrast | 0.830 | 0.829 | +0.001 |
| read.lines | 0.928 | 0.926 | +0.001 |
| read.presence | 0.938 | 0.953 | -0.015 |
| read.size | 0.939 | 0.952 | -0.013 |

## Engine hard fails on cases where the designer reference is clean

