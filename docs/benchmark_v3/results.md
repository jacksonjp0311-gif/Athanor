# ATHANOR 3.0.0 unified benchmark

Seeds 3000–3015 (16 per arm; seed set: bench-v3), 1000 steps for the self-modifying systems. Medians over seeds unless stated; a broken program counts as worst.

Reproduce: `athanor bench --all` (about 2–3 minutes on 8 cores).

## Headline

| system | arm | unsafe commits¹ | severe regressions² | quality early³ | quality final³ | never reached target⁴ | frozen runs |
|---|---|---:|---:|---:|---:|---:|---:|
| synthetic | ungoverned | 163 | n/a | n/a | H7 0.781 | n/a | n/a |
| synthetic | governed | 0 | n/a | n/a | H7 0.914 | n/a | n/a |
| selfmod | ungoverned | 31 | 116 | MSE 1.153 | MSE 0.433 | 0 | n/a |
| selfmod | validity | 8 | 84 | MSE 1.153 | MSE 0.874 | 0 | n/a |
| selfmod | validity+athanor | 0 | 4 | MSE 2.190 | MSE 1.044 | 3 | n/a |
| selfmod | athanor adaptive (incumbent) | 0 | 10 | MSE 1.031 | MSE 0.930 | 3 | n/a |
| tsp | ungoverned | 16 | 16 | ratio never | ratio never | 9 | 0 |
| tsp | validity | 4 | 15 | ratio 1.177 | ratio 1.045 | 1 | 0 |
| tsp | validity + scaled checks | 0 | 11 | ratio 1.177 | ratio 1.044 | 0 | 0 |
| tsp | validity+athanor | 0 | 0 | ratio 1.177 | ratio 1.177 | 16 | 16 |
| tsp | athanor adaptive 2.6 (adaptive@1.1.0) | 2 | 2 | ratio 1.177 | ratio 1.068 | 7 | 0 |
| tsp | athanor adaptive + scaled checks (incumbent, adaptive@1.2.0) | 0 | 0 | ratio 1.177 | ratio 1.049 | 7 | 0 |

¹ selfmod/tsp: committed self-edits that broke the program on held-out inputs (crash, timeout, non-finite or invalid output); synthetic: parent promotions of a non-APPROVED child (summed over seeds).
² selfmod: held-out MSE more than 2× worse or broken; tsp: held-out tour ratio worse by more than 0.05 or broken.
³ selfmod: median held-out MSE at step 100 / final (lower is better); tsp: median held-out tour length ÷ harness reference at step 50 / final (lower is better; the seed program is 1.177); synthetic: mean population H7 over the last 10 generations (higher is better).
⁴ selfmod: runs that never reached MSE < 1.5; tsp: runs that never reached ratio ≤ 1.05.

## Synthetic evolution loop

| metric | governed | ungoverned |
|---|---:|---:|
| mean H7, last 10 gens | 0.914 | 0.781 |
| median ΔΦ, last 10 gens | 0.202 | 0.327 |
| worst generation ΔΦ | 45.753 | 82.971 |
| parent promotions | 559 | 640 |
| promotions of non-APPROVED parents | 0 | 163 |

Per seed: governed H7 higher on 10, ungoverned higher on 4, tied on 2.

## Self-modifying curve-fitting program

| arm | broken | severe | MSE@100 | MSE@final | best-ever MSE | steps to MSE<1.5 | never | commits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ungoverned | 31 | 116 | 1.153 | 0.433 | 0.238 | 5.5 | 0 | 2076 |
| validity | 8 | 84 | 1.153 | 0.874 | 0.425 | 5.5 | 0 | 2231 |
| validity+athanor | 0 | 4 | 2.190 | 1.044 | 0.796 | 382.0 | 3 | 1789 |
| athanor adaptive (incumbent) | 0 | 10 | 1.031 | 0.930 | 0.853 | 27.5 | 3 | 1532 |

## Self-modifying TSP solver

| arm | broken (crash/timeout/invalid) | severe | ratio@50 | ratio@final | best | steps to ≤1.05 | never | frozen | commits |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ungoverned | 16 (0/0/16) | 16 | never | never | 1.137 | never | 9 | 0 | 47 |
| validity | 4 (0/4/0) | 15 | 1.177 | 1.045 | 1.030 | 93.5 | 1 | 0 | 511 |
| validity + scaled checks | 0 (0/0/0) | 11 | 1.177 | 1.044 | 1.030 | 93.5 | 0 | 0 | 495 |
| validity+athanor | 0 (0/0/0) | 0 | 1.177 | 1.177 | 1.177 | never | 16 | 16 | 0 |
| athanor adaptive 2.6 (adaptive@1.1.0) | 2 (0/2/0) | 2 | 1.177 | 1.068 | 1.041 | 585.0 | 7 | 0 | 195 |
| athanor adaptive + scaled checks (incumbent, adaptive@1.2.0) | 0 (0/0/0) | 0 | 1.177 | 1.049 | 1.041 | 585.0 | 7 | 0 | 199 |

