# Learned ranker vs linear fit (v8)

720 cases, 120 hold-out; 50 features; leave-one-design-out over 25 folds on the tuning set.

| model | n | agreement | gap to best | gap to best clean | hard | fallback wins | order tau | winner families |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| tuning: judge as run (hand) | 600 | 0.598 | 0.099 | 0.065 | 1 | 0 | 0.675 | anchor 65, anchor+opt 98, structure 63, structure+opt 86, template 92, template+opt 196 |
| tuning: linear fit (in sample) | 600 | 0.607 | 0.089 | 0.056 | 1 | 0 | 0.704 | anchor 76, anchor+opt 98, structure 103, structure+opt 80, template 59, template+opt 184 |
| tuning: linear-ext C=0.3 (leave-one-design-out) | 600 | 0.608 | 0.088 | 0.055 | 1 | 0 | 0.709 | anchor 43, anchor+opt 150, structure 57, structure+opt 155, template 24, template+opt 171 |
| tuning: linear-ext C=0.3 (in sample) | 600 | 0.610 | 0.087 | 0.053 | 1 | 0 | 0.709 | anchor 44, anchor+opt 149, structure 61, structure+opt 158, template 20, template+opt 168 |
| tuning: linear-ext C=3 (leave-one-design-out) | 600 | 0.605 | 0.091 | 0.058 | 1 | 0 | 0.701 | anchor 80, anchor+opt 114, structure 75, structure+opt 125, template 43, template+opt 163 |
| tuning: linear-ext C=3 (in sample) | 600 | 0.611 | 0.085 | 0.052 | 1 | 0 | 0.711 | anchor 77, anchor+opt 117, structure 79, structure+opt 140, template 32, template+opt 155 |
| tuning: gbt-point d3 (leave-one-design-out) | 600 | 0.608 | 0.088 | 0.055 | 1 | 0 | 0.704 | anchor 132, anchor+opt 61, structure 100, structure+opt 122, template 73, template+opt 112 |
| tuning: gbt-point d3 (in sample) | 600 | 0.617 | 0.080 | 0.046 | 1 | 0 | 0.715 | anchor 130, anchor+opt 65, structure 92, structure+opt 124, template 68, template+opt 121 |
| tuning: gbt-point d4 (leave-one-design-out) | 600 | 0.609 | 0.088 | 0.054 | 1 | 0 | 0.701 | anchor 131, anchor+opt 64, structure 88, structure+opt 118, template 90, template+opt 109 |
| tuning: gbt-point d4 (in sample) | 600 | 0.623 | 0.074 | 0.040 | 1 | 0 | 0.720 | anchor 129, anchor+opt 64, structure 83, structure+opt 117, template 101, template+opt 106 |
| HOLD-OUT: judge as run (hand) | 120 | 0.603 | 0.115 | 0.049 | 1 | 0 | 0.716 | anchor 19, anchor+opt 16, structure 7, structure+opt 31, template 17, template+opt 30 |
| HOLD-OUT: linear fit | 120 | 0.610 | 0.107 | 0.042 | 1 | 0 | 0.732 | anchor 19, anchor+opt 17, structure 10, structure+opt 30, template 14, template+opt 30 |
| HOLD-OUT: linear-ext C=0.3 | 120 | 0.611 | 0.106 | 0.041 | 1 | 0 | 0.737 | anchor 8, anchor+opt 32, structure 5, structure+opt 38, template 2, template+opt 35 |
| HOLD-OUT: linear-ext C=3 | 120 | 0.614 | 0.104 | 0.038 | 1 | 0 | 0.739 | anchor 10, anchor+opt 30, structure 8, structure+opt 36, template 2, template+opt 34 |
| HOLD-OUT: gbt-point d3 | 120 | 0.604 | 0.113 | 0.048 | 1 | 0 | 0.710 | anchor 14, anchor+opt 26, structure 12, structure+opt 27, template 5, template+opt 36 |
| HOLD-OUT: gbt-point d4 | 120 | 0.608 | 0.109 | 0.044 | 1 | 0 | 0.707 | anchor 15, anchor+opt 25, structure 16, structure+opt 26, template 13, template+opt 25 |

linear-ext C=0.3 largest coefficients: en.pres.order -1.90, bd.faith.order +1.08, fam.anchor +0.87, en.pres.drift -0.75, en.aes.read -0.65, bd.read.size +0.65, en.pres.contain -0.58, fam.floorplan -0.56, en.pres.anchor -0.41, bd.faith.anchors +0.41, bd.faith.rows -0.36, en.aes.presence -0.36, bd.read.presence +0.36, bd.faith.scale +0.33, en.pres.scale -0.33, fam.structure -0.31, en.pres.prox -0.30, en.aes.balance -0.29, bd.layout.balance +0.29, bd.layout.size +0.24
