# The picker gap on the designer references (v8 diagnosis)

720 (design, format) cases, 120 of them from the sealed hold-out designs (own block). One engine run per case (optimiser on, no pixels); every judged candidate is scored for designer agreement (eval/metrics.designer_agreement, 1 = the reference itself). 'best' is the candidate with the highest agreement, 'winner' the one the judge returned.

## Tuning set (designs not in the hold-out) (600 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.595 |
| best candidate agreement, mean | 0.696 |
| best *clean* candidate agreement, mean | 0.663 |
| best - winner gap, mean / p50 / p90 | 0.101 / 0.067 / 0.265 |
| winner is the best candidate | 91 |
| judge missed by >= 0.02 | 415 |
| judge missed by >= 0.10 | 233 |
| best candidate has a hard fail | 77 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 47 |
| reference judge total > winner total (clean refs) | 127 |
| candidates per case, mean | 13.8 |
| runtime p50 / p95 (s) | 0.35 / 0.79 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 250 | 0.649 | 0.739 | 0.090 | 163 | template+opt 30%, template 22%, anchor+opt 21%, anchor 14%, structure+opt 8%, structure 5% |
| square | 50 | 0.694 | 0.773 | 0.079 | 29 | template+opt 34%, anchor+opt 22%, anchor 22%, structure+opt 8%, template 8%, structure 6% |
| wide | 150 | 0.562 | 0.673 | 0.111 | 102 | template+opt 41%, anchor+opt 15%, structure 14%, template 13%, structure+opt 9%, anchor 8% |
| banner | 150 | 0.506 | 0.623 | 0.117 | 121 | template+opt 51%, structure+opt 15%, template 15%, structure 7%, anchor+opt 7%, anchor 5% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 50 | 0.676 | 0.755 | 0.079 | 34 |
| 1080x1920 | 50 | 0.647 | 0.749 | 0.102 | 32 |
| 1000x1500 | 50 | 0.666 | 0.751 | 0.085 | 30 |
| 1080x1350 | 50 | 0.678 | 0.762 | 0.084 | 29 |
| 1600x900 | 50 | 0.568 | 0.681 | 0.113 | 34 |
| 1080x1080 | 50 | 0.694 | 0.773 | 0.079 | 29 |
| 1280x720 | 50 | 0.562 | 0.686 | 0.124 | 33 |
| 1600x400 | 50 | 0.512 | 0.642 | 0.130 | 43 |
| 1584x396 | 50 | 0.520 | 0.641 | 0.121 | 43 |
| 820x312 | 50 | 0.555 | 0.650 | 0.095 | 35 |
| 160x600 | 50 | 0.579 | 0.678 | 0.100 | 38 |
| 728x90 | 50 | 0.487 | 0.588 | 0.100 | 35 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 4379 | 0.473 | 100 | 113 | 55 |
| structure | 963 | 0.503 | 48 | 71 | 33 |
| template+opt | 954 | 0.511 | 229 | 58 | 138 |
| anchor | 540 | 0.757 | 65 | 293 | 4 |
| anchor+opt | 323 | 0.754 | 97 | 37 | 13 |
| structure+opt | 246 | 0.579 | 61 | 28 | 38 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 91 | 0.185 |
| template | anchor | 39 | 0.203 |
| anchor+opt | anchor | 38 | 0.082 |
| template+opt | structure | 38 | 0.149 |
| template+opt | template | 36 | 0.116 |
| structure+opt | anchor | 23 | 0.175 |
| structure | anchor | 21 | 0.192 |
| template | template | 20 | 0.105 |
| template | structure | 15 | 0.111 |
| anchor+opt | template | 11 | 0.158 |
| structure+opt | template | 10 | 0.099 |
| anchor | anchor | 10 | 0.074 |
| template+opt | structure+opt | 9 | 0.110 |
| template+opt | template+opt | 8 | 0.098 |
| template | template+opt | 7 | 0.129 |
| structure | template | 5 | 0.060 |
| anchor+opt | anchor+opt | 5 | 0.066 |
| structure | template+opt | 4 | 0.259 |
| structure | structure | 4 | 0.067 |
| structure+opt | template+opt | 3 | 0.167 |
| structure | anchor+opt | 3 | 0.217 |
| structure+opt | structure | 2 | 0.049 |
| structure+opt | anchor+opt | 2 | 0.207 |
| anchor | anchor+opt | 2 | 0.076 |
| anchor | structure+opt | 2 | 0.029 |
| anchor+opt | template+opt | 1 | 0.053 |
| anchor | template | 1 | 0.074 |
| anchor+opt | structure+opt | 1 | 0.021 |
| template | structure+opt | 1 | 0.040 |
| structure+opt | structure+opt | 1 | 0.041 |
| structure | structure+opt | 1 | 0.034 |
| anchor | structure | 1 | 0.047 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +414.46 | +233.13 | +68.97 | +470.59 | +694.21 |
| penalty | +6.23 | +5.54 | +5.55 | +8.49 | +5.40 |
| read.size | +1.54 | +1.28 | +1.08 | +1.78 | +1.81 |
| layout.size | +1.41 | +1.13 | +0.92 | +1.66 | +1.68 |
| layout.fill | +0.83 | +0.74 | +0.70 | +0.92 | +0.91 |
| faith.anchors | -0.80 | -0.77 | -0.43 | -0.96 | -0.77 |
| layout.spacing | +0.56 | +0.84 | +0.93 | +0.24 | +0.35 |
| layout.margins | +0.54 | +0.63 | +0.53 | +0.50 | +0.46 |
| layout.alignment | +0.49 | +0.37 | +0.48 | +0.52 | +0.64 |
| layout.cohesion | +0.47 | +0.47 | -0.04 | +0.58 | +0.49 |
| read.presence | +0.42 | +0.30 | +0.17 | +0.51 | +0.55 |
| layout.balance | +0.32 | +0.27 | +0.13 | +0.38 | +0.39 |
| faith.scale | -0.32 | -0.32 | -0.28 | -0.45 | -0.21 |
| read.contrast | +0.26 | +0.21 | +0.17 | +0.34 | +0.27 |
| read.lines | +0.13 | -0.03 | +0.27 | +0.16 | +0.29 |
| faith.order | +0.03 | -0.19 | -0.16 | -0.23 | +0.57 |
| faith.hierarchy | +0.01 | +0.02 | +0.03 | +0.01 | -0.00 |

| term | all missed | best = anchor | best = template | best = structure | best = template+opt | best = structure+opt | best = anchor+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +414.46 | +720.72 | +84.34 | +66.67 | +43.48 | +0.00 | +0.00 |
| penalty | +6.23 | +11.59 | +0.11 | +0.00 | +0.00 | +0.24 | -0.07 |
| read.size | +1.54 | +2.29 | +0.48 | +1.39 | -0.24 | +0.74 | +0.32 |
| layout.size | +1.41 | +2.04 | +0.67 | +0.98 | +0.26 | +0.35 | +0.47 |
| layout.fill | +0.83 | +1.16 | +0.19 | +0.76 | -0.10 | +1.64 | +0.37 |
| faith.anchors | -0.80 | -2.15 | +1.37 | +0.35 | +0.47 | +0.45 | -0.43 |
| layout.spacing | +0.56 | +0.29 | +0.74 | +1.06 | +0.86 | +1.21 | +0.34 |
| layout.margins | +0.54 | +0.77 | -0.01 | +0.81 | -0.05 | +0.17 | +0.45 |
| layout.alignment | +0.49 | +0.94 | +0.03 | +0.01 | +0.05 | -0.38 | -0.11 |
| layout.cohesion | +0.47 | +0.71 | +0.31 | +0.24 | +0.02 | -0.38 | +0.06 |
| read.presence | +0.42 | +0.64 | +0.39 | -0.17 | +0.42 | -0.17 | +0.04 |
| layout.balance | +0.32 | +0.51 | +0.01 | +0.39 | -0.07 | -0.19 | -0.02 |
| faith.scale | -0.32 | -0.73 | +0.22 | +0.11 | +0.21 | +0.14 | -0.13 |
| read.contrast | +0.26 | +0.40 | +0.24 | -0.12 | +0.42 | -0.29 | -0.09 |
| read.lines | +0.13 | +0.24 | +0.07 | -0.09 | +0.19 | -0.15 | +0.00 |
| faith.order | +0.03 | -0.28 | +0.78 | +0.03 | +0.50 | -0.44 | +0.06 |
| faith.hierarchy | +0.01 | -0.03 | +0.05 | +0.13 | +0.00 | +0.00 | +0.03 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 104 |
| hard | 72 |
| layout.spacing | 53 |
| faith.anchors | 38 |
| layout.fill | 33 |
| read.size | 31 |
| faith.order | 27 |
| layout.size | 22 |
| layout.margins | 12 |
| layout.alignment | 9 |
| faith.hierarchy | 4 |
| read.lines | 4 |
| read.presence | 3 |
| read.contrast | 2 |
| layout.cohesion | 1 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.441 | 0.642 |
| da_within10 | 0.159 | 0.389 |
| da_order_tau | 0.613 | 0.750 |
| da_size_rho | 0.906 | 0.932 |

## HOLD-OUT (10 sealed designs) (120 cases)

| metric | value |
|---|---:|
| winner agreement, mean | 0.603 |
| best candidate agreement, mean | 0.717 |
| best *clean* candidate agreement, mean | 0.652 |
| best - winner gap, mean / p50 / p90 | 0.114 / 0.086 / 0.275 |
| winner is the best candidate | 25 |
| judge missed by >= 0.02 | 81 |
| judge missed by >= 0.10 | 56 |
| best candidate has a hard fail | 15 |
| winner has a hard fail | 1 |
| reference trips a judge hard fail | 12 |
| reference judge total > winner total (clean refs) | 27 |
| candidates per case, mean | 15.0 |
| runtime p50 / p95 (s) | 0.47 / 0.72 |

### By target family

| family | n | winner | best | gap | missed | winner families (share) |
|---|---:|---:|---:|---:|---:|---|
| tall | 50 | 0.633 | 0.748 | 0.116 | 36 | template+opt 30%, template 18%, anchor 16%, anchor+opt 16%, structure+opt 12%, structure 8% |
| square | 10 | 0.758 | 0.812 | 0.054 | 5 | anchor+opt 40%, anchor 40%, template 10%, template+opt 10% |
| wide | 30 | 0.606 | 0.731 | 0.125 | 19 | structure+opt 27%, template+opt 27%, anchor+opt 17%, anchor 13%, template 10%, structure 7% |
| banner | 30 | 0.497 | 0.619 | 0.122 | 21 | structure+opt 50%, template+opt 27%, template 13%, anchor 7%, structure 3% |

### By format

| format | n | winner | best | gap | missed |
|---|---:|---:|---:|---:|---:|
| 1240x1754 | 10 | 0.666 | 0.776 | 0.110 | 8 |
| 1080x1920 | 10 | 0.621 | 0.764 | 0.143 | 9 |
| 1000x1500 | 10 | 0.662 | 0.774 | 0.112 | 7 |
| 1080x1350 | 10 | 0.669 | 0.786 | 0.116 | 6 |
| 1600x900 | 10 | 0.662 | 0.764 | 0.102 | 5 |
| 1080x1080 | 10 | 0.758 | 0.812 | 0.054 | 5 |
| 1280x720 | 10 | 0.654 | 0.763 | 0.109 | 6 |
| 1600x400 | 10 | 0.520 | 0.657 | 0.137 | 6 |
| 1584x396 | 10 | 0.520 | 0.657 | 0.137 | 6 |
| 820x312 | 10 | 0.502 | 0.667 | 0.165 | 8 |
| 160x600 | 10 | 0.545 | 0.641 | 0.096 | 6 |
| 728x90 | 10 | 0.451 | 0.542 | 0.091 | 9 |

### Agreement by seed family (every clean candidate, not only winners)

| family | candidates | agreement mean | is the winner | is the best | wins while another family is best |
|---|---:|---:|---:|---:|---:|
| template | 651 | 0.457 | 17 | 10 | 14 |
| structure | 222 | 0.485 | 7 | 10 | 4 |
| template+opt | 160 | 0.491 | 32 | 7 | 26 |
| anchor | 104 | 0.779 | 18 | 74 | 0 |
| anchor+opt | 76 | 0.798 | 17 | 9 | 2 |
| structure+opt | 73 | 0.506 | 29 | 10 | 16 |

### Missed cases (gap >= 0.02): winner family -> best family

| winner | best | n | mean gap |
|---|---|---:|---:|
| template+opt | anchor | 23 | 0.238 |
| structure+opt | anchor | 12 | 0.193 |
| template | anchor | 11 | 0.184 |
| anchor+opt | anchor+opt | 5 | 0.068 |
| structure+opt | template | 4 | 0.103 |
| anchor+opt | anchor | 3 | 0.048 |
| anchor | anchor | 3 | 0.083 |
| template | structure | 3 | 0.135 |
| structure+opt | structure | 2 | 0.263 |
| anchor | anchor+opt | 2 | 0.059 |
| structure | anchor | 2 | 0.108 |
| template+opt | structure | 2 | 0.180 |
| template | template | 1 | 0.077 |
| structure+opt | structure+opt | 1 | 0.235 |
| anchor+opt | structure+opt | 1 | 0.092 |
| structure | structure+opt | 1 | 0.100 |
| anchor+opt | template | 1 | 0.065 |
| structure | template | 1 | 0.178 |
| structure | template+opt | 1 | 0.046 |
| template+opt | anchor+opt | 1 | 0.132 |
| template | template+opt | 1 | 0.092 |

### Blame: weight x (winner - best) per term, missed cases

Positive = the term voted for the judge's (worse) pick. Mean over the missed cases, then split by the target family and by the best candidate's family (the layout the judge should have taken).

| term | all missed | target tall | target square | target wide | target banner |
|---|---:|---:|---:|---:|---:|
| hard | +469.14 | +333.33 | +400.00 | +105.26 | +1047.62 |
| penalty | +10.00 | +10.00 | +7.20 | +9.47 | +11.14 |
| faith.anchors | -1.76 | -2.08 | -1.04 | -1.45 | -1.64 |
| layout.size | +1.51 | +1.40 | +0.27 | +1.44 | +2.06 |
| read.size | +1.38 | +1.35 | +0.87 | +1.15 | +1.78 |
| read.presence | +1.10 | +1.08 | -0.05 | +0.76 | +1.72 |
| layout.cohesion | +0.81 | +0.89 | +0.64 | +0.49 | +1.00 |
| layout.alignment | +0.73 | +0.87 | +0.24 | +0.71 | +0.63 |
| read.contrast | +0.52 | +0.41 | +0.54 | -0.01 | +1.18 |
| faith.scale | -0.47 | -0.48 | -0.35 | -0.55 | -0.43 |
| layout.spacing | +0.44 | +0.09 | +0.23 | +0.83 | +0.73 |
| layout.margins | +0.36 | +0.42 | +0.38 | +0.30 | +0.30 |
| read.lines | +0.29 | +0.38 | +0.32 | +0.16 | +0.23 |
| layout.balance | +0.27 | +0.50 | +0.14 | +0.06 | +0.08 |
| layout.fill | +0.24 | +0.37 | +0.85 | -0.02 | +0.11 |
| faith.hierarchy | -0.10 | -0.05 | +0.00 | -0.09 | -0.21 |
| faith.order | -0.06 | +0.07 | +0.67 | -0.27 | -0.27 |

| term | all missed | best = anchor | best = anchor+opt | best = template | best = structure | best = structure+opt | best = template+opt |
|---|---:|---:|---:|---:|---:|---:|---:|
| hard | +469.14 | +518.52 | +0.00 | +1142.86 | +0.00 | +0.00 | +1000.00 |
| penalty | +10.00 | +15.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| faith.anchors | -1.76 | -2.77 | -0.38 | +1.43 | -0.01 | -0.82 | +1.51 |
| layout.size | +1.51 | +1.91 | +0.61 | +0.57 | +1.62 | -0.20 | -0.30 |
| read.size | +1.38 | +1.89 | +0.31 | -0.39 | +2.19 | +0.12 | -2.74 |
| read.presence | +1.10 | +1.32 | +0.06 | +1.84 | +0.12 | +0.06 | +1.83 |
| layout.cohesion | +0.81 | +1.18 | +0.13 | -0.10 | +0.22 | +0.07 | +0.00 |
| layout.alignment | +0.73 | +0.90 | +0.03 | +0.20 | +1.13 | +0.14 | +0.26 |
| read.contrast | +0.52 | +0.29 | -0.17 | +3.35 | -0.17 | -0.03 | +2.93 |
| faith.scale | -0.47 | -0.76 | +0.03 | +0.22 | +0.15 | +0.21 | -0.35 |
| layout.spacing | +0.44 | +0.34 | +0.39 | +0.95 | +0.30 | +1.74 | -0.11 |
| layout.margins | +0.36 | +0.41 | +0.30 | +0.00 | +0.84 | -0.54 | +0.00 |
| read.lines | +0.29 | +0.48 | +0.13 | -0.40 | -0.09 | +0.00 | +0.00 |
| layout.balance | +0.27 | +0.26 | +0.13 | +0.32 | +0.40 | +0.12 | +0.51 |
| layout.fill | +0.24 | +0.48 | +0.18 | -1.52 | +0.71 | +0.00 | -1.13 |
| faith.hierarchy | -0.10 | -0.13 | -0.02 | +0.13 | +0.00 | +0.00 | -0.94 |
| faith.order | -0.06 | -0.50 | +0.42 | +0.61 | +1.18 | +2.40 | -0.51 |

| term | largest single vote for the winner (cases) |
|---|---:|
| penalty | 37 |
| hard | 14 |
| faith.order | 8 |
| layout.spacing | 7 |
| layout.alignment | 6 |
| layout.size | 3 |
| read.size | 3 |
| layout.margins | 1 |
| faith.scale | 1 |
| faith.anchors | 1 |

### Where the winner loses agreement (components, missed cases)

| component | winner | best |
|---|---:|---:|
| da_pos | 0.422 | 0.662 |
| da_within10 | 0.152 | 0.408 |
| da_order_tau | 0.646 | 0.801 |
| da_size_rho | 0.845 | 0.890 |

## Largest misses (tuning set)

- 5952983995a7 1080x1350: winner `tall scale=1.5` 0.352 -> best `anchor fallback scale=2.500` 0.831 (rank 12); for the winner: penalty +18.0, layout.spacing +5.1, read.size +3.1
- level2_core 728x90: winner `banner structure flip +opt` 0.410 -> best `banner scale=1.3` 0.859 (rank 3); for the winner: faith.order +3.2, read.presence +0.2, layout.balance +0.1
- 5c346ef7048d 1600x900: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 2); for the winner: faith.order +2.4, layout.spacing +1.1, read.presence +1.1
- 5c346ef7048d 1280x720: winner `wide structure swap` 0.344 -> best `wide chips=corner +opt` 0.787 (rank 2); for the winner: faith.order +2.4, read.presence +1.1, layout.spacing +0.9
- 595298a695a7 1280x720: winner `anchor x1.4 scale=3.600 +opt` 0.365 -> best `wide scale=1.3` 0.806 (rank 7); for the winner: faith.anchors +3.4, layout.spacing +1.0, layout.size +0.8
- 5889bae595a7 1600x400: winner `banner chips=stack +opt` 0.460 -> best `anchor fallback scale=1.600` 0.878 (rank 17); for the winner: penalty +18.0, read.size +4.8, layout.size +2.9
- 59b268f51350 1584x396: winner `banner text=column, scale=1.3` 0.425 -> best `anchor fallback scale=0.330` 0.842 (rank 17); for the winner: penalty +18.0, read.size +7.0, layout.size +5.7
- 5889bae595a7 820x312: winner `wide hero=stack, scale=1.3 +opt` 0.478 -> best `anchor fallback scale=1.248` 0.883 (rank 12); for the winner: penalty +18.0, read.size +3.7, layout.size +3.6
- 595256d795a7 160x600: winner `tall scale=1.3 +opt` 0.392 -> best `tall structure keep` 0.788 (rank 14); for the winner: hard +1000.0, layout.spacing +2.2, read.size +2.1
- 5889bae595a7 1584x396: winner `banner scale=1.5, fill +opt` 0.484 -> best `anchor fallback scale=1.584` 0.874 (rank 17); for the winner: penalty +18.0, read.size +5.1, layout.size +4.4
- 5889bae595a7 1000x1500: winner `tall scale=1.5 +opt` 0.409 -> best `anchor fallback scale=3.333` 0.798 (rank 14); for the winner: penalty +18.0, read.size +2.6, layout.size +1.8
- 5952975a95a7 728x90: winner `banner spacing=0.75 +opt` 0.533 -> best `banner structure flip` 0.922 (rank 1); for the winner: faith.anchors +1.3, layout.balance +0.4, layout.alignment +0.2
- 5eec925b499b 1600x900: winner `wide scale=1.5 +opt` 0.476 -> best `anchor fallback scale=1.418` 0.858 (rank 11); for the winner: penalty +18.0, read.size +5.0, layout.fill +4.8
- 5eec925b499b 1280x720: winner `wide hero=stack, scale=1.3 +opt` 0.480 -> best `anchor fallback scale=1.135` 0.858 (rank 10); for the winner: penalty +18.0, read.size +5.0, layout.fill +4.9
- 5952983995a7 1240x1754: winner `tall scale=1.5 +opt` 0.346 -> best `anchor fallback scale=2.870` 0.717 (rank 12); for the winner: penalty +18.0, layout.spacing +4.8, layout.cohesion +3.1
