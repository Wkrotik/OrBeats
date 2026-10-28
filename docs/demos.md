# Beat Saber Deluxe Demo Videos and Screenshots🎵⚡

## Demo Videos

- [Demo video v0.8053 plugin, v0.5363 converter](https://youtu.be/NsUhL8NioCA)
- [Demo video v0.8048 plugin, v0.5362 converter](https://youtu.be/vd4rVxODBmY)
- [Demo Video v0.8047 plugin, v0.5351 converter](https://youtu.be/WrqExCvC3d4)
- [Demo Video v0.46](https://www.youtube.com/watch?v=J835HDdB-7g)

## In-Game Screenshots

<img width="2048" height="1536" alt="beatsaberdeluxev08040-rollingstones" src="https://github.com/user-attachments/assets/0fd72ed3-122c-436f-8b77-b6fc2bb4982a" />
<img width="1536" height="2048" alt="beatsaberdeluxev08040-billieeilish" src="https://github.com/user-attachments/assets/7a39af3e-d461-4ecf-b2df-e7b408ff0c21" />
<img width="1536" height="2048" alt="beatsaberdeluxev08040-Lizzo" src="https://github.com/user-attachments/assets/795cc606-606e-438e-b65c-dcba45f6996f" />
<img width="766" height="670" alt="image" src="https://github.com/user-attachments/assets/d1e3abbb-c66d-40e1-871c-d94658d9cb2d" />

## Web UI Screenshots

<img width="928" height="914" alt="image" src="https://github.com/user-attachments/assets/95d319e7-8eca-49a6-b434-a3743937a388" />
<img width="942" height="831" alt="image" src="https://github.com/user-attachments/assets/f77ada23-b167-4c38-ab06-a819e1faa2d9" />
<img width="949" height="400" alt="image" src="https://github.com/user-attachments/assets/7cfd03f9-b7dd-4499-853c-21c5361c560a" />
<img width="940" height="902" alt="image" src="https://github.com/user-attachments/assets/fe5693f7-561e-4aa8-bc49-60a2d5458ce6" />
<img width="939" height="738" alt="image" src="https://github.com/user-attachments/assets/0924f8c1-8669-4394-8350-dba67c6e05ff" />
<img width="952" height="277" alt="image" src="https://github.com/user-attachments/assets/82847d07-9a01-470e-9c10-e6ea4dd2007e" />
<img width="943" height="792" alt="image" src="https://github.com/user-attachments/assets/dc7adb87-6e31-41de-b2c4-190e4f4f1755" />
<img width="945" height="838" alt="image" src="https://github.com/user-attachments/assets/a8451469-5ef0-4789-9006-b086a7945436" />
<img width="945" height="798" alt="image" src="https://github.com/user-attachments/assets/b960d728-b00f-4c5f-b442-9eb2a37a783e" />
<img width="950" height="738" alt="image" src="https://github.com/user-attachments/assets/8592a353-fa3d-4f6f-beeb-8e5de2a502e6" />
<img width="940" height="843" alt="image" src="https://github.com/user-attachments/assets/6ec2fac1-6824-4849-b5cf-3dc80872ecca" />
<img width="944" height="518" alt="image" src="https://github.com/user-attachments/assets/68842306-c290-486a-8243-38c0da2f2616" />
<img width="940" height="841" alt="image" src="https://github.com/user-attachments/assets/32f1d884-989b-47ff-99b7-0e233fd0333d" />

> **📋 Prerequisites:**
>
> - **Beat Saber PS4 version 2.04** (CUSA12878, patch 2.04) — this is the specific version all development targets
> - **Full decrypted game dump** — place the dump in `/workspace/ps4_dump/` with the following structure:
>   ```
>   ps4_dump/CUSA12878-app/          # Base game (v1.00)
>   ps4_dump/CUSA12878-patch/        # Game patch (v2.04)
>   ```
>   The dump must include the unpacked patch files (eboot.bin, Media/ directory, etc.). Tools like PS4 Dumper on a jailbroken PS4 create this via the `split=3` config option.
> - **Bring your own dump — it is NOT included in this repo or any release.**
>   Dumped game data is copyrighted content and cannot be distributed. **You are responsible for obtaining your own decrypted dump of the game with the correct version (v2.04) and the DLC loadout you intend to modify** (the music packs whose songs you want to replace must be installed on the PS4 BEFORE dumping — their pack bundles live in the patch's `Media/StreamingAssets/aa/` and the pipeline reads them from your dump). Place the dump files into the `ps4_dump/` folder as shown above.

## Features

| Feature                                                                                     | Status                | Description                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Custom Song Replacement](beat_saber_deluxe/docs/features/custom-song-replacement.md)       | ✅ Working            | Replace DLC song audio and beatmaps with custom songs via GoldHEN file redirection                                                                                                                                                          |
| [Song Metadata Modification](beat_saber_deluxe/docs/features/song-metadata-modification.md) | ✅ Working            | Display custom song names and artists in-game via IL2CPP MoveNext hook                                                                                                                                                                      |
| **Song Previews**                                                                           | ✅ Working (v0.5357+) | Song-menu previews play the CUSTOM song's own ~10s audio (mapper's chosen moment, busy-section fallback), patched into each music pack's preview AudioClips behind the `enable_song_previews` flag. Any pack, any song — fully data-driven. |
| **Song Previews**                                                                           | ✅ Working (v0.5357+) | Song-menu previews play the CUSTOM song's own ~10s audio (mapper's chosen moment, busy-section fallback), patched into each music pack's preview AudioClips behind the `enable_song_previews` flag. Any pack, any song — fully data-driven. |
| [Extra Game Modes](beat_saber_deluxe/docs/features/beatmap-mode-mapping.md)                 | ✅ Working (v0.5316+) | OneSaber/NoArrows/90Degree mode selector support via catalog-redirect + pack-bundle patch (Phase 1 pipeline beatmap generation + Phase 2 pack preview-set injection). Generated modes verified on-device (2026-08-11 boot test).            |
| [Web App Interface](beat_saber_deluxe/webapp/)                                              | 🚧 Phase 1 (M9)       | Point-and-click UI over the pipeline CLI: setup wizard (game-dump guide + live validation), BeatSaver song picker, guided deploys with live log streaming, PS4 state dashboard. Thin layer — every deploy is the same pipeline subprocess.  |
| Note Colors                                                                                 | ⏳ Planned            | Custom left/right saber colors per song                                                                                                                                                                                                     |

> **⚠️ Current limitations:**
>
> - **Single-artist packs only** — Song metadata modification works perfectly for single-artist packs (Rolling Stones, Billie Eilish, Lizzo). Multi-artist packs would incorrectly blank all artist names. Currently only single-artist packs are targeted.
> - **Artist line is blank** — For single-artist packs, the artist line in the song list is intentionally blanked. The custom song name and artist are combined on the song name line (e.g., "Espresso / Sabrina Carpenter").
> - **Deploy via self-contained `--deploy-full`** — The primary workflow is single-song-at-a-time. Run `python3 tools/full_custom_song_pipeline.py --download-beat-saver-song <MAP_ID> --target <slot> --deploy-full` one at a time, testing after each. For clean slate: `python3 /workspace/backup-beat-saber-deluxe-files.py backup --clean-ps4` first.

## Available Song Slots (Default Targets)

The pipeline replaces songs by targeting specific filenames in the game's `BeatmapLevelsData/` directory. Below are the 13 default target slots currently configured. Use the `--target <name>` argument to specify which slot a custom song goes into.

The pipeline can target **any** song present in the game's dump — if the song has a `.bundle` file in `BeatmapLevelsData/`, you can replace it. To use a non-default target, point `--target` at any other bundle name from that directory.

| Target Name              | Original Song                                   |
| ------------------------ | ----------------------------------------------- |
| `angry`                  | Angry                                           |
| `bitemyheadoff`          | Bite My Head Off                                |
| `cantyouhearmeknocking`  | Can't You Hear Me Knocking                      |
| `deadmanwalking`         | Dead Man Walking                                |
| `gimmeshelter`           | Gimme Shelter                                   |
| `icantgetnosatisfaction` | (I Can't Get No) Satisfaction                   |
| `livebythesword`         | Live By The Sword                               |
| `messitup`               | Mess It Up                                      |
| `paintitblack`           | Paint It Black                                  |
| `startmeup`              | Start Me Up (most tested — good starting point) |
| `sugarsoaker`            | Sugar Soaker                                    |
| `sympathyforthedevil`    | Sympathy For The Devil                          |
| `wholewideworld`         | The Whole Wide World                            |

---

## Table of Contents

1. [Devcontainer Setup](#1-devcontainer-setup)
2. [Building the Plugin](#2-building-the-plugin)
3. [Deploying to PS4](#3-deploying-to-ps4)
4. [Activating the Plugin on PS4](#4-activating-the-plugin-on-ps4)
5. [Quick Start: Replace a Song from BeatSaver](#5-quick-start-replace-a-song-from-beatsaver)
6. [Full Custom Song Workflow](#6-full-custom-song-workflow)
7. [PS4 Log Management](#7-ps4-log-management)
8. [Architecture Overview](#8-architecture-overview)
9. [Unit Testing](#9-unit-testing)
10. [Roadmap](#10-roadmap)
11. [Developer Information](#11-developer-information)
12. [License & Credits](#12-license--credits)

---

...

## 11. Developer Information

See [docs/developer-info.md](docs/developer-info.md) for build, test, and release procedures.

## 12. Backup Utility

The `backup-beat-saber-deluxe-files.py` script provides backup, clean, and restore functionality for Beat Saber Deluxe files on PS4.

- **Backup**: `./backup-beat-saber-deluxe-files.py backup` — Creates a datetime-stamped backup zip of all BS Deluxe files from PS4
- **Clean PS4**: `./backup-beat-saber-deluxe-files.py backup --clean-ps4` — Backs up then clears all BS Deluxe files for fresh deployment
- **Restore**: `./backup-beat-saber-deluxe-files.py restore <path>` — Restores files from a backup zip/directory to PS4
- **Local mode**: Add `--local` flag for testing without PS4 connectivity

Usage examples:

```bash
# Backup current PS4 state
./backup-beat-saber-deluxe-files.py backup

# Backup and clean PS4 for fresh deployment
./backup-beat-saber-deluxe-files.py backup --clean-ps4

# Restore from a backup
./backup-beat-saber-deluxe-files.py restore /path/to/backup.zip

# Clean PS4 first, then restore
./backup-beat-saber-deluxe-files.py restore /path/to/backup.zip --clean-ps4

# List backup contents
./backup-beat-saber-deluxe-files.py list /path/to/backup.zip

# Run in local mode (no PS4 required)
./backup-beat-saber-deluxe-files.py backup --local
```

Full documentation: [backup-documentation.md](./backup-documentation.md)

## 12. License & Credits

## 1. Devcontainer Setup

This project uses a VS Code Devcontainer with the OpenOrbis PS4 Toolchain pre-installed. This is the **only supported development environment**.

### 1.1 Prerequisites on your host machine

- **VS Code** with the **Dev Containers** extension (ms-vscode-remote.remote-containers)
- **Docker** (Docker Desktop on Windows/Mac, or Docker Engine on Linux)
- **Git** (to clone the repo)

### 1.2 Open the project in the devcontainer

```bash
# Clone the repository
git clone <repo-url> /path/to/beat-saber-deluxe
cd /path/to/beat-saber-deluxe
```

Then in VS Code:

1. Open the `/path/to/beat-saber-deluxe` folder
2. Press `F1` → **Dev Containers: Reopen in Container**
3. Select the **"OpenOrbis SDK Workspace"** option when prompted
4. Wait for the container to build (first time takes 5-10 minutes — it downloads the OpenOrbis toolchain and all dependencies)

Once the container is ready, you'll have:

- **clang / clang++** — PS4 cross-compiler (x86_64-pc-freebsd12-elf)
- **lld-link** — PS4 linker
- **OpenOrbis PS4 Toolchain** at `/opt/openorbis/OpenOrbis/PS4Toolchain`
- **Python 3** with all required packages
- **lftp** — for FTP deployment to PS4
- **vgmstream-cli** — for audio conversion
- **GoldHEN Plugin SDK** — included in the workspace

### 1.3 Configure PS4 connection

Edit `beat_saber_deluxe/ps4_config.json` with your PS4's IP address:

```json
{
  "ps4": {
    "ip": "192.168.100.117",
    "ftp_port": 2121,
    "ftp_user": "anonymous",
    "ftp_password": ""
  },
  "title": {
    "id": "CUSA12878",
    "name": "Beat Saber"
  }
}
```

Replace `192.168.100.117` with your PS4's IP address. The default FTP port for GoldHEN is `2121`.

> **Note:** The pipeline now uses `/data/GoldHEN/AFR/CUSA12878/` as the AFR base directory (where custom bundles and configs are deployed). This is configured in `ps4_config.json` under `paths.afr_base`.

---

## Feature Flags

The Beat Saber Deluxe plugin uses `features.json` to control experimental features without recompiling.

- **Config Path:** `/data/GoldHEN/AFR/CUSA12878/features.json`

| Flag                                | Default             | Description                                                                                                                                                                                                                                                                                                                                                                        |
| ----------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `enable_plugin`                     | **`true`** (unique) | **Global kill switch** — when explicitly `false`, the ENTIRE plugin is inert on next boot (no redirects, no metadata swaps; 100% official songs). The only flag defaulting true when absent, so a missing features.json keeps a deployed setup working.                                                                                                                            |
| `enable_custom_song_replacements`   | `false`             | Gates all song redirects — when OFF, no bundle redirects fire and the game plays original songs                                                                                                                                                                                                                                                                                    |
| `enable_song_metadata_modification` | `false`             | Gates song metadata modification — when ON, hooks MoveNext() to replace song names/artists in the UI                                                                                                                                                                                                                                                                               |
| `enable_beatmap_mode_mapping`       | `false`             | Gates the extra game modes (OneSaber, NoArrows, 90Degree) — when OFF, pack bundles and the catalog redirect are skipped so every song shows only Standard (custom audio still plays); when ON, patched packs show all 4 mode sets                                                                                                                                                  |
| `enable_song_previews`              | `false`             | Gates **song previews** — highlighting a custom song in the menu plays a ~10s cut of ITS OWN audio (the mapper's chosen moment when known, else the busiest-bar heuristic) instead of the stock song's clip. Previews ride inside the patched pack bundles; either this or mode-mapping keeps the patched pair live. Re-deploy after flipping to ship the matching bundle variant. |

### Startup Notifications

On boot the plugin shows **one notification** reporting both its version and its
feature-flag state (a single toast because the PS4VR headset switch-over can
swallow a second toast when the headset is already powered on at launch):

```
BS Deluxe v0.8048 (ON)
By Chris Primeish
(4/4 features ON)
```

- **`(ON)` / `(OFF)`** — the global `enable_plugin` kill-switch state
- **`(N/4 features ON)`** — how many of the four feature flags are enabled
- When the kill switch is OFF: `BS Deluxe v0.8048 (OFF) / By Chris Primeish / (official songs only)`

To change what the next boot shows:

```bash
# Play only official songs (plugin fully inert on next boot):
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=false
# Back to your custom songs:
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=true
```

### Surgical metadata fixes (`--metadata-only`, v0.5346+)

Add/update one song's display-name entry and ship it to the PS4 without
processing a song, touching redirects, or redeploying the plugin:

```bash
python3 tools/full_custom_song_pipeline.py --metadata-only \\
    --target "BabyOneMoreTime" --song-name "Take On Me" --artist "A-ha" --deploy
```

`song_metadata.json` is written as raw UTF-8 — non-ASCII stock titles
(e.g. `…Baby One More Time`) match correctly; the plugin unescapes older
`\uXXXX`-escaped files and folds keys through the same `?` projection it
applies to the game's UTF-16 strings (v0.8047).

> **All runtime features MUST be gated behind feature flags in `features.json`.** No hardcoded behavior in the plugin. When adding a new feature:
>
> 1. Add a `enable_<feature_name>` key to `features.json` and `DEFAULT_FEATURES` in the pipeline
> 2. Add a `g_feature_<feature_name>` global in `main.cpp`
> 3. Gate the feature code behind `if (g_feature_<feature_name>)`
> 4. Defaults to `false` when absent (exception: `enable_plugin` defaults true)

### Example `features.json`

```json
{
  "enable_plugin": true,
  "enable_custom_song_replacements": true,
  "enable_song_metadata_modification": true,
  "enable_beatmap_mode_mapping": true
}
```

Every pipeline deploy (`--deploy-full`, `--deploy-features`) merges missing keys
from `DEFAULT_FEATURES` before uploading, so a stale local file can never ship
with a flag silently absent.

You can deploy these settings using the pipeline:

```bash
# Deploy the plugin and update features.json
python3 tools/full_custom_song_pipeline.py \
    --deploy-plugin \
    --set-feature enable_custom_song_replacements=true \
    --set-feature enable_song_metadata_modification=true

# Disable custom songs (play originals without rebooting)
python3 tools/full_custom_song_pipeline.py \
    --deploy-plugin \
    --set-feature enable_custom_song_replacements=false
```

## 2. Building the Plugin

The plugin is a GoldHEN PRX (PS4-format shared library) that hooks file I/O to redirect song assets.

### 2.1 Quick build

```bash
cd /workspace/beat_saber_deluxe

# Release build (no verbose logging)
make

# Debug build (verbose per-file logging to bs_log.txt)
make DEBUG=1
```

Output files:

- `beat_saber_deluxe.prx` — release plugin
- `beat_saber_deluxe_debug.prx` — debug plugin (verbose logs)

### 2.2 Clean build

```bash
make clean
make
```

### 2.3 What the build does

1. Compiles all `.c` and `.cpp` files in `src/` using clang targeting `x86_64-pc-freebsd12-elf`
2. Links with `ld.lld` using the GoldHEN SDK libraries (`libGoldHEN_Hook`, `libSceLibcInternal`, `libkernel`)
3. Creates a PS4 FSELF (FSigned ELF with SCE magic `4f 15 3d 1d`) using the OpenOrbis `create-fself` tool
4. Outputs the final `.prx` file in the project root

### 2.4 Build system details

- **Makefile:** `/workspace/beat_saber_deluxe/Makefile`
- **Source files:** `/workspace/beat_saber_deluxe/src/`
- **Headers:** `/workspace/beat_saber_deluxe/include/`
- **Toolchain:** `/opt/openorbis/OpenOrbis/PS4Toolchain`

---

## 3. Deploying to PS4

Your PS4 must be:

- On firmware 9.00
- Running GoldHEN (2.3 or 2.4b)
- FTP server enabled (GoldHEN's built-in FTP on port 2121)
- On the same network as your dev machine
- **IP configured in** `beat_saber_deluxe/ps4_config.json`

### 3.1 Quick deploy — one song at a time (RECOMMENDED)

```bash
cd /workspace/beat_saber_deluxe

# Build + deploy EVERYTHING for one song (bundle, music-pack patch, catalog,
# plugin, features.json, scoped redirects, validation) in ONE command:
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song <MAP_ID> \
    --target <SLOT_NAME> \
    --deploy-full
```

Each command is self-contained: it always builds and deploys the LATEST plugin
source (opt out with `--skip-plugin-deployment`), surgically patches only that
song's music pack with a matching catalog (Unity CRC-safe), preserves custom
songs already deployed in other packs, regenerates `redirects.json` scoped to
exactly what is deployed, and runs post-deploy validation — **a failed
validation exits non-zero** so a broken state can never look green.

**Batch deploys:** for a whole music pack, use the ready-made scripts in
`docs/example-scripts/example_script_to_install_custom_songs_over_<pack>_music_pack.sh`
(one `--deploy-full` per song, with a PS4-state check + confirmation prompt up
front and error handling per song). Pass `--no-prompt` to skip the confirmation
and chain several packs unattended:

```bash
'/workspace/docs/example-scripts/example_script_to_install_custom_songs_over_billie_eilish_music_pack.sh' --no-prompt && \
'/workspace/docs/example-scripts/example_script_to_install_custom_songs_over_britney_spears_music_pack.sh' --no-prompt
```

> **`deploy_all.sh` is OUTDATED** (13 hardcoded Rolling Stones slots, pre-dating
> pack-mode patching). It remains only for historical reference — do not use it
> for new deployments.

### 3.1b Web App — deploy without the CLI (M9)

The same pipeline, point-and-click. The web app is a **thin layer**: every
Deploy button press runs the exact `--deploy-full` command above as a
subprocess — nothing is re-implemented in the browser.

```bash
python3 beat_saber_deluxe/webapp/server.py
# opens http://127.0.0.1:8765 in your browser (--no-browser to skip)
```

- **Setup Wizard** — point it at your `ps4_dump` folder; it validates the dump
  live (patch 2.04 files, eboot.bin, origin catalog, DLC-pack confidence list),
  tests the PS4 connection, and writes a fully-localized `ps4_config.json`.
- **Game Dump Guide** — never dumped a console? The built-in guide walks the
  process (patch 2.04, DLC installed _before_ dumping) and provides the
  ready-made `dumper.cfg` (`split=3`) for your USB stick.
- **Song Picker** — search BeatSaver (or paste a map ID); maps are badged with
  native Easy/Normal/Hard availability (the pipeline auto-fills
  Expert/E+ from lower difficulties).
- **Deploy** — pick a target slot grouped by music pack, review the exact
  command before running, watch the live log stream, and get the pipeline's
  own PASSED/FAILED verdict.
- **Manage Songs** — pick a music pack from a dropdown to see every stock song
  in it and what custom song (name / artist) is deployed over each slot, with a
  per-row **Clear** button (surgical: only that song reverts; its pack's other
  songs and every other pack stay untouched).
- **Full Loadout** — every music pack and song in the game with its custom
  status, in one table. **Save the page (Ctrl+S) or print it to PDF (Ctrl+P)**
  to keep a reference of your PS4's song loadout. Same per-row Clear button.
- **PS4 page** — read-only live state (redirects, feature flags, custom-song
  metadata counts).
- **Game Dump Guide** — also built into the web app.

- **Feature Flags** — live read of the four runtime flags (kill switch
  first) with detailed descriptions; the Apply button diffs against the live
  PS4 state and deploys only what changed, through the pipeline's
  `--features-only` path.
- **Backup / Restore** — wraps `backup-beat-saber-deluxe-files.py` (the same
  script the CLI uses): one-click backup (optionally clean the PS4 after,
  behind a hard confirm), browse `ps4_backups/`, per-row restore, live job log.
- **Batch** — deploy whole music packs point-and-click: all 34
  example-script loadouts (parsed live from the `docs/example-scripts/example_*.sh`
  files, so the tab always matches the scripts), a multi-pack checkbox mode
  (e.g. the standard 5-pack loadout = 47 songs in one serial run), and a
  custom batch builder with BeatSaver search, save/load, and
  platform-agnostic JSON batch files (format documented in the tab).
- **Feature Request** — composes a prefilled GitHub issue for this repo;
  opens it on GitHub for you to review and submit.

**GitHub Pages command-builder:** the same UI is hosted online (deployed by
`.github/workflows/pages.yml` from `webapp/build_pages.py`) at the repo's Pages
URL. There, the app detects it has no backend and switches to command-builder
mode: configure your dump folder, song, and slot visually, then copy the
generated `python3 tools/full_custom_song_pipeline.py …` command and run it on
the machine with your PS4 + game dump. The hosted page can never touch your
PS4 — deploys need the local backend or the CLI.

No PS4 credentials leave your machine — the local server binds to `127.0.0.1`
only. Local-folder song deploys, saved presets, and the built-in 35-check
validator page arrive in later phases.

### 3.2 Manual deploy (individual components)

```bash
# Deploy only the plugin
python3 /workspace/beat_saber_deluxe/tools/full_custom_song_pipeline.py --deploy-plugin

# Deploy plugin with debug logging
python3 /workspace/beat_saber_deluxe/tools/full_custom_song_pipeline.py --deploy-plugin --debug-logging

# Deploy a single custom song bundle (built separately)
python3 /workspace/beat_saber_deluxe/tools/full_custom_song_pipeline.py \
    --target startmeup \
    --deploy

# Deploy the redirects config
python3 /workspace/beat_saber_deluxe/tools/full_custom_song_pipeline.py \
    --target startmeup \
    --deploy-config
```

### 3.3 FTP details

- **IP:** Your PS4's IP (configured in `ps4_config.json`)
- **Port:** 2121 (GoldHEN's default FTP port)
- **User:** `anonymous` (no password)
- **Plugin destination:** `/data/GoldHEN/plugins/beat_saber_deluxe.prx`
- **Bundle destination:** `/data/GoldHEN/AFR/CUSA12878/<slot>_v3.bundle` (exact filename — the plugin opens the redirect VALUE verbatim and `open()` is case-sensitive, so the value must byte-match the deployed file, Exp 187)
- **Config destination:** `/data/GoldHEN/AFR/CUSA12878/redirects.json`
- **Log file:** `/data/GoldHEN/AFR/CUSA12878/bs_log.txt`

---

## 4. Activating the Plugin on PS4

1. **Ensure GoldHEN is running** on your PS4 (FW 9.00, GoldHEN payload enabled)
2. **Deploy the plugin** — see section 3
3. **Start Beat Saber** on your PS4
4. The plugin activates automatically when GoldHEN loads at startup — no manual enable needed

### 4.1 Verifying the plugin is active

After starting Beat Saber, check the PS4 log:

```bash
# Download the log from PS4
lftp -u anonymous, -p 2121 192.168.100.117 \
    -e "get /data/GoldHEN/AFR/CUSA12878/bs_log.txt -o /tmp/ps4_log.txt; quit"

# Check for the plugin version header
grep "BS Deluxe" /tmp/ps4_log.txt
# Expected: "=== BS Deluxe v0.80 started ==="

# Check for redirects (songs being replaced)
grep "->" /tmp/ps4_log.txt | grep AFR
# Expected: "/.../BeatmapLevelsData/startmeup -> /data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle"
```

### 4.2 Plugin hot-reload

You can deploy an updated plugin while the game is running:

```bash
# Build and deploy the latest plugin source without restarting the game
python3 tools/full_custom_song_pipeline.py --deploy-plugin

# Then restart Beat Saber from the PS4 menu
```

The plugin is reloaded by GoldHEN when the game executable is launched. A full PS4 reboot is rarely needed but can help if the plugin isn't loading.

### 4.3 Troubleshooting activation

| Symptom                                       | Cause                    | Fix                                                                                     |
| --------------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------- |
| No "BS Deluxe" in log                         | Plugin not deployed      | Run `python3 tools/full_custom_song_pipeline.py --deploy-plugin`                        |
| Old version shown                             | Plugin cache             | Restart Beat Saber or reboot PS4                                                        |
| CE-34878-0 crash                              | Bundle CRC/size mismatch | Use default build (PCM16 + no-pad, both default since v0.5314) or `--preserve-metadata` |
| "redirect" shows in log but song doesn't play | Bundle format issue      | Verify bundle deployed correctly                                                        |

---

## 5. Quick Start: Replace a Song from BeatSaver

This is the fastest way to get a custom song onto your PS4. Run this single command from the devcontainer:

```bash
cd /workspace/beat_saber_deluxe

# OPTIONAL: Clean PS4 to a truly blank slate first
python3 /workspace/backup-beat-saber-deluxe-files.py backup --clean-ps4

# Complete end-to-end deployment in ONE command (self-contained single-song):
# - Downloads song from BeatSaver
# - Converts to V3.2.0 (V2→V3 auto-conversion)
# - Generates all 4 modes (Standard, OneSaber, NoArrows, 90Degree)
# - Builds song bundle with PCM16 lossless audio
# - Builds/deploys pack mode bundles + merged catalog for the target's DLC pack
# - Deploys song bundle, pack bundles, catalog, redirects.json, features.json, song_metadata.json
# - Builds/deploys plugin + ensures plugins.ini entry
# - Runs post-deploy validation
python3 tools/full_custom_song_pipeline.py \
  --download-beat-saver-song <MAP_ID> \
  --target <slot_name> \
  --deploy-full
```

**Parameters explained:**

- `<MAP_ID>` — the BeatSaver map key (e.g. `1d6c7c2`). Find it on [BeatSaver.com](https://beatsaver.com) — it's the short hash in the URL (e.g. `beatsaver.com/maps/1d6c7c2`)
- `--target <slot_name>` — which PS4 song slot to replace. See [Available Song Slots](#available-song-slots-targets) above
- `--deploy-full` — **Self-contained SINGLE-SONG orchestration in ONE command**: deploys only the target song + its music-pack mode bundle + matching catalog + plugin + `plugins.ini` entry + `features.json` + scoped redirects + post-deploy validation. Run one command at a time and test in-game after each (it does NOT deploy the other packs/songs). Deploys the plugin built from the LATEST source (repo checkout) or the **bundled CI build** (packaged release — no Makefile needed); add `--skip-plugin-deployment` to keep the PS4's current plugin pinned. **A failed post-deploy validation exits non-zero** (the deploy is never reported complete with an inconsistent PS4 state — that state crashes the game with CE-34878-0).
- `--skip-plugin-deployment` — skip the plugin deploy even in `--deploy-full` (for pinning a specific plugin build on the PS4).
- `--skip-song-preview-management` — skip building/deploying song-previews variants this run (v0.5359+). **For BATCH deploys**: every `--deploy-full` refreshes previews for packs whose inputs changed — across an N-song batch that's N−1 throwaway preview passes, since only the LAST deploy's refresh matters. Pass this flag on every batch command **except the last** so previews regenerate exactly once at the end (the web app's Batch tab injects it automatically). The variant bundle already on the PS4 keeps serving previews meanwhile. Preview builds are also **dirty-checked per pack** — a pack's variant is rebuilt only when its modes base, its set of custom slots, or any song's bundle content / preview-start input actually changed, so untouched packs cost seconds to verify.
- `--debug-logging` — deploy the verbose-logging plugin variant (`beat_saber_deluxe_debug.prx`; replaces the same `beat_saber_deluxe.prx` plugins.ini entry — re-deploy without the flag to restore the quiet build).

> **v0.5314+ safe defaults (no flags needed):** PCM16 lossless audio + full-length (no padding truncation) + beatmap mode mapping (OneSaber/NoArrows/90Degree auto-generated to fill gaps) + V2→V3 conversion are all **default ON**. The old explicit flags (`--pcm16`, `--no-pad`, `--convert-to-v3`, `--enable-beatmap-mode-mapping`) are still accepted as no-op compat flags. To opt out: `--hevag`/`--vorbis` (codec), `--pad-fsb5` (**DANGER** — truncates audio to 12MB, produces partial songs), `--disable-beatmap-mode-mapping` (Standard only), `--no-convert-to-v3` (leave V2).

**Example — download "Espresso" by Sabrina Carpenter and replace Start Me Up:**

```bash
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song 1d6c7c2 \
    --target startmeup \
    --deploy-full
```

**After the command completes:**

1. The bundle is built and deployed to `/data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle`
2. Pack mode bundles + merged catalog are deployed
3. The redirect config is updated and deployed
4. Post-deploy validation runs
5. Restart Beat Saber on your PS4
6. Navigate to the target song in the game's song pack — your custom song will play with all 4 modes available!

---

## 6. Full Custom Song Workflow

### 6.1 Download a song from BeatSaver manually

```bash
# Download by map key
python3 tools/full_custom_song_pipeline.py \
    --download-beat-saver-song <MAP_ID> \
    --target startmeup \
    --deploy
```

The pipeline automatically:

1. Downloads the song ZIP from BeatSaver API
2. Extracts the audio (WAV/OGG) and beatmap `.dat` files
3. Converts audio to FSB5 format (PS4-compatible, PCM16 lossless by default)
4. Converts beatmaps from V2 to V3 format (default ON)
5. Auto-detects beatmap modes and generates missing OneSaber/NoArrows/90Degree variants (default ON)
6. Packages everything into an AssetBundle
7. Deploys to PS4 via FTP

### 6.2 Use a local song directory

If you already have a custom song folder with audio + beatmap files:

```bash
python3 tools/full_custom_song_pipeline.py \
    --song-dir /path/to/song/folder \
    --target startmeup \
    --deploy
```

The song folder should contain:

- A single audio file (`.wav`, `.ogg`, or `.mp3`)
- Beatmap `.dat` files (generated by [ChroMapper](https://ChroMapper.com), [MediocreMapper](https://github.com/Kylemc1413/Mediocre-Map-Mapper), or downloaded from BeatSaver)

### 6.3 Pipeline steps in detail

The pipeline (`tools/full_custom_song_pipeline.py`) performs these steps:

1. **Load template** — reads the original song's AssetBundle from the game dump
2. **Convert audio** — WAV/OGG → PCM16 → FSB5 (with optional padding)
3. **Replace audio** — overwrites the `.resource` data in the bundle with new FSB5
4. **Update metadata** — fixes `AudioClip.m_Length` and `m_Resource.m_Size`
5. **Update audio.gz** — fixes `songSampleCount` and BPM data
6. **Replace beatmaps** — converts V2 `.dat` → gzip → TextAsset for all 5 difficulties
7. **Save bundle** — writes the modified bundle with LZ4 compression
8. **Deploy** — uploads to PS4 via FTP (if `--deploy` is set)

### 6.4 Additional pipeline options

| Flag                             | Description                                                                                           |
| -------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `--vorbis`                       | Use Vorbis audio encoding instead of PCM16 (smaller files, may be slower) — opposes the PCM16 default |
| `--hevag`                        | Use HEVAG audio encoding (Sony proprietary, usually blocked) — opposes the PCM16 default              |
| `--pcm16`                        | Use PCM16 audio encoding (**default** — lossless, best compatibility; kept as compat no-op)           |
| `--no-pad`                       | Skip 12MB audio padding (**default** — keeps full-length audio; kept as compat no-op)                 |
| `--pad-fsb5`                     | **Restore** the old 12MB truncating padding (**DANGER**: produces partial/truncated songs)            |
| `--preserve-metadata`            | Keep original song metadata (audio length, etc.)                                                      |
| `--convert-to-v3`                | Convert V2 beatmaps to V3 format (**default** — required for PS4; kept as compat no-op)               |
| `--no-convert-to-v3`             | Leave V2 beatmaps unconverted (opposes the default)                                                   |
| `--disable-beatmap-mode-mapping` | Standard-only bundle (opposes the default mode mapping)                                               |
| `--skip-mode-generation`         | Keep mode mapping but don't generate missing mode beatmaps                                            |
| `--one-saber-min-gap <s>`        | Min beats between same-cell arrowed notes (OneSaber generator, default 0.25)                          |
| `--rotation-cycle-beats <b>`     | Beats per 90-degree rotation flip (90Degree generator, default 8.0)                                   |
| `--enable-modes`                 | Comma-separated list of modes to enable (e.g. `OneSaber,90Degree`)                                    |
| `--features-only`                | Apply + deploy `--set-feature` changes to features.json only, then exit (no song/plugin processing)   |
| `--set-feature key=value`        | Set a runtime feature flag in features.json (use with `--features-only` or `--deploy-plugin`)         |
| `--ignore-non-standard-beatmaps` | Skip non-standard difficulty beatmaps                                                                 |
| `--target <name>`                | PS4 song slot to replace (see [Available Song Slots](#available-song-slots-targets))                  |
| `--output <path>`                | Custom output path for the built bundle                                                               |
| `--deploy`                       | Upload the bundle to PS4 via FTP                                                                      |
| `--deploy-plugin`                | Upload the plugin PRX to PS4                                                                          |
| `--debug-logging`                | Deploy plugin with verbose logging (only with `--deploy-plugin`)                                      |
| `--generate-config`              | Generate/update `redirects.json`                                                                      |
| `--deploy-config`                | Upload `redirects.json` to PS4                                                                        |
| `--sync-config`                  | Upload config and sync all bundles to PS4                                                             |
| `--enable-plugin`                | Enable the plugin in GoldHEN's config                                                                 |
| `--disable-plugin`               | Disable the plugin in GoldHEN's config                                                                |

---

## 7. PS4 Log Management

The plugin writes a log file to `/data/GoldHEN/AFR/CUSA12878/bs_log.txt` on the PS4. This is essential for debugging.

### 7.1 Clear the log

Before each experiment, clear the log so you only see fresh output:

```bash
# Via FTP
lftp -u anonymous, -p 2121 <PS4_IP> \
    -e "rm /data/GoldHEN/AFR/CUSA12878/bs_log.txt; quit"

# Or via the pipeline (plugin deploys also clear the log)
python3 tools/full_custom_song_pipeline.py --deploy-plugin
```

### 7.2 Download and analyze the log

```bash
# Download the log
lftp -u anonymous, -p 2121 <PS4_IP> \
    -e "get /data/GoldHEN/AFR/CUSA12878/bs_log.txt -o /tmp/ps4_log.txt; quit"

# Check plugin version
grep "BS Deluxe" /tmp/ps4_log.txt

# Check for memory injection (MEMINJ) activity
grep "MEMINJ" /tmp/ps4_log.txt

# Check for redirects (songs being replaced)
grep "->" /tmp/ps4_log.txt | grep AFR

# Check for errors
grep -i "error\|fail\|crash" /tmp/ps4_log.txt

# Archive the log for reference
cp /tmp/ps4_log.txt "/workspace/.ai_memory/experiment_logs/ps4_log_$(date +%Y%m%d_%H%M%S).txt"
```

### 7.3 Log format

```
=== BS Deluxe v0.80 started ===           # Plugin header + version
v0.80 — dynamic redirect config (...)
loaded 32 redirects from config
  e.g. BeatmapLevelsData/startmeup -> /data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle
open:/data/GoldHEN/AFR/CUSA12878/bs_log.txt
[MEMINJ] Initialized                     # Memory injection module ready
...
open:/archive/mount/point/Media/StreamingAssets/BeatmapLevelsData/startmeup -> /data/GoldHEN/AFR/CUSA12878/startmeup_v3.bundle   # Redirect fired!
[MEMINJ] Scanning...                     # Memory injection triggered
[MEMINJ] Found klass 0x... via pattern   # BeatmapLevelSO class found
[MEMINJ] Found 1 candidates with klass   # Objects located
...
```

---

## 8. Architecture Overview

```
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Custom Song ZIP    │────▶│  Pipeline (Python) │────▶│  .bundle + config  │
└─────────────────────┘     └──────────────────┘     └───────────────────┘
                                                              │
                                                              ▼
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Beat Saber PS4     │◀────│  GoldHEN Plugin   │◀────│  FTP Deploy (2121)  │
│  (CUSA12878 v2.04)  │     │  (beat_saber.prx) │     └───────────────────┘
└─────────────────────┘     └──────────────────┘
```

The plugin hooks file I/O to redirect DLC song asset paths to custom song bundles stored in `/data/GoldHEN/AFR/CUSA12878/`. The pipeline handles audio conversion (lossless → PCM16 FSB5), beatmap V2→V3 conversion, and addressable bundle assembly.

### Key Components

| Component           | Location                                           | Description                                                                                  |
| ------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| GoldHEN Plugin      | `src/`                                             | C++ plugin that hooks file I/O, detects song loading, and redirects to custom bundles        |
| Song Pipeline       | `tools/full_custom_song_pipeline.py`               | Python script that converts custom songs into PS4-compatible bundles                         |
| Deploy Flow         | `tools/full_custom_song_pipeline.py --deploy-full` | One-command per-song deploy: bundle + pack patch + catalog + plugin + redirects + validation |
| Development Scripts | `development/scripts/`                             | Experimental scripts — not production-ready                                                  |
| Game Dump           | `/workspace/ps4_dump/`                             | Decrypted PS4 game dump (base app + patch)                                                   |
| Bundles             | `custom_songs/`                                    | Built custom song bundles ready for deployment                                               |
| Config              | `ps4_config.json`                                  | PS4 connection settings (IP, port)                                                           |

### 🎥 Demo Video

https://www.youtube.com/watch?v=J835HDdB-7g

---

## 9. Unit Testing

The project includes a comprehensive pytest test suite covering the Python pipeline tools. Tests run automatically in CI on every push and pull request.

### Quick Start

```bash
cd beat_saber_deluxe

# Run all tests
python3 run_tests.py

# Run with coverage report
python3 run_tests.py --coverage

# Run only fast tests (skip slow/integration)
python3 run_tests.py --fast

# Test a specific module
python3 run_tests.py --module hevag
python3 run_tests.py --module pipeline
```

### Available Modules

| Module Flag         | Target                         | Tests                                                                        |
| ------------------- | ------------------------------ | ---------------------------------------------------------------------------- |
| `pipeline`          | `full_custom_song_pipeline.py` | Config loading, V2/V3 conversion, beatmap selection, blob building, metadata |
| `pipeline-bugfixes` | Recent bug fixes               | Info.dat case handling, metadata passthrough, note counting                  |
| `hevag`             | `hevag_encoder.py`             | HEVAG encoding, FSB5 building, audio I/O, tone generation                    |
| `lapped`            | `lapped_audio.py`              | BPM loading, V2 detection, lapped song detection                             |
| `inject`            | `inject_pack_bundle.py`        | UTF-8 strings, characteristic path IDs, BeatmapLevelSO blobs                 |
| `patched`           | `build_patched_pack_bundle.py` | UTF-8 strings, blob building                                                 |
| `replacement`       | `build_replacement_pack.py`    | UTF-16LE encoding, Unity strings, PPtrs                                      |
| `beatsaver`         | `download_beatsaver_songs.py`  | BeatSaver API calls, download flow                                           |

### Test Harness Options

```bash
python3 run_tests.py --coverage      # Coverage report (htmlcov/)
python3 run_tests.py --lint          # Run ruff/flake8 on tools/
python3 run_tests.py --fix           # Auto-fix lint issues
python3 run_tests.py --ci            # CI mode (strict, coverage enforced)
python3 run_tests.py --module hevag  # Single module
python3 run_tests.py --fast          # Skip slow/integration tests
```

### Running pytest Directly

```bash
cd beat_saber_deluxe

# All tests
python3 -m pytest tests/ -v

# With coverage
python3 -m pytest tests/ -v --cov=tools --cov-report=term-missing

# Specific test file
python3 -m pytest tests/test_pipeline.py -v

# Specific test class
python3 -m pytest tests/test_pipeline.py::TestIsV2Beatmap -v

# By marker
python3 -m pytest tests/ -m "not slow and not integration"
```

### CI Pipeline

GitHub Actions runs on every push to `main` and on pull requests. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

The CI job:

1. Checks out the code
2. Sets up Python 3.12
3. Installs dependencies (pytest, coverage, UnityPy, soundfile, numpy)
4. Runs all tests with coverage (minimum 20% enforced)
5. Uploads coverage report and test output as artifacts

### Writing New Tests

Tests live in `beat_saber_deluxe/tests/`. Each test file targets one production module. Shared fixtures are in `conftest.py`.

```python
import os, sys, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from full_custom_song_pipeline import is_v2_beatmap

class TestMyFeature:
    def test_something(self, tmp_dir):
        """Test description."""
        # tmp_dir is a pytest fixture that provides a clean temp directory
        path = os.path.join(tmp_dir, "test.dat")
        with open(path, 'w') as f:
            json.dump({"_version": "2.0.0", "_notes": []}, f)
        assert True
```

### Markers

| Marker                        | Description                    | Use When                           |
| ----------------------------- | ------------------------------ | ---------------------------------- |
| `@pytest.mark.slow`           | Long-running test (>5s)        | Audio encoding, full pipeline runs |
| `@pytest.mark.requires_audio` | Needs real audio files on disk | WAV/OGG processing tests           |
| `@pytest.mark.integration`    | Needs game bundles on disk     | Bundle loading/patching tests      |

### Release Validation (hardware, against a real PS4)

Every release is validated end-to-end on a real PS4 before tagging — this is
the release-acceptance test. The automated validator downloads the release
zip, audits it statically, then exercises **all functionality** against the
live console: read-only state verification, song build quality, end-to-end
`--deploy-full` (including the bundled plugin), `--skip-plugin-deployment`,
`--debug-logging` plugin swap + restore, feature-flag and kill-switch
round-trips, `--metadata-only`, `--clear-target-song` surgical revert +
restore, config sync/enforce, pack-mode scoping, and final state-integrity
checks against the pre-run backups (both `redirects.json` AND
`song_metadata.json` are backed up and compared — divergence auto-restores,
so a healthy PS4 is left functionally unchanged).

```bash
# Live console output as it works + a timestamped logfile for later review.
# Exit code 0 = every check PASSED.
bash .agent/docs/release-validation-test-procedure.sh \
    --log /workspace/temp/release-validation-$(date +%Y%m%d-%H%M%S).log \
    v0.8047-pipeline-0.5351-alpha01
```

Full per-step commands and expected results:
[`.agent/docs/release-validation-test-procedure.md`](.agent/docs/release-validation-test-procedure.md)
(the `.sh` companion is the automated form of that same procedure).

---

## 10. Roadmap

| Milestone              | Status         | Description                                                                                                                                                                     |
| ---------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1: Song Replacement   | ✅ Complete    | Any song slot replaced with custom audio + beatmaps                                                                                                                             |
| M2: Song Metadata      | ✅ Complete    | Custom song names and artists displayed in-game (single-artist packs)                                                                                                           |
| M3: Mode Selector      | ✅ Complete    | OneSaber/90Degree/NoArrows mode selector support via catalog-redirect + pack-bundle preview-set injection (4 modes × 5 difficulties for all DLC packs, generalized in v0.5319+) |
| M4: Note Colors        | ⏳ Planned     | Custom left/right saber colors per song                                                                                                                                         |
| M5: Multi-Artist Packs | 🔬 Researching | Artist replacement for multi-artist packs without global blanking                                                                                                               |

---

## 11. License & Credits

This project is for educational/research purposes. It does not modify Beat Saber's game code or bypass DRM. Custom songs are sourced from the community and remain the property of their respective creators.

- **OpenOrbis PS4 Toolchain** — the cross-compilation toolchain used to build the plugin
- **GoldHEN** — the PS4 homebrew enabler that provides the hooking framework
- **vgmstream** — audio conversion library used for FSB5 encoding
