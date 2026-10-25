# The picker gap on the designer references (v8 diagnosis)

720 (design, format) cases, 120 of them from the sealed hold-out designs (own block). One engine run per case (optimiser on, no pixels); every judged candidate is scored for designer agreement (eval/metrics.designer_agreement, 1 = the reference itself). 'best' is the candidate with the highest agreement, 'winner' the one the judge returned.

## Tuning set (designs not in the hold-out) (600 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.608 |
| best candidate agreement, mean | 0.696 |
| best *clean* candidate agreement, mean | 0.663 |
| best - winner gap, mean / p50 / p90 | 0.089 / 0.049 / 0.252 |
| winner is the best candidate | 115 |
| judge missed by >= 0.02 | 383 |
| judge missed by >= 0.10 | 197 |
| best candidate has a hard fail | 77 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 47 |
| reference judge total > winner total (clean refs) | 167 |
| candidates per case, mean | 13.8 |
| runtime p50 / p95 (s) | 0.53 / 1.16 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 250 | 0.661 | 0.739 | 0.078 | 146 | template+opt 26%, anchor+opt 21%, anchor 16%, structure 15%, structure+opt 12%, template 11% |
| square | 50 | 0.714 | 0.774 | 0.059 | 26 | anchor 26%, anchor+opt 24%, template+opt 24%, structure 12%, structure+opt 10%, template 4% |
| wide | 150 | 0.570 | 0.673 | 0.103 | 102 | template+opt 29%, structure+opt 19%, structure 19%, anchor+opt 17%, anchor 9%, template 7% |
| banner | 150 | 0.521 | 0.623 | 0.102 | 109 | template+opt 41%, structure+opt 21%, structure 15%, template 10%, anchor 7%, anchor+opt 6% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.682 | 0.755 | 0.074 | 28 |
| 1080x1920 | 50 | 0.658 | 0.748 | 0.090 | 30 |
| 1000x1500 | 50 | 0.677 | 0.752 | 0.075 | 27 |
| 1080x1350 | 50 | 0.695 | 0.763 | 0.068 | 27 |
| 1600x900 | 50 | 0.574 | 0.680 | 0.106 | 34 |
| 1080x1080 | 50 | 0.714 | 0.774 | 0.059 | 26 |
| 1280x720 | 50 | 0.578 | 0.685 | 0.107 | 34 |
| 1600x400 | 50 | 0.531 | 0.642 | 0.111 | 36 |
| 1584x396 | 50 | 0.535 | 0.641 | 0.106 | 39 |
| 820x312 | 50 | 0.557 | 0.652 | 0.095 | 34 |
| 160x600 | 50 | 0.596 | 0.678 | 0.083 | 34 |
| 728x90 | 50 | 0.497 | 0.587 | 0.090 | 34 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 4379 | 0.473 | 55 | 119 | 24 |
| structure | 963 | 0.503 | 94 | 58 | 57 |
| template+opt | 804 | 0.512 | 183 | 49 | 105 |
| anchor | 540 | 0.757 | 76 | 288 | 3 |
| anchor+opt | 359 | 0.750 | 99 | 42 | 13 |
| structure+opt | 350 | 0.558 | 93 | 44 | 57 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 77 | 0.184 |
| structure | anchor | 40 | 0.144 |
| anchor+opt | anchor | 38 | 0.080 |
| template+opt | template | 33 | 0.108 |
| structure+opt | anchor | 32 | 0.180 |
| template+opt | structure | 22 | 0.151 |
| structure+opt | template | 19 | 0.101 |
| template | anchor | 17 | 0.197 |
| template | template | 14 | 0.121 |
| structure | template | 13 | 0.120 |
| anchor+opt | template | 12 | 0.139 |
| anchor | anchor | 10 | 0.063 |
| template | structure | 7 | 0.103 |
| anchor | anchor+opt | 6 | 0.064 |
| structure+opt | template+opt | 6 | 0.267 |
| template+opt | structure+opt | 6 | 0.095 |
| structure | structure+opt | 5 | 0.042 |
| anchor+opt | anchor+opt | 5 | 0.107 |
| structure+opt | structure | 4 | 0.036 |
| structure | template+opt | 4 | 0.243 |
| structure | structure | 4 | 0.055 |
| template+opt | template+opt | 2 | 0.061 |
| template | template+opt | 2 | 0.030 |
| anchor | template+opt | 1 | 0.084 |
| anchor | template | 1 | 0.074 |
| anchor+opt | structure+opt | 1 | 0.021 |
| structure+opt | structure+opt | 1 | 0.041 |
| anchor | structure+opt | 1 | 0.036 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +446.48 | +260.27 | +76.92 | +460.78 | +770.64 |
| penalty | +6.80 | +5.95 | +6.77 | +8.62 | +6.22 |
| read.size | +1.45 | +1.22 | +1.21 | +1.47 | +1.79 |
| layout.size | +1.08 | +0.82 | +0.72 | +1.18 | +1.43 |
| faith.anchors | -0.75 | -0.65 | -0.57 | -0.62 | -1.04 |
| faith.order | +0.52 | +0.14 | -0.00 | +0.23 | +1.41 |
| faith.scale | -0.46 | -0.46 | -0.41 | -0.58 | -0.37 |
| read.presence | +0.43 | +0.31 | +0.10 | +0.42 | +0.66 |
| layout.alignment | +0.41 | +0.33 | +0.38 | +0.44 | +0.50 |
| layout.cohesion | +0.35 | +0.37 | +0.01 | +0.38 | +0.38 |
| read.contrast | +0.29 | +0.34 | +0.26 | +0.25 | +0.28 |
| layout.balance | +0.23 | +0.21 | +0.17 | +0.21 | +0.29 |
| layout.spacing | +0.19 | +0.32 | +0.26 | -0.00 | +0.17 |
| layout.fill | +0.15 | +0.09 | +0.19 | +0.15 | +0.24 |
| read.lines | +0.14 | +0.04 | +0.21 | +0.14 | +0.27 |
| layout.margins | +0.10 | +0.11 | +0.08 | +0.08 | +0.09 |
| faith.rows | -0.06 | -0.07 | -0.20 | -0.03 | -0.05 |
| faith.hierarchy | -0.01 | +0.02 | +0.01 | -0.04 | -0.01 |

| term | all missed | best = anchor | best = template | best = structure | best = template+opt | best = structure+opt | best = anchor+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +446.48 | +742.99 | +86.96 | +108.11 | +0.00 | +0.00 | +0.00 |
| penalty | +6.80 | +11.75 | +0.85 | -0.32 | +1.20 | +0.25 | +0.00 |
| read.size | +1.45 | +2.10 | +0.29 | +1.73 | -0.07 | +0.88 | +0.29 |
| layout.size | +1.08 | +1.60 | +0.41 | +0.82 | -0.39 | +0.26 | +0.56 |
| faith.anchors | -0.75 | -2.39 | +1.86 | +0.62 | +1.97 | +0.18 | -0.10 |
| faith.order | +0.52 | +0.07 | +1.68 | +0.29 | +0.65 | +0.34 | +0.29 |
| faith.scale | -0.46 | -1.03 | +0.36 | +0.24 | +0.27 | -0.26 | -0.00 |
| read.presence | +0.43 | +0.64 | +0.40 | -0.23 | +0.04 | -0.17 | -0.01 |
| layout.alignment | +0.41 | +0.71 | +0.04 | +0.07 | +0.17 | -0.05 | -0.31 |
| layout.cohesion | +0.35 | +0.50 | +0.15 | +0.35 | +0.07 | +0.02 | +0.07 |
| read.contrast | +0.29 | +0.41 | +0.22 | -0.01 | +0.10 | +0.15 | -0.05 |
| layout.balance | +0.23 | +0.37 | -0.04 | +0.42 | -0.16 | +0.05 | +0.00 |
| layout.spacing | +0.19 | +0.04 | +0.30 | +0.51 | +0.62 | +0.49 | +0.05 |
| layout.fill | +0.15 | +0.27 | -0.03 | +0.12 | -0.25 | +0.08 | +0.13 |
| read.lines | +0.14 | +0.22 | +0.01 | +0.12 | +0.24 | -0.13 | +0.00 |
| layout.margins | +0.10 | +0.16 | -0.03 | +0.23 | -0.14 | +0.05 | -0.04 |
| faith.rows | -0.06 | -0.16 | +0.11 | +0.00 | +0.00 | +0.00 | +0.00 |
| faith.hierarchy | -0.01 | -0.05 | +0.03 | +0.14 | -0.04 | +0.00 | +0.04 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 117 |
| hard | 71 |
| faith.anchors | 50 |
| faith.order | 41 |
| read.size | 37 |
| layout.size | 22 |
| layout.spacing | 19 |
| layout.alignment | 8 |
| read.lines | 6 |
| faith.hierarchy | 5 |
| read.presence | 3 |
| read.contrast | 2 |
| faith.rows | 1 |
| faith.scale | 1 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.438 | 0.633 |
| da_within10 | 0.154 | 0.381 |
| da_order_tau | 0.653 | 0.741 |
| da_size_rho | 0.906 | 0.931 |

## HOLD-OUT (10 sealed designs) (120 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.610 |
| best candidate agreement, mean | 0.718 |
| best *clean* candidate agreement, mean | 0.653 |
| best - winner gap, mean / p50 / p90 | 0.108 / 0.077 / 0.258 |
| winner is the best candidate | 22 |
| judge missed by >= 0.02 | 80 |
| judge missed by >= 0.10 | 54 |
| best candidate has a hard fail | 15 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 12 |
| reference judge total > winner total (clean refs) | 33 |
| candidates per case, mean | 15.0 |
| runtime p50 / p95 (s) | 0.70 / 1.15 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 50 | 0.637 | 0.751 | 0.114 | 36 | template+opt 26%, anchor 20%, template 18%, anchor+opt 14%, structure+opt 14%, structure 8% |
| square | 10 | 0.758 | 0.812 | 0.054 | 5 | anchor+opt 40%, anchor 40%, template 10%, template+opt 10% |
| wide | 30 | 0.621 | 0.731 | 0.111 | 18 | structure+opt 33%, anchor+opt 20%, template+opt 20%, structure 10%, anchor 10%, template 7% |
| banner | 30 | 0.507 | 0.619 | 0.112 | 21 | structure+opt 43%, template+opt 33%, structure 10%, anchor 7%, template 7% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.666 | 0.784 | 0.118 | 8 |
| 1080x1920 | 10 | 0.635 | 0.764 | 0.129 | 8 |
| 1000x1500 | 10 | 0.679 | 0.780 | 0.100 | 7 |
| 1080x1350 | 10 | 0.678 | 0.786 | 0.108 | 6 |
| 1600x900 | 10 | 0.686 | 0.764 | 0.078 | 4 |
| 1080x1080 | 10 | 0.758 | 0.812 | 0.054 | 5 |
| 1280x720 | 10 | 0.670 | 0.763 | 0.092 | 5 |
| 1600x400 | 10 | 0.532 | 0.657 | 0.124 | 6 |
| 1584x396 | 10 | 0.534 | 0.657 | 0.124 | 6 |
| 820x312 | 10 | 0.506 | 0.667 | 0.161 | 9 |
| 160x600 | 10 | 0.527 | 0.641 | 0.114 | 7 |
| 728x90 | 10 | 0.454 | 0.542 | 0.088 | 9 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 651 | 0.457 | 14 | 10 | 12 |
| structure | 222 | 0.485 | 10 | 10 | 5 |
| template+opt | 151 | 0.501 | 30 | 7 | 24 |
| anchor | 104 | 0.779 | 19 | 72 | 0 |
| structure+opt | 79 | 0.507 | 30 | 11 | 18 |
| anchor+opt | 76 | 0.797 | 17 | 10 | 3 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 20 | 0.231 |
| structure+opt | anchor | 14 | 0.195 |
| template | anchor | 9 | 0.154 |
| structure+opt | template | 4 | 0.103 |
| anchor+opt | anchor+opt | 4 | 0.057 |
| structure | anchor | 3 | 0.159 |
| structure+opt | structure | 3 | 0.183 |
| template | structure | 3 | 0.167 |
| anchor | anchor+opt | 3 | 0.061 |
| anchor+opt | anchor | 2 | 0.041 |
| template | template | 2 | 0.129 |
| anchor | anchor | 2 | 0.055 |
| anchor+opt | structure+opt | 2 | 0.079 |
| template+opt | structure | 2 | 0.082 |
| template+opt | anchor+opt | 2 | 0.118 |
| structure+opt | structure+opt | 1 | 0.235 |
| structure | structure+opt | 1 | 0.100 |
| anchor+opt | template | 1 | 0.065 |
| structure | template | 1 | 0.178 |
| structure | template+opt | 1 | 0.046 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +475.00 | +333.33 | +400.00 | +111.11 | +1047.62 |
| penalty | +10.09 | +10.00 | +7.20 | +9.50 | +11.43 |
| faith.anchors | -1.88 | -2.38 | -1.29 | -1.29 | -1.65 |
| read.size | +1.18 | +1.29 | +0.84 | +0.53 | +1.64 |
| layout.size | +1.17 | +1.10 | +0.22 | +1.06 | +1.62 |
| read.presence | +1.14 | +1.06 | -0.05 | +1.04 | +1.65 |
| faith.scale | -0.72 | -0.68 | -0.51 | -1.01 | -0.61 |
| read.contrast | +0.51 | +0.39 | +0.52 | -0.04 | +1.18 |
| layout.alignment | +0.47 | +0.44 | +0.17 | +0.63 | +0.47 |
| layout.cohesion | +0.47 | +0.59 | +0.45 | +0.15 | +0.53 |
| faith.rows | -0.27 | -0.14 | +0.00 | -0.29 | -0.55 |
| read.lines | +0.24 | +0.30 | +0.26 | +0.14 | +0.19 |
| layout.balance | +0.23 | +0.36 | +0.12 | +0.14 | +0.11 |
| layout.spacing | +0.13 | +0.04 | +0.15 | +0.11 | +0.30 |
| faith.order | +0.12 | +0.34 | +0.99 | -0.10 | -0.28 |
| faith.hierarchy | -0.11 | -0.07 | +0.00 | -0.10 | -0.21 |
| layout.fill | +0.08 | +0.11 | +0.28 | +0.04 | +0.04 |
| layout.margins | +0.06 | +0.07 | +0.10 | +0.02 | +0.08 |

| term | all missed | best = anchor | best = anchor+opt | best = template | best = structure | best = structure+opt | best = template+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +475.00 | +560.00 | +0.00 | +1000.00 | +0.00 | +0.00 | +2000.00 |
| penalty | +10.09 | +16.14 | +0.00 | +0.75 | -0.75 | +0.00 | +0.00 |
| faith.anchors | -1.88 | -3.25 | -0.59 | +1.70 | +0.26 | -0.54 | +4.18 |
| read.size | +1.18 | +1.71 | +0.25 | -0.41 | +1.86 | +0.17 | -5.42 |
| layout.size | +1.17 | +1.56 | +0.50 | +0.40 | +1.14 | -0.18 | -0.44 |
| read.presence | +1.14 | +1.46 | +0.05 | +1.55 | +0.10 | +0.09 | +4.01 |
| faith.scale | -0.72 | -1.24 | -0.01 | +0.20 | +0.18 | +0.46 | -0.76 |
| read.contrast | +0.51 | +0.31 | -0.16 | +2.90 | -0.21 | -0.02 | +5.49 |
| layout.alignment | +0.47 | +0.63 | -0.04 | +0.10 | +0.69 | +0.10 | +0.09 |
| layout.cohesion | +0.47 | +0.72 | +0.08 | -0.06 | +0.16 | -0.05 | +0.00 |
| faith.rows | -0.27 | -0.44 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| read.lines | +0.24 | +0.40 | +0.19 | -0.29 | -0.06 | +0.00 | +0.00 |
| layout.balance | +0.23 | +0.25 | +0.12 | +0.24 | +0.25 | +0.11 | +0.37 |
| layout.spacing | +0.13 | +0.10 | +0.20 | +0.39 | -0.37 | +0.90 | +0.00 |
| faith.order | +0.12 | -0.60 | +0.74 | +0.97 | +2.11 | +2.65 | -2.35 |
| faith.hierarchy | -0.11 | -0.14 | -0.02 | +0.06 | +0.00 | +0.00 | -1.90 |
| layout.fill | +0.08 | +0.17 | +0.08 | -0.44 | +0.22 | +0.00 | -0.75 |
| layout.margins | +0.06 | +0.07 | +0.04 | +0.00 | +0.18 | -0.10 | +0.00 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 37 |
| hard | 14 |
| faith.order | 14 |
| layout.size | 3 |
| faith.anchors | 3 |
| faith.scale | 3 |
| layout.spacing | 2 |
| read.size | 2 |
| layout.alignment | 2 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.433 | 0.656 |
| da_within10 | 0.147 | 0.395 |
| da_order_tau | 0.652 | 0.791 |
| da_size_rho | 0.841 | 0.894 |

## Largest misses (tuning set)

- 5952983995a7 1080x1350: winner `tall scale=1.5` 0.352 -> best `anchor fallback scale=2.500` 0.831 (rank 12); for the winner: penalty +18.0, layout.spacing +3.3, read.size +3.0
- level2_core 728x90: winner `banner structure flip +opt` 0.410 -> best `banner scale=1.3` 0.859 (rank 2); for the winner: faith.order +4.7, penalty +3.0, read.presence +0.2
- 5c346ef7048d 1600x900: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 3); for the winner: faith.order +3.5, penalty +3.0, read.presence +1.0
- 5c346ef7048d 1280x720: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 3); for the winner: faith.order +3.5, penalty +3.0, read.presence +1.0
- 5eec925b499b 1600x900: winner `wide structure keep +opt` 0.428 -> best `anchor fallback scale=1.418` 0.858 (rank 11); for the winner: penalty +18.0, read.size +4.8, layout.size +3.1
- 5eec925b499b 1280x720: winner `wide structure keep +opt` 0.432 -> best `anchor fallback scale=1.135` 0.858 (rank 10); for the winner: penalty +18.0, read.size +4.9, layout.size +3.3
- 5889bae595a7 1600x400: winner `banner chips=stack +opt` 0.460 -> best `anchor fallback scale=1.600` 0.878 (rank 16); for the winner: penalty +18.0, read.size +4.6, layout.size +2.3
- 5889bae595a7 1584x396: winner `banner chips=stack +opt` 0.465 -> best `anchor fallback scale=1.584` 0.874 (rank 17); for the winner: penalty +18.0, read.size +4.7, layout.size +2.4
- 59b27ce91350 1000x1500: winner `tall structure keep +opt` 0.468 -> best `tall scale=1.3 +opt` 0.875 (rank 6); for the winner: faith.anchors +7.5, penalty +3.0, layout.alignment +0.3
- 5889bae595a7 820x312: winner `wide hero=stack, scale=1.3 +opt` 0.478 -> best `anchor fallback scale=1.248` 0.883 (rank 12); for the winner: penalty +18.0, read.size +3.6, layout.size +2.9
- 595256d795a7 160x600: winner `tall scale=1.3 +opt` 0.392 -> best `tall structure keep` 0.788 (rank 14); for the winner: hard +1000.0, read.size +2.0, layout.spacing +1.4
- 5889bae595a7 1000x1500: winner `tall scale=1.5 +opt` 0.409 -> best `anchor fallback scale=3.333` 0.798 (rank 14); for the winner: penalty +18.0, read.size +2.5, layout.size +1.5
- 5eec925b499b 820x312: winner `wide structure keep +opt` 0.410 -> best `anchor fallback scale=0.727` 0.792 (rank 10); for the winner: penalty +18.0, read.size +3.7, layout.alignment +3.0
- 5952983995a7 1240x1754: winner `tall scale=1.5 +opt` 0.346 -> best `anchor fallback scale=2.870` 0.717 (rank 12); for the winner: penalty +18.0, layout.spacing +3.1, read.size +2.5
- 59b27ce91350 1080x1920: winner `tall structure keep +opt` 0.458 -> best `tall scale=1.5 +opt` 0.826 (rank 7); for the winner: faith.anchors +7.5, layout.balance +0.1, layout.alignment +0.1
