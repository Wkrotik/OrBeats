# Feature: Beatmap Mode Mapping

Auto-detect custom song beatmap files and map them to the game's 4 characteristic
mode slots (**Standard, OneSaber, NoArrows, 90Degree** — 360Degree was purged in
v0.5308 as 360° gameplay is physically unsupported on PS4 single-camera ~90° tracking)
with configurable fallback logic for slots without dedicated files.

## Requirements

1. **Feature flag enabled** — `enable_beatmap_mode_mapping` must be `true` in `/data/GoldHEN/AFR/CUSA12878/features.json` (absent key defaults `false`; the pipeline's DEFAULT_FEATURES deploys it as `true`). Since plugin v0.8046 the flag REALLY gates: OFF serves stock pack bundles + catalog (Standard-only everywhere, per-song customs still play)
2. **Pipeline v0.5310+** — CLI flag `--enable-beatmap-mode-mapping` (plus optional `--fallback-mode-map`, `--skip-mode-generation`, `--one-saber-min-gap`, `--rotation-cycle-beats`)

## How It Works

### Phase 1 (Pipeline-side, v0.5307+)

The pipeline performs the following steps when `--enable-beatmap-mode-mapping` is passed:

1. **`detect_song_modes(song_dir)`**
   Scans all `.dat` and `.json` files in the song directory, classifies them by
   mode using filename patterns:

   | Pattern | Example | Mode Detected |
   |---------|---------|---------------|
   | Bare difficulty | `Expert.dat` | Standard |
   | Standard suffix | `ExpertPlusStandard.dat` | Standard |
   | Mode suffix | `ExpertPlusOneSaber.dat` | OneSaber |
   | Mode prefix | `OneSaberExpert.dat` | OneSaber |
   | Beatmap dot | `ExpertPlus.beatmap.dat` | Standard |
   | Legacy | `EasyLegacy.dat` | Standard (alias) |
   | SingleSaber | `ExpertSingleSaber.dat` | OneSaber (alias) |
   | Lawless | `ExpertLawless.dat` | NoArrows (alias) |

2. **Mode generation (v0.5310, Step 5a — BEFORE beatmap replacement)**
   `generate_missing_mode_beatmaps(song_dir, detected_modes, enabled_modes, ...)`
   fills gaps: for every difficulty that has a Standard source, it writes
   `<Diff><Mode>.dat` for each enabled mode the song does NOT already provide.
   Generation is the **default** under `--enable-beatmap-mode-mapping`; opt out
   with `--skip-mode-generation`. Songs' own mode files are **never overwritten**,
   and difficulties without a Standard source are skipped.
   - **NoArrows** — `_generate_no_arrows`: every color note becomes a dot
     (V2 `_cutDirection`/V3 `d` = 8); bombs keep direction. Non-mutating.
   - **OneSaber** — `_generate_one_saber`: recolors all notes to the RIGHT/blue
     saber (color 1 — red OneSaber maps are unplayable, fixed v0.5323) AND
     converts every note to a DOT (`d`/`_cutDirection` = 8, since v0.5338 — the
     user-facing convention is dots-only), removes simultaneous notes (one
     saber cuts one note per instant). Mapper-authored `<Diff>OneSaber.dat`
     charts are normalized through the same generator at injection. Bombs pass
     through. Non-mutating.
   - **90Degree** — `_generate_90_degree`: V2 sources are converted to V3 first,
     then `rotationEvents` stepping ±15° lanes within a ±45° arc are added every
     `cycle_beats` (rewritten v0.5313 — the old alternating +90/-90 swung the
     lane perpendicular to the player)
     (default 8.0 = 2 measures, `--rotation-cycle-beats`). Non-mutating.

3. **`build_mode_mapping(detected_modes, fallback_map)`**
   Resolves the game characteristic slots against the detected modes.
   Default fallback chain (each mode falls back to the next if not detected):

   ```
   90Degree → Standard
   NoArrows → Standard
   OneSaber → Standard
   Standard (always present)
   ```

   Custom fallbacks override defaults: `--fallback-mode-map 90Degree=Standard`.

4. **`apply_mode_mapping(cab, enabled_modes)`**
   Injects new `_difficultyBeatmapSets` entries into the per-song bundle's
   `BeatmapLevel` object by cloning Standard's beatmap asset references.
   Each enabled mode gets its own entry in the array.

### Mode Slot Ordering

The 4 game characteristic slots are always processed in this order:

```python
GAME_CHARACTERISTIC_MODES = [
    "Standard", "OneSaber", "NoArrows", "90Degree"
]
```

### CLI Examples

```bash
# Auto-detect modes + generate missing mode beatmaps (default):
python3 full_custom_song_pipeline.py \
  --song-dir ./my_song \
  --target startmeup \
  --enable-beatmap-mode-mapping

# Generate modes but keep tuning knobs at defaults:
python3 full_custom_song_pipeline.py \
  --song-dir ./my_song \
  --target startmeup \
  --enable-beatmap-mode-mapping \
  --one-saber-min-gap 0.5 \
  --rotation-cycle-beats 4.0

# Map modes but DON'T generate beatmaps (use song's own mode files only):
python3 full_custom_song_pipeline.py \
  --song-dir ./my_song \
  --target startmeup \
  --enable-beatmap-mode-mapping \
  --skip-mode-generation

# Custom fallback: 90Degree falls to Standard directly:
python3 full_custom_song_pipeline.py \
  --song-dir ./my_song \
  --target startmeup \
  --enable-beatmap-mode-mapping \
  --fallback-mode-map 90Degree=Standard
```

## Relationship to `--enable-modes`

| Flag | Behavior |
|------|----------|
| `--enable-modes` | Manually specify which modes to add (e.g. `OneSaber,90Degree`). All use cloned Standard beatmaps. |
| `--enable-beatmap-mode-mapping` | Auto-detect modes from files + generate missing mode beatmaps. Falls back through chain for undetected modes. May be combined with `--enable-modes` for explicit additions. |

When both are present, `--enable-beatmap-mode-mapping` runs after `--enable-modes`
and adds any modes it detects that weren't manually enabled.

## Known Limitations

- ~~**Mode selector in-game still shows only Standard** (as of v0.5310, Exp 177).~~
  **✅ CLOSED (Exp 180, 2026-08-08):** The catalog-redirect + pack-bundle patch approach works. The selector now shows Standard/OneSaber/NoArrows/90Degree for songs with patched pack bundles. See [[pack-bundle-patching]] for the complete working method.
- **Per-song mode sets ARE injected** (Standard/OneSaber/NoArrows/90Degree each with 5 difficulties) with real generated beatmap data compiled via the mode mapping path.
- **The 90Degree→Standard fallback** is the default; 360Degree was removed (v0.5308).

## ✅ RESOLVED: NoArrows Bug (Exp 181, 2026-08-09)

**NoArrows mode showed arrows instead of dots.** Root cause was two bugs in `_create_text_asset_object()` (the function that creates new TextAsset objects for injected beatmap data):

1. **`type_id=0` hardcoded:** This mapped new TextAssets to MonoScript (class_id 115) instead of TextAsset (class_id 49) in the CAB's type table. The game's Unity runtime interpreted these as MonoScript objects, couldn't find them as beatmap assets, and silently fell back to Standard beatmaps for all modes.
2. **Binary serialization format mismatch:** Used manual `struct.pack` with null terminators and `len+1` length prefix. Unity's actual format uses `write_aligned_string` (int32 length + UTF-8 data + 4-byte alignment, no null in length). The mismatch caused `read_typree()` to fail with "read_str out of bounds" in the Unity runtime.

**Fix:** Use `EndianBinaryWriter.write_aligned_string()` for `m_Name` and `write_int(len) + write(bytes) + align_stream(4)` for `m_Script`. Set `type_id` to the actual TextAsset type index from `cab.types` (not hardcoded 0).

**Verification:** All 5 NoArrows difficulties confirmed to have dot notes (d=8) at Easy/Normal/Hard/Expert/ExpertPlus levels. 381 tests pass. Bundle saved with LZ4 compression and verified loadable.

## Testing

```bash
# Unit tests for detect/build/map/generate functions:
python3 -m pytest tests/test_pipeline.py -v -k "TestDetectSongModes or TestBuildModeMapping"

# Mode generator unit tests (V2+V3, mutation-safety, gap-filling):
python3 -m pytest tests/test_mode_generators.py -v

# Integration tests (detect→build→generate chain):
python3 -m pytest tests/test_integration.py -v -k "TestBeatmapModeMappingIntegration"

# Full suite:
python3 -m pytest tests/
```
