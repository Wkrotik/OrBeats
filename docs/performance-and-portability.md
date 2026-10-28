# Import performance and future platforms

## Implemented: pipeline 0.5375 / companion 0.7.3

Normal additive imports no longer download and checksum every installed bundle,
cover and preview twice. They retain the validated manifest's descriptors and
fetch **one verified bundle** as the legal conversion template. Existing records
remain unchanged; an import is not an integrity audit or a repair operation.
The one-time migration from compiled defaults still verifies all seed files:
there is no published installed manifest to trust in that case.

New files still get staged full-content readback. Closed-title checks, active
plugin/capability verification, the writer lock, immutable owned paths, collision
refusal, optimistic manifest-byte checks, rollback and publish-last are retained.
Missing/corrupt unrelated files can remain undiagnosed until runtime or a separate
investigation. No new audit UI was added.

The old two-map baseline alone reread **164,912,436 bytes (~157 MiB)** of existing
bundle/cover/preview content per import, before counting new uploads. A regression
now appends to 62 existing descriptors without reading the 61 unrelated bundles
or any old cover/preview. This establishes bounded reads, not 63-map PS4 playback.

Removing the final map now lists for a retained template instead of downloading
it merely to establish existence. If one must be saved, only its verified bundle
is fetched; cover/preview are unnecessary.

## Measured local checksum improvement

The wire protocol uses FNV-1a64. A tiny dependency-free C implementation replaces
the Python byte loop when an optional local library is present. `ctypes` loads it
without compiling at runtime. Known-vector startup checks reject incompatible
implementations; absent/unloadable acceleration falls back to the same Python
algorithm. Native/Python outputs, binary buffers and encoded manifests are tested
for identical results. FNV remains a corruption check, not authentication; bundle
SHA256 and existing publication checks are unchanged.

Build for the current host with an installed GCC/Clang-compatible compiler:

```sh
.venv/bin/python orbeats/development/scripts/build_native_hash.py
```

Source setup and Linux CI also build it. Future portable packages must include
the matching library; users of packaged releases should not need a compiler.
The helper source builds independently from Python and could be reused with the
Android NDK or a PS4 toolchain. Those target builds are not validated here.

Same-machine comparison: Ryzen 5 8645HS, Linux x86_64, three warm runs per input
and backend, medians below. Production normalization, audio conversion, bundle
build/validation, cover/preview and descriptor calls are included. Imports/module
startup, downloads and FTP are excluded. All six descriptors per map matched.

| Map | Python total | Native total | Descriptor/checksum portion, Python → native |
| --- | ---: | ---: | ---: |
| Bloom: 107 s / 951 notes / V4 | 1.95 s | 0.44 s | 1.54 → 0.027 s |
| 4cb11: 209 s / 1024 notes / V3 arcs | 3.70 s | 0.82 s | 2.94 → 0.052 s |

This is about **4.4–4.5× faster local preparation**, not the same multiplier for
real installation. Private reproducible-input reports remain in
`temp/orbeats-info-format/preparation-after-native.json`; original conversion and
checksum reports are beside it. No copyrighted inputs/bundles enter version control.

## Remaining costs and recommendations

1. **Full PCM audio and FTP.** The two outputs are roughly 19/37 MB. New-file full
   readback deliberately transfers them again to prove publication safety. Keep
   that verification; do not trade data integrity for a better progress timer.
   Since pipeline0.5378, supported original-packet Vorbis reduces real example
   bundles by75.2–89.3%; PCM remains the fallback. Those newer size results are in
   `compressed-audio-experiment.md`, not included in the earlier timing table.
2. **One whole existing template bundle per import.** This is now constant in
   library size but still includes a song's audio (PCM or Vorbis). A smaller owned template or a
   checked template cache could avoid it later; neither is implemented here.
3. **Library browsing round trips.** Catalog reads per-map JSON metadata and
   browser requests fetch individual covers. Reads are serialized for GoldHEN
   compatibility. A batched metadata index/cache could reduce round trips, but
   invalidation and external manifest changes must remain correct. Previews are
   already on demand, not full-library audio downloads.
4. **Identical reimports still convert before comparison.** Early no-op detection
   needs a trustworthy original-source identity across V3/V4 normalization. Do
   not skip content/collision validation based only on a BeatSaver display ID.
5. **Subprocess startup** is outside the timings above. Retain job isolation until
   it is measured to justify a persistent conversion worker.

No console/network performance was measured in this update. Do not describe
unmeasured network throughput or all-map memory behavior as a tested bottleneck.

## Android, Tauri and a future PS4 companion

Tauri 2 supports Android, with a **separate Android build** (APK/AAB) using Android
SDK/NDK and Java tooling. Web UI and compatible Rust code can be shared; it is not
one desktop executable that also runs on a phone. Desktop Python/FFmpeg sidecars
do not automatically become mobile-compatible: Python/native packages, audio
conversion, storage permissions, networking and background execution need their
own Android integration. Keeping a small platform-neutral checksum core avoids
a new obstacle but does not solve the rest of that work.

Official references: [mobile prerequisites](https://v2.tauri.app/start/prerequisites/),
[Android builds](https://v2.tauri.app/distribute/google-play/) and
[target-specific sidecars](https://v2.tauri.app/develop/sidecar/).

A PS4-native homebrew companion is a separate target. Tauri does not provide a
supported PS4 runtime. It would need a PS4 frontend, networking/storage and a
working asset/audio conversion stack. C algorithm/protocol code is reusable;
Python desktop packaging and the system webview are not a PS4 port. Such an app
could remove external hardware and FTP transfers, but must still run with Beat
Saber closed and retain transaction/recovery safety. No Android or PS4-only app
was implemented or promised by this optimization.

## Inherited-project cleanup

Removed 150 obsolete tracked files (16,897 lines): the parallel
`beat-saber-ps4-custom-songs/` scaffold, unused `beat_saber_ps4_tools/`, unrelated
`test_rb4dx_build/`, stale root song catalog/backup exercise and three hardcoded
bulk replacement-deploy shell scripts. Active converter dependencies, backup
support, regression fixtures, historical evidence, licenses and upstream notices
remain. Private toolchains, game inputs, settings and unrelated pre-existing
working-tree edits were not swept away. No history rewrite was performed.

OrBeats can use an independent repository rather than GitHub's fork association,
but it still incorporates modified Beat Saber Deluxe source. README attribution
therefore accurately describes that origin rather than calling it only
inspiration. GPL/corresponding-source obligations remain on distribution.


### Real-install failures reviewed after sidebar queue testing

- Colors4852 upload: a bundle already existed but its media directory did not.
  The optional cover read attempted `RETR` followed by `NLST` before directory
  creation, so both returned550. Create/verify the directory first; do not weaken
  the absence-vs-permission guard. Strict mock now matches this server behavior.
- Map25570 ExpertStandard.dat (V2.2.0):38 ChroMapper editor-grid BPM markers,
  editor cursor metadata and empty waypoints were rejected by the original
  constant-BPM guard. These markers are not runtime BPM events. Verified against
  ChroMapper revision `0d67a67d9b6ee750c412660a43ce34aa889378ae`, especially
  `Assets/__Scripts/Beatmap/V2/V2Difficulty.cs` (`LoadCustom`) and
  `Assets/__Scripts/Beatmap/Base/BaseDifficulty.cs` (`JsonTimeToSongBpmTime`,
  `ConvertCustomBpmToOfficial`): runtime timing uses BpmEvents, separate from
  BpmChanges; converting custom markers into official events also adjusts objects.
  Therefore validate/omit reviewed editor markers, not apply a second retiming.
  All328 notes,86 walls and1370 events survive local independent bundle validation;
  start-time error <=1.43e-14s and both wall endpoints preserved. This is local
  conversion proof, not user-observed console playback.

## Production compression and portable dependencies

Pipeline0.5378 uses the PS4-proven Vorbis/preload profile, not the proprietary
FMOD decoder used for the initial developer experiment. Production reconstructs
the FSB packets into Ogg and decodes them with libsndfile for verification. Bundle
`fsb5` plus its lookup module, libvorbis/libvorbisenc/libogg and the existing
soundfile/libsndfile/FFmpeg stack in portable artifacts. Missing optional Vorbis
libraries retain PCM rather than requiring users to install system packages.
Linux is exercised; Windows/macOS/Android packaging remains unvalidated. Do not
ship proprietary FMOD development binaries as a workaround.
