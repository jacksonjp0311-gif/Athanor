# TSP self-modification arms

Seeds: 0-15 (16), metric = mean tour length / harness reference over 32 held-out instances (lower is better; 1.177 = the seed program). Medians over seeds; a broken program counts as worst.

| arm | broken commits (crash/timeout/silent-invalid) | runs broken at end | severe | worst committed ratio | held@50 | held@1000 | best | steps to <=1.05 (never) | frozen runs | % run-steps broken |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| ungoverned | 16 (0/1/15) | 16 | 17 | 1.201 | broken/never | broken/never | 1.177 | broken/never (10) | 0 | 95.3 |
| validity | 4 (0/4/0) | 1 | 21 | 2.376 | 1.177 | 1.046 | 1.032 | 75.5 (0) | 0 | 2.3 |
| athanor | 0 (0/0/0) | 0 | 0 | 1.177 | 1.177 | 1.177 | 1.177 | broken/never (16) | 16 | 0.0 |
| validity+athanor | 0 (0/0/0) | 0 | 0 | 1.177 | 1.177 | 1.177 | 1.177 | broken/never (16) | 16 | 0.0 |
| validity+athanor-conservative | 4 (1/3/0) | 0 | 5 | 1.201 | 1.177 | 1.100 | 1.098 | broken/never (9) | 0 | 4.0 |
| validity+athanor-adaptive | 6 (0/6/0) | 1 | 7 | 1.201 | 1.167 | 1.053 | 1.032 | 57.0 (6) | 0 | 4.4 |
| validity+athanor-tuned | 2 (0/2/0) | 0 | 2 | 1.201 | 1.096 | 1.046 | 1.033 | 76.0 (3) | 0 | 0.5 |
