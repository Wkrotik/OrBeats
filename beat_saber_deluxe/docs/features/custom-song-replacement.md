# Feature: Custom Song Replacement

Replace Beat Saber DLC song audio and beatmaps with community-made custom songs.

## Requirements

1. **Feature flag enabled** — `enable_custom_song_replacements` must be `true` in `/data/GoldHEN/AFR/CUSA12878/features.json`
2. **Plugin deployed** — `beat_saber_deluxe.prx` must be deployed to `/data/GoldHEN/plugins/`
3. **Custom song bundles** — Built bundles must be deployed to `/data/GoldHEN/AFR/CUSA12878/`
4. **Redirect config** — `redirects.json` must be deployed to `/data/GoldHEN/AFR/CUSA12878/`
5. **Decrypted game dump** — Required for building bundles (see [Prerequisites](../../README.md#prerequisites))

## How It Works

The plugin hooks the PS4's file I/O system (`open`, `fopen`, `close`) to intercept attempts to load song asset bundles. When the game tries to load a DLC song bundle from `BeatmapLevelsData/`, the plugin checks if a redirect exists for that path.

If a redirect is found, the plugin redirects the file open to the custom song bundle stored in `/data/GoldHEN/AFR/CUSA12878/`. The game loads the custom audio and beatmaps instead of the originals.

### Redirect Flow

```
Game requests: /archive/mount/point/Media/StreamingAssets/BeatmapLevelsData/startmeup
Plugin checks: redirects.json → "BeatmapLevelsData/startmeup" → "startmeup_v3.bundle"
Plugin redirects to: /data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle
```

> ⚠️ **Naming rule (Exp 187):** the redirect VALUE is the exact filename the plugin opens
> (`AFR_BASE/TITLE_ID/` + value), and `open()` is case-sensitive. The value MUST byte-match
> the deployed bundle filename — `<canonical slot casing>` + `_v3.bundle`. The pipeline's
> `_deployed_bundle_name()` + `_ensure_mass_song_redirects()` enforce this on every config
> save, so regenerating the config can never silently point at a stale `_v3` file again.

## How It Appears In-Game

- **Song plays** — Custom audio and beatmaps load correctly
- **Song name/artist** — Shows original DLC metadata (unless song metadata modification is also enabled)
- **Cover art** — Shows original DLC cover art
- **Difficulty levels** — Custom beatmaps replace all difficulty levels

## Why This Approach

GoldHEN provides a file redirection hook that can intercept any file open on the PS4. By placing custom song bundles in a known location and redirecting the game's file opens, we can replace songs without modifying the game's code or memory.

This approach:
- Works with any GoldHEN-enabled PS4
- Doesn't require game modding or code injection
- Can be toggled on/off via feature flags
- Supports any song in the game's `BeatmapLevelsData/` directory

## Files Involved

| File | Location | Purpose |
|------|----------|---------|
| `redirects.json` | `beat_saber_deluxe/redirects.json` | Local copy — maps original paths to custom bundles |
| `redirects.json` | `/data/GoldHEN/AFR/CUSA12878/redirects.json` | PS4 copy — read by plugin at runtime |
| `main.cpp` | `beat_saber_deluxe/src/main.cpp` | Plugin source — file I/O hooks + redirect logic |
| `full_custom_song_pipeline.py` | `beat_saber_deluxe/tools/full_custom_song_pipeline.py` | Pipeline — builds custom song bundles |
| `--deploy-full` | `tools/full_custom_song_pipeline.py` | Self-contained per-song deploy (bundle + pack patch + catalog + plugin + redirects + validation). `deploy_all.sh` is OUTDATED (13 hardcoded slots) |

## Redirect Config Format

```json
{
  "redirects": {
    "BeatmapLevelsData/startmeup": "startmeup_v3.bundle",
    "BeatmapLevelsData/angry": "angry_v3.bundle"
  }
}
```

- **Key**: Relative path from `StreamingAssets/` to the original bundle
- **Value**: Filename of the custom bundle in `/data/GoldHEN/AFR/CUSA12878/`

## Building Custom Songs

### From BeatSaver

```bash
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song <MAP_ID> \
    --target startmeup \
    --pcm16 --no-pad --convert-to-v3 \
    --deploy --generate-config --deploy-config
```

### From Local Directory

```bash
python3 tools/full_custom_song_pipeline.py \
    --song-dir /path/to/song \
    --target startmeup \
    --pcm16 --no-pad --convert-to-v3 \
    --deploy --generate-config --deploy-config
```

## Available Song Slots

See [Available Song Slots](../../README.md#available-song-slots-default-targets) in the main README.

## Limitations

- **Song metadata unchanged** — Song names, artists, and cover art show original DLC metadata unless song metadata modification is also enabled
- **No note color customization** — Left/right saber colors are the game's defaults
- **Bundle size** — Custom bundles can be larger than originals due to audio encoding

## Debugging

Check the PS4 log for redirect entries:

```bash
# Download log
curl -s ftp://192.168.100.117:2121/data/GoldHEN/AFR/CUSA12878/bs_log.txt -o ps4_log.txt

# Check for redirects
grep "REDIRECTED" ps4_log.txt

# Check redirect loading
grep "loaded.*redirects" ps4_log.txt
```

Expected output:
```
loaded 32 redirects from config
  e.g. BeatmapLevelsData/startmeup -> /data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle
[OPEN #123] /archive/mount/point/Media/StreamingAssets/BeatmapLevelsData/startmeup -> REDIRECTED
```
