# OrBeats

An experimental **Beat Saber PS4 custom-song plugin and local companion**.
Independent custom songs appear in a first-position Custom Songs pack without
replacing original or DLC songs. One plugin, with modular internals.

**Supported console build:** CUSA12878, patch 2.04, GoldHEN with plugin support.
Other game versions/regions are not supported. This is not a PS4 emulator or a
way to bypass DLC ownership. Original game files and music are not distributed.

## Companion

The new companion provides:

- **Discover:** BeatSaver search, direct map links, rating/date filters, covers,
  mapper information, chart statistics and complete API metadata.
- **Your library:** read installed maps directly from the PS4; view metadata and
  remove individual custom maps without touching stock songs.
- **Settings:** PS4 FTP connection, safe local plugin deployment, light/dark
  theme and explicit update-feed availability.
- Staged imports with file readback, a progress/activity indicator and collapsible
  logs that can be copied or saved for reports.
- Supported 44.1/48 kHz Vorbis imports retain original audio packets without
  re-encoding; other audio uses uncompressed PCM16 fallback. Existing installed
  songs are not automatically converted.

### Run from this checkout

Install Python 3.11+ and FFmpeg. Keep FFmpeg available on `PATH`. A native plugin
artifact must be built separately before the Settings deployment button is usable.
No game dump is required to use an already configured additive library.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r beat_saber_deluxe/requirements-companion.txt
.venv/bin/python beat_saber_deluxe/webapp/server.py
```

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r beat_saber_deluxe/requirements-companion.txt
.venv\Scripts\python.exe beat_saber_deluxe/webapp/server.py
```

Open **http://127.0.0.1:8765**. In Settings, enter your PS4 IP and GoldHEN FTP
port (usually 2121). Keep this server local: it controls console files and stores
your FTP settings on your computer. Windows/macOS launch paths are documented;
only Linux has been exercised in this development environment. Android is a
future target, not a supported phone-only release today.

For faster checksums, optionally build the tiny C helper once with an installed
GCC/Clang-compatible compiler:

```sh
.venv/bin/python beat_saber_deluxe/development/scripts/build_native_hash.py
# Windows: .venv\Scripts\python.exe with the same script path
```

There is no runtime compilation. Without the helper, the same checksum runs in
Python. Linux is validated; Windows/macOS helper builds are not yet exercised.

Main song audio now prefers compatible original Ogg Vorbis packets, without a
second lossy encode; other sources retain PCM16. The source-checkout path uses
`fsb5` and open-source libvorbis/libvorbisenc/libogg when available. Missing codec
libraries keep the PCM fallback. No proprietary FMOD SDK is needed for normal
imports. Portable builds must bundle the codec libraries; desktop/mobile packaging
is not delivered yet. Existing installed songs, covers and WAV previews are not
automatically changed. See [compression validation](docs/compressed-audio-experiment.md).

### Before importing, removing maps or deploying the plugin

**Fully close Beat Saber; leave GoldHEN FTP enabled.** No live library refresh is
implemented. Start Beat Saber only after the operation finishes successfully.
The companion checks title state and refuses writes while it is mounted.

The active filename is **`orbeats.prx`** (including when deploying the diagnostic
build). The installer migrates the old owned filename/registration together and
preserves other plugins and existing songs. Recovery archives live in local
`ps4_backups/transactions/`, including the original FSELF and a journal. Temporary
`.stage-`/`.rollback-` files are transaction state only; successful operations
remove them. An interrupted or concurrent operation stops for recovery rather
than deleting unknown bytes. Do not clear its lock without inspecting the local
journal. Historical names in compatibility readers, source-directory paths and
upstream attribution are not active product branding.


Imports use temporary working directories, not a permanent computer-side music
collection. Converted bundles, art, previews and metadata are installed on the
PS4. Existing library content supplies the conversion template. On a truly empty
setup, you must supply your own legally obtained, validated prepared template;
the app cannot manufacture the game's copyrighted assets.

## Compatibility and limits

- **Local expanded-map candidate:** validated V2/V3/V4 with arcs/chains, native
  V4 NJS/lighting, changing-BPM event boxes, catalog-reviewed environments,
  Standard/OneSaber/NoArrows/90Degree/360Degree routes, authored palettes,
  bounded offsets/loudness and separate previews. Expanded paths require the
  new plugin capability. Bloom and Looping the Rooms have user-reported passing
  tests; that does not validate every expanded feature. Here Come the Cats exposed
  a palette-registration regression repaired in0.8077; the user confirms playlist
  recovery and playback. Unknown fields and mod
  requirements refuse rather than silently discard behaviours.
  See [native-map support and precise limits](docs/native-map-expansion.md).
- No advertised eight-song limit. The current parser/registration resource bound
  is **64 entries**, not an unlimited library; large-library console performance
  has not been demonstrated.
- Current installed playlist candidate: **v0.8077**; companion **0.7.22**.
- Local plugin branding candidate: **v0.8078**, not installed. The custom pack is
  named **OrBeats**, with the owned logo also used by its startup toast; IDs and
  songs stay unchanged. See [native extension research](docs/plugin-expansion-research.md)
  for menu/settings, anonymous ScoreSaber and selected-mod feasibility.
  Existing desktop0.1.11 bundles remain unchanged; web0.7.25 is source-only.
  Source pipeline is **0.5389** (the independent running source service still
  reports its earlier import-time0.5387 until an idle preserving reload).
  **Hardware recovery confirmed:** user reports0.8077 restores Custom Songs and
  Here Come the Cats plays correctly.0.8077 accepts both declared Object[] and
  covariant EnvironmentInfoSO[] with unchanged bounded entry checks. All **27**
  songs/settings/queue were preserved. Exact visual parity and every advanced
  feature combination are not established by this report.
- Active plugin is **orbeats.prx** with one GoldHEN registration. Fourteen owned
  old backups were archived locally and removed; unrelated plugins/backups were
  untouched. Successful updates retain recovery locally, not in console clutter.
- [Tauri desktop work](desktop/README.md) now includes a tested **frozen Linux
  backend** without host Python on PATH, private authenticated API,
  persistent state/paused queue, and graceful close during fake publication.
  The **native Linux window also compiles and opens the real UI**, with a verified
  normal window-close/backend-drain test on private Xvfb. Startup deadline,
  failure status and backend monitoring are implemented. No system installs.
  Linux candidate **0.1.11** bundles FFmpeg/ffprobe and isolated Ogg/Vorbis with
  offline conversion proof; the complete image is built against GLIBC2.35 and
  tested in a minimal Ubuntu22.04 userspace. Downloads keeps a collapsible active/
  last-job log above queue/history, with bounded scroll and reader-aware follow.
  Complete license/source review, Windows execution and broader distribution/
  installer checks remain pending. It is **not a public-ready release**.
- No official release repository/feed is configured. The UI reports update
  checking as unavailable rather than claiming that you are up to date.

[Protocol, CLI, recovery and implementation notes](docs/additive-companion.md)
· [Plugin changelog](beat_saber_deluxe/CHANGELOG-PLUGIN.md)
· [Pipeline changelog](beat_saber_deluxe/CHANGELOG-PIPELINE.md)
· [Companion changelog](beat_saber_deluxe/webapp/CHANGELOG-WEBAPP.md)
· [Performance findings and portability](docs/performance-and-portability.md)

## Development

Use the project-local OpenOrbis/GoldHEN tooling in `.devcontainer/` to build the
plugin. Run the complete host suite with:

```sh
bash beat_saber_deluxe/development/scripts/run_additive_host_tests.sh
```

Tests and uploads are not evidence of hardware playback. Never deploy while the
game is running. Preserve rollback copies, existing custom songs and unrelated
plugins. Settings deployment reads and merges **the user's existing
`/data/GoldHEN/plugins.ini`**; a repository-wide replacement INI is not shipped.

Legacy replacement tools still used by conversion/regressions remain; they are
not the new companion's import path. Obsolete parallel converter/plugin
scaffolds, unrelated Rock Band test code and hardcoded bulk-deploy wrappers have
been removed. Historical documentation is under `docs/legacy/` and `.ai_memory/`;
it is not a current installation guide.

## Attribution and license

OrBeats is independently developed from **Beat Saber Deluxe by Chris Primeish**
and contributors. It retains and modifies upstream code, not just inspiration:
https://github.com/free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter

Additive development and OrBeats integration: **Wkrotik**. Original source
attribution is retained. GPL-3.0 applies; see [LICENSE](LICENSE). An independent
repository name or GitHub fork setting does not change upstream attribution or
license obligations. Preserve notices and corresponding-source obligations when
distributing modified binaries.
GoldHEN, OpenOrbis, UnityPy and BeatSaver belong to their respective projects.
Beat Saber and PlayStation belong to their respective owners; no affiliation is
claimed. Song creators retain rights to their work.

### Desktop distribution targets

The first release targets **Windows x64** and **Linux x64 AppImage** (optional
`.deb`). The current development AppImage is rebuilt on **Ubuntu22.04 /
GLIBC2.35**, and passes isolated userspace window/close and offline conversion
checks without host Python, FFmpeg or WebKit. Windows execution, broader
clean-machine/installer tests and full licensing/source gates remain open.
No public release is published yet. See the
[baseline evidence](desktop/packaging/LINUX-BASELINE.md) and
[AppImage recipe](desktop/packaging/APPIMAGE.md).
