## Current Exp304 — media prepared locally; runtime binding pending (2026-10-25)

Exp303 full Wake Me Up gameplay/music and difficulty differences are confirmed by
user m08271. Native0.8063 installed, experiment OFF after archived stable logs;
no new runtime deploy or AI launch. Original100$Bills entry remains untested.

New experimental development script prepare_additive_media.py prepares the map's
own artwork and actual preview excerpt without touching game/stock files. For
Wake Me Up: source cover250x250 -> PNG512x512; preview73s..83s -> PCM16 stereo
44100Hz10s WAV. Hash-verified media manifest says runtime_bound=false. Assets
remain ignored temp/additive-exp304-media/ and are NOT uploaded/visible yet.
Pipeline0.5370; plugin0.8063/UI0.6.28 unchanged.1021passed124skipped1 inherited
Starlette warning;15 new focused tests validate exact excerpt/covers/path and
bounds/hash/no-overwrite rules. No new dependencies or system install.

Playlist art DESIGN TARGET: square512x512 PNG (JPEG accepted/normalized). This
is our chosen preparation target, NOT a verified mandatory native texture size.
Original stock pack texture/sprite dimensions remain unverified: no Texture2D or
Sprite in owned quick_test/full-map bundles, no active game/PFS mount to read
stock ostvol1_pack_assets_all_774a625d0b21a1d013d9b5f1c404c6d3.bundle.
Keep important artwork away from edges; user can provide512px square PNG.

Next runtime step: replace ONLY the new level's inherited previewMediaData with
its own cover/audio (and its preview start0/duration10 for pretrimmed clip),
without moving Unity object operations to native worker or blocking on asyncTasks.
Candidate managed classes: FileSystemPreviewMediaData, AudioClipAsyncLoader and
SpriteAsyncLoader; Sprite factory delegate/engine lifecycle not yet validated.
No guessed native method-pointer calls/addresses, no claiming prepared assets
are already displayed or that stock playlist icon resolution was measured.
Existing gameplay bundle/metadata remain working and unchanged. Optional pack
art follows user-provided design later; song art and pack art are separate.

## CURRENT Exp303 — full Wake Me Up installed; ONE captured test enabled

Verified0.8063 DEBUG/full map44,181,622B at separate additive path; all stock
assets/catalog/saves untouched. Canonical ELF169760B SHA256
666e73ea98b830c56af2b37ef59071822d9c3bd2180cc78e53e0caa73d3f7e7d, exact readback.
Map SHA256305d527c61902fb069f37e63b2223ef74ada5cf65cac1636f1c502e543741fa6.
Old0.8062 plugin retained remote .exp303-backup-20261025T185606Z and local
ignored temp/additive-exp303-deployment-20261025T185606Z; old tone bundle retained.
Initial180s host transfer timeout reconciled read-only, then resumed exact existing
map and installed plugin; no unverified overwrite/stock edit. Reports:
additive-exp303-deployment.json, additive-exp303-enable-preparation.json.

ONLY additiveON/globalON/other6OFF, INI unchanged. Fresh bounded klogPID89342
started19:02:25Z1800s; prelaunch offset65878; private folder
 temp/additive-exp303-capture-20261025T190225Z. No AI launch. Test menu:
Custom Songs -> Wake Me Up (Avicii),~4:09, StandardEasy312 colorednotes.
Five difficulties with original note/bomb/wall/NJS/jump-offset stats preserved.
Gameplay music UNPROVEN; startEasy and check first10–15seconds for music+notes,
if silent exit/fully close/report (do not waste a full silent song). If audible,
finish/results/menu then fully close/report. Stock artwork/menu preview reused;
judge audio in gameplay, not song-selection preview. If locked Buy/download,
crash or hang: stop/no repeated launch/no purchasing. Archive stable logs after
closed title, stop capture and only additiveOFF afterward. Original100$Bills
entry remains UNTESTED.1006tests passed124skipped1 inherited warning; both builds
and JS syntax pass. No source change after tests; hardware success NOT claimed.
Default one Custom Songs pack; future playlists can reference same stored song.
One compiled full-map profile, not generic multi-song production import UI/CLI.
Changes staged only, no commit/push. Prior OFF states below are historical.

## Current Exp303 — full map prepared; installation next (2026-10-25)

Exp302 user m08116 saw notes but was unsure music was audible. Completion and
original100$Bills were NOT confirmed. Final0.8062 log182013B SHA256
8ae06d9de7aa0bbe4c7d62880035aab30bfadaba5eb0ca5f91332d0ce4d18b94 archived and stable;
load/existence routes reached. Title unmounted; log cleared and only additiveOFF.
Capture stopped. Silent tone cause UNKNOWN (no decisive native audio error).

Exp303 prepares BeatSaver437d Wake Me Up—Avicii, mapped by Uninstaller & Joetastic
& SkylerWallace, full249.432494s, Standard5 difficulties. New ID
bsd_additive_e3195d81452f3550696b607c,44,181,622B bundle SHA256
305d527c61902fb069f37e63b2223ef74ada5cf65cac1636f1c502e543741fa6.
Colored notes312/438/709/1118/1311; bombs0/12/108/0/120; walls15/3/13/0/14.
New development CLI import_v2_additive.py preserves vanilla V2 geometry/basic
lighting/full audio via PCM16 (no clipping/normalization), refuses mod requirements,
BPM changes/rotations. Independent lightshow objects fix template sharing across
five difficulties. Full roundtrip/hash/audio samples validated HOST ONLY.

LOCAL0.8063/pipeline0.5369/webapp0.6.28 binds this one exact map and per-difficulty
NJS/jump offsets/counts/artist/duration; normal pack now named Custom Songs. Still
one compiled profile, NOT arbitrary multi-song production importer or playlists.
Stable song storage separate from grouping; default one Custom Songs pack, optional
many-to-many user playlists later; no duplicate audio per playlist.
1006tests passed124skipped1 inherited warning, clean debug/release+JS pass.
AudioClip explicit load0/preloadTRUE/backgroundFALSE is an unproven compatibility
change, NOT a demonstrated fix. Stock cover/menu preview remain intentionally.
No paid entitlement/platform changes or stock replacement. Old0.8062/additiveOFF
is still installed at this point; back up/upload new map and plugin OFF next.
Sources/dumps/audio/bundles remain private ignored, only text metadata/tests stage.

### Full vanilla V2 source import (offline, explicit experimental opt-in)

```sh
.venv/bin/python orbeats/development/scripts/import_v2_additive.py \
  --experimental --source path/to/extracted/map --output temp/new-normalized-map
.venv/bin/python orbeats/development/scripts/prepare_additive_bundle.py \
  --experimental --song-dir temp/new-normalized-map \
  --template orbeats/custom_songs/quick_test.bundle \
  --output temp/new-prepared-map
```

Needs ffmpeg already in the environment; all outputs NEW/outside source. Supports
constant-BPM vanilla Standard/all5 difficulties only, <=600s, no requirements or
rotations. It does NOT upload or update the compiled runtime profile. Do not use
production replacement deploy to pretend it is an additive song installer.

## Exp301 result — do not confuse metadata with playable installation

0.8061 showed12seconds/title but was blocked by Buy/download UI, with no custom
loader/check callbacks. Purchase option alone is not ownership/availability.
Local0.8062 uses the game's existing free-content sets for ONLY the bound,
self-generated level+pack. No paid/platform checks changed.997/124 local tests;
OFF until a fresh user-ready captured run, not a playback success. Bundle and
CLI preparation remain unchanged; no generic importer claimed.

# Exp299: independent custom-content bundle preparation (development only)

This is **offline preparation**, not custom-song installation. The current PS4
plugin does not read the generated manifest or register its independent song ID.
Do not upload it as a stock-song replacement. Do not use `--deploy-full` to
pretend this proof is additive. The replacement CLI remains unchanged.

From `/home/neo/Projects/beat-saber-deluxe-additive`, using the project venv:

```sh
# Choose NEW, nonexistent output directories each time; no overwrite option.
.venv/bin/python orbeats/development/scripts/prepare_additive_bundle.py \
  --experimental --generate-probe temp/my-additive-source

.venv/bin/python orbeats/development/scripts/prepare_additive_bundle.py \
  --experimental --song-dir temp/my-additive-source \
  --template orbeats/custom_songs/quick_test.bundle \
  --output temp/my-additive-candidate

.venv/bin/python orbeats/development/scripts/prepare_additive_bundle.py \
  --experimental --verify temp/my-additive-candidate
```

The existing local template is read-only. It provides the title-compatible
serialized object/type layout; it is not an instruction to replace that song.
Do not distribute copyrighted game templates/dumps with prepared artifacts.

## Supported initial proof

- A newly generated twelve-second, low-volume tone sequence and nine simple
  alternating red/blue notes, in all five Standard difficulties. No downloaded
  music or third-party map is needed for the initial loading test.
- Or a narrow user-provided subset: `Info.dat` v2, unmodded Standard V3 color
  notes, stereo PCM16 WAV at 44.1kHz, zero time offset, bounded duration.
- Unsupported requirements, characteristics, arcs/chains/walls/events and unknown
  V3 fields are refused, not silently dropped. This is not a general importer.
- Sound uses Deluxe's existing **unpadded FSB5 PCM16** path. All samples and exact
  duration are retained. No legacy 12MB cap, HEVAG predictor assumptions or dropped
  partial compressed frames in this experiment. Compression/playback still needs
  a console test once the independent registration route exists.

## What is prepared and verified

- A content-derived `bsd_additive_<24 hex>` ID, separate from every stock ID.
- New CAB/resource names, a new asset container entry and matching level/clip
  names, rather than retaining the template's target names.
- New compressed beatmap/lightshow/audio-metadata TextAssets, actual new audio,
  sample count, BPM region, duration and difficulty references.
- SHA256/size manifest and independent reopen validation of objects, references,
  gzip JSON, sample descriptor, audio resource and actual PCM samples (the
  existing encoder's one-LSB normalization rounding is allowed).
- Stable bytes across repeated builds; existing outputs, input escapes and
  symlink escapes refused; staging is renamed only after verification passes.
- Manifest explicitly says `runtime_ready: false`, `deployment_attempted: false`.
  These are deliberate status fields, not a switch that makes a bundle playable.

## Remaining runtime work

The exact game's `BeatmapLevelLoader` has a bundle-loading route that builds
`levelID + "BeatmapLevelData.asset"` and asks `BeatmapDataAssetsModel` for its
bundle path. That is distinct from the unimplemented PC-style custom-song stubs.
An independent registration/file-route prototype must still be built and tested.
Do not assume an Addressables catalog change is needed, or assume none is needed,
until the existence/data/preview paths are traced end to end.

The new `BeatmapLevel` needs its own ID and coherent difficulty/basic-data keys,
not just a renamed stock title. Reusing unrelated stock difficulty metadata would
advertise modes/maps that may not exist in this bundle. Keep stock repositories,
lookup identities, entitlement behavior, catalog, saves and files unchanged.

Next console test is only appropriate after matching new-ID model construction,
asset-name/path routing, failure rollback and original lookup preservation have
regressions. Then back up, arm logs, deploy only an isolated custom directory and
candidate plugin, manually test the generated tone, and compare the original song.
No purchase/ownership bypass; the separate local0.8060 own-pack DisableBuyOption
fix remains untested on console. Installed0.8059/additive OFF is unchanged.

## Exp300 fixed-profile runtime test (not general import)
Plugin0.8061 consumes ONLY the exact Exp299 generated-tone artifact bound in
`include/additive_probe_profile.h`. Runtime FNV/size is a corruption gate, not
cryptographic verification. Deployment must compare manifest SHA256/full remote
readback, preserve prior debug binary/INI/features, stage uploads and keep title
closed. No stock target/catalog/replacement files are written. New levelID comes
from source hash, not100bills; source cover/menu preview/mapper labels reused.
21st class-value-size API and three safe managed-entry prologues must resolve.
Local996tests124skip do not prove Unity/FSB5/V3 playback on this hardware.
No production `--deploy-full` invocation is additive; never substitute it here.
Next captured manual test: BSD Additive Proof -> BSD Additive Tone Test -> Standard
Easy ->12second beep/new notes/results -> menu -> original100$Bills comparison if
stable -> fully close/report. Stop on crash/missing level, no repeated launches.

Exp300 deployment completed/verified; test PENDING. Reports in `.ai_memory/experiment_logs/additive-exp300-{deployment,enable-preparation,klog-capture}.json`.0.8059 rollback retained; runtime new content NOT yet validated.
