# Game-Data Extractor

**Status:** ✅ **HARDWARE-PROVEN (2026-10-20, Exp 281f): a full song deploy completed with the developer's decrypted dump physically hidden — validation PASSED.** Users need NO game dump. (plugin v0.8055+, pipeline v0.5365+) · **Feature flag:** `enable_game_data_extractor` (**ON by default**)

## What it does

**You never need to make or hold a decrypted dump of the game on your PC.**
With this flag armed, the plugin copies the exact files the pipeline needs —
per-slot template bundles (~13 MB each), the target music packs' bundles, and
the addressables catalog — out of the game's own data **during a normal boot**,
and the web app mirrors them into a small local `game_data/` cache. The cache
mirrors the dump's layout exactly, so the pipeline uses it as a drop-in
replacement for `ps4_dump/`.

For the live 5-pack / 47-song loadout that's ~658 MB instead of a 4.9 GB dump;
a one-pack setup needs ~140 MB; adding one more song needs one ~13 MB file.

**Legally clean:** everything is extracted from your own console — the
repository ships only the tooling, never game content.

## How to use it (the web app flow)

1. **Arm the flag once** — Feature Flags tab → `enable_game_data_extractor` →
   Apply (requires plugin v0.8054+ deployed).
2. **Pick the packs you want** on the Dump Guide tab ("Option A — Let the game
   extract it") and press **Request extraction** — the web app writes the file
   list to the PS4 (`game_data_requests.txt`).
3. **Boot Beat Saber once.** The plugin extracts during the boot (idempotent —
   already-extracted files are skipped; failures retry automatically on the
   next boot).
4. Back at the web app: **Pull extracted files** — the extracted set is mirrored
   into the local `game_data/` cache (resumable; identical files skip).
5. **Use the extracted cache** — the web app points the pipeline's
   `paths.game_dump_dir` at the cache. Deploy songs as usual.

## How it works (under the hood)

- The game reads its own assets from `/archive/mount/point/Media/...` and
  `/app0/Media/...` — both mounts are openable inside the game process (proven
  by the plugin's own open-hook logs). The extractor opens each requested
  relative path on either mount and stream-copies it to
  `/data/GoldHEN/AFR/CUSA12878/game_data/<rel>`.
- **Ownership (pull-before-push doctrine):** `game_data_requests.txt` is
  web-app/pipeline-owned (the plugin only reads it — one path per line);
  `game_data_status.txt` is plugin-owned (one extracted path per line;
  `ERR <rel> <reason>` lines mark failures). No file is written by both sides.
- **Idempotence + retries:** successes are recorded in the status file and
  skipped on later boots; ERR lines never match a request line, so failures
  re-attempt on the next boot automatically.
- **CLI equivalents** (the web app uses exactly these):
  - `python3 tools/full_custom_song_pipeline.py --request-game-data --game-data-packs lizzo`
  - `python3 tools/full_custom_song_pipeline.py --pull-game-data`
- Like the M11 hotkey, the extractor is console-maintenance tooling, **not game
  behavior** — it works even while the plugin's kill switch is OFF, so you can
  fill your game-data cache regardless of the plugin's game-feature state.

## Limitations

- The extraction (and the boot it happens during) adds some seconds for large
  requests (the full 5-pack set is ~650 MB of console-side copies) — one-time.
- The DLC music packs you want to modify must be **installed on the console**
  (their bundles live in the patch data the extractor reads).
- The extraction happens on **boot of the game** — no boot, no extraction
  (the web app tells you when a boot is pending).

## Rollback / disable

```bash
python3 tools/full_custom_song_pipeline.py \
    --features-only --set-feature enable_game_data_extractor=false
```

The extracted files stay on the console (`game_data/` in the AFR dir) and in
your local cache — nothing about your song deployments changes when the flag
is off; they are only inputs for building.
