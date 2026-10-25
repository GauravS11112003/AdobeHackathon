# Learned ranker vs linear fit (v8)

720 cases, 120 hold-out; 50 features; leave-one-design-out over 25 folds on the tuning set.

| model | n | agreement | gap to best | gap to best clean | hard | fallback wins | order tau | winner families |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| tuning: judge as run (hand) | 600 | 0.599 | 0.098 | 0.064 | 1 | 0 | 0.686 | anchor 65, anchor+opt 99, structure 79, structure+opt 102, template 80, template+opt 175 |
| tuning: linear fit (in sample) | 600 | 0.604 | 0.092 | 0.059 | 1 | 0 | 0.707 | anchor 81, anchor+opt 89, structure 135, structure+opt 117, template 55, template+opt 123 |
| tuning: linear-ext C=0.3 (leave-one-design-out) | 600 | 0.609 | 0.088 | 0.054 | 1 | 0 | 0.708 | anchor 43, anchor+opt 150, structure 30, structure+opt 188, template 25, template+opt 164 |
| tuning: linear-ext C=0.3 (in sample) | 600 | 0.610 | 0.086 | 0.053 | 1 | 0 | 0.711 | anchor 43, anchor+opt 150, structure 33, structure+opt 195, template 19, template+opt 160 |
| tuning: linear-ext C=3 (leave-one-design-out) | 600 | 0.607 | 0.090 | 0.056 | 1 | 0 | 0.699 | anchor 80, anchor+opt 115, structure 55, structure+opt 149, template 48, template+opt 153 |
| tuning: linear-ext C=3 (in sample) | 600 | 0.612 | 0.085 | 0.051 | 1 | 0 | 0.713 | anchor 72, anchor+opt 123, structure 50, structure+opt 175, template 32, template+opt 148 |
| tuning: gbt-point d3 (leave-one-design-out) | 600 | 0.608 | 0.089 | 0.055 | 1 | 0 | 0.706 | anchor 136, anchor+opt 59, structure 64, structure+opt 139, template 77, template+opt 125 |
| tuning: gbt-point d3 (in sample) | 600 | 0.616 | 0.080 | 0.047 | 1 | 0 | 0.719 | anchor 133, anchor+opt 62, structure 60, structure+opt 141, template 78, template+opt 126 |
| tuning: gbt-point d4 (leave-one-design-out) | 600 | 0.607 | 0.090 | 0.056 | 1 | 0 | 0.695 | anchor 134, anchor+opt 61, structure 71, structure+opt 128, template 99, template+opt 107 |
| tuning: gbt-point d4 (in sample) | 600 | 0.625 | 0.071 | 0.038 | 1 | 0 | 0.721 | anchor 129, anchor+opt 64, structure 55, structure+opt 142, template 95, template+opt 115 |
| HOLD-OUT: judge as run (hand) | 120 | 0.605 | 0.113 | 0.047 | 1 | 0 | 0.728 | anchor 19, anchor+opt 16, structure 8, structure+opt 33, template 15, template+opt 29 |
| HOLD-OUT: linear fit | 120 | 0.611 | 0.107 | 0.041 | 1 | 0 | 0.736 | anchor 20, anchor+opt 18, structure 13, structure+opt 31, template 10, template+opt 28 |
| HOLD-OUT: linear-ext C=0.3 | 120 | 0.610 | 0.107 | 0.042 | 1 | 0 | 0.735 | anchor 8, anchor+opt 32, structure 2, structure+opt 40, template 2, template+opt 36 |
| HOLD-OUT: linear-ext C=3 | 120 | 0.613 | 0.105 | 0.040 | 1 | 0 | 0.737 | anchor 11, anchor+opt 29, structure 6, structure+opt 37, template 2, template+opt 35 |
| HOLD-OUT: gbt-point d3 | 120 | 0.602 | 0.115 | 0.050 | 1 | 0 | 0.708 | anchor 14, anchor+opt 26, structure 8, structure+opt 25, template 15, template+opt 32 |
| HOLD-OUT: gbt-point d4 | 120 | 0.600 | 0.117 | 0.052 | 1 | 0 | 0.712 | anchor 16, anchor+opt 24, structure 7, structure+opt 28, template 14, template+opt 31 |

linear-ext C=0.3 largest coefficients: en.pres.order -1.84, bd.faith.order +1.13, fam.anchor +0.89, en.pres.drift -0.77, bd.read.size +0.67, en.aes.read -0.67, en.pres.contain -0.57, fam.floorplan -0.55, bd.faith.rows -0.40, en.pres.anchor -0.38, bd.faith.anchors +0.38, en.aes.presence -0.36, bd.read.presence +0.36, fam.structure -0.34, bd.faith.scale +0.31, en.pres.scale -0.31, bd.layout.balance +0.27, en.aes.balance -0.27, en.pres.prox -0.27, bd.layout.size +0.24
