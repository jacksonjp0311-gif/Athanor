Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 1000 self-edit steps per run.

| Metric | Governed | Ungoverned |
|---|---:|---:|
| Median held-out MSE after 25 steps | 2.9705 | 1.3816 |
| Median held-out MSE after 50 steps | 2.5484 | 1.2217 |
| Median held-out MSE after 100 steps | 2.2501 | 1.1734 |
| Median held-out MSE after 200 steps | 2.1464 | 1.1373 |
| Median held-out MSE after 1000 steps | 1.1099 | 0.8619 |
| Runs broken at the end | 0 | 1 |
| Committed self-edits | 1642 | 2519 |
| Commits that worsened held-out MSE | 639 | 1032 |
| Severe regressions (>2× worse or broken) | 3 | 140 |
| Commits that broke the program on held-out inputs | 0 | 23 |
| Steps spent broken (all runs) | 0 | 167 |
| Commits whose verdict was REFINE/REJECT | 0 | 723 |
| Median ΔΦ of committed edits | 0.0894 | 0.1799 |
| Median C of committed edits | 0.9207 | 0.8621 |
| Verdicts APPROVE / REFINE / REJECT | 6112 / 566 / 7370 | 6618 / 1458 / 5100 |
| Verdicts of commits that broke the program (A/RF/RJ) | 0 / 0 / 0 | 20 / 2 / 1 |
| Verdicts of severe-regression commits (A/RF/RJ) | 3 / 0 / 0 | 56 / 25 / 59 |

Final held-out MSE per seed: governed lower on 7/16, ungoverned lower on 9/16, tied on 0/16.

| Seed | Governed final MSE | Ungoverned final MSE | Governed commits | Ungoverned commits | Ungoverned broken commits |
|---:|---:|---:|---:|---:|---:|
| 0 | 1.3518 | 0.2141 | 151 | 196 | 0 |
| 1 | 0.5454 | 1.1835 | 75 | 157 | 0 |
| 2 | 1.1711 | 1.1078 | 71 | 149 | 0 |
| 3 | 1.7981 | 1.5726 | 112 | 179 | 3 |
| 4 | 0.5370 | 0.9023 | 101 | 163 | 0 |
| 5 | 1.2101 | 1.1103 | 89 | 198 | 0 |
| 6 | 0.2044 | 0.6342 | 75 | 131 | 0 |
| 7 | 0.4904 | 0.5571 | 161 | 156 | 0 |
| 8 | 0.2123 | 0.3376 | 77 | 68 | 0 |
| 9 | 0.8835 | broken | 72 | 93 | 8 |
| 10 | 1.8362 | 0.8216 | 82 | 135 | 0 |
| 11 | 1.2131 | 0.2070 | 114 | 185 | 3 |
| 12 | 2.5561 | 1.0794 | 110 | 207 | 0 |
| 13 | 0.0244 | 0.0644 | 121 | 140 | 0 |
| 14 | 1.0488 | 0.9962 | 126 | 181 | 6 |
| 15 | 1.1952 | 0.7485 | 105 | 181 | 3 |
