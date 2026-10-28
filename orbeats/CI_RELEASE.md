<!-- START_PROTECTED -->

# CI/CD Release Instructions

This document describes the CI/CD pipeline for Beat Saber Deluxe and serves as the release body reference. The release workflow is defined in `.github/workflows/plugin-build.yml`.

## Artifacts Per Release

### 📦 Plugin

| File                          | Description                                                        |
| ----------------------------- | ------------------------------------------------------------------ |
| `plugins/beat_saber_deluxe.prx`       | **CI-built release build** — no verbose logging, minimal file size. Deployed automatically by `--deploy-full` (the pipeline uses this bundled binary when no source tree/Makefile is present) |
| `plugins/beat_saber_deluxe_debug.prx` | **CI-built debug build** — verbose ps4 logging (`bs_log.txt`); deploy with `--deploy-full --debug-logging` (replaces the same plugins.ini entry — re-deploy without the flag to restore quiet logging) |
| `plugins.ini`                 | GoldHEN configuration for CUSA12878                                |
| `redirects.json`              | Empty song-redirect template — the pipeline regenerates the real file on every deploy |

### 🎵 Song Conversion Pipeline

| File                                 | Description                                      |
| ------------------------------------ | ------------------------------------------------ |
| `tools/full_custom_song_pipeline.py` | Main pipeline script for converting custom songs |
| `tools/*.py`                         | Supporting tools (downloader, audio encoder, pack-mode bundle builder, song-previews patcher) |
| `VERSION`                            | Pipeline version                                 |
| `beat_saber_song_ids.json`           | Song-slot catalog: every pack, slot ID, stock song title, bundle name — the pipeline's targeting database |
| `requirements.txt`                    | Python dependencies for the pipeline + web app (fastapi/uvicorn; **python-multipart for the M13 zip/audio uploads; quickjs for the JS syntax/boot-wiring test gates**) |
| `ps4_config.example.json`             | Copy to `ps4_config.json`, fill in your PS4's IP/FTP |

### 🌐 Web App (`webapp/`) — the pipeline without the terminal

| File | Description |
| ---- | ----------- |
| `webapp/server.py` | Local web UI (FastAPI, binds **127.0.0.1 only**) — run `python3 webapp/server.py` and open the browser it launches. A lower-right badge shows the web app / pipeline / plugin versions so you can always tell which build you're running |
| `webapp/adapters/` | Thin-layer adapters: every deploy is the same pipeline subprocess command, zero re-implemented logic |
| `webapp/static/` | The UI (12 tabs): **Get Started** (the guided path for new users: prerequisite checklist → download this release → per-OS extract + run commands → wizard), **Setup Wizard** (game-dump validation + PS4 connection test + config writer), **Song Picker** (BeatSaver search with native-difficulty badges **+ M13: Beat Sage generation — any audio → AI map, with the v1/v2 model selector, per-difficulty chart statistics + sparse-chart warnings, and the 🧪 on-demand rights-clean test song — + local song folders/map zips with live validation + a persistent staged-songs list**), **Deploy** (guided, live console, PASSED/FAILED verdict), **Manage Songs** (per-pack table + surgical clear), **Full Loadout** (every pack/song, printable to PDF as a reference), **Feature Flags** (live toggles + a simulated PS4 boot toast), **Batch** (all 34 example packs parsed live from the scripts + custom batch builder with save/load/export + multi-pack checkbox deploys), **Backup / Restore** (the battle-tested backup script, browsable folder, optional clean-PS4), **PS4 state**, **Feature Request** (prefilled GitHub issue), **Game Dump Guide** with a ready-made `dumper.cfg` (`split=3`) |
| `webapp/batch_runner.py` | Batch deploys run as ONE serial job — each song's exact `--deploy-full` in sequence, stopping at the first failure (the `script1 && script2` semantics) |
| `webapp/beatsage_client.py` | **M13:** the Beat Sage Tier-1 generation job — uploads to beatsage.com, polls at THEIR own UI's cadence, downloads, validates, and stages the map (one job, live console, cancellable; any failure points at the always-works guided flow) |
| `webapp/adapters/songs.py`, `beatsage.py`, `testsong.py` | **M13:** local-map validation (V2/V3/V4, per-problem To-fix messages), zip-slip-guarded intake + persistent staging with **per-difficulty chart statistics** (notes/NPS avg+peak/bombs/walls — sparse charts warn BEFORE you play); the live-captured Beat Sage contract; the rights-clean test song synth (deterministic — the 🧪 button generates it on the spot) |
| `webapp/build_pages.py` | Builds the GitHub Pages bundle from the same UI (command-builder mode) |
| `webapp/VERSION` / `webapp/CHANGELOG-WEBAPP.md` | Web app version + changelog (separate from pipeline/plugin) |
| `webapp/requirements` | Needs `pip install -r requirements.txt` (fastapi, uvicorn) — already included there |

> The same UI is also hosted on GitHub Pages (command-builder mode): configure
> everything visually, copy the generated `python3 tools/full_custom_song_pipeline.py …`
> command, and run it locally. Deploys need the local backend (or the CLI) —
> browsers can't reach your PS4 or your game dump.

### 📚 Documentation

| File | Description |
| ---- | ----------- |
| `README.md` | Main documentation (pipeline, features, feature flags, clean slate) |
| `PIPELINE-README.md` | Pipeline-internal README |
| `CHANGELOG-PLUGIN.md` / `CHANGELOG-PIPELINE.md` | Full change history |
| `docs/features/*.md` | Feature docs: custom-song replacement, song metadata modification, beatmap mode mapping, song previews, in-game plugin toggle, **game-data extractor**, **Beat Sage + local songs** |
| `docs/examples/`, `docs/how-to-replace-pack.md` | Pack-replacement walkthroughs |
| `docs/example-scripts/example_*` | **All 69 ready-to-run example files** — per-music-pack command docs (`.md`) + shell scripts (`.sh`) for every DLC pack, with verified BeatSaver MAP_IDs for five packs (billie eilish, britney spears, camelia, lizzo, rolling stones) and `[REPLACE_WITH_MAP_ID]` templates for the rest |
| `docs/release-validation-test-procedure.md` + `.sh` | **Release validation procedure + the automated validator** — the exact hardware test this release passed (read-only verify, build quality, end-to-end deploy incl. the bundled plugin, feature-flag and kill-switch round-trips, surgical revert + restore, state-integrity auto-restore, song-previews variant + flag round-trip). Run it against your own PS4 to validate your deployment |

## Running the Pipeline

**Prerequisites:**

- Python 3.8+
- `pip install UnityPy` (see `requirements.txt` in this zip)
- A PS4 with GoldHEN, FTP enabled (port 2121), configured in `ps4_config.json`
  (copy `ps4_config.example.json` and fill in your PS4's IP)

**No terminal? Start the web app instead** — it writes `ps4_config.json` for
you (Setup Wizard), validates your game dump, tests the PS4 connection, and
deploys with live logs:

```bash
pip install -r requirements.txt
python3 webapp/server.py
```

**⚠️ REQUIRED — bring your own decrypted game dump (`ps4_dump/`):**

> This release does **NOT** include any dumped game data. The pack-bundle
> patching and catalog merging in the pipeline read the ORIGINAL stock pack
> bundles and Addressables catalog from a decrypted dump of YOUR OWN copy of
> the game. **You are responsible for obtaining your own dump of the correct
> game version with the DLC music packs you intend to modify, and placing the
> files into the `ps4_dump/` folder** next to the repo (the pipeline expects
> `ps4_dump/CUSA12878-patch/...`). We cannot and do not distribute these
> files — they are copyrighted game content. The expected layout is
> documented in the README ("ps4_dump"). Without the dump, per-song deploys
> still work (they only need the dump for the music-pack mode mapping /
> catalog steps); pack-mode deploys will tell you which bundle is missing.

**Quick Start — one command per song (recommended):**

```bash
# Download from BeatSaver, convert, and deploy song + its music pack + plugin +
# feature flags + redirects + catalog, then self-validate — all in ONE command:
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song <MAP_ID> \
    --target <SLOT_NAME> \
    --deploy-full
```

Each `--deploy-full` is self-contained: it deploys the plugin (built from source
in a repo checkout, or the bundled CI build in this extracted release), deploys
only that song's bundle, surgically patches that song's music pack (with
a matching Addressables catalog so the pack passes Unity's CRC check), regenerates
`redirects.json` scoped to exactly what is deployed (existing custom songs in
other packs are preserved), and runs post-deploy validation. **A failed validation
aborts the deploy with a non-zero exit** — the game never boots into a broken
state silently.

Useful variants:

```bash
# Temporarily play only OFFICIAL songs (kill switch — no uninstall, next boot):
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=false
# ...and back to custom songs:
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=true

# Skip building/deploying the plugin (pin a specific plugin build on the PS4):
python3 tools/full_custom_song_pipeline.py ... --deploy-full --skip-plugin-deployment

# Revert a single song slot to stock without a full clean slate:
python3 tools/full_custom_song_pipeline.py --clear-target-song <SLOT_NAME>
```

See the main `README.md` for full pipeline documentation.

## Runtime Feature Flags (`features.json`)

| Flag | Default | Purpose |
|------|---------|---------|
| `enable_plugin` | `true` (when absent) | Global kill switch — `false` = fully inert plugin, 100% official songs on next boot |
| `enable_custom_song_replacements` | **`true`** | Gates all bundle redirects |
| `enable_song_metadata_modification` | **`true`** | Gates song name/artist swaps in the UI |
| `enable_beatmap_mode_mapping` | **`true`** | Gates extra game modes (OneSaber/NoArrows/90Degree) — OFF serves stock pack bundles + catalog |
| `enable_song_previews` | **`true`** | Gates **song previews**: highlighting a custom song in the menu plays its own ~10s audio (the mapper's chosen moment when known, else the busiest-bar heuristic) instead of the stock song's clip. Previews ride inside the patched pack bundles — either this flag or `enable_beatmap_mode_mapping` keeps the patched pair live |
| `enable_game_data_extractor` | **`true`** | **M12: the no-dump flow** — the plugin copies the files the pipeline needs (per-slot templates, pack bundles, catalog) out of the game's own data during a normal boot; the web app pulls them into the local `game_data/` cache (a drop-in for `ps4_dump/`). Full details: `docs/features/game-data-extractor.md` |
| `enable_in_game_plugin_toggle` | **`true`** | **In-game plugin toggle (hardware-confirmed):** arms the Move hotkey — hold the **Move button + trigger together for 2 seconds** to flip the global plugin state (a notification sounds; **restart Beat Saber to apply**). Works even while the plugin is toggled OFF so you can always flip back without a PC. Full details: `docs/features/in-game-plugin-toggle.md` |

On boot the plugin shows one combined toast with its state:
`BS Deluxe vX (ON) / By Chris Primeish / (6/6 features ON)` — or
`BS Deluxe vX (OFF) / By Chris Primeish / (official songs only)`. The debug
build (`--deploy-plugin --debug-logging`) reports its version with a ` DEBUG`
suffix so logs and toasts always show which build is live.

## Plugin Installation

1. Copy `beat_saber_deluxe.prx` to `/data/GoldHEN/plugins/` on your PS4
2. Copy `features.json` to `/data/GoldHEN/AFR/CUSA12878/features.json`
3. Add `/data/GoldHEN/plugins/beat_saber_deluxe.prx` under `[CUSA12878]` in `/data/GoldHEN/plugins.ini`
4. Deploy songs with the pipeline (it manages `redirects.json` for you — the
   bundled copy is an empty template)
5. Launch Beat Saber — the boot toast confirms the plugin state
<!-- END_PROTECTED -->
