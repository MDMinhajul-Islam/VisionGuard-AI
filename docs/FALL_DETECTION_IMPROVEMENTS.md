# Fall detection improvements

The persisted baseline remains unchanged: transition window 1.5 s, drop 0.12, horizontal persistence 0.6 s, pose confidence 0.5, smoothing window 3, and no aspect gate.

The diagnostic profile `diagnostic-shape-gated-v1` makes two narrow changes supported by stored evidence:

1. Require full-body aspect ratio at least `0.8` at transition confirmation. This rejects `adl-30`, whose trigger aspect is `0.559`, while retaining the four baseline true positives (minimum trigger aspect `0.860`).
2. Reduce horizontal persistence to `0.08 s`, which requires a second temporally adjacent horizontal sample after causal smoothing. This recovers `fall-18` without lowering the vertical-drop threshold.

No new neural network, training, or model download was introduced. Baseline events remain persisted; improved events are clearly labeled deterministic replay over cached pose outputs.

## Measured comparison

| Scope | Profile | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| All 20 diagnostic replay | Baseline | 4 | 1 | 9 | 6 | 0.800 | 0.400 | 0.533 |
| All 20 diagnostic replay | Improved | 5 | 0 | 10 | 5 | 1.000 | 0.500 | 0.667 |
| Calibration, 8 videos | Baseline | 1 | 1 | 3 | 3 | 0.500 | 0.250 | 0.333 |
| Calibration, 8 videos | Improved | 2 | 0 | 4 | 2 | 1.000 | 0.500 | 0.667 |
| Non-calibration replay, 12 videos | Baseline | 3 | 0 | 6 | 3 | 1.000 | 0.500 | 0.667 |
| Non-calibration replay, 12 videos | Improved | 3 | 0 | 6 | 3 | 1.000 | 0.500 | 0.667 |

The non-calibration split is unchanged. UR sequence files expose no participant or session identifier, and every failure was inspected diagnostically, so a credible participant-disjoint unbiased test is unavailable. The overall improvement is a calibration result, not a generalization claim.

Corrected hybrid temporal metrics improve from `4 TP / 1 FP / 6 FN` (F1 `0.533`, mean matched onset error `0.538 s`) to `5 TP / 0 FP / 5 FN` (F1 `0.667`, error `0.474 s`).

Cached rule replay takes about 15 ms for all 20 videos. It does not rerun GPU inference; the underlying measured pipeline remains 103.19 s with 370.25 MiB peak PyTorch allocation. Remaining misses require better pose representation or additional validated temporal cues—not indiscriminate threshold relaxation.
