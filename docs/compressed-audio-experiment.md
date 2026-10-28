> **Current status — pipeline 0.5382:** the user confirmed the separate 48 kHz
> test's playback and seeking. Normal imports now support compatible stereo
> 44.1/48 kHz Vorbis using original packets. Unknown codebooks still use PCM16;
> existing songs are not rewritten. Earlier experimental/pending statements below
> record the historical stages, not current restrictions.

# Compressed main audio: offline Vorbis passthrough experiment

Status: **user-confirmed PS4 playback; integrated into normal imports in
pipeline0.5378** (m11121). Supported source audio now prefers original-packet
Vorbis; PCM16 remains the fallback. Existing installations are not rewritten.
The original separate test deployment changed only owned custom-song files and
its library entry; native plugin, feature flags, stock/DLC and saves were unchanged.
Do not advertise reduced gameplay RAM: Unity retains
**decompress-on-load / preload** settings. This reduces disk and transfer sizes.

## Measured candidates

| Source map | Existing PCM bundle | Compressed bundle | Saving |
| --- | ---: | ---: | ---: |
| 25570 — This Is What Falling in Love Feels Like | 22,324,206 B | 2,396,970 B | 89.3% |
| 4852 — Colors | 33,437,062 B | 8,290,109 B | 75.2% |

These are bundle-only sizes; separate cover and WAV preview files are unchanged.
PC extracted source folders (excluding our added BeatSaver metadata) were
2,508,938 B and 8,754,261 B respectively. The compressed candidates are therefore
close to PC size, without requiring another lossy encode.

## Why the new experiment differs from the abandoned legacy encoder

- Original source Ogg audio packets are retained **byte-for-byte**. Only Ogg
  container overhead and three Vorbis headers are replaced with FMOD's FSB5
  framing. There is no encoding step, resampling or additional lossy generation.
- Validate the setup CRC **and the complete setup packet** against independently
  reconstructed FMOD codebook metadata. Unsupported sample rates, channel/block
  configurations or unknown setups fail instead of borrowing the stock CRC.
- Emit a new 60-byte FSB5 v1 header (format-version field at28 must be1), new
  descriptor with exact final sample count, Vorbis metadata and packet payload.
  Do not retain stock sample headers, fixed file sizes or stale seek offsets.
- Build a fresh approximately one-second seek table using libvorbis packet
  blocksizes. The table entry points to a packet whose initial overlap is
  discarded; its sample index is the accumulated granule **after that packet**,
  not before it. A missing table decoded linearly but failed random seeking in
  host FMOD. The first wrong-granule attempt sought to misaligned audio; rejected.
- Set Unity's compression enum to Vorbis1 (distinct from FSB's Vorbis codec15).
  Keep channels, rate, exact clip length and preload/load settings unchanged.
  Reopen the saved UnityFS independently and check the actual stored FSB bytes.
- Each experiment has a new owned level ID/CAB and `[Vorbis test]` title, retaining
  the existing PCM entries. The manifest uses a distinct experimental kind, which
  the normal PCM validator/installer intentionally rejects.

## Independent verification

The developer proof uses existing `fsb5` test tooling plus UnityPy's existing
FMOD decoder. Production uses the same proven packet wrapper but reconstructs
Ogg for independent libsndfile validation instead of calling the proprietary
FMOD decoder. `requirements-companion.txt` includes `fsb5`; libvorbis,
libvorbisenc and libogg support header reconstruction/packet timing when
available. Missing optional codec libraries select PCM. Self-contained builds
must bundle these open-source libraries alongside the existing audio stack;
Windows/macOS/Android packaging is not validated here. No proprietary FMOD SDK
is required by normal imports.

- Full host suite: **1206 passed,124 skipped**, one inherited Starlette/httpx
  deprecation warning. Twelve new regressions cover packet identity, odd final
  sample count, malformed/chained/truncated/checksum-corrupt streams, unsupported
  source profiles, mismatched/unknown setups, safe isolated candidate output,
  original-map preservation, full FMOD decoding and compressed random access.
- Both real candidates return exactly5,560,877 /8,331,511 stereo frames at44100Hz.
  Host FMOD seek+decode checks cover start, unaligned1-second position, midpoint,
  near-end, backward seek and reset to start, rather than slicing predecoded PCM.
- Maximum error against clipped source float decode is0.00006122 or less
  (approximately2 PCM16 quantization steps), with no timing/sample-count change.
  Some original Vorbis samples exceed the PCM range (source peaks1.965/1.077).
  FMOD's PCM16 output clamps these; this is source overshoot, not new encoding
  distortion. Original packet bytes remain unchanged.
- Private input songs/bundles and detailed reports stay ignored under `temp/`.
  Reports: `temp/compressed-audio/{25570,4852}-v2/verification.json`.

Primary format reference inspected at vgmstream revision
`d9875b1fff307e4759dfb85e49e3d5e6fb196f7c`:
`src/meta/fsb5.c`, `src/coding/vorbis_custom_utils_fsb.c` and
`src/coding/vorbis_custom_decoder.c`. Format descriptions were checked against
actual FMOD decoding; no third-party decoder source or codebook tables were
copied into the project.

## Reproduce locally with owned inputs

```sh
.venv/bin/python orbeats/development/scripts/probe_vorbis_audio.py \
  --experimental --pcm-candidate /path/to/verified-pcm-candidate \
  --audio /path/to/original/song.egg --output temp/new-vorbis-candidate
bash orbeats/development/scripts/run_additive_host_tests.sh
```

Output must not exist or be inside either input directory. The script has no FTP,
console address, deploy switch or publication operation. It does not modify its
inputs. Samples must agree with the verified PCM candidate; audio is independently
decoded and checked before any output is published locally.

## First explicit console staging (m11045)

- User removed installed songs and asked to continue compressed-audio testing.
  Existing canonical library was empty; append only the separate test ID
  `bsd_additive_e12f6738fd8db99e0add5c25`, titled
  **This is What Falling in Love Feels Like [Vorbis test]**, Expert only.
- `development/scripts/deploy_vorbis_probe.py` independently regenerates the
  compressed candidate, validates original-map/PCM content, binds preview to the
  actual original Vorbis bytes and checks exact candidate metadata/bytes before
  connecting. It is opt-in (`--experimental --deploy`), not an app mode.
- Verified closed title, exact active ELF/capability, enabled additive flags and
  disabled legacy replacement flags. The actual installed marker is **0.8068**;
  it predates `max_songs`, so use the same conservative **8-song** default as the
  production installer, never assume the newer local plugin was installed.
  Initial attempt refused the absent key before any content upload; fixed with
  a legacy-marker regression, not a plugin upgrade or expanded limit.
- Used `.install-lock`, immutable-file collision checks, full staged/final readback,
  canonical manifest CAS and retained local/remote previous-library backup.
  Published `library.bin` last. Companion Library API independently lists the one
  test entry and exact bundle SHA256
  `5f5c92290139f3003a7a2f5a65406842871cc564277cd925bc5b49521b84b320`.
- Bundle2396970B, cover460637B, unchanged18-second WAV preview3175278B. No automatic
  game launch. Paused Brainrot Giga Choir queue entry55528 retained untouched.
- Full host **1221 passed,124 skipped**, one inherited warning. Fifteen additional
  deployment regressions cover closed title/capability/flags, old8-song capacity,
  lock exclusion, no migration, canonical floats/idempotence, existing entries,
  collision/corrupt staging and failed publication rollback, plus title opening
  mid-stage retaining the interrupted lock. Reports/backups remain ignored under
  `temp/compressed-audio/console-test-25570/`; console output is
  `temp/compressed-audio/deploy-25570-console.txt`.
- A normal conversion using the compressed bundle as its first-library-entry
  template independently produced validated PCM16. The writer generates fresh
  PCM headers/load settings rather than reusing the template codec.
- Supplied lighting reference `benzhenwen/V4-to-V3-lighting`, inspected at
  `81fe13dfe96a94a93e4fbcc3814e9a0f111169eb`, unpacks V4 lighting tables/event boxes
  into V3 structures. Useful separately, not an audio-size fix or proof of PS4
  environment compatibility. Its own README warns about unverified conversion;
  no LICENSE file was found at repository root. No source copied or executed.

Example explicit developer deployment (owned local inputs required):

```sh
.venv/bin/python orbeats/development/scripts/deploy_vorbis_probe.py \
  --experimental --deploy --config orbeats/ps4_config.json \
  --pcm-candidate /path/to/verified-pcm-candidate --audio /path/to/source/song.egg \
  --source /path/to/source --candidate temp/new-vorbis-candidate \
  --report-dir temp/compressed-audio/console-test
```

## Production integration (m11121)

- User confirmed that the compressed console candidate works correctly and
  authorized making it the normal supported import path. That hardware evidence
  is distinct from the new production code's host regression results.
- V2/V3/V4 companion imports preserve original audio through normalization, try
  the proven stereo44100 profile, and report either original-packet Vorbis or a
  specific PCM fallback reason. No additional lossy encoding occurs.
- The production candidate has a codec-specific deterministic ID/CAB. Exact-ID
  reimports independently validate retained audio/maps, avoiding false collisions
  after a song becomes its own template. Existing matching PCM entries stay
  installed, without duplicates or automatic conversion. The separate `[Vorbis
  test]` developer ID remains separate; it is not silently merged or deleted.
- Fresh headers, seek metadata, exact samples and independent decode checks are
  mandatory. Once a codec is selected, validation failures are fatal. Corruption
  cannot trigger a silent PCM fallback. Single-difficulty templates now support
  every later authored difficulty using distinct map/lightshow TextAssets and
  complete preload pointers, whether the new output is PCM or Vorbis.
- Production host verification rebuilt both real maps through normal preparation:
  25570 still22324206→2396970B,4852 still33437062→8290109B; exact samples,
  difficulties, notes and stored audio independently checked. Report:
  `temp/compressed-audio/production-real-maps.json`. No console writes.
- Full host **1247 passed,124 skipped**, one inherited Starlette/httpx warning,
  51.05s. `temp/compressed-audio/production-full-host-tests.txt`. Production codec,
  installer and preparation pass scoped Ty; new codec/tests/probe and installer
  pass Ruff. Existing preparation/developer-probe style/type findings are separate
  from runtime correctness; no global diagnostics-clean claim.
- New production imports still require user verification on PS4. No further
  deployments, plugin updates, automatic queue start or console launch were done
  during integration. Active service/paused queue were preserved; fresh job
  subprocesses load pipeline0.5378 without clearing the pending queue. The service
  ping still reports its import-time0.5377 until an eventual idle-safe restart.

## Investigated source-specific fallbacks (27 October 2026)

The current fallback is PCM16, not another lossy Vorbis/MP3 encode. Two real
recent map sources reproduce fallback without any console changes:

- Light Switch (2076a): stereo Vorbis **48000 Hz**, 256/2048 blocks. The proven
  passthrough profile is44100Hz; the importer resamples for the existing PCM path.
  Source3271529B; complete prepared PCM bundle33293490B.
- Legends Never Die (934): stereo44100Hz Vorbis, 256/2048 blocks, but setup CRC
  **b2c77468** is absent from the bundled known-FMOD codebook lookup. It therefore
  cannot pass the current validated passthrough path. Source1989945B; complete
  prepared PCM bundle29566418B. Not evidence of a corrupt song.
- Ignite4fd8, Spectre155a and Fade2e2 use supported44100Hz profiles (setup CRC
  **6c87a72f**) and pass original-packet compression on the same machine. Missing
  codec dependencies are not the cause of these two individual fallbacks.

Evidence: `temp/audio-fallback-audit/source-profiles.json` and
`temp/audio-fallback-audit/local-pcm-reports.json`. The deliberate old PCM baseline
builds with "no original compressed source supplied" are not unexpected import
failures. Investigation only; no production changes or console writes. Additional
48kHz passthrough would need generalized sample-rate/frame/FSB validation and PS4
testing; unknown codebooks still need a verified compatible path. Re-encoding to
a supported Vorbis profile would be a separate lossy option, not the present
fallback.

## Explicit48kHz candidate (27 October2026)

The generalized developer path now builds Light Switch without changing its
compressed audio packets. It is **not enabled in normal imports** and has not
been deployed or tested on the PS4. Default helpers remain44100Hz-only. Both
AudioClip and AudioData rate/frame coordinates are updated for the candidate.

- Source9032535frames at48000Hz; output3352366B vs33293490B PCM bundle.
- Independent FMOD decode exact9032535frames; full clipped-source comparison
  maxerror5.2869319915771484e-05; six compressed seeks pass, including near-end
  and backwards-to-start. No packet re-encoding, source overshoot or frame padding.
- Repeated developer payload preparation binds original source identity, validates
  media and independently rebuilds the same bundle; no console writes.
- Candidate: `temp/audio-48k-probe/light-switch-v2`; report
  `temp/audio-48k-probe/light-switch-v2-result.txt`; payload report
  `temp/audio-48k-probe/payload-proof.txt`.
- CLI: probe_vorbis_audio.py --experimental --sample-rate 48000, followed only
  after separate approval/closed title by deploy_vorbis_probe.py --deploy
  --sample-rate 48000. Normal imports do not select this profile until hardware
  validation.

Unknown setupb2c77468 (Legends Never Die, aoTuV b5a20080330) also failed a direct
host-FMOD experiment with `FmodError: VERSION`. Nearest lookup header differs at
nine byte positions, so never substitute itsCRC or setup: matching source audio
packets are inseparable from their real codebooks. The supported44.1kHz path and
PCM fallback are unchanged. Evidence: `temp/audio-fallback-audit/unknown-codebook-fmod.json`.

### User-requested48k console test deployment

After user confirmation that plugin0.8072 restored the playlist, the separate
**Light Switch [48k Vorbis test]** entry was staged/read back and appended last
to the canonical library. All14 original entries remain; total15. Plugin,
capability, feature flags and plugins.ini bytes are unchanged. The15 pending
queue items and52 history entries remain paused/restored; no game launch.

Evidence: `temp/audio-48k-deployment/deployment-report.json`. The test bundle
is3352366B, SHA2569362f967d5bc852e018bc4d8c7b5a8f7a785fde7abb1bee60f9f02dc45f19e83.
**48k playback/seek confirmation remains pending; normal imports still use the
proven44.1k path or PCM fallback.**

## Promotion to normal 48 kHz imports

User confirmation (m11854) followed the separately staged Light Switch test,
including the requested playback/seek checks. Pipeline **0.5382** now selects
44.1/48 kHz from the original source and passes it explicitly through the proven
packet/FSB construction and independent decoder validation. The low-level helper
API still defaults to 44.1 kHz for compatibility; the normal importer now opts in
to the detected, supported rate.

AudioClip and AudioData are written in the stored audio's own sample coordinates,
not the normalized 44.1 kHz WAV's frame count. Manifest fields include
`audio_sample_rate` and a distinct `vorbis-passthrough-preload-48k-v1` identity.
For independent source comparison only, FFmpeg decodes/resamples reconstructed
48 kHz packets to the normalized baseline's coordinates. Stored packets remain
unchanged. Source duration must agree within one normalized sample; a selected
compressed candidate that fails validation is not silently downgraded.

- Normal production Light Switch: **3,346,918 bytes**, down from 33,293,490 bytes;
  original **9,032,535 frames / 48,000 Hz**, same note/difficulty/timing data.
  Local proof: `temp/48k-production/real-light-switch.txt`.
- Tests cover original packet/decoded-sample identity, exact nonaligned frames,
  rate/frame/profile/AudioClip/AudioData/tempo corruption even with updated hashes,
  deterministic preparation, normal fake-FTP install/reimport, existing PCM
  preservation, unsupported-rate/codebook fallbacks, fatal decoder failures and
  48 kHz-template reuse for later 44.1 kHz/PCM songs.
- Unknown aoTuV setup `b2c77468` remains PCM16. No CRC/codebook substitution or
  lossy re-encoding was introduced. Covers and WAV previews are unchanged.
- No console writes, queue changes or service restart for this promotion. Existing
  PCM installations stay PCM even on reimport; changing an installed song's audio
  format requires explicitly removing/reimporting it with the title closed.
