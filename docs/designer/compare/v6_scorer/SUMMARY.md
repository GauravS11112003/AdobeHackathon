# Designer references vs engine

240 (design, format) pairs. Scores are the engine's own scorer (no pixels).

**Headline numbers:** designer agreement of the engine's winner **0.594** (best judged candidate 0.702); references tripping a hard fail **10/240**; designer scores higher in 77/240; engine hard fails 11/240.

| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | designer hard fails | engine hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 87.3 | 38.5 | 6/20 | 141 | 137 | 0.73 | 0.73 | 36 | 37 | 0 | 1 |
| 1080x1920 | 20 | 86.7 | 38.5 | 2/20 | 126 | 142 | 0.71 | 0.70 | 32 | 37 | 0 | 1 |
| 1000x1500 | 20 | 87.0 | 39.0 | 6/20 | 114 | 117 | 0.73 | 0.73 | 29 | 31 | 0 | 1 |
| 1080x1350 | 20 | 87.7 | 38.8 | 6/20 | 120 | 113 | 0.73 | 0.73 | 30 | 31 | 0 | 1 |
| 1600x900 | 20 | 86.5 | 37.3 | 7/20 | 114 | 120 | 0.73 | 0.70 | 32 | 30 | 0 | 1 |
| 1080x1080 | 20 | 87.4 | 38.0 | 5/20 | 106 | 99 | 0.71 | 0.66 | 28 | 26 | 0 | 1 |
| 1280x720 | 20 | 86.5 | 37.4 | 8/20 | 91 | 96 | 0.73 | 0.70 | 26 | 24 | 0 | 1 |
| 1600x400 | 20 | -13.9 | 88.4 | 6/20 | 78 | 83 | 0.73 | 0.78 | 20 | 23 | 2 | 0 |
| 1584x396 | 20 | -13.8 | 88.5 | 6/20 | 77 | 79 | 0.73 | 0.76 | 20 | 22 | 2 | 0 |
| 820x312 | 20 | -14.4 | 86.7 | 7/20 | 47 | 44 | 0.75 | 0.71 | 13 | 12 | 2 | 0 |
| 160x600 | 20 | -14.3 | -16.1 | 9/20 | 31 | 30 | 0.80 | 0.71 | 9 | 9 | 2 | 2 |
| 728x90 | 20 | -15.7 | -16.0 | 9/20 | 28 | 25 | 0.81 | 0.73 | 9 | 8 | 2 | 2 |

## Designer agreement (eval/metrics.designer_agreement; 1 = the reference itself)

| format | n | agreement (winner) | agreement (best candidate) | winner is best | centre error | within 10 % | reading-order tau | size rho | winner >= 0.7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | 0.648 | 0.774 | 2/20 | 0.105 | 0.31 | 0.65 | 0.94 | 7/20 |
| 1080x1920 | 20 | 0.636 | 0.772 | 3/20 | 0.122 | 0.31 | 0.63 | 0.92 | 6/20 |
| 1000x1500 | 20 | 0.656 | 0.769 | 5/20 | 0.110 | 0.34 | 0.64 | 0.95 | 8/20 |
| 1080x1350 | 20 | 0.669 | 0.784 | 5/20 | 0.111 | 0.39 | 0.72 | 0.93 | 9/20 |
| 1600x900 | 20 | 0.575 | 0.689 | 3/20 | 0.154 | 0.20 | 0.62 | 0.91 | 7/20 |
| 1080x1080 | 20 | 0.728 | 0.809 | 8/20 | 0.090 | 0.50 | 0.77 | 0.90 | 12/20 |
| 1280x720 | 20 | 0.595 | 0.697 | 4/20 | 0.153 | 0.25 | 0.64 | 0.92 | 7/20 |
| 1600x400 | 20 | 0.502 | 0.636 | 2/20 | 0.190 | 0.11 | 0.49 | 0.92 | 3/20 |
| 1584x396 | 20 | 0.522 | 0.632 | 2/20 | 0.174 | 0.13 | 0.54 | 0.91 | 4/20 |
| 820x312 | 20 | 0.546 | 0.647 | 4/20 | 0.188 | 0.21 | 0.56 | 0.85 | 6/20 |
| 160x600 | 20 | 0.590 | 0.661 | 5/20 | 0.121 | 0.19 | 0.64 | 0.83 | 4/20 |
| 728x90 | 20 | 0.467 | 0.549 | 2/20 | 0.197 | 0.10 | 0.40 | 0.84 | 2/20 |
| **all** | 240 | 0.594 | 0.702 | 45/240 | 0.143 | 0.25 | 0.61 | 0.90 | 75/240 |

### By design

| design | n | agreement (winner) | agreement (best) | winner >= 0.7 | structure wins | designer hard fails |
|---|---:|---:|---:|---:|---:|---:|
| 58a4091695a7a863ddcc6c53 | 12 | 0.383 | 0.487 | 0/12 | 0/12 | 0 |
| 5952983995a7a863ddce040b | 12 | 0.496 | 0.708 | 3/12 | 0/12 | 0 |
| 595256d795a7a863ddcde397 | 12 | 0.503 | 0.645 | 2/12 | 0/12 | 3 |
| 5952645b95a7a863ddcde7c9 | 12 | 0.527 | 0.610 | 2/12 | 0/12 | 0 |
| 5953611d95a7a863ddce13e0 | 12 | 0.530 | 0.649 | 2/12 | 0/12 | 0 |
| 593112f495a7a863ddcdc5a7 | 12 | 0.538 | 0.720 | 2/12 | 0/12 | 0 |
| 5e68e28db04a3d1f19b3c3fc | 12 | 0.543 | 0.620 | 3/12 | 0/12 | 0 |
| 5ca7253923c829c8213e6cd2 | 12 | 0.561 | 0.706 | 4/12 | 0/12 | 0 |
| 59b27d591350e8329300d8b3 | 12 | 0.573 | 0.638 | 3/12 | 0/12 | 0 |
| 5e709a0f4b3890eb0783cb50 | 12 | 0.594 | 0.739 | 4/12 | 0/12 | 0 |
| 5c346ef7048d064dbc063111 | 12 | 0.617 | 0.718 | 3/12 | 0/12 | 5 |
| 5e8d96cb4b3890eb071c683d | 12 | 0.635 | 0.699 | 4/12 | 0/12 | 0 |
| 5888cec295a7a863ddcc24c9 | 12 | 0.635 | 0.732 | 4/12 | 0/12 | 0 |
| 59b27f4d1350e8329300daea | 12 | 0.638 | 0.770 | 5/12 | 0/12 | 0 |
| level3_advanced | 12 | 0.655 | 0.740 | 5/12 | 0/12 | 0 |
| 59b27ce91350e8329300d847 | 12 | 0.674 | 0.764 | 5/12 | 0/12 | 0 |
| 59b26b291350e8329300d483 | 12 | 0.677 | 0.716 | 6/12 | 0/12 | 0 |
| level2_core | 12 | 0.685 | 0.736 | 4/12 | 0/12 | 2 |
| 5952492d95a7a863ddcddfa0 | 12 | 0.690 | 0.791 | 5/12 | 0/12 | 0 |
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
| faith.anchors | 0.609 | 0.592 | +0.018 |
| faith.hierarchy | 0.965 | 0.987 | -0.022 |
| faith.order | 0.904 | 0.852 | +0.053 |
| faith.scale | 0.751 | 0.808 | -0.057 |
| layout.alignment | 0.562 | 0.584 | -0.022 |
| layout.balance | 0.878 | 0.892 | -0.014 |
| layout.cohesion | 0.919 | 0.927 | -0.008 |
| layout.fill | 0.823 | 0.870 | -0.047 |
| layout.margins | 0.710 | 0.951 | -0.241 |
| layout.size | 0.851 | 0.830 | +0.021 |
| layout.spacing | 0.614 | 0.736 | -0.122 |
| read.contrast | 0.830 | 0.790 | +0.040 |
| read.lines | 0.928 | 0.926 | +0.002 |
| read.presence | 0.938 | 0.875 | +0.063 |
| read.size | 0.939 | 0.935 | +0.004 |

## Engine hard fails on cases where the designer reference is clean

- 59b26b291350e8329300d483 160x600: el_04 unreadable contrast 1.00 (source 13.06)
- 59b26b291350e8329300d483 728x90: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1000x1500: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1080x1080: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1080x1350: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1080x1920: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1240x1754: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1280x720: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 1600x900: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 160x600: el_04 unreadable contrast 1.00 (source 13.06)
- 59b27f4d1350e8329300daea 728x90: el_04 unreadable contrast 1.00 (source 13.06)
