# Judge weight fit on the designer references (v8)

dump: ../docs/designer/compare/v8_picker_v7scorer/candidates.jsonl (720 cases, 120 hold-out); pairs fitted: 31398 (24450 candidate, 6887 designer, 61 human); hold-out pairs (never fitted): 5692; margin 0.05, floor 1%, l2 0.5, min pairs 5; fit 0.7 s

pair agreement (decisive, weighted): hand 0.6406, fitted 0.7041 in sample, leave-one-design-out None
  candidate: n=24450 hand 0.7162 fitted 0.7701
  designer: n=6887 hand 0.5723 fitted 0.6488
  human: n=44 hand 0.5227 fitted 0.5455
  HOLD-OUT pairs: n=5692 hand 0.6253 fitted 0.6815
temperature 0.1637, loss 0.5649; frozen: faith.rows

| component | hand | fitted | change | pairs where it differs | agrees with label |
|---|---|---|---|---|---|
| read.size | 11.0 | 9.0 | -2.0 | 23584 | 0.58 |
| read.lines | 6.0 | 5.0 | -1.0 | 2163 | 0.50 |
| read.contrast | 8.0 | 11.3 | +3.3 | 7176 | 0.49 |
| read.presence | 6.0 | 10.9 | +4.9 | 15872 | 0.61 |
| layout.balance | 6.0 | 3.8 | -2.2 | 31357 | 0.54 |
| layout.alignment | 7.0 | 1.0 | -6.0 | 27263 | 0.44 |
| layout.spacing | 5.0 | 3.1 | -1.9 | 23600 | 0.49 |
| layout.fill | 6.0 | 1.0 | -5.0 | 20338 | 0.53 |
| layout.margins | 4.0 | 1.0 | -3.0 | 9360 | 0.38 |
| layout.size | 8.0 | 4.5 | -3.5 | 28172 | 0.59 |
| layout.cohesion | 4.0 | 2.0 | -2.0 | 18508 | 0.51 |
| faith.order | 12.0 | 23.6 | +11.6 | 24506 | 0.73 |
| faith.anchors | 6.0 | 7.2 | +1.2 | 27990 | 0.62 |
| faith.hierarchy | 8.0 | 6.5 | -1.5 | 7016 | 0.52 |
| faith.scale | 3.0 | 6.2 | +3.2 | 30492 | 0.60 |
| faith.rows | 4.0 | 3.8 | -0.2 | 2 | 0.50 |

## Re-ranking: the judge's winner under each weight set

| set | n | agreement | gap to best | gap to best clean non-fallback | winner is best | >= 0.7 | hard | fallback wins | order tau | judge total | winner families |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| tuning hand | 600 | 0.595 | 0.101 | 0.068 | 91 | 179 | 1 | 0 | 0.665 | 89.2 | anchor 65, anchor+opt 97, structure 48, structure+opt 61, template 100, template+opt 229 |
| tuning hand (re-ranked) | 600 | 0.596 | 0.101 | 0.067 | 95 | 178 | 1 | 0 | 0.668 | 89.2 | anchor 65, anchor+opt 99, structure 47, structure+opt 63, template 104, template+opt 222 |
| tuning fitted | 600 | 0.604 | 0.092 | 0.059 | 105 | 190 | 1 | 0 | 0.696 | 88.5 | anchor 102, anchor+opt 75, structure 112, structure+opt 62, template 70, template+opt 179 |
| HOLD-OUT hand | 120 | 0.603 | 0.114 | 0.049 | 25 | 35 | 1 | 0 | 0.716 | 81.2 | anchor 18, anchor+opt 17, structure 7, structure+opt 29, template 17, template+opt 32 |
| HOLD-OUT fitted | 120 | 0.609 | 0.108 | 0.043 | 20 | 37 | 1 | 0 | 0.731 | 80.7 | anchor 26, anchor+opt 14, structure 10, structure+opt 29, template 19, template+opt 22 |

| set | n | agreement hand | agreement fitted | gap hand | gap fitted | hard hand | hard fitted |
|---|---:|---:|---:|---:|---:|---:|---:|
| tuning tall | 250 | 0.649 | 0.661 | 0.090 | 0.077 | 1 | 1 |
| tuning square | 50 | 0.694 | 0.708 | 0.079 | 0.065 | 0 | 0 |
| tuning wide | 150 | 0.562 | 0.572 | 0.111 | 0.101 | 0 | 0 |
| tuning banner | 150 | 0.506 | 0.506 | 0.117 | 0.117 | 0 | 0 |
| HOLD-OUT tall | 50 | 0.633 | 0.640 | 0.116 | 0.108 | 1 | 1 |
| HOLD-OUT square | 10 | 0.758 | 0.763 | 0.054 | 0.050 | 0 | 0 |
| HOLD-OUT wide | 30 | 0.606 | 0.616 | 0.125 | 0.116 | 0 | 0 |
| HOLD-OUT banner | 30 | 0.497 | 0.497 | 0.122 | 0.121 | 0 | 0 |
