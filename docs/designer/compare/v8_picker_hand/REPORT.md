# The picker gap on the designer references (v8 diagnosis)

720 (design, format) cases, 120 of them from the sealed hold-out designs (own block). One engine run per case (optimiser on, no pixels); every judged candidate is scored for designer agreement (eval/metrics.designer_agreement, 1 = the reference itself). 'best' is the candidate with the highest agreement, 'winner' the one the judge returned.

## Tuning set (designs not in the hold-out) (600 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.598 |
| best candidate agreement, mean | 0.696 |
| best *clean* candidate agreement, mean | 0.663 |
| best - winner gap, mean / p50 / p90 | 0.099 / 0.059 / 0.262 |
| winner is the best candidate | 104 |
| judge missed by >= 0.02 | 402 |
| judge missed by >= 0.10 | 226 |
| best candidate has a hard fail | 77 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 47 |
| reference judge total > winner total (clean refs) | 153 |
| candidates per case, mean | 13.8 |
| runtime p50 / p95 (s) | 0.36 / 0.84 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 250 | 0.650 | 0.739 | 0.089 | 155 | template+opt 28%, anchor+opt 22%, template 20%, anchor 13%, structure+opt 10%, structure 7% |
| square | 50 | 0.696 | 0.774 | 0.077 | 28 | template+opt 28%, anchor+opt 22%, anchor 22%, structure+opt 12%, template 10%, structure 6% |
| wide | 150 | 0.561 | 0.673 | 0.112 | 104 | template+opt 33%, structure 17%, structure+opt 16%, anchor+opt 16%, template 10%, anchor 9% |
| banner | 150 | 0.515 | 0.623 | 0.108 | 115 | template+opt 41%, structure+opt 21%, template 15%, structure 11%, anchor+opt 6%, anchor 5% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.676 | 0.755 | 0.079 | 31 |
| 1080x1920 | 50 | 0.647 | 0.749 | 0.102 | 32 |
| 1000x1500 | 50 | 0.663 | 0.751 | 0.088 | 28 |
| 1080x1350 | 50 | 0.677 | 0.762 | 0.085 | 29 |
| 1600x900 | 50 | 0.567 | 0.681 | 0.114 | 34 |
| 1080x1080 | 50 | 0.696 | 0.774 | 0.077 | 28 |
| 1280x720 | 50 | 0.562 | 0.686 | 0.125 | 34 |
| 1600x400 | 50 | 0.520 | 0.642 | 0.123 | 41 |
| 1584x396 | 50 | 0.530 | 0.641 | 0.110 | 40 |
| 820x312 | 50 | 0.554 | 0.650 | 0.096 | 36 |
| 160x600 | 50 | 0.585 | 0.678 | 0.093 | 35 |
| 728x90 | 50 | 0.496 | 0.588 | 0.092 | 34 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 4379 | 0.473 | 92 | 113 | 49 |
| structure | 963 | 0.503 | 63 | 65 | 39 |
| template+opt | 887 | 0.507 | 196 | 58 | 114 |
| anchor | 540 | 0.757 | 65 | 292 | 4 |
| anchor+opt | 328 | 0.753 | 98 | 38 | 13 |
| structure+opt | 295 | 0.571 | 86 | 34 | 53 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 79 | 0.189 |
| anchor+opt | anchor | 39 | 0.082 |
| template | anchor | 37 | 0.197 |
| template+opt | template | 33 | 0.115 |
| structure+opt | anchor | 30 | 0.169 |
| template+opt | structure | 29 | 0.134 |
| structure | anchor | 27 | 0.182 |
| template | template | 19 | 0.115 |
| structure+opt | template | 15 | 0.099 |
| anchor+opt | template | 11 | 0.151 |
| template | structure | 11 | 0.141 |
| anchor | anchor | 9 | 0.072 |
| template+opt | template+opt | 7 | 0.102 |
| template | template+opt | 6 | 0.128 |
| structure+opt | template+opt | 6 | 0.218 |
| template+opt | structure+opt | 6 | 0.137 |
| anchor+opt | anchor+opt | 6 | 0.065 |
| structure | template+opt | 5 | 0.278 |
| structure | template | 5 | 0.060 |
| structure | structure | 4 | 0.055 |
| structure+opt | structure | 3 | 0.039 |
| structure+opt | anchor+opt | 2 | 0.207 |
| structure | anchor+opt | 2 | 0.294 |
| anchor | anchor+opt | 2 | 0.076 |
| anchor | structure+opt | 2 | 0.029 |
| anchor+opt | template+opt | 1 | 0.053 |
| anchor | template | 1 | 0.074 |
| template | anchor+opt | 1 | 0.212 |
| anchor+opt | structure+opt | 1 | 0.021 |
| structure+opt | structure+opt | 1 | 0.041 |
| structure | structure+opt | 1 | 0.034 |
| anchor | structure | 1 | 0.047 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +427.86 | +245.16 | +71.43 | +461.54 | +730.43 |
| penalty | +6.32 | +5.52 | +5.54 | +8.29 | +5.79 |
| read.size | +1.59 | +1.33 | +1.06 | +1.74 | +1.93 |
| layout.size | +1.44 | +1.13 | +0.96 | +1.60 | +1.82 |
| faith.anchors | -0.81 | -0.80 | -0.58 | -0.86 | -0.82 |
| layout.fill | +0.63 | +0.52 | +0.52 | +0.65 | +0.79 |
| layout.alignment | +0.55 | +0.44 | +0.53 | +0.59 | +0.67 |
| layout.margins | +0.52 | +0.64 | +0.55 | +0.44 | +0.44 |
| layout.cohesion | +0.51 | +0.53 | +0.02 | +0.60 | +0.53 |
| read.presence | +0.45 | +0.32 | +0.17 | +0.51 | +0.64 |
| layout.spacing | +0.42 | +0.73 | +0.65 | +0.15 | +0.19 |
| faith.scale | -0.31 | -0.31 | -0.25 | -0.39 | -0.23 |
| read.contrast | +0.26 | +0.25 | +0.17 | +0.27 | +0.29 |
| layout.balance | +0.26 | +0.25 | +0.16 | +0.25 | +0.30 |
| read.lines | +0.13 | +0.00 | +0.20 | +0.14 | +0.26 |
| faith.rows | -0.06 | -0.08 | -0.15 | -0.03 | -0.03 |
| faith.order | +0.01 | -0.24 | -0.25 | -0.24 | +0.64 |
| faith.hierarchy | +0.00 | +0.02 | +0.03 | -0.02 | -0.01 |

| term | all missed | best = anchor | best = template | best = structure | best = template+opt | best = anchor+opt | best = structure+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +427.86 | +723.98 | +83.33 | +83.33 | +40.00 | +0.00 | +0.00 |
| penalty | +6.32 | +11.31 | +0.61 | -0.69 | +0.96 | -0.06 | -0.22 |
| read.size | +1.59 | +2.32 | +0.46 | +1.76 | -0.23 | +0.24 | +0.61 |
| layout.size | +1.44 | +2.06 | +0.66 | +1.16 | +0.17 | +0.48 | +0.14 |
| faith.anchors | -0.81 | -2.10 | +1.42 | +0.15 | +0.63 | -0.48 | +0.27 |
| layout.fill | +0.63 | +0.91 | +0.14 | +0.58 | -0.16 | +0.32 | +1.05 |
| layout.alignment | +0.55 | +0.97 | +0.04 | +0.07 | +0.09 | -0.05 | -0.14 |
| layout.margins | +0.52 | +0.72 | -0.03 | +0.96 | -0.13 | +0.51 | +0.42 |
| layout.cohesion | +0.51 | +0.74 | +0.26 | +0.50 | +0.02 | +0.03 | -0.52 |
| read.presence | +0.45 | +0.66 | +0.41 | -0.14 | +0.40 | +0.01 | -0.23 |
| layout.spacing | +0.42 | +0.19 | +0.56 | +0.93 | +0.76 | +0.47 | +0.72 |
| faith.scale | -0.31 | -0.71 | +0.22 | +0.17 | +0.25 | -0.16 | +0.25 |
| read.contrast | +0.26 | +0.41 | +0.22 | -0.14 | +0.12 | -0.09 | -0.09 |
| layout.balance | +0.26 | +0.40 | -0.01 | +0.38 | -0.06 | -0.01 | -0.04 |
| read.lines | +0.13 | +0.20 | +0.02 | +0.06 | +0.15 | +0.00 | -0.17 |
| faith.rows | -0.06 | -0.14 | +0.10 | +0.00 | +0.00 | +0.00 | +0.00 |
| faith.order | +0.01 | -0.33 | +0.83 | -0.13 | +0.50 | +0.02 | +0.09 |
| faith.hierarchy | +0.00 | -0.04 | +0.04 | +0.13 | +0.00 | +0.03 | +0.00 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 116 |
| hard | 72 |
| layout.spacing | 36 |
| faith.anchors | 33 |
| read.size | 33 |
| faith.order | 26 |
| layout.fill | 22 |
| layout.size | 22 |
| layout.alignment | 13 |
| layout.margins | 13 |
| read.lines | 5 |
| faith.hierarchy | 4 |
| read.presence | 3 |
| faith.rows | 1 |
| read.contrast | 1 |
| layout.cohesion | 1 |
| faith.scale | 1 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.439 | 0.642 |
| da_within10 | 0.157 | 0.393 |
| da_order_tau | 0.618 | 0.745 |
| da_size_rho | 0.904 | 0.930 |

## HOLD-OUT (10 sealed designs) (120 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.603 |
| best candidate agreement, mean | 0.717 |
| best *clean* candidate agreement, mean | 0.652 |
| best - winner gap, mean / p50 / p90 | 0.115 / 0.089 / 0.275 |
| winner is the best candidate | 25 |
| judge missed by >= 0.02 | 83 |
| judge missed by >= 0.10 | 57 |
| best candidate has a hard fail | 15 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 12 |
| reference judge total > winner total (clean refs) | 27 |
| candidates per case, mean | 15.0 |
| runtime p50 / p95 (s) | 0.45 / 0.77 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 50 | 0.634 | 0.749 | 0.115 | 36 | template+opt 28%, template 18%, anchor 16%, anchor+opt 16%, structure+opt 14%, structure 8% |
| square | 10 | 0.758 | 0.812 | 0.054 | 5 | anchor+opt 40%, anchor 40%, template 10%, template+opt 10% |
| wide | 30 | 0.604 | 0.731 | 0.127 | 21 | structure+opt 30%, template+opt 23%, anchor 17%, anchor+opt 13%, template 10%, structure 7% |
| banner | 30 | 0.497 | 0.619 | 0.122 | 21 | structure+opt 50%, template+opt 27%, template 13%, anchor 7%, structure 3% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.666 | 0.781 | 0.115 | 8 |
| 1080x1920 | 10 | 0.621 | 0.764 | 0.143 | 9 |
| 1000x1500 | 10 | 0.668 | 0.774 | 0.106 | 7 |
| 1080x1350 | 10 | 0.669 | 0.786 | 0.116 | 6 |
| 1600x900 | 10 | 0.660 | 0.764 | 0.104 | 6 |
| 1080x1080 | 10 | 0.758 | 0.812 | 0.054 | 5 |
| 1280x720 | 10 | 0.653 | 0.763 | 0.110 | 6 |
| 1600x400 | 10 | 0.520 | 0.657 | 0.137 | 6 |
| 1584x396 | 10 | 0.520 | 0.657 | 0.137 | 6 |
| 820x312 | 10 | 0.500 | 0.667 | 0.166 | 9 |
| 160x600 | 10 | 0.546 | 0.641 | 0.096 | 6 |
| 728x90 | 10 | 0.451 | 0.542 | 0.091 | 9 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 651 | 0.457 | 17 | 10 | 14 |
| structure | 222 | 0.485 | 7 | 10 | 4 |
| template+opt | 154 | 0.491 | 30 | 7 | 25 |
| anchor | 104 | 0.779 | 19 | 73 | 0 |
| anchor+opt | 77 | 0.797 | 16 | 10 | 2 |
| structure+opt | 75 | 0.508 | 31 | 10 | 17 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 21 | 0.246 |
| structure+opt | anchor | 13 | 0.184 |
| template | anchor | 11 | 0.197 |
| anchor+opt | anchor+opt | 5 | 0.068 |
| structure+opt | template | 4 | 0.103 |
| anchor | anchor | 4 | 0.071 |
| anchor+opt | anchor | 3 | 0.048 |
| structure+opt | structure | 3 | 0.183 |
| template | structure | 3 | 0.135 |
| anchor | anchor+opt | 2 | 0.059 |
| structure | anchor | 2 | 0.108 |
| template+opt | anchor+opt | 2 | 0.118 |
| template+opt | structure | 2 | 0.180 |
| template | template | 1 | 0.077 |
| structure+opt | structure+opt | 1 | 0.235 |
| anchor+opt | structure+opt | 1 | 0.092 |
| structure | structure+opt | 1 | 0.100 |
| anchor+opt | template | 1 | 0.065 |
| structure | template | 1 | 0.178 |
| structure | template+opt | 1 | 0.046 |
| template | template+opt | 1 | 0.092 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +457.83 | +333.33 | +400.00 | +95.24 | +1047.62 |
| penalty | +9.76 | +10.08 | +7.20 | +8.14 | +11.43 |
| faith.anchors | -1.71 | -2.06 | -1.04 | -1.35 | -1.64 |
| layout.size | +1.50 | +1.41 | +0.27 | +1.39 | +2.06 |
| read.size | +1.36 | +1.33 | +0.87 | +1.11 | +1.78 |
| read.presence | +1.07 | +1.07 | -0.05 | +0.71 | +1.72 |
| layout.cohesion | +0.78 | +0.87 | +0.64 | +0.44 | +1.00 |
| layout.alignment | +0.69 | +0.78 | +0.24 | +0.69 | +0.63 |
| read.contrast | +0.50 | +0.41 | +0.54 | -0.04 | +1.18 |
| faith.scale | -0.46 | -0.48 | -0.35 | -0.50 | -0.43 |
| layout.spacing | +0.37 | +0.13 | +0.19 | +0.58 | +0.61 |
| layout.margins | +0.33 | +0.38 | +0.38 | +0.27 | +0.30 |
| read.lines | +0.24 | +0.33 | +0.27 | +0.13 | +0.20 |
| layout.balance | +0.21 | +0.40 | +0.12 | +0.04 | +0.07 |
| layout.fill | +0.21 | +0.33 | +0.73 | -0.01 | +0.10 |
| faith.rows | -0.20 | -0.11 | +0.00 | -0.19 | -0.42 |
| faith.hierarchy | -0.10 | -0.07 | +0.00 | -0.08 | -0.21 |
| faith.order | -0.06 | +0.05 | +0.67 | -0.22 | -0.27 |

| term | all missed | best = anchor | best = anchor+opt | best = structure | best = template | best = structure+opt | best = template+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +457.83 | +518.52 | +0.00 | +0.00 | +1142.86 | +0.00 | +1000.00 |
| penalty | +9.76 | +15.00 | +0.00 | -0.75 | +0.86 | +0.00 | +0.00 |
| faith.anchors | -1.71 | -2.73 | -0.52 | -0.10 | +1.43 | -0.82 | +1.51 |
| layout.size | +1.50 | +1.93 | +0.67 | +1.45 | +0.57 | -0.20 | -0.30 |
| read.size | +1.36 | +1.90 | +0.28 | +1.93 | -0.39 | +0.12 | -2.74 |
| read.presence | +1.07 | +1.32 | +0.06 | +0.10 | +1.84 | +0.06 | +1.83 |
| layout.cohesion | +0.78 | +1.16 | +0.15 | +0.19 | -0.10 | +0.07 | +0.00 |
| layout.alignment | +0.69 | +0.86 | +0.04 | +1.02 | +0.20 | +0.14 | +0.26 |
| read.contrast | +0.50 | +0.29 | -0.17 | -0.22 | +3.35 | -0.03 | +2.93 |
| faith.scale | -0.46 | -0.76 | +0.00 | +0.13 | +0.22 | +0.21 | -0.35 |
| layout.spacing | +0.37 | +0.30 | +0.37 | +0.22 | +0.79 | +1.45 | -0.10 |
| layout.margins | +0.33 | +0.37 | +0.36 | +0.74 | +0.00 | -0.54 | +0.00 |
| read.lines | +0.24 | +0.39 | +0.20 | -0.07 | -0.34 | +0.00 | +0.00 |
| layout.balance | +0.21 | +0.20 | +0.15 | +0.29 | +0.28 | +0.10 | +0.43 |
| layout.fill | +0.21 | +0.41 | +0.21 | +0.53 | -1.30 | +0.00 | -0.97 |
| faith.rows | -0.20 | -0.31 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| faith.hierarchy | -0.10 | -0.14 | -0.02 | +0.00 | +0.13 | +0.00 | -0.94 |
| faith.order | -0.06 | -0.52 | +0.37 | +1.13 | +0.61 | +2.40 | -0.51 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 37 |
| hard | 14 |
| faith.order | 9 |
| layout.spacing | 6 |
| layout.alignment | 6 |
| layout.size | 5 |
| read.size | 3 |
| layout.margins | 1 |
| faith.scale | 1 |
| faith.anchors | 1 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.428 | 0.661 |
| da_within10 | 0.156 | 0.409 |
| da_order_tau | 0.643 | 0.797 |
| da_size_rho | 0.844 | 0.890 |

## Largest misses (tuning set)

- 5952983995a7 1080x1350: winner `tall scale=1.5` 0.352 -> best `anchor fallback scale=2.500` 0.831 (rank 12); for the winner: penalty +18.0, layout.spacing +4.2, read.size +3.1
- level2_core 728x90: winner `banner structure flip +opt` 0.410 -> best `banner scale=1.3` 0.859 (rank 3); for the winner: faith.order +3.2, penalty +3.0, read.presence +0.2
- 5c346ef7048d 1600x900: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 3); for the winner: penalty +3.0, faith.order +2.4, read.presence +1.1
- 5c346ef7048d 1280x720: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 3); for the winner: penalty +3.0, faith.order +2.4, read.presence +1.1
- 5eec925b499b 1280x720: winner `wide structure keep +opt` 0.432 -> best `anchor fallback scale=1.135` 0.858 (rank 10); for the winner: penalty +18.0, read.size +5.0, layout.alignment +4.1
- 5889bae595a7 1600x400: winner `banner chips=stack +opt` 0.460 -> best `anchor fallback scale=1.600` 0.878 (rank 17); for the winner: penalty +18.0, read.size +4.8, layout.size +2.9
- 59b268f51350 1584x396: winner `banner text=column, scale=1.3` 0.425 -> best `anchor fallback scale=0.330` 0.842 (rank 17); for the winner: penalty +15.0, read.size +7.0, layout.size +5.7
- 59b27ce91350 1000x1500: winner `tall structure keep +opt` 0.468 -> best `tall scale=1.3 +opt` 0.875 (rank 6); for the winner: faith.anchors +6.0, penalty +3.0, layout.alignment +0.4
- 5889bae595a7 820x312: winner `wide hero=stack, scale=1.3 +opt` 0.478 -> best `anchor fallback scale=1.248` 0.883 (rank 12); for the winner: penalty +18.0, read.size +3.7, layout.size +3.6
- 595256d795a7 160x600: winner `tall scale=1.3 +opt` 0.392 -> best `tall structure keep` 0.788 (rank 14); for the winner: hard +1000.0, read.size +2.1, layout.margins +2.0
- 5889bae595a7 1584x396: winner `banner scale=1.5, fill +opt` 0.484 -> best `anchor fallback scale=1.584` 0.874 (rank 17); for the winner: penalty +18.0, read.size +5.1, layout.size +4.4
- 5889bae595a7 1000x1500: winner `tall scale=1.5 +opt` 0.409 -> best `anchor fallback scale=3.333` 0.798 (rank 14); for the winner: penalty +18.0, read.size +2.6, layout.size +1.8
- 5eec925b499b 1600x900: winner `wide scale=1.5 +opt` 0.476 -> best `anchor fallback scale=1.418` 0.858 (rank 11); for the winner: penalty +15.0, read.size +5.0, layout.size +4.4
- 5952983995a7 1240x1754: winner `tall scale=1.5 +opt` 0.346 -> best `anchor fallback scale=2.870` 0.717 (rank 12); for the winner: penalty +18.0, layout.spacing +4.0, layout.cohesion +3.1
- 5952983995a7 1080x1920: winner `tall scale=1.5 +opt` 0.350 -> best `anchor fallback scale=2.500` 0.712 (rank 12); for the winner: penalty +18.0, layout.spacing +3.8, read.size +3.6
