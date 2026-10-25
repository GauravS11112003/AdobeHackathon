# Judge weight fit on the designer references (v8)

dump: /Users/gauravshrivastava/Projects/AdobeHack/docs/designer/compare/v8_picker/candidates.jsonl (720 cases, 120 hold-out); pairs fitted: 31732 (24783 candidate, 6888 designer, 61 human); hold-out pairs (never fitted): 5734; margin 0.05, floor 1%, l2 0.5, min pairs 5; fit 6.6 s

pair agreement (decisive, weighted): hand 0.6792, fitted 0.7232 in sample, leave-one-design-out 0.7117
  candidate: n=24783 hand 0.7181 fitted 0.7567
  designer: n=6888 hand 0.6532 fitted 0.7045
  human: n=44 hand 0.5 fitted 0.5227
  HOLD-OUT pairs: n=5734 hand 0.6678 fitted 0.6938
temperature 0.1911, loss 0.5289; frozen: read.size, read.lines, read.contrast, read.presence

| component | hand | fitted | change | pairs where it differs | agrees with label |
|---|---|---|---|---|---|
| read.size | 11.0 | 10.6 | -0.4 | 23957 | 0.58 |
| read.lines | 6.0 | 5.8 | -0.2 | 2184 | 0.52 |
| read.contrast | 8.0 | 7.7 | -0.3 | 7220 | 0.50 |
| read.presence | 6.0 | 5.8 | -0.2 | 16195 | 0.61 |
| layout.balance | 6.0 | 6.0 | +0.0 | 31692 | 0.53 |
| layout.alignment | 7.0 | 3.2 | -3.8 | 27565 | 0.44 |
| layout.spacing | 5.0 | 3.2 | -1.8 | 23910 | 0.49 |
| layout.fill | 6.0 | 1.0 | -5.0 | 20693 | 0.53 |
| layout.margins | 4.0 | 1.0 | -3.0 | 9670 | 0.38 |
| layout.size | 8.0 | 5.4 | -2.6 | 28518 | 0.59 |
| layout.cohesion | 4.0 | 2.2 | -1.8 | 18614 | 0.51 |
| faith.order | 12.0 | 22.5 | +10.5 | 24779 | 0.73 |
| faith.anchors | 6.0 | 5.9 | -0.1 | 28369 | 0.62 |
| faith.hierarchy | 8.0 | 9.0 | +1.0 | 7176 | 0.52 |
| faith.scale | 3.0 | 4.8 | +1.8 | 30837 | 0.60 |
| faith.rows | 4.0 | 5.9 | +1.9 | 1232 | 0.56 |

## Re-ranking: the judge's winner under each weight set

| set | n | agreement | gap to best | gap to best clean non-fallback | winner is best | >= 0.7 | hard | fallback wins | order tau | judge total | winner families |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| tuning hand | 600 | 0.599 | 0.098 | 0.064 | 104 | 188 | 1 | 0 | 0.686 | 88.3 | anchor 65, anchor+opt 99, structure 79, structure+opt 102, template 80, template+opt 175 |
| tuning hand (re-ranked) | 600 | 0.599 | 0.098 | 0.064 | 104 | 188 | 1 | 0 | 0.686 | 88.3 | anchor 65, anchor+opt 99, structure 79, structure+opt 102, template 80, template+opt 175 |
| tuning fitted | 600 | 0.606 | 0.091 | 0.057 | 110 | 195 | 1 | 0 | 0.708 | 88.0 | anchor 83, anchor+opt 91, structure 128, structure+opt 114, template 54, template+opt 130 |
| HOLD-OUT hand | 120 | 0.605 | 0.113 | 0.047 | 25 | 35 | 1 | 0 | 0.728 | 80.6 | anchor 19, anchor+opt 16, structure 8, structure+opt 33, template 15, template+opt 29 |
| HOLD-OUT fitted | 120 | 0.608 | 0.109 | 0.044 | 21 | 36 | 1 | 0 | 0.730 | 80.5 | anchor 19, anchor+opt 18, structure 9, structure+opt 31, template 15, template+opt 28 |
| tuning fitted (leave-one-design-out) | 600 | 0.605 | 0.091 | 0.058 | 111 | 193 | 1 | 0 | 0.707 | 88.0 | anchor 82, anchor+opt 91, structure 123, structure+opt 119, template 54, template+opt 131 |

| set | n | agreement hand | agreement fitted | gap hand | gap fitted | hard hand | hard fitted |
|---|---:|---:|---:|---:|---:|---:|---:|
| tuning tall | 250 | 0.651 | 0.664 | 0.088 | 0.075 | 1 | 1 |
| tuning square | 50 | 0.705 | 0.723 | 0.068 | 0.050 | 0 | 0 |
| tuning wide | 150 | 0.561 | 0.564 | 0.111 | 0.109 | 0 | 0 |
| tuning banner | 150 | 0.513 | 0.511 | 0.111 | 0.112 | 0 | 0 |
| HOLD-OUT tall | 50 | 0.636 | 0.634 | 0.114 | 0.115 | 1 | 1 |
| HOLD-OUT square | 10 | 0.758 | 0.762 | 0.054 | 0.050 | 0 | 0 |
| HOLD-OUT wide | 30 | 0.610 | 0.623 | 0.121 | 0.108 | 0 | 0 |
| HOLD-OUT banner | 30 | 0.497 | 0.499 | 0.122 | 0.120 | 0 | 0 |
