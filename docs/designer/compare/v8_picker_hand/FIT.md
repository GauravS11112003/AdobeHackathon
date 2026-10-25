# Judge weight fit on the designer references (v8)

dump: ../docs/designer/compare/v8_picker_hand/candidates.jsonl (720 cases, 120 hold-out); pairs fitted: 31424 (24486 candidate, 6877 designer, 61 human); hold-out pairs (never fitted): 5705; margin 0.05, floor 1%, l2 2.0, min pairs 5; fit 6.1 s

pair agreement (decisive, weighted): hand 0.6572, fitted 0.7011 in sample, leave-one-design-out 0.6943
  candidate: n=24486 hand 0.7095 fitted 0.7501
  designer: n=6877 hand 0.6157 fitted 0.6664
  human: n=44 hand 0.5 fitted 0.5
  HOLD-OUT pairs: n=5705 hand 0.6316 fitted 0.6831
temperature 0.1727, loss 0.5687; frozen: read.size, read.lines, read.contrast, read.presence

| component | hand | fitted | change | pairs where it differs | agrees with label |
|---|---|---|---|---|---|
| read.size | 11.0 | 10.6 | -0.4 | 23625 | 0.58 |
| read.lines | 6.0 | 5.8 | -0.2 | 2148 | 0.51 |
| read.contrast | 8.0 | 7.7 | -0.3 | 7162 | 0.50 |
| read.presence | 6.0 | 5.8 | -0.2 | 15892 | 0.61 |
| layout.balance | 6.0 | 5.7 | -0.3 | 31382 | 0.54 |
| layout.alignment | 7.0 | 5.1 | -1.9 | 27254 | 0.44 |
| layout.spacing | 5.0 | 3.9 | -1.1 | 23652 | 0.49 |
| layout.fill | 6.0 | 2.3 | -3.7 | 20450 | 0.53 |
| layout.margins | 4.0 | 1.0 | -3.0 | 9454 | 0.38 |
| layout.size | 8.0 | 6.5 | -1.5 | 28207 | 0.59 |
| layout.cohesion | 4.0 | 2.8 | -1.2 | 18490 | 0.51 |
| faith.order | 12.0 | 17.7 | +5.7 | 24531 | 0.73 |
| faith.anchors | 6.0 | 7.5 | +1.5 | 28034 | 0.62 |
| faith.hierarchy | 8.0 | 8.1 | +0.1 | 6993 | 0.52 |
| faith.scale | 3.0 | 4.4 | +1.4 | 30528 | 0.60 |
| faith.rows | 4.0 | 5.2 | +1.2 | 893 | 0.54 |

## Re-ranking: the judge's winner under each weight set

| set | n | agreement | gap to best | gap to best clean non-fallback | winner is best | >= 0.7 | hard | fallback wins | order tau | judge total | winner families |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| tuning hand | 600 | 0.598 | 0.099 | 0.065 | 104 | 185 | 1 | 0 | 0.675 | 89.1 | anchor 65, anchor+opt 98, structure 63, structure+opt 86, template 92, template+opt 196 |
| tuning hand (re-ranked) | 600 | 0.598 | 0.099 | 0.065 | 104 | 185 | 1 | 0 | 0.675 | 89.1 | anchor 65, anchor+opt 98, structure 63, structure+opt 86, template 92, template+opt 196 |
| tuning fitted | 600 | 0.607 | 0.089 | 0.056 | 111 | 194 | 1 | 0 | 0.704 | 88.9 | anchor 76, anchor+opt 98, structure 103, structure+opt 80, template 59, template+opt 184 |
| HOLD-OUT hand | 120 | 0.603 | 0.115 | 0.049 | 25 | 35 | 1 | 0 | 0.716 | 81.2 | anchor 19, anchor+opt 16, structure 7, structure+opt 31, template 17, template+opt 30 |
| HOLD-OUT fitted | 120 | 0.610 | 0.107 | 0.042 | 22 | 36 | 1 | 0 | 0.732 | 81.0 | anchor 19, anchor+opt 17, structure 10, structure+opt 30, template 14, template+opt 30 |
| tuning fitted (leave-one-design-out) | 600 | 0.606 | 0.090 | 0.057 | 112 | 192 | 1 | 0 | 0.702 | 88.9 | anchor 76, anchor+opt 98, structure 105, structure+opt 77, template 62, template+opt 182 |

| set | n | agreement hand | agreement fitted | gap hand | gap fitted | hard hand | hard fitted |
|---|---:|---:|---:|---:|---:|---:|---:|
| tuning tall | 250 | 0.650 | 0.660 | 0.089 | 0.079 | 1 | 1 |
| tuning square | 50 | 0.696 | 0.714 | 0.077 | 0.059 | 0 | 0 |
| tuning wide | 150 | 0.561 | 0.570 | 0.112 | 0.103 | 0 | 0 |
| tuning banner | 150 | 0.515 | 0.520 | 0.108 | 0.103 | 0 | 0 |
| HOLD-OUT tall | 50 | 0.634 | 0.636 | 0.115 | 0.113 | 1 | 1 |
| HOLD-OUT square | 10 | 0.758 | 0.758 | 0.054 | 0.054 | 0 | 0 |
| HOLD-OUT wide | 30 | 0.604 | 0.621 | 0.127 | 0.111 | 0 | 0 |
| HOLD-OUT banner | 30 | 0.497 | 0.506 | 0.122 | 0.112 | 0 | 0 |
