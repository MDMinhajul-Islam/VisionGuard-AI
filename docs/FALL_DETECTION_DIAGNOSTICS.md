# Fall detection diagnostics

This report uses the persisted MediaPipe landmarks from the 20-video UR Fall Detection run. No screenshots or participant media are tracked. Reproduce it with:

```powershell
.\.venv\Scripts\python .\scripts\evaluate_fall_profiles.py
```

Per-video timelines are written locally to `data/external/validation/reports/fall-diagnostics/`. The dashboard exposes the same measured torso angle, hip Y, visibility, full-body aspect, missing landmarks, source intervals, and rule events.

| Recording | Pose evidence | Root cause |
|---|---|---|
| `fall-18` | 17/23 valid; max angle 89.45°, aspect 4.26, drop 0.271 | Strong transition exists, but visible horizontal persistence is shorter than the baseline 0.6 s requirement. |
| `fall-19` | 21/34 valid; zero horizontal samples; max angle 40.41°, drop 0.077 | MediaPipe never represents the fall as horizontal; pose loss and sub-threshold orientation/drop prevent a candidate. |
| `fall-20` | 38/38 valid; five horizontal samples; max measured recent-upright drop 0.061 | Horizontal samples do not have a qualifying recent upright-to-horizontal drop within the 1.5 s window. |
| `fall-23` | 21/26 valid; all valid samples upright; max angle 17.37° | The pose model keeps the torso upright. A late hip displacement exists, but the required orientation transition is absent. |
| `fall-25` | 24/29 valid; one horizontal sample; drop 0.094 | Both the 0.12 drop and 0.6 s persistence requirements fail. |
| `fall-26` | 13/21 valid; four horizontal samples; drop 0.061 | Brief horizontal evidence, low measured drop, and eight unknown samples prevent a continuous qualifying transition. |
| `adl-30` | 70/136 valid; 23 horizontal samples; trigger aspect 0.559 | Bending rotates the torso past 55° while knees/ankles are missing. The baseline has no full-body shape gate, so torso rotation alone persists as a false fall. |

The source intervals are UR cam0 depth-posture label `0` mapped to RGB time. They are not independent RGB human event-onset annotations. Several interval midpoints visually depict bending or transition rather than the final grounded posture, which explains why source timing and RGB pose state do not always align semantically.

The original temporal report's precision `1.000` was calculated only across ten positive fall videos; it omitted the `adl-30` negative-video false alarm. Per-video matching itself was one-to-one and valid. The corrected hybrid scope includes all predictions from 20 videos, ten source-positive intervals, and ten video-level negative controls; baseline temporal precision is therefore `0.800`, not `1.000`.
