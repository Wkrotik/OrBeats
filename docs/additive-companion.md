# OrBeats companion: usage and recovery

## Run and connect

Install Python 3.11+ and FFmpeg (including ffprobe) on PATH. Install
`beat_saber_deluxe/requirements-companion.txt` in a virtual environment and run
`beat_saber_deluxe/webapp/server.py` with that environment's Python.
See the [README](../README.md) for Linux/macOS and Windows commands.
The default address is **http://127.0.0.1:8765**; keep the server local.

In **Console & settings**, save the PS4 IP, GoldHEN FTP port (normally 2121),
username and optional password. Saved passwords are not returned by the settings
API. FTP is not encrypted; use a trusted local network.

**Fully close Beat Saber before imports, removal or plugin setup. Leave GoldHEN
FTP on.** Start the game only after the operation completes. Live refresh is not
implemented. The companion refuses writes when the title is mounted or its state
cannot be checked. Do not launch the game during an active operation.

## Discover, install and manage

- **Discover:** search BeatSaver, paste a map link, choose rating/date/curation
  filters, inspect covers, mapper details, chart statistics and complete API data.
  Click a cover to play/stop the BeatSaver preview; View details opens map info.
  **Add to queue** adds a map quietly without moving the page. Open the sidebar
  **Downloads** button to review the queue, then explicitly start it with Beat
  Saber closed. A badge shows waiting/active maps; the activity mark flags errors.
  Downloads contains progress, pending-map removal, pause/clear controls, recent
  results and one readable log; Copy diagnostic log/Save report include the full
  unfiltered output without a second log display.
  Installations run one at a time. Failed maps are skipped and other maps
  continue; their reason stays in recent results with a **Retry** button. Retry
  appends once to the queue without auto-starting a paused queue. Recent results
  retain up to128 entries (enough for a full64-map pending batch). Pause/clear
  finishes an active transaction normally; Cancel stops the active job and pauses
  remaining work. Pending maps survive browser closure, not an ordinary service
  restart. An operator can explicitly use `--restore-queue snapshot.json` for a
  validated idle/paused service handoff; this always waits for manual start.
  BeatSaver's play/download counters are not shown: the current API returns zero
  for sampled maps. Rating shows the BeatSaver score **and total votes** (a small
  sample is labelled Few votes), not an invented approval/play count. Upload
  times are relative, with the exact timestamp in a tooltip.
  Compatibility is a metadata hint: **✓ No known blockers**, **✕ Not compatible**,
  or **? Needs validation**. Known blockers disable queueing; missing flags are
  unknown. A check does not prove chart format/geometry/lighting/audio support;
  the downloaded archive must still pass the unchanged strict importer checks.
- **Your library:** reads the PS4's installed manifest, not a computer-side song
  collection. Inspect a map or remove only its own entry and files. Selection is
  off by default: choose **Edit selection**, then click anywhere on a song card
  (or focus it and press Enter/Space) to select it. Selected cards change colour;
  there are no checkboxes. **Done editing** clears selection and restores normal
  card controls. **Select all**, **Clear selection** and **Remove selected** provide
  bulk removal with one confirmation listing the selected titles. Removals run one at
  a time and stop on the first error; completed work is reported and remaining
  selections are retained after refresh. Unselected songs are untouched. Close
  Beat Saber and keep FTP enabled. Running jobs and queued installations block
  removal; the reason and an **Open Downloads** control appear in Your Library.
  Finish the queue or explicitly clear pending work to unblock removal; nothing
  is cleared or started automatically. Older installs
  without saved BeatSaver metadata still show their available runtime statistics.
  Covers are read and checksum-verified directly from the PS4; they do not depend
  on a previous search. FTP reads are serialized to avoid concurrent-browser
  artwork timeouts. Library playback controls are intentionally removed; listen
  to BeatSaver previews from Discover instead.
- **Console & settings:** deploy the locally built plugin, configure the console,
  switch themes and see whether an update feed is available. No official release
  feed exists yet; the UI does not pretend that this means “up to date”.

Imports use temporary storage. No source music or converted map library is kept
on the computer. Converted content and optional BeatSaver metadata reside on the
PS4. Existing content provides a legal conversion template. If the library is
empty, configure a path to your own validated prepared bundle; game assets are
not shipped. Removing the last map retains a conversion seed on the PS4 so a
later import remains possible. This is not a turnkey fresh-console asset dumper.

CLI uses the same additive backend:

```sh
.venv/bin/python beat_saber_deluxe/tools/full_custom_song_pipeline.py \
  --additive-install --download-beat-saver-song 4ebb2 \
  --config beat_saber_deluxe/ps4_config.json
# Alternatively: --song-dir /path/to/map instead of the BeatSaver argument.
```

Legacy replacement commands remain for regression/reference purposes; they are
not this UI's import or removal path.

## Format support and resource limits

- CUSA12878 patch 2.04 only, with a matching companion-capable plugin.
- InfoV2 with validated vanilla V2/V3 charts; bounded InfoV4/V4 native chart,
  lightshow and audio-data routing. Current **local**0.8075/0.5385 candidate adds
  chains, translation/FX, changing-BPM event boxes, V4 arcs/chains/dynamic NJS,
  stock environments, distinct Standard/OneSaber/NoArrows/90Degree/360Degree
  characteristics, palettes, offsets/loudness and separate V4 previews. It is
  **not installed or PS4-tested**. See [expanded-map support](native-map-expansion.md)
  for native evidence, exact version gates and restrictions.
- ChroMapper V2 editor-grid markers are omitted without retiming authored
  objects; unsupported actual V2 BPM changes and runtime mod requirements still
  fail. V2 types14/15 become early/late native V3 rotations only in explicit
  rotational characteristics, not assumed mod-light lanes. Lighting-only charts
  are explicitly omitted; packs without playable charts fail. Nothing fabricates
  absent difficulties or relabels another characteristic as Standard.
- Earlier0.8073 Weave lighting was tested by the user with correct gameplay and
  visible background lights. That does not validate every new0.8075 path.
- Prefer supported original Ogg Vorbis packets for main audio (stereo 44.1 or
  48 kHz, compatible setup/codebook), without another lossy encoding. Unsupported audio
  profiles and unavailable open-source codec libraries fall back to PCM16.
  Independently validate sample counts, stored audio, seek tables and charts
  before publication; a validation failure is fatal, not a fallback bypass.
  Covers and WAV previews are unchanged. Decompress-on-load still uses decoded
  gameplay memory; compression reduces installed/transfer sizes, not proven RAM.
- Existing PCM installs remain untouched and identical reimports do not replace
  them. To opt an existing song into compression, remove it explicitly and import
  again with the game closed. No batch conversion or live replacement is done.
- There is no eight-song UI restriction. The native parser and registration retain
  a deliberate **64-entry / 131072-byte manifest bound**. This is not an unlimited
  library or demonstrated 64-song console-performance claim.
- Identical reimports are no-ops, not repair or integrity audits; the same ID with
  different data is refused.
  Edit/reorder/automatic replacement of an existing map is not implemented.
- Linux has been exercised. Windows/macOS launch paths avoid shell-based FTP in
  the new flows, but those platforms have not been executed here. Android remains
  a future target; phone-only conversion is not delivered by this desktop build.

## Publication, plugin setup and recovery

`tools/additive_library.py` and `include/additive_runtime_library.h` share
`BSDALIB1`: eight-byte magic, little-endian uint32 payload length and uint64
FNV-1a payload checksum, followed by count and bounded records. Records contain
length-prefixed UTF-8 text, finite float32 statistics, exact difficulty masks,
bundle SHA256, and file size/FNV values. IDs have the exact form
`bsd_additive_<24 lowercase hex>`; file paths/assets are derived, never supplied
arbitrarily. Zero records is a valid empty library. Invalid present manifests
refuse registration; only ENOENT permits the reviewed migration defaults.
These checks detect corruption; they are not an untrusted-code sandbox.

Normal imports validate and preserve the manifest, but do not audit unrelated
installed files. One existing bundle is read and checksum-verified as the legal
conversion template; cover/preview and other map files are not reread. Migration
from compiled legacy defaults still verifies all seed files once, because no
installed manifest proves their presence. Missing/corrupted old content is not
repaired or diagnosed by an ordinary append/reimport.

Song imports verify a capability marker against the active plugin's full ELF
hash. They touch only this title's additive content, not the plugin, stock/DLC
bundles, catalog, redirects, saves, flags or unrelated plugins.

A remote `.install-lock` excludes writers. Immutable content is staged and fully
read back first. The checked `library.bin` is renamed **last**, with an optimistic
previous-byte check and durable local recovery archive. Removal publishes the reduced library
before deleting only that map's derived paths. Cleanup failures are reported.
Plugin setup separately stages/verifies the binary, preserves rollback copies,
merges the existing `plugins.ini` without changing original bytes/comments or
other game sections, and publishes its capability marker last. A conflicting
plugin entry outside the exact title section is refused, not relocated silently.

Forced cancellation or power loss may leave a lock, staging files or a retained
manifest backup. **Keep the game closed, inspect evidence, restore the matching
backup if needed, then explicitly clear a stale lock.** Never reset silently or
remove unknown files. Cleanup and rollback also recheck title state.

## Evidence and next console test

The committed hardware baseline is `8d53b5e`: v0.8067, Wake Me Up + Cities,
first-position pack, working independent gameplay/artwork/previews. v0.8068 was
uploaded and its real companion Cities reimport succeeded; subsequent native
runtime boot and new arc playback were not user-confirmed.

Current local candidate: **v0.8070 / pipeline 0.5375 / app 0.7.3**.
Bloom (BeatSaver 5219c, Info4.0.1/chart4.1.0) passes real-source content-hash,
all-951-note/timing, bundle and preview checks locally; no Bloom playback claim. Offline tests
cover management transactions, permissions, INI preservation, rollback/concurrent
writes, native parser/64-level publication and actual conversion. Chromium smoke
tests exercise the responsive UI with fixture APIs. Neither proves PS4 playback.
See [the overnight audit](overnight-audit.md) for earlier results and
[performance/portability findings](performance-and-portability.md) for the latest
import-read changes and checksum measurements.
The new candidate was not deployed while the user's PS4 was off.

### Notifications and native speed defaults

General messages appear in a solid, dismissible bottom popup, never in a page-top
banner. The × control stays usable with Downloads or confirmations open; messages
do not scroll the page or disappear on a timer.

For InfoV2, finite NJS <=0 (or omitted) requests the native difficulty default:
Easy/Normal/Hard10, Expert12, ExpertPlus16. Positive authored speed is unchanged;
missing jump offset is0. The importer reports default resolution. Mod-dependent
charts remain unsupported; a mixed pack is not silently stripped of requirements.

Capacity comes from the exact matched console plugin/protocol, not queue size.
The read-only check on2026-10-26 found active0.8068 with a matching ELF hash and no
`max_songs` field, so the companion preserves that profile's8-song cap. Local
0.8070 has a64-song profile, but is not assumed installed. Higher-capacity hardware
performance is unproven; no plugin upgrade is done implicitly by queue changes.


## OrBeats filename and local-only recovery (0.5384 / app0.7.16)

The active plugin filename is now `orbeats.prx`, even for a DEBUG artifact;
source-build outputs are `orbeats.prx` and `orbeats_debug.prx`. Installation
migrates an exact owned legacy registration/binary together, preserving other
plugins and INI bytes. Ambiguous registration or unknown legacy content refuses.

Recovery archives live under local `ps4_backups/transactions/<UUID>/`. The journal
maps numbered before/rollback files to exact console paths. For plugins the
before file is GoldHEN's canonical ELF view, while the rollback archive is the
original FSELF downloaded after the temporary remote rename. Do not confuse them.
Successful publication removes its temporary remote rollback files. Interrupted
or concurrent state is not blindly deleted; inspect the journal and keep the title
closed before recovery. The developer backup cleanup helper accepts only exact
recognized owned backup names and native identities, archives/readbacks all of
them locally, then rechecks exact remote bytes before each deletion. Unrelated
plugins/backups and interrupted transaction state are not cleanup candidates.

Local tests and builds pass. The first console migration attempt timed out during
FTP connect, before any PS4 writes; filename migration and old-backup cleanup have
not been deployed yet. The previous lighting0.8073 remains last-known installed.
