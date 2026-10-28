# Reference Bundles

## therollingstones_WORKING_v0.5324era_aug20.bundle
md5 5ed238290df7d06722786193cc0bd813, 7,906,184 B.

Pulled from the PS4 (`/data/GoldHEN/AFR/CUSA12878/pack_modes_bundles/`, Aug 20 build).
This is the ONLY known hardware-validated pack bundle structure: user played all 4 modes
(Standard/OneSaber/NoArrows/90Degree) successfully across all 11 Rolling Stones songs.

Structure (extracted, ground truth for `build_modes_blob()`):
- Every BeatmapLevelSO: exactly 4 preview sets
- pathIDs DISTINCT per set: Standard -7286399427822119286, OneSaber -5623662769225589684,
  NoArrows -8583864861369561029, 90Degree -5995858427784384822 (i.e. CHAR_PATH_IDS[mode],
  even though NoArrows/90Degree pathIDs do not exist in BeatmapLevelsData — the game does
  NOT resolve them there and this is safe)
- Every set: diffCount 5, ranks exactly [0,1,2,3,4]

The v0.5325 "pathID fix" (all sets -> Standard's pathID) CRASHES the game at menu init
(CE-34878-0, Exp 198). Reverted in v0.5326.
