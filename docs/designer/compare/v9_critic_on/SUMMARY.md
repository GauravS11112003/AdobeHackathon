# Designer references vs engine

240 (design, format) pairs. Scores are the engine's own scorer (no pixels).

**Headline numbers:** designer agreement of the engine's winner **0.617** (best judged candidate 0.717); references tripping a hard fail **10/240**; designer scores higher in 63/240; engine hard fails 0/240.

| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | designer hard fails | engine hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 87.3 | 90.3 | 4/20 | 141 | 134 | 0.73 | 0.73 | 36 | 36 | 0 | 0 |
| 1080x1920 | 20 | 86.7 | 89.5 | 4/20 | 126 | 133 | 0.71 | 0.74 | 32 | 35 | 0 | 0 |
| 1000x1500 | 20 | 87.0 | 90.7 | 3/20 | 114 | 118 | 0.73 | 0.75 | 29 | 29 | 0 | 0 |
| 1080x1350 | 20 | 87.4 | 90.8 | 4/20 | 120 | 112 | 0.73 | 0.73 | 30 | 30 | 0 | 0 |
| 1600x900 | 20 | 85.7 | 87.4 | 6/20 | 114 | 117 | 0.73 | 0.71 | 32 | 30 | 0 | 0 |
| 1080x1080 | 20 | 87.6 | 89.6 | 3/20 | 106 | 96 | 0.71 | 0.69 | 28 | 25 | 0 | 0 |
| 1280x720 | 20 | 85.7 | 87.9 | 3/20 | 91 | 97 | 0.73 | 0.76 | 26 | 26 | 0 | 0 |
| 1600x400 | 20 | -16.0 | 87.2 | 6/20 | 78 | 79 | 0.73 | 0.77 | 20 | 21 | 2 | 0 |
| 1584x396 | 20 | -15.8 | 87.1 | 7/20 | 77 | 77 | 0.73 | 0.79 | 20 | 21 | 2 | 0 |
| 820x312 | 20 | -15.1 | 86.9 | 8/20 | 47 | 48 | 0.75 | 0.82 | 13 | 13 | 2 | 0 |
| 160x600 | 20 | -14.9 | 86.1 | 8/20 | 31 | 28 | 0.80 | 0.85 | 9 | 9 | 2 | 0 |
| 728x90 | 20 | -17.8 | 84.7 | 7/20 | 28 | 26 | 0.81 | 0.79 | 9 | 8 | 2 | 0 |

## Designer agreement (eval/metrics.designer_agreement; 1 = the reference itself)

| format | n | agreement (winner) | agreement (best candidate) | winner is best | centre error | within 10 % | reading-order tau | size rho | winner >= 0.7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 0.679 | 0.786 | 1/20 | 0.104 | 0.39 | 0.75 | 0.94 | 9/20 |
| 1080x1920 | 20 | 0.673 | 0.795 | 3/20 | 0.111 | 0.40 | 0.77 | 0.91 | 10/20 |
| 1000x1500 | 20 | 0.690 | 0.785 | 4/20 | 0.099 | 0.40 | 0.77 | 0.94 | 10/20 |
| 1080x1350 | 20 | 0.703 | 0.796 | 5/20 | 0.102 | 0.45 | 0.81 | 0.93 | 11/20 |
| 1600x900 | 20 | 0.604 | 0.695 | 3/20 | 0.145 | 0.25 | 0.74 | 0.89 | 7/20 |
| 1080x1080 | 20 | 0.776 | 0.824 | 8/20 | 0.072 | 0.59 | 0.86 | 0.90 | 15/20 |
| 1280x720 | 20 | 0.612 | 0.704 | 5/20 | 0.142 | 0.26 | 0.73 | 0.90 | 7/20 |
| 1600x400 | 20 | 0.529 | 0.645 | 5/20 | 0.184 | 0.18 | 0.51 | 0.91 | 4/20 |
| 1584x396 | 20 | 0.518 | 0.643 | 3/20 | 0.190 | 0.16 | 0.49 | 0.91 | 4/20 |
| 820x312 | 20 | 0.554 | 0.650 | 1/20 | 0.162 | 0.16 | 0.69 | 0.85 | 5/20 |
| 160x600 | 20 | 0.615 | 0.705 | 2/20 | 0.124 | 0.26 | 0.72 | 0.84 | 4/20 |
| 728x90 | 20 | 0.452 | 0.569 | 1/20 | 0.214 | 0.07 | 0.40 | 0.86 | 1/20 |
| **all** | 240 | 0.617 | 0.717 | 41/240 | 0.137 | 0.30 | 0.69 | 0.90 | 87/240 |

### By design

| design | n | agreement (winner) | agreement (best) | winner >= 0.7 | structure wins | designer hard fails |
|---|---:|---:|---:|---:|---:|---:|
| 58a4091695a7a863ddcc6c53 | 12 | 0.479 | 0.515 | 0/12 | 0/12 | 0 |
| 5c346ef7048d064dbc063111 | 12 | 0.502 | 0.722 | 1/12 | 7/12 | 5 |
| 5952983995a7a863ddce040b | 12 | 0.540 | 0.718 | 4/12 | 4/12 | 0 |
| 595256d795a7a863ddcde397 | 12 | 0.547 | 0.673 | 3/12 | 7/12 | 3 |
| 5953611d95a7a863ddce13e0 | 12 | 0.551 | 0.649 | 3/12 | 5/12 | 0 |
| 5e68e28db04a3d1f19b3c3fc | 12 | 0.551 | 0.630 | 3/12 | 2/12 | 0 |
| 5952645b95a7a863ddcde7c9 | 12 | 0.556 | 0.628 | 5/12 | 8/12 | 0 |
| 59b27d591350e8329300d8b3 | 12 | 0.564 | 0.638 | 4/12 | 0/12 | 0 |
| 5ca7253923c829c8213e6cd2 | 12 | 0.572 | 0.740 | 3/12 | 3/12 | 0 |
| 593112f495a7a863ddcdc5a7 | 12 | 0.604 | 0.722 | 2/12 | 2/12 | 0 |
| 5e709a0f4b3890eb0783cb50 | 12 | 0.606 | 0.746 | 4/12 | 2/12 | 0 |
| 59b27ce91350e8329300d847 | 12 | 0.629 | 0.828 | 5/12 | 8/12 | 0 |
| 5e8d96cb4b3890eb071c683d | 12 | 0.637 | 0.700 | 4/12 | 2/12 | 0 |
| level2_core | 12 | 0.678 | 0.740 | 5/12 | 8/12 | 2 |
| 59b26b291350e8329300d483 | 12 | 0.702 | 0.766 | 7/12 | 10/12 | 0 |
| level3_advanced | 12 | 0.705 | 0.760 | 5/12 | 1/12 | 0 |
| 5952492d95a7a863ddcddfa0 | 12 | 0.714 | 0.792 | 6/12 | 5/12 | 0 |
| 59b27f4d1350e8329300daea | 12 | 0.720 | 0.778 | 7/12 | 9/12 | 0 |
| 5888cec295a7a863ddcc24c9 | 12 | 0.726 | 0.743 | 7/12 | 3/12 | 0 |
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
| faith.anchors | 0.609 | 0.689 | -0.079 |
| faith.hierarchy | 0.965 | 0.987 | -0.022 |
| faith.order | 0.904 | 0.917 | -0.013 |
| faith.rows | 1.000 | 1.000 | +0.000 |
| faith.scale | 0.751 | 0.815 | -0.064 |
| layout.alignment | 0.562 | 0.597 | -0.035 |
| layout.balance | 0.878 | 0.893 | -0.015 |
| layout.cohesion | 0.919 | 0.965 | -0.046 |
| layout.fill | 0.823 | 0.830 | -0.007 |
| layout.margins | 0.710 | 0.916 | -0.206 |
| layout.size | 0.851 | 0.869 | -0.018 |
| layout.spacing | 0.800 | 0.875 | -0.075 |
| read.contrast | 0.830 | 0.828 | +0.002 |
| read.lines | 0.928 | 0.926 | +0.001 |
| read.presence | 0.938 | 0.953 | -0.015 |
| read.size | 0.939 | 0.952 | -0.014 |

## Engine hard fails on cases where the designer reference is clean

