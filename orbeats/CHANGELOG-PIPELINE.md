## 0.5392 — original map identity for anonymous leaderboard viewing

- Hash original Info.dat and its referenced chart bytes before conversion.
  Publish an optional158-byte identity bound to the installed song ID, bundle
  SHA256 and Standard difficulty mask before publishing the library manifest.
- Closed-title staging/readback; refuse conflicting/concurrently appearing
  identities. No change to library wire formats or normal playback.
- Existing-song reimport may add only this optional sidecar while preserving
  the original descriptor/PCM/media. OrBeats Extras0.0004 consumes it; previous
  companion binaries do not generate it. Source companion version0.7.27.
- Curated/frozen backend inventory includes the new pure-Python helper.

## 0.5391 — default environment, identity BPM markers and instant chains

- Empty environment lists with exact integer index0 retain the authored root
  environment. Other invalid references still fail closed.
- Top-level V2 BPM annotations are ignored only if validated and all exactly equal
  an explicitly provided base BPM. Genuine tempo changes remain refused here.
- Bounded uint32 `_atlasBeatsMap` annotation does not affect gameplay objects.
- V3/V4 zero-duration chains retain every slice, geometry and exact endpoint.
  The owned native BurstSliderSpawner handles equal endpoint times without a
  division by their difference. Negative chain durations and zero-time arcs refuse.
- Offline frozen import/prepare/independent verification passes unmodified public
  47764,3c853,35c11,4980,a87e,55106,54d4e. This is not PS4 playback evidence.

## 0.5390 — default palette and descriptive timing annotations

- Interpret only exact integer scheme index0 with an empty table as the vanilla
  default; retain authored per-difficulty RGB overrides and all other index guards.
- Accept finite bounded numeric InfoV2 _firstNoteBeat/_introPadSeconds annotations
  without applying offsets or altering audio/notes. Mod requirements still refuse.
- Unmodified letter54d4e and Konekomyu55106 pass frozen offline import, preparation
  and independent bundle verification:278/732 and1227notes. No PS4 retry performed.

## [0.5389] — exact legacy empty-wall placeholders

- Ignore only V2 obstacles containing exactly the five standard fields with all
  values zero. Positions/type/width must be real integers, times/durations numeric
  zero; bools, malformed/missing/extra fields and nonzero geometry are not ignored.
- Keep shared V3/V4 wall validation unchanged. Real/decorative walls, notes, bombs,
  timing and events are preserved. Count ignored placeholders per difficulty in
  import-report.json and display them in the installation job log.
- Real bd45 offline import and independent bundle/chart/audio verification pass
  in the frozen backend without host Python/FFmpeg:859/1001notes,102/109walls,
  only3ExpertPlus sentinels skipped. Original archive/files unchanged. No console
  installation/playback proof or automatic retry implied.

## [0.5388] — offline frozen media validation

- Add explicit import-v3 and prepare-additive child-task names to the frozen
  allowlist; arbitrary scripts remain refused. These provide offline conversion
  and bundle validation without host Python or console deployment.
- No native chart semantics, wire formats or installed library changes.

## [0.5387] — frozen desktop child-task dispatch

- Add explicit allowlisted pipeline/batch/BeatSage re-entry for the owned frozen
  helper; source checkouts keep normal Python argv execution. No host-Python
  fallback or arbitrary script dispatcher in packaged mode.
- Keep local recovery archives in the persistent desktop profile rather than
  versioned runtime code. No native plugin/map conversion or console changes.

## [0.5386] — InfoV4 per-difficulty colour metadata

- Normalize only known InfoV4 cosmetic colour/label keys into the existing
  per-difficulty palette path. Retain all nine colours, alpha and per-difficulty
  precedence over schemes. Unknown requirements/mod behaviour remain refused.
- Correct the native V4 arc validator: this PS4 loader takes arc colour from
  head metadata; tail colour is unused and need not match. Keep both reference
  bounds and all metadata validation, without altering authored chart data.
- Compare the existing one-sample AudioData tolerance in exact integer sample
  units, avoiding floating-point rejection at its boundary. Two-sample mismatch
  still refuses; do not silently stretch audio or weaken region validation.
- Add whole-import, real UnityFS, presentation-wire and malformed-metadata
  regressions. Real 555fe retains787notes,18arcs,2675basic light events and six
  authored colours. No plugin ABI change or automatic map replacement.

## [0.5385] — native map expansion (local implementation milestone)

- Native V4 arcs/chains/NJS/lightshow/audio, additional vanilla characteristics,
  stock environments, preserved V3 rotations/FX and BPM-distributed lighting,
  authored presentation and previews. See docs/native-map-expansion.md for
  exact native evidence, version gates and remaining restrictions.

## [0.5384] — OrBeats paths and local recovery

- Publish library/registration/plugin changes through checked transactions with
  durable local recovery archives. Temporary remote rollback files are removed
  after success; errors retain unknown evidence, not silent reset.
- CLI plugin installs delegate to the same guarded installer, including DEBUG.
  Read-only legacy banner/path support permits safe migration; no mod changes.
- Developer cleanup archives exact recognized owned plugin backups locally before
  deleting exact byte-rechecked paths; unrelated plugins/backups remain untouched.

## [0.5383] — bounded V3 boost and Weave event-box lighting

- Retain validated colour-boost, colour/rotation event boxes, filters, group IDs
  and basic-event compatibility flags in per-difficulty lightshows. Accept
  native-zero sparse scalar serialization; still refuse unsupported/mod fields.
- Piecewise BPM conversion for boosts; constant actual BPM for distributed boxes
  with uniform scaling of group/relative beats and beat-distribution width.
  Nonlinear BPM boxes, translation/FX boxes and chains remain explicit failures.
- Resolve reviewed WeaveEnvironment and difficulty indices; refuse mixed stage
  routes. Include environment in immutable identity/manifest and optional
  BSDALIB2. Require a hash-matched environment-aware capability before uploads.
- Actual4f7e2 offline proof retains614notes/73arcs/8boosts/780colour groups/
 714rotation groups in a7,547,864B Vorbis bundle. Hardware test pending; no songs
  or queue retried automatically. Full scope/remaining gaps documented separately.

## [0.5382] — hardware-confirmed 48 kHz Vorbis imports

- Enable supported stereo 48 kHz original-packet Vorbis in normal imports after
  user-confirmed playback and Practice Mode seek tests. Keep 44.1 kHz behavior
  and existing installed songs unchanged; no additional lossy encoding.
- Select the source rate explicitly and keep AudioClip frequency/length, FSB rate,
  exact frame count, AudioData sample coordinates and manifest profile consistent.
  Independent validation checks the original audio against the normalized source
  without confusing 48 kHz frames with 44.1 kHz sample positions.
- Separate 48 kHz immutable identity while retaining the existing PCM identity for
  safe reimports: existing PCM files are not replaced or duplicated. A 48 kHz
  template must not leak its rate into later 44.1 kHz or PCM imports.
- Unsupported profiles, unknown codebooks and unavailable codec libraries retain
  PCM16 fallback with a reason. Once compressed audio is selected, validation
  failures remain fatal, not a silent fallback. Covers/previews are unchanged.
- Real Light Switch normal import: 9,032,535 original frames at 48,000 Hz,
  3,346,918-byte bundle vs 33,293,490-byte PCM baseline. Offline full bundle,
  packet, audio and chart checks pass. No installed files or queue modified.

## [0.5381] — explicit48kHz developer audio proof

- Generalize strict Vorbis helpers to an explicit44100/48000 sample-rate argument,
  including FSB rate descriptor, reconstructed headers, exact frames and per-second
  seek anchors. Defaults remain44100; ordinary48k imports still use PCM pending
  console verification. Unknown codebooks remain refused, not re-encoded.
- Developer probe/deployer accept --sample-rate 48000 under their existing explicit
  experiment gates. Candidate updates both AudioClip frequency/length and AudioData
  sample coordinates; preparation reopens the result, independently decodes FMOD
  output, verifies original packets and tests compressed seeks.
- Real Light Switch9032535frames,3352366B vs33293490B PCM, no packet re-encoding;
  deployment payload binding/media validated offline. Runtime readiness false.
- Actual Legends Never Die aoTuV setupb2c77468 is rejected by hostFMOD (VERSION).
  A nearby known header differs by9bytes; it is not a safe substitute. PCM remains
  the non-reencoding fallback. Source/audio never silently discarded or replaced.

## [0.5380] — reviewed map metadata and source-cover compatibility

- Give blank/missing artist names the explicit Unknown artist fallback, preserving
  the nonempty binary-library string invariant; invalid types still refuse.
- Accept a case-only cover filename mismatch only when the in-directory match is
  unique. Ambiguous matches, missing files, traversal and escaping symlinks refuse.
- Recognize bounded V2/V3 editor bookmarks and bookmark timing flags without
  changing playable object timestamps; unknown bookmark fields still refuse.
  Reviewed ChroMapper sources keep bookmarks separate from runtime BPM events.
- Extend the existing omitted-cosmetic palette to boost/obstacle colours. Nonempty
  requirements/suggestions, mod effects, unsupported runtime lighting/chains,
  invalid wall durations and negative gameplay times remain fail-closed.
- Ten real previously failed maps independently verified offline through complete
  bundle/audio/chart/media/descriptor preparation. No automatic console retries.

## [0.5379] — native default note-jump speeds and explicit refusals

- Normalize finite nonpositive/missing InfoV2 NJS to the exact native difficulty
  default before strict preparation: Easy/Normal/Hard10, Expert12, ExpertPlus16.
  Verified CUSA12878 patch2.04 BeatmapDifficultyMethods at RVA0x97cf70/0x97cfb0;
  positive authored NJS is preserved, invalid types/nonfinite/out-of-range positive
  values still fail. Missing jump offset means0. Report each resolved default.
- Name unsupported BeatSaver extensions and affected difficulty; never strip mod
  requirements or effects to claim successful conversion. Explain capacity refusal
  with the installed profile's exact count rather than a vague upgrade message.
- Real offline In My Head4f2a now validates full audio/maps/media at native Expert
  NJS12:803notes,32bombs,16walls,4072940B compressed bundle. Whatcha Say21d5 also
  validates locally (679notes,28walls,12631465B); its earlier live failure reason
  was not retained, so no cause or console success is claimed for that job.

## [0.5378] — hardware-proven original-packet compressed audio

- Prefer original Ogg Vorbis packets for supported stereo44100 sources, using
  fresh FSB5 headers, exact sample count and independently checked seek metadata.
  No additional lossy encode. Normal V2/V3/V4 companion imports use the path;
  unsupported sources/profiles or absent open-source codec libraries keep PCM16.
- Independently reopen/decode stored compressed audio, compare all samples and
  authored maps, and refuse verification failures before publishing output.
  Production validation needs no proprietary FMOD SDK/runtime. Bundles keep
  decompress-on-load/preload: this saves storage/transfer, not gameplay RAM.
- Separate compressed IDs; preserve existing PCM installs on identical reimport
  and validate an exact-ID retained bundle even if it became its own template.
  No automatic conversion/removal of existing songs or console plugin update.
- Single-difficulty compressed/PCM templates can generate every newly authored
  difficulty with distinct map/lightshow objects and complete preload pointers.

## [0.5377] — new media-folder uploads and reviewed V2 editor metadata

- Create/verify an owned map media directory before attempting optional cover or
  preview reads. Retain strict absence checks, immutable collisions, stage readback
  and manifest-last publication. Strict FTP regression now rejects nonexistent
  directory listings and uploads rather than pretending they are empty.
- Accept reviewed ChroMapper V2 editor-grid BPM markers/cursor metadata and empty
  waypoints without retiming authored objects. Keep real requirements, runtime
  tempo changes, unknown marker fields and nonempty waypoints rejected, with more
  specific errors. Real25570 independently builds/verifies all328 notes,86 walls
  and1370 lights; object timing differs only by <=1.43e-14 seconds of rounding.

## 0.5376 — ordinary V2 charts and empty mod metadata

- Reuse the bounded V2 converter in the additive import path. Accept explicitly
  empty requirement/environment fields and cosmetic editor offsets; nonempty
  requirements, unknown custom data, custom geometry and V2 BPM changes still fail.
- Omit lighting-only difficulties explicitly in the report/log. Never fabricate
  playable notes or silently substitute stock charts. All-lighting packs fail.

## 0.5375 — bounded import reads and portable checksum acceleration

- Append-only imports retain existing manifest entries without rereading every
  installed map twice. Fetch and verify one conversion-template bundle only;
  keep full one-time checks for migration from compiled legacy defaults.
- Preserve new-file readback, manifest validation/CAS, closed-title/plugin guards,
  transaction locking, retained rollback and collision refusal. Reimport is a
  no-op, not a repair or an audit of already installed content.
- Add an optional tiny C FNV-1a implementation loaded through ctypes. Validate it
  against Python at startup; preserve byte-identical wire checksums and fall back
  to Python when absent. Source setup/CI build it; runtime needs no compiler.
- Two-map Linux medians: local preparation 1.95 → 0.44 s and 3.70 → 0.82 s.
  Download/startup/FTP excluded; no new console-performance claim.

## 0.5374 — bounded InfoV4 imports and current branding

- Print the current OrBeats name and pipeline version in conversion jobs.
- Normalize InfoV4 4.0.0/4.0.1 and V4 4.0.0/4.0.1/4.1.0 notes, bombs and
  obstacles through the existing verified importer. Preserve sample-region BPM
  timing and omitted metadata indices; verify original BeatSaver source hashes.
- Refuse unsupported V4 arcs/chains, rotation/NJS events, authored lighting,
  loudness adjustments and separate preview audio rather than discarding them.
- Bloom (5219c) passes local source-hash, 951-note/timing, bundle and preview
  validation. PS4 installation and playback remain untested for this map.

## 0.5373 — companion management and safety audit

- Share byte-preserving GoldHEN INI merging; reject conflicting plugin scope.
- Distinguish denied FTP reads from absent files, recheck title state before
  publication/recovery, and use optimistic manifest-byte checks with rollback.
- Match the new native 64-entry/131072-byte bound; retain immutable file verification.
- Verify existing bundles sequentially instead of keeping the whole library in RAM.
- Preserve a console-side conversion template when removing the final map.
- These are locally tested flows, not new PS4 playback evidence.

## 0.5372 — validated vanilla V3 arcs and actionable import refusals

- Preserve ordinary V3 sliders/arcs, including both endpoints across BPM changes,
  control-point multipliers, directions, color and midpoint mode. Validate their
  exact schema, bounded counts, coordinates and audio-duration bounds before use.
- Keep chains, rotating charts and unsupported advanced lighting/mod data refused;
  errors now name the feature and difficulty/file instead of one generic message.
- Expected additive compatibility failures exit with a readable message, without
  a Python traceback. The native plugin/protocol and existing song data are unchanged.
- Regression source: failed user map4cb11 has75 vanilla arcs. Offline conversion
  and independent UnityFS reopen retained75arcs,1024notes,16bombs,94walls and1100
  basic events. This is not a claim of PS4 arc playback validation.

## [0.5371] — 2026-10-26

- Add --additive-install through existing CLI/jobs: vanilla Standard V3 conversion,
  verified immutable uploads, library-last publication, no stock target/rebuild.
- Closed-title, active-ELF capability, eight-song cap, backups/rollback, concurrency
  lock and idempotent re-import. See docs/additive-companion.md for limits.

## Exp305 — 2026-10-25 (pipeline0.5370 unchanged)

- Native media/credits experiment only; prepared existing reviewed files via Exp304 development script. Production replacement installer unchanged; arbitrary additive installation NOT implemented.

## v0.5370 —2026-10-25 (development, Exp304)
- Local-only prepare_additive_media.py: normalize song/optional playlist artwork
  to512px squarePNG; use original Info.dat previewStart/Duration to extract
  PCM16 stereo44100 WAV. Exact excerpt/hash/path/bounds/no-overwrite validation.
- Explicit runtime_bound=false: not a console uploader or native preview binding.
-512px is an import design target, not an assertion about native pack dimensions.
-1021tests passed124skipped; plugin/UI and existing gameplay assets unchanged.

## v0.5369 —2026-10-25 (development, Exp303)
- New experimental OFFLINE V2 importer: full ffmpeg PCM16 decode, vanilla notes,
  bombs, correct full/crouch walls and basic lighting; reject unsupported mods,
  rotations/BPM changes rather than drop them. No FTP or stock replacement.
- Full per-difficulty bundle metadata and independent lightshow objects/preload
  references; verify audio/geometry/lighting roundtrip. Explicit AudioClip
  load0/preloadTRUE/backgroundFALSE (native audibility remains UNPROVEN).
- Production replacement CLI unchanged, not a generic additive installer yet.

## Exp301 — 2026-10-25 (NO pipeline version/code change)
- Pipeline remains0.5368. Generated bundle/manifest unchanged; playback blocked
  before custom-loader calls, so no re-encoding/replacement deploy is justified.
- Local plugin0.8062 addresses exact proof free/local classification only.

##2026-10-25 Exp300 engineering note —NO pipeline version bump
-0.5368 offline CLI unchanged. Fixed generated profile now has LOCAL0.8061 runtime bridge, not a production additive deploy command; hardware proof pending.

# Pipeline Changelog

## v0.5368 — 2026-10-25 (local unreleased, Exp299)
- Development-only independent custom bundle preparation CLI, explicit --experimental
  opt-in; generated twelve-second tone and five V3 Standard beatmaps, separate
  content ID/CAB/container/FSB5 PCM16/audio metadata, no stock replacement/FTP.
- Reopen/sample validation, deterministic output, input limits/escapes/mod guards,
  no-overwrite. Manifest explicitly NOT runtime ready.28 new tests;991pass124skip.
- Installed0.8059/additive OFF unchanged. Runtime model/loader integration pending.

## v0.5367 — 2026-10-25 (local unreleased, Exp 289)
- Expose user-approved enable_additive_song_packs=False in canonical feature
  defaults; legacy defaults unchanged. Plugin0.8056/webapp0.6.21 synchronized.
- No converter/asset format changes or auto-deployment. This is the runtime
  stock-reference pack experiment, not a new-ID/content loader; no console proof.
- Full local suite957passed124skipped, including native sanitizer model checks.

## Historical preparation — development-only additive research (2026-10-25, Exp 285/287/288)
- Add a read-only dump.cs/catalog inspection CLI under development/scripts/ with
  28 synthetic tests; does not modify assets, generate hooks or contact a console.
- Exp 287: accept real PS4 catalog m_resourceTypes spelling; retain synthetic alias
  and reject malformed primary instead of falling back. Real read-only FTP inputs acquired.
- Exp 288: pinned project-local Il2CppDumper/.NET bootstrap and evidence-recording
  dump runner (11 synthetic tests); actual dump+expanded probe run on owned inputs.
  PS4 custom-loader stubs identified via mapped code; no runtime feature implemented.
- Add optional local host/native setup and a host-test wrapper that blocks lftp.
- No production pipeline/plugin changes or version bump (pipeline remains 0.5366;
  plugin v0.8055); additive registration and the stock duplicate remain unimplemented.


## v0.5366 (2026-10-23)
### Fixed (Exp 283d — the user's field report: a fresh deploy's song kept its STOCK menu preview)
- **Deploy-order bug: the pack/preview pass ran before the deploy's own song
  registered in song_metadata.json** (Step 11 wrote it at the END), so
  `build_preview_map` treated the just-deployed slot as "not custom" and
  baked no preview for it — every deploy baked the PREVIOUS deploy's
  preview, never its own. The target's metadata now registers LOCALLY
  (deploy=False, idempotent) before the pack pass; Step 11 still owns the
  upload. Regression-pinned by test_exp283d_preview_metadata_order.py.


## v0.5365 (2026-10-19)
### Fixed — Exp 281d (the user's cache-only deploy: pack-modes never followed the cache + the redirects refusal blocked clean consoles)
- **`pack_modes.dump_dir` follows `paths.game_dump_dir`** unless the user pinned it explicitly — the pack-modes builder reads the same game-data root as the per-song templates (pack bundles + origin catalog), so the game_data cache is a drop-in for both. Previously the "Use the extracted cache" switch repointed only game_dump_dir and deploys logged "Dump dir missing … cannot build pack mode bundles" — the pack patch (mode buttons + previews) silently skipped. 2 tests (follows unpinned; a pinned dir is never rewritten).
- **Absent redirects.json + a local file = the new state for a clean console.** `_download_redirect_from_ps4` now distinguishes ABSENT (decisive 550 → returns None) from FAILED (raises RuntimeError); the redirect-config deploy treats absent+local as deployable (the local set was just built by this deploy's scoping) and refuses only on genuine failures. The Exp-246 anti-wipe gate is preserved and stronger. 3 tests (absent→None, failure→raise, clean-console+local deploys).

2026-10-19)
### Fixed — Exp 281c (the user's cache-only song deploy failed on a clean console — two real fresh-console bugs)
- **Absent redirects.json is the clean-slate state, not a read failure:** the single-song deploy scoping (the Exp-246 pull-before-push guard) refused to continue when redirects.json was absent — but a decisive 550 means "no customs exist to preserve," so a fresh console's FIRST song deploy must proceed (scope = target song + its pack). The refusal now fires only on genuine read failures. Same fix for the flags reader (`_download_features_from_ps4`: 550 → None → defaults instead of RuntimeError — the flags Apply on a clean console). Shared classifier `_ps4_output_looks_absent`. 4 tests.
- **The bundle-deploy verification false negative:** GoldHEN's FTPD ends `ls` lines with the FULL PATH, not the basename — the verify's basename equality never matched, so every upload reported "⚠️ UNVERIFIED" while the file sat on the console (the user's 28MB bundle was verifiably present). The parser now matches the basename within the last field.

## v0.5365 (2026-10-19)
### Changed — Fresh-install defaults (Exp 281, user directive)
- **Fresh-console write robustness (Exp 281b):** `_ensure_afr_title_dir()` — `mkdir -p -f` on the AFR title dir before any AFR write (request puts, features.json deploys, bundle uploads). The clean normally leaves the dir, but the bootstrap makes every AFR write robust against its absence. 2 regression tests (the mkdir command + its ordering before the put).
- **`DEFAULT_FEATURES` is now ALL-ON** (previews, the M11 toggle, and the M12 extractor flip to True). A fresh install works out of the box; every flag surface (the plugin's absent-file defaults, this dict, the webapp's DEFAULTS_TRUE/KNOWN_FLAGS, the CI-generated features.json template) now carries the same truth.

## v0.5364 (2026-10-19)
### Added — M12: game-data extraction management (the "no dump required" flow)
- **`--request-game-data [--game-data-packs p1,p2] [--game-data-slots s1,s2]`:** computes the extraction manifest from `beat_saber_song_ids.json` (per-slot templates + per-pack bundles + catalog — a slot request automatically includes its pack's bundle) and writes `game_data_requests.txt` to the PS4. NO dump needed to compute it. Upload verified via remote listing; the "no targets" error carries a fix suggestion (Exp-278h policy).
- **`--pull-game-data`:** mirrors the console's `game_data/` into the local cache (`paths.game_data_dir`, new default `./game_data`, PROJECT_ROOT-relative) via resumable lftp mirror; reads the plugin-owned `game_data_status.txt` first; missing files post-pull are reported; every failure path carries a "To fix:" suggestion. The cache mirrors the dump layout exactly — pointing `paths.game_dump_dir` at it is the ONLY change a user makes (the web app's "Use the extracted cache" button does it).
- **OWNERSHIP (pull-before-push doctrine):** requests.txt is pipeline/web-app-owned (the plugin only reads it); status.txt is plugin-owned (the pipeline only reads it). No file is written by both sides.
- `DEFAULT_FEATURES` gains `enable_game_data_extractor: False` — deliberately the only flag-plumbing change.

## v0.5363 (2026-10-14)
### Added
- **M11 flag plumbing (Exp 278): `enable_in_game_plugin_toggle` (default False) added to `DEFAULT_FEATURES`.** The new plugin hotkey (L3+R3 2s on a DS4 → flip `enable_plugin` inside features.json, restart to apply) needs nothing else from the pipeline: `apply_feature_flags`' Exp-248 pull-before-push already bases every flag deploy on the LIVE features.json, so in-game flips are picked up, preserved, and surfaced by the webapp/ps4_state automatically. New reusable development script: `development/scripts/ps4_elf_imports.py` (PS4 ELF dynsym dumper — DT_SCE_* tags are offsets relative to the PT_SCE_DYNLIBDATA segment; game imports are NID-obfuscated, decode against a NID DB such as shadPS4's aerolib.inl).

## v0.5362 (2026-10-12)
### Fixed — release-layout findings (Exp 270a, found validating the v0.8048-pipeline-0.5361-webapp-0.6.4 zip from a clean extraction)
- **The web app showed 0 example packs from an extracted release zip (latent since the FIRST M9 release).** The release zip layout is FLAT (webapp/, tools/, docs/ at the zip root — no beat_saber_deluxe/ wrapper), so `RELEASE_ROOT` (one level above the zip root) pointed at nothing; the batch adapter's `EXAMPLE_DIRS` never probed the zip root itself. Fix: `paths.py` gains `release_root_surname()`/`release_path()` — probing BOTH layout levels — and every RELEASE_ROOT consumer (batch dirs, runner cwd, backup paths, validator) is layout-agnostic now. Verified from a true clean extraction: 34 packs parse.
- **The devcontainer-absolute default config paths (the Exp 234 release finding #1, long documented as "localize the config") are GONE.** All `load_config` defaults are now PROJECT_ROOT-relative (works from any extraction directory), `ps4_config.example.json` ships relative paths (`./ps4_dump/…`, `./custom_songs`) with a description teaching them, and relative paths in a user's config resolve against PROJECT_ROOT at load time. Verified: a user-style `--deploy-full` from the extracted zip ran green end-to-end against the live PS4.
- **`--deploy-pack-modes` / `--deploy-pack-bundle` could ship a variant catalog while live redirects still named the modes bundles — the catalog/bundle CE-34878-0 landmine.** The redirect VALUES name the bundle variant derived from the current flag state; deploying bundles without refreshing redirects leaves the pair inconsistent (found live: variant bundles + variant catalog deployed, redirects still modes-only). The deploy-only CLI paths now call `manage_redirect_config` after deploying, the same guarantee `--deploy-full` always had. Live PS4 healed + verified (all 5 packs' CRCs match, PASSED).
- **The backup helper script now ships in the release zip** (the Backup/Restore tab wraps `backup-beat-saber-deluxe-files.py`; it was never bundled — the tab was repo-only).
- Release notes: the docs tables gained the song-previews feature doc + the previews round-trip in the validation-procedure row.

## v0.5361 (2026-10-10)
### Fixed — CRITICAL
- **CE-34878-0 at boot after a batch deploy (Exp 269e — the live crash the user hit): the deployed lizzo variant's actual CRC (1,065,772,882) did not match the deployed catalog's expected CRC (2,222,108,153) — same size (22,656,896 B), different bytes. Two of the v0.5359 optimizations combined into the crash: (a) the same-SIZE upload-skip was UNSOUND — two different builds of the same variant share size whenever the slot set matches (fixed 10s PCM16 slices = fixed lengths), so "same size" never proved "same bytes"; (b) `--deploy-full` built the variant TWICE (deploy_pack_bundle's upload pass used whatever existed, then deploy_pack_modes rebuilt — fresh BeatSaver re-downloads change song-bundle bytes between passes) — pass 2's CRC went into the catalog while pass 1's file stayed deployed. Fixes: the upload-skip now requires a SAME-SESSION upload record + unchanged remote size (cross-process callers always upload — correct, safe); `deploy_pack_bundle` builds exactly once BEFORE any upload so every upload carries the same final bytes the catalog encodes. NEW DEPLOYED-BUNDLE CRC GUARD in post-deploy validation + `--verify-ps4`: pulls each deployed pack bundle and verifies its actual catalog-scheme CRC equals the manifest/catalog expectation — the check that would have caught this pre-boot; it names the crash signature explicitly ("re-deploy the pack, do NOT boot"). Live PS4 repaired (all 5 packs' deployed CRCs verified matching) and 5 new regression tests pin the class (soundness of the skip ×3, the crash-number contract, single-build ordering, source-level guard presence). 856/856.

## v0.5360 (2026-10-09)
### Fixed
- **The SECOND live batch failure — a modes rebuild clobbered the previews-VARIANT manifest rows (Exp 269c round 2).** `_save_manifest` keyed rows by pack, so the per-song modes rebuild replaced all 5 variant rows; the post-deploy check (working exactly as designed — its new stale-row detector printed the smoking gun) then compared modes CRCs against the correctly-variant deployed catalog → false mismatch on all 5 packs → batch stopped. Fix: the modes builder PRESERVES variant rows (keyed by patchedBundle, deduped to newest previewsAt); only the variant builder ever replaces them. The user's deploy itself was again fully successful — variant bundles + matching catalog were on the PS4.
- **Preview-start drift for maps with separator-mangled titles ('Queencard ( / G)I-DLE').** The map's own title is literally 'Queencard (' (BeatSaver metadata is occasionally malformed), so FIRST-separator splitting truncated the title, the repo-source lookup failed, and the stable-but-mapper-free busiest-bar heuristic silently took over (start drifted 53.4s → 83.1s across rebuilds). Fix: title extraction splits on the LAST ' / ', and a resolution LADDER (exact → trailing-punctuation-stripped → parens-dropped → heuristic) restores the mapper's 53.423s for Queencard; applied identically in build_preview_map and the fingerprint (26/47 slots now resolve to mapper-intent sources; the rest have no local source by design).
- **Batch upload waste: N×5×30 s of pack-bundle uploads per batch.** `_deploy_file_to_ps4` now skips uploading pack/catalog artifacts whose identical SIZE is confirmed in the live remote listing (cross-process-safe: each batch song is a fresh pipeline process, so session memory alone cannot dedupe; a rebuilt variant always differs in size because the resource growth embeds in the LZ4HC stream). Song bundles always re-upload — they ARE the payload. Live-verified: one lizzo-content deploy uploaded ONLY the changed variant + catalog; the 4 fresh packs skipped in seconds.

## v0.5359 (2026-10-09)
### Added
- **`--skip-song-preview-management` + per-pack preview dirty-checking (Exp 269c — the batch optimization).** Every `--deploy-full` was rebuilding song-previews variants for every pack in scope (the user noticed: batch deploys got slow because songs 1..N−1 each paid the full preview pass). Two layers: (1) **`--skip-song-preview-management`** skips previews-variant build management for a run — the web app's **batch_runner now injects it into every batch command except the last** so an N-song batch regenerates previews exactly once, at the end (the variant already deployed keeps serving; a user-supplied flag on the final command is honored with a printed NOTE). (2) **Dirty-check per pack** (`_previews_pack_dirty`): a variant rebuilds only when its modes base changed (mtime — valid for local builds), its custom-slot set changed, or any slot's INPUT changed — fingerprint `[bundle_md5, info_dat_md5]` per slot (NO UnityPy parsing on the skip path; the audio AND the heuristic's embedded beatmaps both live inside the bundle the md5 covers). Clean 5-pack fleet: ~23 s of pure md5 reads vs ~3 min of rebuilds; profiling also caught `_repo_title_index` reparsing ~100 Info.dat files PER SLOT (46× waste) — now process-cached. 7 new tests (flag threading, all 4 dirty-check legs, fingerprint shape, cache identity, runner injection).

## v0.5358 (2026-10-09)
### Fixed
- **The first live previews batch deploy failed post-deploy validation on ALL 5 packs (`mismatched=[all 5 pack guids]`) — a false alarm: the deploy itself was fully successful (all 5 variant bundles + correct catalog on the PS4; verified post-fix with correlation 1.0 between the deployed 2BeLoved preview and the custom song's audio).** Root cause: the previews-variant manifest rows were written with `packBundle = <pack id>` instead of the STOCK bundle filename — the key the post-deploy check indexes by — so the check found each pack's (now-stale) MODES row and compared its crc/size against the deployed catalog (which correctly carries the variant's). Fixes: `_record_previews_manifest` writes the stock bundle name; the check's manifest index is FLAG-AWARE (variant rows win when `enable_song_previews` is on, modes rows win when off — append order can never decide which bundle's CRCs are "expected"); the 5 on-disk manifest rows repaired; the check re-run against the LIVE PS4 catalog → all 5 packs PASS. Regression tests reproduce the exact stale-lookup (buggy packBundle → modes row wins) and pin the flag-aware selection both ways.

## v0.5357 (2026-10-09)
### Added
- **Song previews (M10, Exp 268/269 — behind the new `enable_song_previews` feature flag, default OFF).** When the player highlights a custom song in the song menu, the game plays the pack bundle's preview AudioClip (`BeatmapLevelSO._previewAudioClip` → `SongPreviewPlayer.CrossfadeTo`) — previously always the STOCK song's 10s clip, confusing once the slot is replaced. New `tools/song_previews.py`: for every custom slot in a pack, cuts a 10.0s excerpt of the slot's own deployed audio (the exact FSB5 PCM16 gameplay plays — always in sync), at the mapper's `Info.dat _previewStartTime` when a matching local source dir exists, else the busiest-bar heuristic computed from the deployed bundle's own beatmaps (BPM-aware: notes carry beat values, converted via `bpmEvents.m`; snapped to a 4-beat bar); 8ms fade-in / 250ms fade-out; normalized to the stock-preview fleet loudness (−10.4 dBFS RMS, peak-limited −1 dBFS, applied only when >3dB off). The FSB5 PCM16 blob is APPENDED to the pack bundle's inner `.resource` and the preview AudioClip's `m_Resource.m_Offset/m_Size` are repointed IN PLACE (16 bytes, same blob length — zero object-table shifts); `m_Offset` is relative to the resource node start (spike lesson). SO floats untouched (stock `_previewStartTime=0.0` already plays the pre-cut clip). The variant ships as a SEPARATE bundle (`…_pack_modes_previews_assets_all_…`) — mode buttons and previews ride together; flag OFF deploys the existing modes-only bundle unchanged (byte-identical naming + content). Pipeline threads the variant through `_get_pack_modes_entries` (deploy/catalog/redirect all follow the flag), builds it in `_ensure_pack_mode_bundles`, and records it in the manifest for catalog regeneration. Plugin v0.8048: parses `enable_song_previews`; the Exp-222 pack-assets/catalog gate now serves the patched pair when EITHER mode-mapping OR previews is ON (both OFF → stock bundle, no crash); boot toast counts N/4.

## v0.5356 (2026-10-07)
### Fixed
- **Post-deploy validation's size check no longer fails a deploy over out-of-scope songs' stale LOCAL artifacts (Exp 264 — the bug that stopped the user's first multi-pack batch deploy at song 1/22).** `--deploy-full` for BabyOneMoreTime failed its own validation with `Size mismatches: ['Oxytocin_v3.bundle (local 36,706,086 vs PS4 36,706,075)']` — an 11-byte delta between a stale local bundle (built by the release's 0.5354 tools during validation) and the live PS4 copy (rebuilt by repo tools), for a song the batch never touched. The deployed copy is what the game boots; a stale local artifact of an unrelated song says nothing about the deploy's health. **Fix: a session upload ledger** — `deploy_to_ps4` and the pack `_deploy_file_to_ps4` record every remote filename they upload; the size check hard-fails ONLY for files this session uploaded (its actual purpose: catching failed/incomplete uploads of what THIS deploy pushed), while out-of-scope mismatches become an informational `ℹ️` note. Standalone `--verify-ps4` (no uploads this session) keeps checking everything — that's the deep-audit mode. Pinned by regression tests reproducing the user's exact scenario.

## v0.5355 (2026-10-06)
### Fixed
- **Redirect "healing" could rewrite healthy values into dangling ones (Exp 263, found by release-validating v0.8047-pipeline-0.5354-webapp-0.6.0-alpha01 against the live PS4).** `_ensure_mass_song_redirects` regenerated every song redirect's VALUE from `mass_deploy.slots` casing — with the default config that list spells the Rolling Stones slots lowercase, so a single-song `--deploy-full` "healed" 11 live mixed-case values (`MessItUp_v3.bundle` → `messitup_v3.bundle`) **without re-uploading those slots' bundles**; the files on the PS4 kept their mixed-case names and 1+ redirects dangled (exact-count post-deploy check #3 failed the deploy, correctly). Fixes: the healing now takes the LIVE AFR dir listing; a value that already names a file present on the PS4 is **never rewritten** (casing-only "corrections" are the bug, not the cure); a genuinely-dangling value heals **toward the case variant that actually exists on disk**; unreachable-listing falls back to the old config-driven behavior (deploy-time unreachable state already hard-aborts upstream, Exp 246). Pinned by regression tests reproducing the exact live scenario (pre-validation backup → default config → deploy scope → zero healthy values touched, dangling ones healed to on-disk casing). The live PS4's 11 rewritten values were restored from the validation backup.

## v0.5354 (2026-10-04)
### Fixed
- **`--clear-target-song` could leave the slot's bundle behind in another casing** (Exp 253: the loadout then correctly reported the slot as "stale" — bundle present, no redirect — right after a clear, and the user asked why it wasn't "Stock"). Root cause: the removal used the literal slot casing, but deploy paths have written slot bundles with different casings over time (webapp deploys use the catalog's `MessItUp`; example scripts/mass deploys used `messitup`), and GoldHEN FTP is case-sensitive. The clear now LISTs the AFR dir and removes EVERY file matching `<slot><suffix>` case-insensitively — a reverted slot leaves nothing behind in any casing. (Bundle version bump: pipeline v0.5354.)

## v0.5353 (2026-10-02)
### Fixed
- **CRITICAL — `--features-only --set-feature` pushed a stale LOCAL features.json over the live PS4, silently turning `enable_song_metadata_modification` OFF in-game (Exp 248: the "2/3 features" boot toast + vanished custom-song metadata).** The exact Exp 246 redirects class, on the flags path: `apply_feature_flags` based its write on the local file (stale from the release-validation flag round-trips) and deployed it wholesale; any `--set-feature` diff rode along with every stale local value. **Fix: pull-before-push for flags** — `apply_feature_flags` now downloads the LIVE features.json first (new `_download_features_from_ps4`, banner-proof raw_decode extraction; ABORTS on read failure — never blind-apply; absent file = clean slate from DEFAULT_FEATURES), materializes defaults for flags the live file predates (Exp 221 rule preserved), applies ONLY the requested diffs, resyncs the local file, then deploys. Bad `--set-feature` syntax aborts before any I/O. 9 regression tests (`tests/test_exp248_flags_pull_before_push.py`), including the exact live scenario (stale local metadata=false, live ON, unrelated diff requested → live value preserved).
- **Test-suite PS4-safety net (Exp 248, the amplifier):** a webapp endpoint test had started a REAL `--features-only` subprocess against the user's live console — the vehicle that pushed the stale file. Now: (a) all webapp endpoint tests mock the runner (argv recorded and asserted — better coverage than before); (b) `tests/conftest.py` blocks any lftp UPLOAD (` put `) suite-wide with a loud AssertionError (reads/listings stay allowed for hardware-gated tests; deliberate write-tests need an explicit marker).
- Banner-proof JSON parse in the new flags pull uses `raw_decode` scanning — first-`{`-to-last-`}` slicing BREAKS on trailing banners that start with `}` (real lftp banners do); caught by the new tests pre-field (the Exp 240/221 pattern, third instance this month).

## v0.5352 (2026-10-02)
### Fixed
- **CRITICAL — single-song `--deploy-full` wiped 46 of 47 song redirects on the live PS4 and crashed every other custom song in-game (Exp 246).** Root cause chain (three stacked defects): (1) the release-validation `--clear-target-song` round-trip restored the PS4's redirects.json but left the LOCAL copy at 1 song — local/PS4 divergence; (2) `manage_redirect_config` GENERATE mode based a generate+DEPLOY on the stale LOCAL file and pushed it over the live 47-redirect state (pull-before-push, the Exp 237 invariant, violated by the pipeline itself — post-deploy validation stayed green because it compares local == PS4 and both were equally wiped); (3) the single-song scope-expansion path's `except: pass` silently fell back to "just the new target" when its PS4 read failed (READ-FAILED rendered as empty-truth). Fixes: **generate+deploy now REBASES onto the live PS4 state** (stale local detected → live base used, local file resynced; PS4 unreachable + local file exists → **hard ABORT** with a clear message; genuinely-fresh clean slate unaffected); **scope-expansion read failure → hard ABORT**; `_ensure_mass_song_redirects` **never deletes out-of-scope song redirects** (preserves with a warning — removal is exclusively the job of `--clear-target-song` / clean slate). Pinned by 7 regression tests (`tests/test_exp246_redirect_wipe.py`) reproducing the exact live scenario (local=1, PS4=47, deploy → 47 preserved + 1 new). **The live PS4 was restored from the validator's `redirects.json.bak` (47 songs / 5 packs / catalog — all targets verified present before push, read back and confirmed after).**
- Banner-proof JSON extraction applied to the single-song scope read (lftp-ftp-pitfalls #1): first-`{`-to-last-`}` slicing, immune to transfer banners on slow links.

## v0.5351 (2026-09-26)
### Fixed
- **`--deploy-full` now deploys the plugin end-to-end from a packaged release (Exp 234 finding #2 resolved).** `build_plugin` falls back to the bundled CI-built binary (`plugins/beat_saber_deluxe_debug.prx` / `plugins/beat_saber_deluxe.prx`) when no Makefile is present — the release zip ships tools only, so the previous unconditional `make` failed with `RuntimeError: Plugin build failed`. Verified live from the extracted alpha zip: `--deploy-full` deploys song + pack + catalog + **bundled plugin** (`No Makefile (packaged release) — using bundled plugin` → uploaded → plugins.ini entry confirmed), post-deploy validation PASSED.
- **Plugin deploys always use the canonical remote name `beat_saber_deluxe.prx`** — a `--debug-logging` deploy REPLACES the single plugins.ini entry instead of forking a second one (`beat_saber_deluxe_debug.prx`) that GoldHEN would load alongside. Re-deploy without the flag to restore the quiet build. Plugin-only mode (`--deploy-plugin` with no song) routes through the same resolver (was: hardcoded repo path that missed the bundled binary).

## v0.5350 (2026-09-25)
### Fixed
- **The 3 tracked `custom_songs/` files survived every prior fix attempt but kept dying on real runs (Exp 233 — the ACTUAL bug, third layer).** Exp 229 pinned the git cwd; Exp 231 verified the helper returned the right files — but both tested the helper in isolation and never exercised the COMPARISON. The wipe compared rglob()'s ABSOLUTE paths against `git ls-files`'s REPO-RELATIVE paths with `item not in tracked` — a Path can never equal across forms, so EVERY file (tracked included) was unlinked while the log printed "preserved git-tracked: ...". Fix: `_git_tracked_files` returns resolved-ABSOLUTE paths AND the wipe compares as resolved-absolute string sets (both layers normalized). Pinned by a NEW end-to-end regression test (`tests/test_clean_slate_wipe.py`) that runs the REAL `clear_local_pipeline_state` against a scratch git repo — tracked survive, artifacts removed, dirs pruned — plus a real-repo comparison-match test. The fixture commit/order bug in the first E2E draft (artifacts accidentally committed) was caught by the test itself before it could ship a fourth false green.
### Added
- **`--no-prompt` on all 34 `example_*.sh` scripts**: the pre-deploy confirmation can be skipped so chained pack scripts run in series unattended (`script1.sh --no-prompt && script2.sh --no-prompt && ...`). Default (no flag) keeps the interactive prompt. Skip path announces itself and sleeps 3s so a terminal scroll-by remains readable.
- **CI: both test jobs failed on one live-state test** (`TestPackModesRealArtifacts::test_real_entries_and_redirects`, `assert 0 == (0+1)`): the class asserts on the DEVELOPER's real workspace state (redirects.json + built bundles — gitignored, absent on runners); `_resolve_active_packs` returned [] and the pack-count assertions were contradictory. All four tests in the class now carry the hardware-environment skip gate (same pattern as the pipeline tests), verified to skip in a no-artifacts environment and pass in the real workspace.

## v0.5349 (2026-09-25)
### Fixed
- **Chained multi-pack deploy on a clean slate ended with only the LAST pack working (Exp 232 — CRITICAL).** After a true clean-slate wipe + running the 5 pack scripts in sequence, only the Rolling Stones pack kept its custom beatmaps/modes; the other 4 packs showed swapped metadata but loaded STOCK bundles. Root cause: `_ensure_pack_bundle_redirects`' stale-sweep defined "still configured" purely by LOCAL bundle existence (`_get_pack_bundle_redirects` filters `os.path.isfile`), while the Exp 227 clean-slate wipe empties `pack_modes_bundles/` — so each script's deploy found only ITS OWN pack's bundle and deleted every other pack's redirect as "pack no longer configured" (even though those bundles were live on the PS4). Last writer (RS) won. **Latent since Exp 226** — previous chained QA runs passed only because `pack_modes_bundles/` still held all packs' bundles from earlier sessions; the clean-slate wipe exposed it. Fix: a pack redirect is valid if it is in the current pair OR the pack is DEPLOYED per the redirects state file (`_resolve_deployed_packs` — the same authority every deploy flow uses); true stales (neither local nor deployed) are still removed. Verified: clean-slate 5-script chain simulation now accumulates 1→2→3→4→5 pack entries; deployed-pack-survives-missing-local-bundle and true-stale-removal both pinned by regression tests.
- **Live PS4 state repaired after the broken run**: all 5 pack pairs + catalog re-added to redirects.json, merged catalog regenerated for all 5 packs (patched CRC/size verified), two long-ghost PATD song redirects (deadmanwalking/sugarsoaker — leftover from the Exp 226 PATD revert; bundles absent from the PS4) removed via `--clear-target-song`. Post-deploy validation PASSED (5 packs, 36 songs, catalog md5 match).

## v0.5348 (2026-09-25)
### Fixed
- **'15 Minutes' (443f3) shipped NoArrows charts identical to Standard — arrows on Hard NoArrows (Exp 231).** BeatSaver v4 columnar sources sneak past the NoArrows generator: it writes d=8 (dots) onto the columnar EVENTS, but the `colorNotesData` ROWS keep their arrow d-values — and `convert_v4_to_v3` merges row-OVER-event at injection, so the arrows came back (verified in the deployed bundle: HardNoArrows d-distribution byte-identical to Standard's 220/175/30/32/69/65/46). OneSaber was immune (post-merge re-application since Exp 218); 90Degree is immune (its generator only APPENDS rotationEvents, which the row merge cannot clobber — deployed 90Degree charts verified correct, 52 rotations). **Fix: the injection path re-applies the NoArrows dot pass AFTER the v4/v2 conversion** — idempotent for well-formed sources (d=8 stays d=8), corrective for columnar ones. Deliberately NOT a blanket `_MODE_GENERATORS` re-application: 90Degree's rotation-append is not idempotent (would double rotations).
- **`--clean-ps4` deleted the 3 git-tracked `custom_songs/` files AGAIN on the user's real run (Exp 231).** The Exp 229 preservation fix had a cwd-dependent bug: `_git_tracked_files` ran `git ls-files` inheriting the process's working directory — launching the backup script from anywhere but the repo root made git resolve to no repository → `[]` → wholesale rmtree → tracked files deleted. (My earlier scratch test passed only because it happened to run from /workspace; the user's real run didn't.) **Fix: the git call is pinned with `-C <repo_root>`** (derived from the script's own path) — verified working from /workspace, /tmp, and /.
- Answered for the record: the 3 files ARE needed/tracked — `fsb5_header_template.bin` is a live production dependency (`tools/hevag_encoder.py` DEFAULT_FSB5_TEMPLATE for the legacy `--hevag` codec path; PCM16 default builds headers from scratch, which is why deploys kept working), `quick_test.bundle`/`quick_test_gen.py` are dev fixtures referenced by tests/analyze_audio.py.

## v0.5347 (2026-09-24)
### Fixed
- **Lint: all 17 ruff findings in `full_custom_song_pipeline.py` resolved IN CODE** (Exp 230 — user-approved post-QA; replaces the Exp 229 temporary config suppression, which is removed — the file is fully lint-enforced again):
  - F841 ×2: dead stores removed — `changed` flag in `normalize_v3_schema` (written 6×, never read; function documented as in-place mutation) and `std_lightshow_pid` in `add_mode_characteristics` (computed, never used). **Behavioral equivalence proven**: both versions' extracted `normalize_v3_schema` produce byte-identical JSON across 10 edge cases (all-zero colorNotes repair, bpmEvents repair, empty input, missing keys, non-dict basicEventTypesWithKeywords, non-zero no-repair cases).
  - F401 ×3: unused imports removed — `TypeTreeNode` in `_create_text_asset_object` and duplicate local `import tempfile` in `_download_pack_bundle_from_ps4` + `clear_target_song` (zero references confirmed by AST scan of each function body).
  - F541 ×10: f-string prefixes without placeholders dropped (log strings only).
  - I001 ×2: function-local import blocks sorted (`import subprocess as sp` / `import tempfile` order).
- Zero functional changes: every hunk is a dead store, an unused import, an f-string prefix, or import order. `ruff check tools/` exits 0 with no per-file-ignores; full suite re-verified green; deployed-bundle behavior is byte-identical by construction.

## v0.5346 (2026-09-24)
### Fixed
- **'…Baby One More Time' title metadata never replaced (Exp 228 — Unicode ellipsis chain).** Three independent bugs: (1) `json.dump`'s default `ensure_ascii=True` wrote the key as `…Baby One More Time`; (2) the plugin's byte-verbatim JSON parser kept the escape; (3) the game's UTF-16 title folds to `?Baby One More Time` in `extract_utf16_string`. Fixes: pipeline writes `song_metadata.json` as raw UTF-8 (`ensure_ascii=False`, all 3 dump sites); plugin gained `\uXXXX` unescape (`json_unescape_inplace`) + key fold (`fold_utf8_to_ascii`) mirroring the extraction projection (BMP=1 `?`, astral=2 `?`); plugin `create_il2cpp_string` now decodes UTF-8→UTF-16LE properly (manual fallback was byte-per-codeunit mojibake). Backward compatible: escaped files already deployed still match.
- **V4 (BeatSaver v4.0.x) maps shipped ambiguous mode charts + map-ID display names (Exp 228).** BeatSaver v4 uses the same columnar layout as the PS4's native format (`colorNotes[{b,i}]` + `colorNotesData[{x,y,c,d}]` — the game parses it natively, verified against the stock dump CAB; those Standard charts played fine). The real hazards: (a) the procedural mode generators mutate `colorNotes` events assuming denormalized fields — on columnar events they attach inline `c`/`d` alongside the `i` index, producing an ambiguous mixed event (`i` says "use colorNotesData[2]" while inline says blue/dot); (b) V4 Info.dat uses `song.title`/`song.author`/`audio.bpm` instead of `_songName`/`_songAuthorName`/`_beatsPerMinute`, so display names silently fell back to the map ID ('Oxytocin' -> '4dea2'). New `is_v4_beatmap()`/`convert_v4_to_v3()` denormalize all columnar pairs (notes/bombs/obstacles/arcs/chains/events) in `replace_beatmaps` + mode-injection donor paths, so the generators operate on unambiguous data; `_read_info_song_metadata`/`_read_info_bpm_from_dict` read the V4 keys; `download_beat_saver_song` warns loudly on map-ID fallback.
### Added
- `--metadata-only` early-exit mode: surgically add/update/deploy a `song_metadata.json` entry without processing a song or touching redirects/plugin (used to fix the two live v4 entries; also the pipeline-flag path for metadata repairs per Exp 199).

## v0.5345 (2026-09-23)
### Fixed
- **Ghost packs: `--clear-target-song` on a clean-slate PS4 rebuilt + deployed SIX packs the user never installed (Exp 227).** The user cleared one of 3 BE songs on a fresh clean slate; the run processed britneyspears/camellia/lizzo/panicatthedisco/therollingstones too. Root cause: the Exp 226 union fix added the *local-bundle fallback* discovery (`pack_modes_bundles/` still held 6 stale bundles from earlier repairs) into every deploy scope. Fixes: (1) new `_resolve_deployed_packs()` — deployed state (redirects.json) ONLY, no local-bundle fallback — now drives `deploy_pack_bundle`/`deploy_pack_modes` unions; (2) caller-provided `packs=` is the AUTHORITATIVE scope in `_get_pack_modes_entries`/`_ensure_pack_mode_bundles` (no re-union) — deploy flows union the deployed state themselves. Single-song deploy cross-pack preservation verified intact (BE+camellia+britney test).
### Changed
- **Clean slate now includes ALL local state (user directive, Exp 227).** `backup-beat-saber-deluxe-files.py --clean-ps4` previously cleared only the 3 local config files; `pack_modes_bundles/`, `custom_songs/`, `mass_bundles/`, and stray `.blob` debug artifacts survived and were exactly the fallback source that resurrected ghost packs. `clear_local_pipeline_state()` now removes all of them (verified: 3 configs + 8 + 69 + 39 files + 51 blobs; everything regenerable from BeatSaver sources + game dump).
- 5 scoping tests updated to authoritative-scope semantics; 3 new ghost-pack regression tests (deployed-state-only resolver, clear-song scope, cross-pack preservation).

## v0.5344 (2026-09-23)
### Fixed
- **Only the FIRST-deployed pack got mode-selector buttons (Exp 226 — pure-filter pack scoping).** Each per-song deploy filtered its pack set through the deployed-state discovery (`_resolve_active_packs` — what is on the PS4 NOW), which by definition lags the pack being deployed: britney/camellia/lizzo/RS deploys each found only billieeilish "active" and silently skipped the requested pack's patch (`Requested pack(s) not in the active set — nothing to deploy`). Fixed in all four helpers (`_get_pack_modes_entries`, `_ensure_pack_mode_bundles`, `deploy_pack_bundle`, `deploy_pack_modes`): an explicitly requested pack JOINS the active set instead of being filtered by it. Verified live: britneyspears bundle now builds + deploys with the rest; all 5 packs patched, catalog regenerated with all 5 entries.
- **`--clear-target-song` on the last custom song of an unrelated pack WIPED ALL 44 song redirects (Exp 226, found while fixing the above live).** clear_target_song's step-6 redirect regeneration passed `slots=rebuild_slots` (empty = "no extra modes needed") which the scope filter interpreted as "delete every song redirect". Three fixes: the call now scopes to the redirects that still EXIST after the surgical removal; `_ensure_mass_song_redirects` treats an empty scope as a NO-OP; an unmatched non-empty scope preserves redirects (out-of-scope trimming only runs when the scope matched configured slots). Live state restored from deployed bundles (44 songs + 5 packs + catalog) and validation PASSED.
- **Rolling Stones script contained a misplaced PATD slot:** SugarSoaker is a Panic! At The Disco pack slot, not Rolling Stones — the RS script deployed Venom of Venus over a PATD song and patched the PATD pack. Removed from the RS script/docs (RS is 11 slots); the unintended PATD deployment was reverted (slot cleared, pack redirect + catalog entry removed, catalog regenerated for the 5 intended packs).
### Changed
- Example scripts completed: BE +3 songs (IDidntChangeMyNumber→Mr. Brightside 3fc90, Oxytocin→Kiss Me More 4dea2, YouShouldSeeMeInACrown→15 Minutes 443f3), RS +StartMeUp→Wake Me Up (437d); britney Toxic/Radar/Oops slots swapped off the target artist per user directive (Toxic→Complicated MELODICKA BROS 19849, Womanizer→Teenagers MCR 217f1, OopsIDidItAgain→Hollaback Girl Gwen Stefani 53e4 — no target-artist songs incl. fan re-charts). All verified by download with clean note-count progressions.

## v0.5343 (2026-09-23)
### Fixed
- **Clean-slate first-song deploy booted into CE-34878-0 (Exp 225 — regression from v0.5342).** The patched pack bundle deployed WITHOUT its matching merged catalog and WITHOUT the aa/catalog.json redirect; the game then loaded the patched bundle against the ORIGIN catalog → Unity CRC validation failure at the pack scan (the classic Exp 180 crash signature). Root cause: `deploy_pack_bundle` and `deploy_pack_modes` both gated on a non-empty PINNED `pack_modes.packs` list (`if config.get('pack_modes', {}).get('packs'):`) — the Exp 224 auto-discovery default made that list `[]`, so the gate was permanently False and the catalog branch (build + upload + `aa/catalog.json` redirect) was silently skipped while the pack bundle still deployed via the generic pairs loop. Both gates now check the ACTIVE pack set (`_resolve_active_packs` — pinned list or auto-discovered).
### Changed
- **A FAILED post-deploy validation now aborts with a non-zero exit (Exp 225).** Previously the pipeline printed "⚠️ Post-deploy validation FAILED" but continued to "Pipeline complete!" and exited 0 — the example scripts' `if [ $? -ne 0 ]` guards never fired, so a crash-prone state shipped with a green-looking log. `--deploy-full`/deploy flows now exit 1 on validation failure with a clear error naming the CE-34878-0 risk.
### Tests
- `TestCleanSlateCatalogPair` (4 tests): clean-slate discovery of a locally built bundle; `_ensure_pack_mode_bundles` regenerates the missing merged catalog; `_get_pack_modes_redirects` then carries the aa/catalog.json pair; `deploy_pack_modes` with the empty pinned list deploys the catalog alongside the bundles (the exact crash path, now pinned). 607/607 pass.

## v0.5342 (2026-09-19)
### Changed
- **ZERO hardcoded pack expectations (Exp 224 — user directive).** The default `pack_modes.packs` list (`["therollingstones","billieeilish","lizzo","camellia"]` — an Exp 188 leftover that encoded August's deployed state as a permanent expectation) is REMOVED; default is now `[]`. The active pack set is resolved per-invocation, never hardcoded: (1) a user-pinned `pack_modes.packs` list in ps4_config.json if set; else (2) AUTO-DISCOVERY from the deployment state — exactly the packs whose `*_pack_modes_*` bundles are referenced in redirects.json (the state file synced with the PS4 on every deploy; a state file that references no packs means NO packs are in scope — locally built bundles never count as deployed); else (3) if no state file exists at all (clean slate), packs with local built bundles so build flows have a scope. Affects `_get_pack_modes_entries`, `_ensure_pack_mode_bundles`, `_resolve_configured_packs`, `deploy_pack_modes`, `_get_pack_bundle_redirects`, `_regenerate_merged_catalog` and `--verify-ps4`. A pack merely built locally but never deployed (the rollingstones bundle from an earlier cycle) is no longer expected, validated, or force-added.
### Fixed
- **lftp shell-metacharacter path bug (Exp 224):** `put ... -o .../Scream&Shout_v3.bundle` — lftp's command language splits the path at `&`, so the upload silently failed while lftp exited 0 (validation caught it as a missing redirect target). ALL FTP command constructions in the pipeline now quote paths via a shared `_ftp_quote()` helper (21 sites), and `deploy_to_ps4` verifies the upload landed (remote listing size check) instead of trusting lftp's exit code.
- **Example scripts/docs:** `--target Scream&Shout` quoted in the britney files (bash was splitting the same way — `Shout: command not found`); latent `--target Satisfaction` corrected to the real slot `ICantGetNoSatisfaction` in the rolling_stones files.
- **Local catalog drift:** regenerated catalog_pack_modes.json from the auto-discovered set (RS entry dropped; md5 now matches the deployed catalog).

## v0.5341 (2026-09-19)
### Fixed
- **`ps4_state.py` "Extra data" JSON parse failure (Exp 222):** `cat_remote` returns lftp's combined stdout, which can carry banner chatter around the file bytes — `json.loads` on the raw capture choked at exactly the file's end offset. Both JSON reads (features.json, redirects.json) now locate the first `{` and `raw_decode` exactly one object, ignoring surrounding lftp output.

## v0.5340 (2026-09-19)
### Fixed
- **Stale features.json deployed with silently-absent flags (Exp 221 — the "2/3 feature flags" report).** `--deploy-full`/`--deploy-features` uploaded the local `features.json` verbatim; a local file written before `enable_beatmap_mode_mapping` existed shipped without it, and the plugin booted with that flag OFF (user saw "2/3 feature flags ON" after clean-slate + two pack script installs). `_deploy_features_to_ps4()` now merges missing keys from `DEFAULT_FEATURES` (explicit values — including explicit false — are never overwritten) and creates the file from defaults when absent; the "skip deploy if local file missing" path is gone.
### Added
- **`--skip-plugin-deployment`** — opt out of building + deploying the plugin during `--deploy-full` (e.g. pinning a specific plugin build on the PS4). Default unchanged: every `--deploy-full` builds the LATEST plugin source and installs it (`make clean` + `make -B`, so source changes always reach the PS4).
- **`ps4_state.py` now reports feature-flag status** — reads the PS4's `features.json` and shows `enable_plugin` (ON/OFF), each of the three flags (flagging MISSING keys that would default false), and the boot notification text the next launch will display.
- Regression tests: `TestFeaturesMergeOnDeploy` (3 tests — missing-key materialization preserving explicit values, file creation from defaults, `--deploy-full` plugin-deploy wiring with the skip opt-out).

## v0.5339 (2026-09-18)
### Added
- **Global kill switch support: `enable_plugin`** added to `DEFAULT_FEATURES` (default `true`). `--features-only --set-feature enable_plugin=false` uploads a features.json that makes the plugin (v0.8043+) fully inert on next boot — official songs only, without editing plugins.ini or clearing the AFR dir. `--set-feature enable_plugin=true` re-enables.
### Changed
- **Song selection rule for all `example_*` docs (Exp 219 audit):** every custom song in the 34 pack example files must ship native Easy + Normal + Hard difficulties (per `user_preferences.md` — Expert-only maps lock out lower-skilled players). Audited all 44 unique BeatSaver MAP_IDs against the live API: replaced 15 failing songs across camelia (6), britney_spears (8), lizzo (2), billie_eilish (1), rolling_stones (1) with qualifying maps (verified by downloading each and checking real note counts per difficulty — several API-qualified candidates were rejected for duplicate/flat charts). Difficulty comments in the docs now state the TRUE native difficulties (the old docs claimed "5/5" for maps that shipped ExpertPlus-only — e.g. Sexy Socialite). Expert/Expert+ gaps are auto-filled by the pipeline from the map's own closest difficulty; Easy/Normal/Hard are never clones.

## v0.5338 (2026-09-17)
### Fixed
- **"BPM wayyy too slow, notes wayyy too late" on partial-difficulty maps (Exp 218).** When a BeatSaver map provides fewer than 5 difficulties (e.g. Sexy Socialite/Green Light ship ExpertPlus only; Jealous/'Roni ship Easy+Expert), the pipeline replaced only those slots and left the **stock beatmaps** in the unreplaced difficulty TextAssets — stock timing (the stock song's BPM grid) played over the custom audio. Every difficulty the user selected that the map didn't provide was the wrong chart on the wrong grid. New `fill_missing_standard_difficulties()` (runs before mode detection/generation/replacement) materializes a `<Diff>.dat` for every missing difficulty, cloned from the map's own closest harder (else easier) difficulty — every Standard slot now carries the custom song's own beat grid.
- **BPM grid: Info.dat `_beatsPerMinute` is now authoritative.** The v0.52 heuristic `eff_bpm = max_beat × 60 / audio_duration` undershot BPM by the trailing-silence fraction of any map whose chart ends before its audio (an outro, an extended lighting tail) — every map with a tail got progressively desynced: 'Roni deployed at 112.1 BPM vs the real 117 (−4.2%, notes 9 s late by song end), Green Light −3.8%, FANCY −2.0%, Jealous −1.9%. The heuristic was a misdiagnosis from the same era as the empty-`bpmEvents` bug (fixed v0.52c): those songs' desync came from BPM=60 fallback, not mapper grid drift. The beatmap max-beat scan is retained only as a guard — `eb` extends past the Info.dat grid only when a note actually lands beyond it (mapper genuinely faster than declared). Six cached Camelia maps verified: bpmData `eb` now equals `duration × BPM / 60` exactly (802.3/490.2/417.3/449.9/395.8/478.7 vs the old 791/486.9/404.1/445.6/390.5/469.0).
- **OneSaber is now blue DOTS (user-facing convention, Exp 218).** `_generate_one_saber()` converts every note to a dot (`d`/`_cutDirection` = 8) in addition to the blue recolor, and drops the same-cell arrow-gap rule (moot for dots). Mapper-authored `<Diff>OneSaber.dat` charts (Jealous, 'Roni, Sexy Socialite ship their own, with mixed directions and red notes) are normalized through `_generate_one_saber()` at injection time in `add_mode_characteristics()`. Bombs pass through untouched. User report: "I played one saber mode on these songs and they all still had arrows on the note boxes" — arrows made generated OneSaber indistinguishable from Standard and stock-clone fallbacks.

### Changed
- Missing-difficulty donor order: closest HARDER difficulty first (playing up is safer than down), falling back to closest easier. Never overwrites files the map provides; never uses mode files (OneSaber/NoArrows/90Degree) as donors.
- `load_bpm_regions()` logs `Info.dat BPM grid: <bpm>` instead of `Beatmap-based BPM`.

### Tests
- `TestFillMissingStandardDifficulties` (6 tests): fill-from-harder, fill-from-easier, provided-diffs untouched, mode files never donors, empty dir, idempotent rerun.
- `TestCameliaSyncRegression` (2 tests): every cached Camelia map's `eb` matches the Info.dat grid; 'Roni specifically must NOT regress to 404.1.
- OneSaber generator tests updated to dots-only (5 new/changed assertions incl. bombs-passthrough).
- Full suite: 595/595 pass.

## v0.5337 (2026-09-16)
### Fixed
- **Multi-pack deploys destroyed other packs' custom songs** — Running one pack's install script (e.g. Camelia) removed the custom songs of every OTHER pack (e.g. Billie Eilish) deployed earlier. Two root causes:
  1. **Cross-pack slot scoping:** `deploy_slots` only collected custom songs from the TARGET pack; `_ensure_mass_song_redirects` then treated all other packs' song redirects as "out of scope" and deleted them. Now `deploy_slots` collects ALL custom songs found in the PS4 `redirects.json` (any pack), and `deploy_packs` is extended with every pack that has existing custom songs — so deploying a billieeilish song preserves and re-deploys camellia's patched bundle too.
  2. **Case-sensitive slot matching:** slots discovered from PS4 redirects use the game's casing (`Crystallized`) while `mass_deploy.slots` uses lowercase (`crystallized`). The `s in slots` / `songID in target_slots` comparisons matched nothing, so `_ensure_mass_song_redirects` fell into the "empty slot scope" branch and deleted ALL song redirects. Both comparisons are now case-insensitive (`_ensure_mass_song_redirects` in the pipeline, `patch_pack_bundle` in the builder).
- Also fixed the stale-pack-redirect removal that fired spuriously during multi-pack deploys: `_ensure_pack_bundle_redirects` now receives the full pack scope (target pack + preserved packs), so another pack's redirect is no longer misclassified as "no longer configured".

### Changed
- Single-song deploy log now reports `Preserving existing packs with custom songs: ...` alongside the preserved song slots, making cross-pack state visible during incremental installs.

## v0.5336 (2026-09-15)
### Fixed
- **Second song deployment obliterates first custom song** — When deploying a second song to the same music pack, the first custom song's bundle and redirect were being removed because `deploy_slots` only included the new target. Fixed by downloading the current `redirects.json` from PS4 before each deploy to discover ALL existing custom songs in the target pack, then including them in `deploy_slots` so their redirects and pack bundle modifications are preserved.
- **Incremental pack bundle patching refined** — The pack bundle is now correctly downloaded from PS4 before each new song deploy, ensuring incremental patching preserves all previously-deployed custom songs' mode sets.

### Changed
- Single-song deploy now queries PS4 for existing redirects in the target pack before building/deploying, ensuring all existing custom songs in that pack are included in the deployment scope.

## v0.5335 (2026-09-14)
### Fixed
- **Artist name restored for entire pack when clearing single song** — `--clear-target-song` now only restores artist metadata when NO custom songs remain in the pack. If other custom songs exist, artist metadata stays blanked (as intended for partial custom packs).
- **Second song overwrites first song's custom beatmap modes** — Added incremental pack bundle patching: when deploying a song to a pack that already has a patched bundle on PS4, the pipeline now downloads the existing patched bundle and uses it as the base for adding the new song's mode sets. This preserves previously-deployed custom songs' beatmap mode configurations.

### Added
- `_download_pack_bundle_from_ps4()` helper: downloads the current patched pack bundle from PS4 AFR directory for use as patch base.
- `deploy_pack_bundle()` now threads the downloaded existing bundle to `build_pack_mode_bundles` for incremental patching.

### Changed
- `--clear-target-song` logic: artist metadata is only restored when NO custom songs remain in the pack after the clear operation.

## v0.5334 (2026-09-14)
### Added
- **Surgical pack bundle patching for single-song deploys:** `--deploy-full` now passes `enable_modes` (non-Standard modes for the custom song) and `target_slots` (only the target song slot) to the pack bundle builder. The pack bundle is built with extra preview mode sets ONLY for the custom song being deployed. Stock songs in the same pack keep only Standard — no crashes when selecting non-Standard modes on unmodified songs.
- **Runtime feature flag `enable_beatmap_mode_mapping`** (in `features.json`): Gates visibility of extra mode sets in the mode selector UI. OFF (default when missing) = all songs show only Standard (safe for partial deploys). ON = custom songs with patched mode sets show all 4 modes; stock songs show only Standard.
- **`--clear-target-song <SLOT>` parameter:** Reverts a single custom song slot to its stock state without a full PS4 clean slate. Removes the custom song bundle from PS4 AFR, the redirect entry from `redirects.json`, and the song/artist metadata from `song_metadata.json`. Deploys updated configs to PS4. Useful for testing different custom songs in the same slot, debugging, or partial rollback.
- **Pipeline version bump** to v0.5334.

### Changed
- `build_pack_mode_bundles.py`: `build_modes_blob()`, `patch_pack_bundle()`, and `build_pack_mode_bundles()` now accept `enable_modes` and `target_slots` parameters.
- `full_custom_song_pipeline.py`: Single-song deploy scoping now threads `enable_modes` and `target_slots` through `deploy_pack_bundle()` → `deploy_pack_modes()` → `_ensure_pack_mode_bundles()`.
- `DEFAULT_FEATURES` now includes `enable_beatmap_mode_mapping: true` (default ON in pipeline, default OFF in plugin when file missing — safe for partial deploys).

### Tests
- Updated `TestDefaultFeaturesRuntimeOnly` to expect the new flag.
- Updated `TestFeatureFlagGating` to verify the plugin parses the new flag.
- All 581 tests pass.

## v0.5333 (2026-09-10)
### Fixed
- **Post-deploy validation was checking ALL 4 configured packs instead of just the single deployed pack (Exp 214 follow-up).** After the Exp 214 fix for `--download-beat-saver-song` ordering, a fresh single-song `--deploy-full` run correctly deployed only the billieeilish pack, but `verify_ps4_deployment()` still iterated all 4 `pack_modes.packs` and reported spurious "MISSING" / "BROKEN" errors for the 3 undeployed packs.
- Fixed `verify_ps4_deployment()` to accept and thread the `packs` filter through all internal helpers (`_get_remote_pack_paths`, `_get_pack_bundle_redirects`, `_get_pack_modes_entries`), so validation scopes to exactly the deployed pack(s). Also fixed size-check priority to prefer fresh `custom_songs/` builds over stale `mass_bundles/` for song bundles.
- Validation now correctly PASSES for a clean single-song deploy.

## v0.5332 (2026-09-08)
### Fixed
- **`--deploy-full --download-beat-saver-song <id> --target <slot>` silently failed to download/convert the song (Exp 214).** Root cause: the BeatSaver auto-download that populates `args.song_dir` ran *after* the `plugin-only` early-exit guard inside `main()`. A `--deploy-full` run sets `deploy_plugin=True`, so the guard `if args.deploy_plugin and not args.song_dir:` fired with `song_dir` still `None`, routed the whole run through "plugin-only mode" — which attempted to `put` a never-built `beat_saber_deluxe.prx` (the mangled `/wat_saber_deluxe.prx`  "No such file or directory" error) and regenerated all 43 unscoped redirects with `target_name=None` — then `sys.exit(0)` before ever downloading the song or building/converting anything.
- Moved the `--download-beat-saver-song` → `args.song_dir` resolution to the top of `main()` (immediately after config load, before the `features-only` / `plugin-only` / deploy-only / toggle early-exit guards), so a single-song `--deploy-full` now correctly reaches the song-processing path (audio convert → beatmaps → mode generation → BeatmapLevelSO metadata → bundle → build+deploy plugin → scoped single-pack deploy). Added regression tests (`TestDeployFullDownloadsSong`) guarding the ordering invariant.

## v0.5331 (2026-09-08)
### Added
- **Self-contained single-song `--deploy-full`.** The core deployment function now (for a single `--target` song from BeatSaver) redeploys a mutually-consistent single-song set:
  - deploys ONLY the target song's bundle,
  - deploys ONLY that song's music-pack mode bundle (`_resolve_target_pack` maps `--target` → pack via `beat_saber_song_ids.json`) + a matching single-pack merged catalog,
  - builds + deploys the GoldHEN plugin **and** ensures the `plugins.ini` entry (this is now implied by `--deploy-full` / new `--deploy-plugin`),
  - deploys `features.json` (new implied `--deploy-features` / explicit flag),
  - generates redirects scoped to just that song + pack pair (new `packs`/`slots` filters threaded through `_get_pack_modes_entries`, `_get_pack_modes_redirects`, `_get_pack_bundle_redirects`, `_ensure_pack_bundle_redirects`, `_ensure_mass_song_redirects`, `_regenerate_merged_catalog`, `deploy_pack_modes`, `deploy_pack_bundle`, `_get_remote_pack_paths`, `manage_redirect_config`).
- **Root cause of "it deploys all the other packs":** the old single-song path called `deploy_pack_bundle()`/`manage_redirect_config()` with no pack scope, which re-deployed ALL 4 configured packs + 43 redirects on every song. Now a `--target` scopes deployment to that song's pack and that song slot, so only the target song's content is touched. Full-fleet behavior (all packs) is preserved when no `--target` is used.
- **New flag `--deploy-features`** (implied by `--deploy-full`): deploy the local `features.json` to the PS4.

### Changed
- `--deploy-full` now also implies `--deploy-plugin` + `--deploy-features` (plugin build + upload + plugins.ini entry + features.json deploy). Plugin version unchanged.

## v0.5330 (2026-09-07)
### Added
- **Backup utility now manages the LOCAL pipeline state cache files** (`song_metadata.json`, `redirects.json`, `catalog_pack_modes.json` at the project root). Previously a PS4 `--clean-ps4` cleared the console but left these local caches, so the next single-song deploy re-read the previous full loadout and re-deployed all old bundles. `backup-beat-saber-deluxe-files.py` now:
  - **Backup:** copies these files into the backup under `pipeline_state/`.
  - **Clean:** calls `clear_local_pipeline_state()` to remove them so the pipeline treats the PS4 as fresh (a single custom-song install no longer drags in the full 38-song set).
  - **Restore:** calls `restore_local_pipeline_state()` to put the files back so future pipeline ops understand what was restored.
- **Audit note:** the other local files (`*_2pack.json`, `*_onepack.json`, `*_test_*.json`, `catalog_test.json`, `mass_bundles/*.bundle`) are NOT loaded by the pipeline deployment flow, so they don't force a full redeploy. `mass_bundles/` bundles are only uploaded via explicit `--deploy-mass-bundles`.

### Changed
- Pipeline version bumped 0.5329 → 0.5330.

## v0.5329 (2026-09-05)
### Added
- **Backup utility + exercise scripts with plugins.ini integration (Exp 210):** Created `backup-beat-saber-deluxe-files.py` with backup/clean/restore/list commands for PS4 GoldHEN filesystem via FTP. Updated `exercise-bsd-backup.sh` to exercise all 4 workflows against actual PS4 connection. All 4 exercises now succeed with real content transfer (afr.prx, AFR/CUSA12878, AFR/test, AFR/bs_log — 22 files each).
- **plugins.ini management:** Backup now downloads `/data/GoldHEN/plugins.ini`; clean safely removes the `[CUSA12878]` section containing `beat_saber_deluxe.prx` entry (prevents "data corrupted" error on game launch) while preserving all other plugin entries; restore restores plugins.ini; validate checks for BSD entry.
- **Exercise script validation:** All 4 exercises now validate plugins.ini in outputs.
- **Full cycle test verified:** Original backup (ps4_backup_20260904_120701, 60 bundle files) → Exercise 1 restore 60 files → Exercise 2 backup 3 items (22 files each) → Exercise 3 backup+clean 3 items, AFR/CUSA12878 removed from PS4, BSD entry removed from plugins.ini → Exercise 4 restore 66 files (22+22+22).

### Changed
- Pipeline version bumped 0.5328 → 0.5329.

## v0.5328 (2026-08-26)
### Fixed
- **Camellia-pack custom songs crash at gameplay load (CE-34878-0, Exp 200):** the 6 Chromeo slots' beatmaps came from the V4→V3.2.0 PS4-bundle reconstruction and were (a) MINIMAL-schema — missing `basicBeatmapEvents`, `waypoints`, `lightColorEventBoxGroups`, `lightRotationEventBoxGroups`, `lightTranslationEventBoxGroups`, `useNormalEventsAsCompatibleEvents`, `customData` that every hardware-proven-good map carries, and (b) three slots had ZERO-NOTE Easy difficulties (`cyclehit`/`exitthisearthsatomosphere`/`lightitup` decoded empty). User boot test: RS/lizzo/billieeilish customs all played fine; Chromeo selection crashed before environment/audio loads.
- **Fix A — full-schema normalization at injection:** new `normalize_v3_schema()` fills every missing V3 array/field with game-standard defaults; wired into BOTH injection paths (`replace_beatmaps` for Standard diffs + mode-beatmap injection). Idempotent, preserves existing content.
- **Fix B — empty-difficulty rescue:** new `_find_populated_beatmap()` finds a populated Standard donor (preference Normal > Hard > Expert > ExpertPlus > Easy; accepts both `Normal.dat` and `NormalStandard.dat` naming) and clones its playable content into empty difficulties so no slot ships an unplayable map. Note: rescued Easy maps now carry the donor difficulty's note content (documented trade-off vs a crashing/empty slot).
### Tests
- 9 new tests incl. a regression test against the actual Roni backout sources (empty-Easy rescue + Hard schema normalization). Suite: 571 passing.

## v0.5327 (2026-08-25)
### Changed
- **`mass_deploy.bundle_dir` moved from ephemeral `/tmp/opencode/mass_build` to the stable committed path `/workspace/beat_saber_deluxe/mass_bundles`** (default config + `deploy_mass_bundles` fallback + `verify_ps4_deployment` size-check source). A fresh container/PS4 can now reproduce the full loadout without any /tmp state.
- `development/scripts/build_deploy_all38.py` rewritten as build-all → deploy-once: PHASE 1 runs the per-song pipeline for all 38 slots (no `--deploy`) writing `mass_bundles/<slot>_v3.bundle`; PHASE 2 is a single `--deploy-mass-bundles --deploy-pack-modes --deploy-config --verify-ps4` invocation. Previously every per-song run re-uploaded all pack bundles + catalog (38× redundant) and redeployed redirects mid-batch. Unresolved sources now ABORT before building anything instead of silently skipping. Source resolution covers `songs/chromeo_backout/` and fixes the 2BeLoved metadata-key match (`2 Be Loved (Am I Ready)`). Chromeo backout dirs carry pre-extracted FSB5 audio only — the script now passes `--audio <dir>/audio.fsb` when present (their dirs have no .wav/.ogg for auto-discovery; this was previously a manual flag).
### Fixed
- `--verify-ps4` redirect size check looked in `/tmp/opencode/mass_build` for song bundles; now reads `mass_deploy.bundle_dir` from config.

## v0.5326 (2026-08-25)
### Fixed
- **REVERTS the v0.5325 pathID change — it was the boot-crash, not the fix (Exp 198).** Hardware evidence: the RS bundle the user successfully played all 4 modes on uses DISTINCT characteristic pathIDs per preview set (Standard/OneSaber/NoArrows/90Degree = `CHAR_PATH_IDS[mode]`, even though NoArrows/90Degree have no BeatmapData asset in the pack — the game never resolves them there). The v0.5325 change pointed all four sets at Standard's pathID instead; that structure (4 identical PPtrs) crashes the game at menu init with CE-34878-0 the moment the song-select UI builds the mode list for a redirected pack (reproduced with lizzo-only config, `v0.5325_lizzofix_stage1_boot_crash.txt`). `build_modes_blob()` now appends new mode entries with their OWN `CHAR_PATH_IDS[mode]` again.
- **Kept the v0.5325 rank-dedup padding improvement:** short existing sets (< 5 difficulties) are padded to 5 by copying only template records whose difficulty rank isn't already present (no duplicate ranks), falling back to plain padding only if the template runs out.
- Tests updated to pin the hardware-proven invariant: every patched SO has exactly 4 sets, all pathIDs distinct and equal to `CHAR_PATH_IDS[mode]` for the four target modes, and every set's difficulty ranks are exactly `[0,1,2,3,4]`. New regression test `test_new_mode_entries_use_own_pathids_and_clean_ranks`.
- Reference artifact preserved: `development/reference_bundles/therollingstones_WORKING_v0.5324era_aug20.bundle` (md5 `5ed23829…`) — the hardware-validated structure, with README documenting the extracted layout.
### Changed
- Pipeline version bumped 0.5325 → 0.5326.

## v0.5325 (2026-08-25)
### Fixed
- **No Arrows / 90° gameplay crash: `build_modes_blob()` used target mode's pathID instead of Standard's pathID for cloned entries.** When a pack had songs with pre-existing non-Standard modes (e.g., lizzo with Standard+OneSaber), the function created new mode entries (NoArrows, 90°) using their OWN characteristic pathIDs (e.g., NoArrows `-8583864861369561029`). But BeatmapLevelsData files only contain BeatmapData assets for modes present in the ORIGINAL pack blob — so the game couldn't find the NoArrows/90° assets and crashed (CE-34878-0). therollingstones worked because ALL its songs were Standard-only, so all cloned entries used Standard's pathID. Fix: new mode entries now use `std_path_id` (Standard's pathID from the existing dict) instead of `CHAR_PATH_IDS[mode]`. Updated tests to match new behavior (new entries share Standard's pathID; pre-existing entries keep theirs).
### Changed
- Pipeline version bumped 0.5324 → 0.5325.

## v0.5324 (2026-08-22)
### Fixed
- **Stale pack redirects survive when packs are removed from `pack_modes.packs` — caused CE-34878-0 crash on 4-pack deploy.** `_ensure_pack_bundle_redirects()` only added/updated pack redirects, never removed them. When the config had 4 packs, all 4 pack redirects were written to `redirects.json`. Then removing packs from the config left stale redirects pointing at patched bundles whose catalog entries no longer had matching CRCs — the game loaded the patched bundles, validated CRCs against the catalog, and crashed. Added stale pack redirect removal: any `assets_all_*_pack_*.bundle` redirect not in the current config's pack list is now deleted on every `manage_redirect_config` pass.
### Changed
- Pipeline version bumped 0.5323 → 0.5324.

## v0.5323 (2026-08-16)
### Fixed
- **OneSaber mode was unplayable: the procedural generator forced every note to the LEFT (red) saber.** `_generate_one_saber` used `_ONE_SABER_COLOR = 0` (red), but OneSaber is played exclusively with the RIGHT (blue) saber — so every generated OneSaber note was the wrong color and could not be hit by the (only) right saber. Confirmed by real in-headset play: 90° and No-Arrows were fun, OneSaber was broken (all red notes). Flipped `_ONE_SABER_COLOR = 1` (RIGHT/BLUE) so OneSaber notes are now blue in V2 (`_type = 1`) and V3 (`c = 1` / `a = 1`).
- **Regenerated all buggy OneSaber beatmaps from their Standard sources** via the new `development/scripts/regenerate_onesaber_blue.py`. 33 red OneSaber `.dat` files were regenerated to blue; the 12–15 already-blue (correct, incl. mapper-authored) OneSaber maps were left untouched. Final verified state: 0 red OneSaber files across `beat-saber-ps4-custom-songs/songs/`, all remaining maps blue (or empty). Note: a plain pipeline re-run does NOT fix already-generated red files (generator skips songs that already ship their own `<Diff>OneSaber.dat`) — force-regeneration is required.
### Changed
- Pipeline version bumped 0.5322 → 0.5323.

## v0.5322 (2026-08-16)
### Fixed
- **"Beat Saber still crashes" after the v0.5320 dataIndex fix (Exp 191): the fixed catalog was never deployed.** The v0.5320/v0.5321 pipeline changes were all local — the PS4 still ran the broken v0.5319 `catalog_pack_modes.json` (70/2251 invalid entry dataIndexes, md5 `0eb8a27d…`), so every launch crashed right after the `aa/catalog.json` redirect (OPEN #58/#74) exactly as before. Downloaded the fresh crash log (`.ai_memory/experiment_logs/v0.5321_crash_after_redeploy.txt`), diffed the deployed catalog against the local fixed one (same byte size 795,783 — so size-only checks can never catch this), confirmed the deployed file was the stale broken build, then deployed the fixed catalog (md5 `975bacca…`, 0 invalid) and re-validated on-device.
- **`--verify-ps4` could not catch a stale catalog (root cause of "didn't notice the fix never deployed"):** size checks pass because the broken and fixed catalogs are byte-identical in size. Added check #7 to `verify_ps4_deployment()` that downloads the deployed `catalog_pack_modes.json` and (a) validates every `m_EntryDataString` dataIndex points at a type-7 block start via the new `validate_catalog_dataindexes()`, (b) compares the deployed md5 against the local build output, and (c) verifies every configured pack's catalog block carries the patched `m_Crc`/`m_BundleSize` via the new `validate_catalog_entries()`. A stale catalog now fails the post-deploy validation loudly instead of passing silently.
### Changed
- **Removed the legacy `pack_bundle` single-pack prototype from the DEFAULT config** (`startmeup_pack_modes.bundle` / `catalog_startmeup_modes.json`). It was fully superseded by the generalized `pack_modes` block (the rollingstones pack is in `pack_modes.packs`), its deployed files were cleaned off the PS4, and keeping it made `--verify-ps4` report phantom "MISSING on PS4" entries for the deleted prototype. The `pack_bundle` code path remains supported for configs that still define it (covered by existing tests); the default no longer does.
- Added `validate_catalog_dataindexes()`, `find_catalog_entry_js()`, `validate_catalog_entries()` to `tools/build_pack_mode_bundles.py` as reusable catalog-integrity helpers (byte-wise type-7 block walk — never whole-string UTF-16 alignment).
- Cleaned up stale experiment files on the PS4: deleted `catalog_startmeup_modes.json` and `startmeup_pack_modes.bundle` (legacy prototype, unreferenced by the 43-entry redirects.json).
- Pipeline version bumped 0.5321 → 0.5322.

## v0.5321 (2026-08-15)
### Fixed
- **Reproducibility: `build_pack_mode_bundles.py` kept a leftover `"360Degree"` entry in `CHAR_PATH_IDS`** (pid `4533580413116749821`) from before the Exp 175 360Degree purge. Because `build_modes_blob` extends *any* set whose pid is in `CHAR_PATH_IDS.values()` to `TARGET_DIFFS`, the production module padded the (PS4-unsupported, selector-hidden) 360Degree preview set 1→5 diffs (+144 B per patched blob) for every pack that ships one — producing bundles that did **not** byte-match the committed dev-built artifacts for 10/36 packs (ostvol1, ostvol2, ostvol3, extras, greenday, imaginedragons, monstercat, panicatthedisco, rocketleague, timbaland). Removed the stale entry; the module now reproduces all 36 committed bundles byte-identically (verified full rebuild, 0/36 mismatches). Regression test added (`test_unsupported_360degree_set_not_extended`).
### Changed
- Pipeline version bumped 0.5320 → 0.5321.

## v0.5320 (2026-08-15)
### Fixed
- **PS4 launch crash after pack_modes deploy (Exp 188 follow-up): entry dataIndexes in the merged catalog were stale.** `m_EntryDataString` is a binary array of 28-byte records whose 5th int32 (`rec[4]`) is a byte offset into `m_ExtraDataString` pointing at the start (type byte) of each per-entry block. When a patched block's JSON grows or shrinks (e.g. lizzo's `m_Crc` went 7 → 10 digits, +6 bytes), every later block shifts, so every entry dataIndex pointing *past* the patched block MUST be shifted by the same delta — otherwise the game reads garbage and crashes right after loading the catalog (v0.5319 PS4 crash at OPEN #74). `update_catalog_entry()` now rewrites `m_EntryDataString` shifting all affected dataIndexes whenever a block's byte length changes. 70 of 2251 entries were invalid before the fix (all after the lizzo block); 0 after.
- **`_parse_catalog_block()` token-split fragility:** `m_Crc`/`m_BundleSize` were extracted by splitting the block on `,` and taking the text after `:`. If a field is the last one in the JSON, the token includes the trailing `}` and the value-replace would strip the block's closing brace, corrupting the JSON. Now parsed with regex (`"m_Crc":\s*(\d+)`), robust to field order.
### Changed
- **Pack-mode tests are now fully config-driven — no hardcoded packs.** Real-artifact tests (`TestPackModesRealArtifacts`) derive the pack list from the live pipeline config (`cfg['pack_modes']['packs']`) and the build manifest, so they validate whatever subset of the 36 DLC packs a user configures, not the 4 defaulting packs. Synthetic fixture data was renamed to clearly-fake `demopacka`/`demopackb` so no test couples to real pack names. Added 5 regression tests (dataIndex shifting for single/multiple growing blocks, size growth, plus a real-artifact merge test asserting every dataIndex lands on a type-7 block start).
- Merged catalog regenerated from origin via `_regenerate_merged_catalog()` with the fixes (0 invalid dataIndexes, all 4 pack CRCs/sizes match the manifest).

## v0.5319 (2026-08-14)
### Added
- **Generalized pack patch (Exp 188): ALL DLC packs get 4 preview mode sets (Standard/OneSaber/NoArrows/90Degree) × 5 difficulties**, superseding the single-pack rollingstones prototype. New production module `tools/build_pack_mode_bundles.py` patches every replaced BeatmapLevelSO in a pack bundle (extending short mode sets to 5 diffs, cloning missing modes from Standard, preserving existing records byte-for-byte), rebuilds the UnityFS/LZ4 bundle with a corrected object table, and regenerates the Addressables catalog entry (`m_Crc` = crc32 of the *decompressed* stream + `m_BundleSize`) into a single **merged catalog** (`catalog_pack_modes.json`) built from the ORIGIN catalog.
- **`pack_modes` config block** (`packs`, `build_dir`, `song_ids_path`, `dump_dir`, shared `catalog_key`/`patched_catalog`) defaulting to the 4 packs already verified on-device: therollingstones, billieeilish, lizzo, camellia.
- **`_ensure_pack_mode_bundles()`** — builds any configured pack whose patched bundle is missing (skip-if-no-change), and regenerates the merged catalog to exactly match the current redirect set. **`--build-pack-modes`**, **`--force-pack-modes`**, **`--pack-modes-packs`**, **`--deploy-pack-modes`** CLI flags.
- **`adopt_pack_modes_manifest.py`** dev script — one-time adoption of the 36 bundles built by the old dev tooling into the production manifest (`pack_modes_bundles/manifest.json`, records per-pack size + dec-stream CRC + catalog bundle name) so the pipeline treats them as already-built.
- **Single source of truth for redirects:** `_get_pack_bundle_redirects()` now merges the single-pack prototype pair FIRST and the `pack_modes` redirects LAST, so pack_modes override the rollingstones/startmeup prototype (merged catalog carries the rollingstones entry too). Redirects for a pack are only emitted once its patched bundle exists locally, and the shared `aa/catalog.json` redirect only once the merged catalog exists — the pipeline never points a redirect at a file that isn't ready (Exp 180 crash rule).
- Tests: `tests/test_pack_mode_bundles.py` (21 tests) — synthetic-blob mode expansion, byte-wise catalog entry updates, deterministic entries/redirects, override semantics, and real-artifact CRC/size verification of the merged catalog against the built bundles. Full suite 440/440 pass.

### Fixed
- **Catalog `m_ExtraDataString` updates now walk the binary block structure byte-wise** instead of substring-searching a whole-string UTF-16 decode. The concatenated per-entry blocks (type byte + 1-byte-len assembly/class names + 4-byte JS length + UTF-16-LE JSON) can start at odd byte offsets, so a whole-buffer decode misaligns some blocks and the marker becomes unfindable — camellia's entry failed this way. `update_catalog_entry()` now parses each block (as the scan does), patches only the matching block's JSON in place, and resizes the length field when the digit count changes.
- **Object-table rebuild logic bugs in the pack patcher** (from `development/scripts/build_all_pack_modes.py`, now fixed in the production module): (1) cumulative offset deltas applied in a single pass (each object's stored offset shifts by the sum of deltas of patches *starting before it*; a patched blob's own offset is unchanged), (2) a patched blob's `byte_start` is no longer shifted by its own delta — only its size field updates, (3) the mode-set extension now checks `pid in CHAR_PATH_IDS.values()` (keys are mode names).

### Changed
- **Deploy ordering (Exp 188):** patched pack bundles + catalogs are deployed BEFORE `redirects.json` is generated (Step 9a before Step 9), so `pack_modes` redirects — which are only emitted for packs whose bundles exist locally — are picked up by redirect generation, and the redirected files are already on the PS4 when the game boots.
- `deploy_pack_bundle()` now also builds-if-missing + deploys `pack_modes` when configured; `verify_ps4_deployment()` steps 4–5 validate every pack redirect + the shared catalog redirect pair, not just the single-pack pair.

## v0.5318 (2026-08-13)
### Fixed
- **Redirect VALUES must match the exact deployed bundle filename (Exp 187).** The game opens the redirect VALUE verbatim and `open()` is case-sensitive, so a value like `Crystallized_v3` silently keeps serving the stale Jul/Aug build while the freshly mass-deployed bundle sits on the PS4 as `crystallized_v3.bundle`. The Aug-13 redeploy uploaded all 38 new bundles correctly, but the generated `redirects.json` still pointed at old `_v3` names (and titlecase Camellia names) — the game would never have loaded the new builds. The pipeline now has a single source of truth for deployed bundle naming: `_deployed_bundle_name()` builds `{slot}{afr_target_suffix}` using the canonical slot casing from `mass_deploy.slots`, and `_ensure_mass_song_redirects()` (run on every config save, like the pack/catalog pair) rewrites every per-song value to that exact filename, preserving known-good keys while healing stale values. Default `afr_target_suffix` is now `_v3.bundle` (was `_v3`) so single-song deploys, mass deploys, and redirect values all converge on the same filenames.
- **`deploy_mass_bundles` / `deploy_to_ps4` now upload under the exact filename the redirect will reference** (local file basename), so a future rename can never split "what's deployed" from "what the redirects point at".
### Changed
- `manage_redirect_config()` dropped its `bundle_suffix` parameter — target entries use `_deployed_bundle_name()` (canonical slot casing + suffix) instead of the caller-provided suffix string, eliminating the class of bug where the suffix used for uploading and the suffix used for redirects diverged.
### Added
- Regression tests: `TestDeployedBundleNaming` (6 tests) — slot-casing canonicalization, stale `_v3`/titlecase value healing, missing-slot insertion, default suffix fallback. Full suite 419/419 pass.

## v0.5317 (2026-08-13)
### Fixed
- **PS4 crash at boot when the pack bundle is redirected without the catalog (Exp 180 root cause).** Unity validates a bundle against the `m_Crc` in `aa/catalog.json` at load time (crc32 of the *decompressed* stream, Exp 179). The patched pack bundle (`startmeup_pack_modes.bundle`) has a different dec-stream CRC than the original, so serving it against the ORIGINAL catalog → CRC mismatch → crash during the pack scan (observed: died at ~[OPEN #591] with a 39-redirect config that dropped `aa/catalog.json` and pointed the pack at the stale `rollingstones_pack_patched.bundle`).
- **The pipeline now enforces the pack bundle + catalog redirect pair on every config save.** `manage_redirect_config` always calls `_ensure_pack_bundle_redirects()`, which (a) (re)inserts `aa/catalog.json -> catalog_startmeup_modes.json` and `therollingstones_pack_assets_all_*.bundle -> startmeup_pack_modes.bundle`, and (b) removes stale truncated-key variants that could shadow the canonical entry via the plugin's substring matching. A regenerated/synced/enforced `redirects.json` can no longer silently lose the pair that causes the boot crash. Regression tests: `TestPackBundleRedirectConsistency` (6 tests).
### Added
- **`--deploy-pack-bundle`** — uploads the patched pack bundle + patched `catalog_startmeup_modes.json` to the PS4 (both files must exist before `redirects.json` references them).
- **`--deploy-mass-bundles`** — deploys all custom song bundles from `mass_deploy.bundle_dir` (38 slots) to the PS4; replaces the manual `deploy_all38.sh` loop.
- **`--verify-ps4`** — post-deploy self-validation that reports PASS/FAIL for: PS4 reachability, deployed `redirects.json` matching local, every redirect target existing on the PS4, the pack bundle + catalog files present, the pack+catalog redirect pair intact, and redirect target sizes matching local files. **Auto-runs after any `--deploy*` invocation** (opt out with `--no-verify-ps4`), so a broken deploy is caught immediately instead of on the next console boot.
- **`mass_deploy` + `pack_bundle` config defaults** in `load_config` so the pipeline is all-inclusive with zero manual config steps.
### Changed
- `--deploy-mass-bundles`/`--deploy-pack-bundle`/`--verify-ps4` are usable standalone (no `--song-dir`) and automatically regenerate + deploy a consistent `redirects.json` first.

## v0.5316 (2026-08-12)
### Fixed
- **Mode generators crash on V3 beatmaps with omitted position fields.** Some BeatSaver sources (e.g. "Take Me to the Beach" for the `livebythesword` / `IDidntChangeMyNumber` slots) ship V3 notes with `y` (and sometimes `b`) omitted — valid per the V3 spec, where omitted fields default to 0. The OneSaber generator indexed `n["y"]`/`n["x"]` directly → `KeyError: 'y'`; the 90Degree generator indexed `n["b"]`/`obs["b"]`/`ev["b"]` directly. All generator field reads now use `.get(..., 0)` defaults for V3, matching the V2 branch. Regression tests: `test_v3_omitted_position_fields_default_to_zero` (OneSaber + NoArrows) and `test_v3_omitted_fields_in_90_degree`.

## v0.5315 (2026-08-11)
### Fixed
- **Idempotency bug in mode mapping:** re-running the pipeline on a source dir that already contains generated mode `.dat` files (e.g. a prior run's output, or hand-authored modes) silently skipped TextAsset injection and fell back to cloning Standard references — producing a *different, degraded* bundle than the first build. `apply_mode_mapping()` gated injection on `song_dir AND non-empty generated_files`, but `add_mode_characteristics()` already scans `song_dir` for ALL mode files (pre-existing included). The gate now only requires `song_dir`, so a rebuild of a previously-built song dir yields a byte-equivalent, fully-populated bundle. Regression test: `test_idempotent_injection_with_pre_existing_mode_files`.
- Tests: full suite pass (405/405; +1 idempotency regression).

## v0.5314 (2026-08-11)
### Changed
- **Safe-by-default pipeline — standard command now bakes in the previously-required flags.** PCM16 + no-pad are now the DEFAULT audio settings, beatmap mode mapping + generation is ON by default, and V2→V3 conversion is ON by default. A plain `--song-dir X --target Y` build now produces a full-length, lossless, all-modes-populated bundle — no partial songs from a forgotten flag.
- **Each new default has an oppose flag** (per project rule: any changed default needs a way to opt out):
  - `--hevag` / `--vorbis` — opt out of the PCM16 default codec.
  - `--pad-fsb5` — restore the old 12MB truncating padding (DANGER: produces partial songs; kept only for the rare case a slot needs exact-size resources).
  - `--disable-beatmap-mode-mapping` — Standard-only bundle (opposes the new default).
  - `--skip-mode-generation` — keep mode mapping but do not generate missing mode beatmaps.
  - `--no-convert-to-v3` — leave V2 beatmaps unconverted (opposes the new default).
  - The old flags (`--pcm16`, `--no-pad`, `--enable-beatmap-mode-mapping`, `--convert-to-v3`) are kept for backward compatibility and now match the defaults.
- **`--features-only` standalone mode added:** apply `--set-feature key=value` changes and deploy `features.json` to PS4, then exit — no song processing, no plugin rebuild, no redirects. Audit found no standalone features-only mode previously existed; `--set-feature` only ran via `--deploy-plugin` or as a step of a full song build.
- **`enable_beatmap_mode_mapping` removed from `features.json` / `DEFAULT_FEATURES`.** Mode mapping is a build-time pipeline feature (baked into the bundle), not a runtime plugin toggle — the v0.8040 plugin never parsed it. `features.json` now holds exactly the runtime flags the plugin reads at startup (`enable_custom_song_replacements`, `enable_song_metadata_modification`), so every flag in the file is handled the same way: read at runtime from the PS4 JSON, redeployable via `--features-only`.
- Flag resolution moved to testable pure helpers: `resolve_audio_codec()`, `resolve_pad_to_size()`, `resolve_mode_mapping()`, `resolve_convert_to_v3()`.
- Tests: +17 (default behavior resolution + runtime-only feature flags). Full suite 404/404 pass.

## v0.5313 (2026-08-10)
### Fixed
- **90° rotation events now survive V2→V3 conversion (source song's 90Degree Expert keeps its lane changes):** `convert_v2_to_v3()` no longer hardcodes `"rotationEvents": []`. V2 spawn-rotation events (types 14/early, 15/late) are converted to V3 `rotationEvents` (`e` 0/1) with the authoritative BSMG value table → signed degrees: `0=-60, 1=-45, 2=-30, 3=-15, 4=+15, 5=+30, 6=+45, 7=+60`. Values are relative deltas the game accumulates. Laser-speed events (types 12/13) correctly remain basic events.
- **V3 basic event type field corrected `t` → `et`:** The game's `BeatmapSaveDataVersion3.BasicEventData` serializes the event type as `et` (confirmed from the PS4 il2cpp dump). The converter previously wrote `t`, so every lighting event deserialized as type 0 (BackLasers). Lighting now uses its real event types.
- **`_generate_90_degree()` rewritten with correct 90° gameplay semantics** (previously swung the lane ±90° every cycle — perpendicular to the player and disorienting):
  - 90° mode confines the playfield to a 90° arc centered on the player's forward lane: positions 0° (center), ±15°, ±30°, ±45° (3 lanes left + 3 right).
  - One `rotationEvents` entry per `cycle_beats` (default 8.0), each moving a single 15° lane in the current sweep direction; the sweep starts at the center lane and reverses only after reaching a ±45° extreme — it never skips lanes or jumps the center.
  - Uses `e: 1` (late rotation) per BSMG best practice (chevron guides the player after the block hit).
  - Constants renamed: `_ROTATION_DEGREES` → `_ROTATION_STEP_DEGREES` (15) + `_ROTATION_MAX_DEGREES` (45).
- **Spec verified against two ground truths:** (1) BSMG wiki Extended Mapping / Map Format pages; (2) the community 90° map `Drop Pop Candy 90DegreeExpert.dat`, whose 340 rotation events (values 3/4 = ±15°, a few 2/5 = ±30°) accumulate to exactly [-45°, +45°] — confirming relative-delta semantics and the 90°-mode arc limit. The user's observed behavior (old generator alternating +90/-90 produced "center ↔ perpendicular" switching) independently confirms V3 `r` accumulates.

## v0.5312 (2026-08-09)
### Fixed
- **Characteristic path IDs corrected repo-wide (90Degree mode selector now enabled):** The BeatmapCharacteristicSO pathIDs were mislabeled in `_CHAR_PATH_IDS` / `CHAR_PATH_IDS` across `tools/full_custom_song_pipeline.py`, `tools/build_patched_pack_bundle.py`, `tools/build_per_song_metadata.py`, `tools/build_replacement_pack*.py`, `tools/inject_pack_bundle.py`, `tools/patch_pack_bundle.py`, and the `development/scripts/build_espresso*` dev scripts. Verified against the real BeatmapCharacteristicSO objects in `sharedassets_assets_all_068cd59e9a6fba13da706dc9269bf759.bundle` (CAB `cb38b3e2985c65d4cf8a63437da74a89`):
  - Standard `-7286399427822119286` (unchanged)
  - OneSaber/OneColor `-5623662769225589684` (was NoArrows)
  - NoArrows `-8583864861369561029` (was OneSaber)
  - 90Degree `-5995858427784384822` (was 360Degree's `4533580413116749821`)
  - 360Degree `4533580413116749821`
  - **Why it matters:** the 90Degree slot previously pointed at the 360Degree characteristic (`requires360=1`), so the game hid the selector button — 90Degree was never visible. The OneSaber/NoArrows swap was cosmetic (each PID drives its own button AND gameplay lookup) but is now also corrected for clarity.
- **Pack bundle rebuilt & redeployed:** `startmeup_pack_modes.bundle` now has all 4 preview sets pointing at the correct characteristics (Standard/OneSaber/NoArrows/90Degree); `catalog_startmeup_modes.json` regenerated with the new dec-stream CRC (0xe9e40bd3 → `3924036563`) and size (7,905,425 B). Deployed to PS4, `bs_log.txt` cleared.

## v0.5311 (2026-08-09)
### Changed
- **Test template shrunk 12 MB → 2.9 KB (no audio):** Added `development/scripts/build_test_template.py` which regenerates `tests/test_data/template_standard.bundle` from any per-song bundle. The template now contains ONLY a Standard-only BeatmapLevel + its 5 beatmap TextAssets + lightshow TextAsset + m_Script target — all audio (AudioClip, audio TextAsset, external `.resource` file) is stripped and beatmap/lightshow payloads are replaced with minimal placeholder JSON. This keeps the repo lean and avoids shipping 12 MB of song audio as test fixture.

### Fixed
- **TextAsset binary serialization:** Fixed `_create_text_asset_object()` to use UnityPy's `EndianBinaryWriter.write_aligned_string()` instead of manual `struct.pack`. The previous format added null terminators and used `len+1` for string lengths, which caused `read_typetree()` to fail with "read_str out of bounds" on the PS4 Unity runtime. The correct Unity format is: `int32 length + UTF-8 bytes + 4-byte alignment padding` (no null terminator in length, no null after data).
- **type_id for new TextAsset objects:** Fixed `_create_text_asset_object()` to use the correct type index from `cab.types` instead of hardcoded `type_id=0`. Previously, new objects were assigned `type_id=0` which mapped to MonoScript (class_id 115) instead of TextAsset (class_id 49), causing the game to misinterpret the object type.
- **Mode file matching:** Fixed gen_lookup matching in `add_mode_characteristics()` to handle both prefix (`90DegreeExpert.dat`) and suffix (`Expert90Degree.dat`) naming conventions. Previously, 90Degree Expert and ExpertPlus files with prefix-style naming were not detected, leaving those difficulty slots pointing to Standard beatmaps.
- **generated_files parameter usage:** Fixed `add_mode_characteristics()` to use the `generated_files` parameter in addition to scanning `song_dir`. Previously, generated files passed via the parameter were ignored if they weren't written to disk first.
- **Test fix:** Fixed `TestModeBeatmapInjection.test_injected_beatmaps_reference_new_textassets` to properly handle BundleFile format and save/reload the bundle before verifying typetree changes. Added `test_data/template_standard.bundle` for test isolation.

## v0.5310 (2026-08-07)
- **Beatmap Mode Generators — Fully Implemented (default when `--enable-beatmap-mode-mapping`):**
  - `_generate_no_arrows()` — real implementation, V2/V3-aware: converts every color note to a dot (`_cutDirection`/`d` = 8); bombs untouched.
  - `_generate_one_saber()` — real implementation (replaces placeholder): recolors all notes to a single saber (color 0), removes simultaneous notes (one saber can cut only one note per instant) and same-cell arrowed notes closer than `min_gap` (default 0.25 beats). Never mutates its input.
  - `_generate_90_degree()` — real implementation (replaces placeholder): converts V2 sources to V3, then adds `_rotationEvents` alternating +90/-90 every `cycle_beats` (default 8.0 beats = 2 measures) starting at the first note, swinging the lane back and forth. Never mutates its input.
  - Added `generate_missing_mode_beatmaps(song_dir, detected_modes, enabled_modes, ...)` — gap-filling: for each difficulty with a Standard source, generates `<Diff><Mode>.dat` for every enabled mode the song does NOT already provide (songs' own mode beatmaps are never overwritten).
  - **Integration fix:** mode generation now runs in Step 5a, BEFORE beatmap replacement (previously it ran after `replace_beatmaps` and wrote files too late to be consumed). Generation is the default behavior whenever `--enable-beatmap-mode-mapping` is passed.
  - New CLI flags: `--skip-mode-generation` (opt out), `--one-saber-min-gap` (default 0.25), `--rotation-cycle-beats` (default 8.0).
  - Expanded `tests/test_mode_generators.py` from 3 placeholder assertions to 17 tests (V2+V3, mutation-safety, gap-filling behavior). Full suite: 365 tests pass.

## v0.5309 (2026-08-04)
- **Beatmap Mode Generators (In Progress):**
  - Added procedural beatmap generator logic for `NoArrows` mode (automatically strips direction arrows from Standard beatmaps).
  - Placeholder implementations added for `OneSaber` and `90Degree` generators.
  - Integration: Pipeline now generates missing mode-specific `.dat` files procedurally during bundle construction if they are enabled via flag.

## v0.5308 (2026-08-04)
- **360Degree Mode Purge:**
  - Removed all `360Degree` mode support from pipeline (`full_custom_song_pipeline.py`), tools, and tests as 360° gameplay is physically unsupported on PS4 single-camera ~90° tracking.
  - Restricted supported modes to 4: `Standard`, `OneSaber`, `NoArrows`, `90Degree`.
  - Updated all test suites and pipeline defaults to 4 modes.

## v0.5307 (2026-07-28)
- **Beatmap mode mapping (Phase 1):**
  - Added `detect_song_modes(song_dir)` — auto-detects characteristic modes from beatmap .dat/.json filename patterns. Handles suffix-style (`ExpertPlusOneSaber.dat`), prefix-style (`OneSaberExpert.dat`), bare (`Expert.dat` → Standard), and `.beatmap.dat` variants. Aliases: `SingleSaber`→`OneSaber`, `Lawless`→`NoArrows`, `Legacy`→`Standard`. Excludes `Info.dat`, `BPMInfo.dat`, `Lightshow`, `AudioData`. Returns canonically-ordered difficulty lists per mode.
  - Added `build_mode_mapping(detected_modes, fallback_mode_map)` — resolves the 5 game characteristic slots using detected modes with configurable fallback chain. Default: `360Degree→NoArrows→Standard`, `NoArrows→Standard`, `90Degree→Standard`, `OneSaber→Standard`. Custom overrides via `SRC=DEST` format.
  - Added `apply_mode_mapping(cab, enabled_modes)` — calls existing `add_mode_characteristics()` to inject new mode sets into the per-song bundle's BeatmapLevel.
  - New CLI flags: `--enable-beatmap-mode-mapping`, `--fallback-mode-map SRC=DEST`.
  - Feature flag `enable_beatmap_mode_mapping` added to `DEFAULT_FEATURES` (default `True`) and `features.json`.
  - 22 new unit tests + 4 new integration tests — 361 total.
  - `beat_saber_song_ids.json` enriched with `characteristicModes` field for all 305 songs (94 multi-mode) from bundle scan.

## v0.5306 (2026-07-28)
- **Integration testing:**
  - Expanded `test_integration.py` from 1 test to 34 tests covering: PCM16 FSB5 build, V2→V3 beatmap conversion, beatmap file selection priority, redirect config management, song metadata management, song ID lookup, config loading, and metadata file handling.
  - Fixed 7 pre-existing test failures in `test_pipeline_bugfixes.py::TestManageSongMetadata` — tests updated to match current `manage_song_metadata()` behavior (combined "SongName / Artist" format, original author blanking).
  - Total test suite: 335 tests across 10 files (up from 302).
- **Agent context:**
  - Added `.agent/context.yml` — compact quick-reference file for giving project context to another agent with minimal token usage.
  - Added context.yml update rule to both `CLAUDE.md` and `.opencode/rules.md` (Section 1 item 7, Section 3.1 item F2).
  - Synced missing Section 0 (Rule Synchronization) to `.opencode/rules.md`.

## v0.5305 (2026-07-27)
- **CI/CD Infrastructure:**
  - Fixed failing lint check in CI pipeline. Ruff configuration was using incompatible `--output-format=github` and `--statistics` flags simultaneously. Removed `--statistics` to fix the pipeline error.

## v0.5304 (2026-07-27)
- **Bug fixes:**
  - Fixed `info.dat` case sensitivity — BeatSaver uses lowercase `info.dat`, pipeline now falls back to lowercase when uppercase `Info.dat` is not found. Affects `main()` pre-load, Step 6.5 re-read, and `replace_beatmaps()`.
  - Fixed undefined variables in `main()` — `bpm`, `song_name`, `song_artist`, and `note_count_standard` were referenced before being defined. Now initialized from Info.dat before Step 0.
  - Fixed `manage_song_metadata()` passthrough — When `--song-name`/`--artist` not provided via CLI, resolved values from Info.dat are now passed through to metadata management.
- **Unit testing infrastructure:**
  - Added `run_tests.py` test harness with `--fast`, `--coverage`, `--module`, `--lint`, `--ci` options
  - Added GitHub Actions CI workflow (`.github/workflows/ci.yml`) — runs all tests with coverage on push/PR
  - Added `requirements-test.txt` for CI dependency installation
  - Added 39 new tests in `test_pipeline_bugfixes.py` covering all three bug fixes
  - Fixed broken `test_hevag_audio_compatibility.py` (syntax errors, wrong function names)
  - Updated `pyproject.toml` with ruff linter config and improved coverage settings
- **Test suite:** 301 total tests across 8 test files (up from 262)

## v0.5303 (2026-07-26)
- **Song ID lookup** — Added `_load_song_ids()` and `_lookup_song_name()` functions. Pipeline now resolves slot IDs (e.g., "StartMeUp") to exact game strings via `beat_saber_song_ids.json`. Fixes case sensitivity issues where game uses different casing than expected.
- **`beat_saber_song_ids.json` added** — Copied from `.agent/beat_saber_song_ids.json` to `beat_saber_deluxe/` for pipeline access.
- **`manage_song_metadata()` updated** — Now resolves `target_name` to exact game song name before writing to `song_metadata.json`.

## v0.5302 (2026-07-26)
- **Song metadata management** — Added `manage_song_metadata()` function and `--song-name`/`--artist` CLI arguments. Generates/updates `song_metadata.json` with song name and artist replacements for the TMP_Text hook.
- **Auto-deploy on `--deploy`** — `song_metadata.json` is automatically deployed to PS4 alongside `redirects.json` and `features.json` when `--deploy` is used.
- **`deploy_all.sh` updated** — Step 3.5 now deploys `song_metadata.json` to `/data/GoldHEN/AFR/CUSA12878/song_metadata.json`.
- **Feature flag default updated** — `enable_song_metadata_modification` defaults to `false` in `DEFAULT_FEATURES`.

## v0.5301 (2026-07-19)
- **Feature flags support** — Added `--set-feature key=value` CLI argument. Writes `features.json` locally and deploys it to PS4 via FTP.
- **Supported flags:** `enable_custom_song_replacements` (default: false), `enable_song_metadata_modification` (default: false — preserved for future use)
- Usage: `--set-feature enable_song_metadata_modification=true` or `--set-feature enable_custom_song_replacements=false`
- **BeatSaver API override** — Added `--beatsaver-api-base` to override the default BeatSaver API URL (useful for mirrors/local servers).

## v1.49 (2026-07-17)
- **Uncompressed block independence test FAILED:** Critical finding that 49 uncompressed blocks (flag=0) are part of a shared decompressed stream, NOT independent storage. Modifying their content changes file_size by ~817-2,177 bytes due to cascading compression ratio effects.
- **Option B BLOCKED:** Uncompressed block injection approach cannot achieve zero size impact — blocks are not independent storage as initially hypothesized.
- **New fallback identified:** Memory injection (patch BeatmapLevelSO in RAM after Addressables load) as alternative to pack bundle modification.

## v1.48 (2026-07-17)
- **Size + CRC dual validation confirmed:** Both `m_BundleSize` and `m_Crc` in Addressables catalog must match simultaneously or game crashes with CE-34878-0
- **Root cause of size difference identified (Exp 155):** Decompressed stream grows by exactly the blob size delta (+817 bytes for Espresso blob replacing original BeatmapLevelSO). Remaining ~1,895 bytes from bundle rebuild overhead.
- **Viable approach identified:** Uncompressed block injection — 49 blocks (flag=0) are stored as fixed-size raw data; modifying content affects CRC but NOT file_size. Provides ~6.1 MB of free variables for CRC control.
- **Knowledge base updated** with detailed size analysis and Option B approach documentation.

## v1.47 (2026-07-17)
- **CRC correction via GF(2) linear algebra works:** Achieved exact CRC match `0xdc8b314f` using alignment padding bytes for correction. Bundle size differs by +2,712 bytes; `m_BundleSize` validation in catalog causes crash when size doesn't match.
- **New tool added:** `build_patched_pack_bundle.py` in `tools/` — proven working CRC correction via GF(2) linear algebra on 9 alignment padding bytes. Produces rollingstones_pack_patched.bundle (7,905,515 bytes).

## v1.46 and earlier
- See previous changelog entries for full history of pipeline development.

### 2026-10-25 — Exp295 plugin-only correction (pipeline0.5367 unchanged)
- Local plugin0.8059 fixes reference-publication ABI after native startup crash; no pipeline tools/conversion/deploy behavior changed. Console remains0.8058/additive OFF.
