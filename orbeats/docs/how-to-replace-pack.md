# How to Replace Every Song in a Song Pack

This guide walks through the end-to-end process of replacing an entire official Beat Saber song pack (e.g., Camellia Music Pack) with custom community songs.

## Prerequisites
- A target song pack on PS4 (e.g., `CUSA12878`).
- Pipeline script (`tools/full_custom_song_pipeline.py`) installed and configured.
- A list of BeatSaver Map IDs for your replacements.

## Flags

Since v0.5314 these are all **default ON** (the explicit flags below remain as
no-op compat options):
- PCM16 FSB5 audio encoding (lossless — required for PS4 compatibility)
- Full-length audio (no 12MB padding truncation)
- V2→V3.2.0 beatmap conversion (required for Beat Saber PS4)

Pack replacement (one song at a time — the recommended flow):
- `--download-beat-saver-song <MAP_ID>` — fetch the custom song from BeatSaver
- `--target <SLOT_NAME>` — which song slot to replace
- `--deploy-full` — ONE command: bundle + music-pack patch + catalog + plugin +
  features.json + scoped redirects + post-deploy validation (exits non-zero on
  validation failure)

Metadata: song/artist names are picked up from the map's Info.dat
automatically; `--song-name`/`--artist` override if desired.
- `--generate-config` — Update `redirects.json` with new slot mapping
- `--deploy-config` — Upload updated config to PS4

## End-to-End Workflow

For each song you wish to replace, follow these steps:

### 1. Execute Pipeline for Each Song
Run the pipeline for each song in your target pack. Replace `<MAP_ID>`, `<TargetSlot>`, `<SongName>`, and `<Artist>` with the specific values for your pack.

```bash
# Example for Camellia Pack (Song 1: Crystallized -> Bloom)
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song 12a \
    --target Crystallized \
    --song-name "Bloom" \
    --artist "ODESZA" \
    --pcm16 --no-pad --convert-to-v3 \
    --deploy \
    --generate-config \
    --deploy-config
```

*Note: You only need to run `--generate-config` and `--deploy-config` once if you prefer, but running it every time is safe as it merges into the existing `redirects.json`.*

### 2. Verify Deployment
After the pipeline completes:
1. Ensure the log shows `✅ Redirect config deployed` and `Beatmaps replaced: X/5`.
2. Check the PS4 folder `/data/GoldHEN/AFR/CUSA12878/` via FTP.
3. You should see `{TargetSlot}_v3.bundle` bundles for every replaced song.

### 3. Final Metadata Sync
Once all songs are deployed, perform a final sync of the metadata:
```bash
python3 tools/full_custom_song_pipeline.py \
    --deploy-plugin \
    --enforce-config
```
This ensures your `redirects.json` and `song_metadata.json` are consistent and pushed to the PS4.

## Example Song Pack Replacements
| Original Song | Replacement Song | BeatSaver ID |
| :--- | :--- | :--- |
| **Crystallized** | Bloom | 12a |
| **Cycle Hit** | Powerful | 133 |
| **EXiT This Earth's Atmosphere** | Red Lips | 156 |
| **Ghost** | Lone Digger | 1bf |
| **Light it up** | Batshit | 7e |
| **WHAT THE CAT!?** | G.O.M.D | 7f |
