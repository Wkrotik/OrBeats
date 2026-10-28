# Feature: Song Metadata Modification

Replace song names and artist names displayed in the game's UI with custom text.

## Requirements

1. **Feature flag enabled** — `enable_song_metadata_modification` must be `true` in `/data/GoldHEN/AFR/CUSA12878/features.json`
2. **Plugin deployed** — `beat_saber_deluxe.prx` must be deployed to `/data/GoldHEN/plugins/`
3. **Song metadata file** — `song_metadata.json` must be deployed to `/data/GoldHEN/AFR/CUSA12878/`

## How It Works

The plugin hooks `MoveNext()` of the `LevelListTableCell.SetDataFromLevelAsync` state machine (RVA `0x1D377C0`). This is the method that populates song list cells with data from `BeatmapLevel` objects.

When the hook fires, it:
1. Reads `beatmapLevel` from the state machine struct (offset 0x30)
2. Reads `beatmapLevel.songName` (offset 0x20) and `beatmapLevel.songAuthorName` (offset 0x30)
3. Checks if either field matches a key in the replacement table
4. If matched, creates a new IL2CPP `System.String` with the replacement text
5. Writes the replacement string pointer directly to the `BeatmapLevel` field
6. Calls the original `MoveNext()` — which now reads our replacement from the data source

This approach modifies the **data source** rather than the text output, which means the UI framework reads our replacement directly without being overwritten by re-rendering.

## How It Appears In-Game

### Song List (Pack View)
- **Song name line**: Shows `CustomSongName / CustomArtist` (e.g., "Espresso / Sabrina Carpenter")
- **Artist line**: Blank (single-artist packs only)

### Song Details Panel
- **Song name**: Shows custom song name
- **Artist**: Shows custom artist name

### In-Level Pause Menu
- **Song name**: Shows custom song name
- **Artist**: Shows custom artist name

## Why This Approach

Previous approaches were tried and failed:

1. **Memory injection (v0.66–v0.8024)** — Scanned IL2CPP heap for `BeatmapLevel` objects. After 14+ versions, 0 strings found. Strings don't exist in scannable memory at scan time.

2. **TMP_Text.set_text hook (v0.8026–v0.8035)** — Hooked the Unity text rendering pipeline. Works for song details and pause menu, but song list re-renders from the `BeatmapLevel` data model after the hook fires, overwriting the replacement.

3. **TMP_Text.SetText hook (v0.8037)** — Same issue as above — song list re-renders from data model.

4. **SetDataFromLevelAsync hook (v0.8038)** — Hooked the async method entry point, but it's a trampoline that gets inlined by `AsyncVoidMethodBuilder.Start<T>()`. Never fired.

5. **MoveNext() hook (v0.8039)** — **WORKS.** Hooks the state machine's actual execution method. Modifies `BeatmapLevel` fields before the original reads them.

## Files Involved

| File | Location | Purpose |
|------|----------|---------|
| `song_metadata.json` | `beat_saber_deluxe/song_metadata.json` | Local copy — source of truth for replacements |
| `song_metadata.json` | `/data/GoldHEN/AFR/CUSA12878/song_metadata.json` | PS4 copy — read by plugin at runtime |
| `beat_saber_song_ids.json` | `beat_saber_deluxe/beat_saber_song_ids.json` | Official song reference — exact game strings |
| `main.cpp` | `beat_saber_deluxe/src/main.cpp` | Plugin source — MoveNext hook + metadata loading |
| `full_custom_song_pipeline.py` | `beat_saber_deluxe/tools/full_custom_song_pipeline.py` | Pipeline — `manage_song_metadata()` function |

## Song Metadata JSON Format

```json
{
  "song_names": {
    "Start Me Up": "Espresso / Sabrina Carpenter",
    "Angry": "Rhythm Is A Dancer / Pegboard Nerds"
  },
  "song_artists": {
    "The Rolling Stones": " ",
    "Billie Eilish": " ",
    "Lizzo": " "
  }
}
```

- **`song_names`**: Maps exact game song names to replacement strings. The replacement format is typically `CustomSongName / CustomArtist`.
- **`song_artists`**: Maps exact game artist names to replacement strings. A single space `" "` blanks the artist line.

### Key Format Rules

- **Keys must match the exact game string** — case-sensitive, including trailing spaces. The pipeline resolves slot IDs (e.g., "StartMeUp") to exact game names via `beat_saber_song_ids.json`.
- **Song name replacements** can include the artist: `"Espresso / Sabrina Carpenter"` shows as one line in the song list.
- **Artist blanking** uses a single space: `" "` — this clears the artist line in the song list.

## Limitations

### Single-Artist Packs Only

Artist blanking (`"The Rolling Stones" → " "`) is **global** — it replaces every occurrence of that string. This works perfectly for single-artist packs (Rolling Stones, Billie Eilish, Lizzo) where all songs share the same artist.

For multi-artist packs, this approach would incorrectly blank all artist names. Currently, only single-artist packs are targeted.

### Case Sensitivity

Song name matching is **case-sensitive** and **space-sensitive**. The pipeline uses `beat_saber_song_ids.json` to resolve slot IDs to exact game strings. If the song IDs file is outdated or incorrect, matching will fail.

The plugin also trims trailing spaces before comparison for robustness.

### No Dynamic Updates

The replacement table is loaded from `song_metadata.json` at plugin startup. Changes require restarting Beat Saber.

## Managing Song Metadata via Pipeline

```bash
# Add/update a song name replacement
python3 tools/full_custom_song_pipeline.py \
    --song-name "Custom Song / Custom Artist" \
    --target StartMeUp \
    --deploy

# Add/update an artist replacement
python3 tools/full_custom_song_pipeline.py \
    --artist " " \
    --target TheRollingStones \
    --deploy
```

The `--target` parameter accepts slot IDs (e.g., `StartMeUp`) or exact song names. The pipeline resolves slot IDs to exact game strings via `beat_saber_song_ids.json`.

## Debugging

Check the PS4 log for `[METADATA]` entries:

```bash
# Download log
curl -s ftp://192.168.100.117:2121/data/GoldHEN/AFR/CUSA12878/bs_log.txt -o ps4_log.txt

# Check MoveNext hook entries
grep "MoveNext" ps4_log.txt

# Check for hook installation
grep "hooks installed" ps4_log.txt
```

Expected output:
```
[METADATA] TMP_Text.set_text + SetText + MoveNext hooks installed
[METADATA] MoveNext #1: songName 'Start Me Up' -> 'Espresso / Sabrina Carpenter'
[METADATA] MoveNext #2: author 'The Rolling Stones' -> ' '
```
