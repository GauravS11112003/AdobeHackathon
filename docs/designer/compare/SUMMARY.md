# Designer references vs engine

240 (design, format) pairs. Scores are the engine's own scorer (no pixels).

| format | n | designer score | engine score | designer wins | designer headline px | engine headline px | designer hull | engine hull | designer min font | engine min font | engine hard fails |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1240x1754 | 20 | -113.1 | 38.4 | 3/20 | 141 | 135 | 0.73 | 0.73 | 36 | 36 | 1 |
| 1080x1920 | 20 | -113.7 | 38.1 | 2/20 | 126 | 141 | 0.71 | 0.70 | 32 | 37 | 1 |
| 1000x1500 | 20 | -113.3 | 38.7 | 2/20 | 114 | 118 | 0.73 | 0.73 | 29 | 30 | 1 |
| 1080x1350 | 20 | -162.7 | 38.3 | 3/20 | 120 | 112 | 0.73 | 0.74 | 30 | 30 | 1 |
| 1600x900 | 20 | -163.9 | 37.2 | 5/20 | 114 | 118 | 0.73 | 0.71 | 32 | 30 | 1 |
| 1080x1080 | 20 | -163.0 | 37.9 | 2/20 | 106 | 99 | 0.71 | 0.67 | 28 | 26 | 1 |
| 1280x720 | 20 | -163.9 | 37.2 | 5/20 | 91 | 96 | 0.73 | 0.71 | 26 | 24 | 1 |
| 1600x400 | 20 | -364.3 | 88.4 | 2/20 | 78 | 83 | 0.73 | 0.78 | 20 | 23 | 0 |
| 1584x396 | 20 | -364.2 | 88.4 | 2/20 | 77 | 79 | 0.73 | 0.77 | 20 | 22 | 0 |
| 820x312 | 20 | -314.8 | 86.5 | 4/20 | 47 | 44 | 0.75 | 0.71 | 13 | 12 | 0 |
| 160x600 | 20 | -214.7 | -16.2 | 6/20 | 31 | 30 | 0.80 | 0.71 | 9 | 9 | 2 |
| 728x90 | 20 | -366.3 | -16.1 | 5/20 | 28 | 25 | 0.81 | 0.73 | 9 | 8 | 2 |

## Score components, mean (designer vs engine)

| component | designer | engine | gap |
|---|---:|---:|---:|
| faith.anchors | 0.609 | 0.595 | +0.014 |
| faith.hierarchy | 0.965 | 0.987 | -0.022 |
| faith.order | 0.904 | 0.850 | +0.054 |
| faith.scale | 0.751 | 0.806 | -0.055 |
| layout.alignment | 0.562 | 0.586 | -0.023 |
| layout.balance | 0.878 | 0.891 | -0.013 |
| layout.cohesion | 0.919 | 0.925 | -0.006 |
| layout.fill | 0.823 | 0.871 | -0.047 |
| layout.margins | 0.605 | 0.931 | -0.326 |
| layout.size | 0.851 | 0.825 | +0.025 |
| layout.spacing | 0.614 | 0.734 | -0.120 |
| read.contrast | 0.830 | 0.791 | +0.039 |
| read.lines | 0.928 | 0.926 | +0.002 |
| read.presence | 0.938 | 0.871 | +0.067 |
| read.size | 0.939 | 0.933 | +0.005 |

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
