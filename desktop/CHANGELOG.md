## 0.1.15 — import compatibility patch

- Restore horizontal page controls below the results (companion0.7.31).
- Include pipeline0.5394's Borderline lighting-event validation fix.
- Correct FFmpeg's configure muxer name to pcm_s16le (CLI format s16le), fixing
  the48kHz preserved-audio verification failure. Gate media builds on actual
  PCM pipe/resampling output, and exercise48kHz in frozen-codec regressions.
- Native Windows release checks now exercise frozen44.1/48kHz codec verification
  without host tools. Interactive Windows testing remains unperformed.
- Owner confirmed Borderline imports, installed maps and in-app previews work
  with the corrected Linux candidate. Keep original horizontal pagination.
- Consolidate supporting source/notices/provenance into one labelled archive;
  retain the required update manifest and optional verification checksums.

## 0.1.12 — canonical transparent branding and source layout

- Use the supplied root icon.svg in the companion and startup UI; regenerate
  transparent native desktop PNG/ICO and plugin artwork from the same source.
- Bundle plugin0.8079 / companion0.7.26 / pipeline0.5391.
- Main source directory is now orbeats; orbeats_extras remains a separate plugin.
  Existing console paths and internal library IDs are unchanged.
- Replace the README status board with a concise overview, navigation and clearly
  labelled sample-data screenshots. Setup/build details move to dedicated guides.

## 0.1.11 — recurring import compatibility fixes, testing candidate

- Pipeline0.5391 / companion0.7.24, plugin unchanged0.8077.
- Preserve the authored root environment for index0 with an empty environment
  table. Other invalid references still refuse.
- Accept validated top-level legacy BPM markers only when every value exactly
  matches the explicit song BPM; no changing-tempo markers are discarded.
- Accept bounded legacy `_atlasBeatsMap` scalar annotations. Preserve zero-time
  chains and all slice geometry/timing; negative durations and zero-time arcs
  remain invalid. No epsilon insertion, flattening or object loss.
- Keep the actionable exception in failed-job summaries instead of the generic
  PyInstaller wrapper. The older Konekomyu wrapper-only failure is not diagnosed
  retroactively; its full frozen conversion now verifies successfully.
- Seven original public maps pass frozen offline import, preparation and independent
  bundle/chart/audio verification with no host media tools or console operations.
  Local tests/runtime evidence and Windows hosted results are recorded separately.

## 0.1.10 — platform diagnostics and GoldHEN setup, testing candidate

- Explicit UTF-8, unbuffered frozen task output and resilient live job draining;
  Windows regression now runs on the native Actions runner. Original Windows
  stall is not yet reproduced; do not claim a confirmed FTP fix.
- Owned SVG logo in brand/hero/favicon; compositor-based activity indicator with
  reduced-motion support. Linux WebKit smooth-scroll interpolation disabled only
  inside this webview; no wheel interception or desktop preference changes.
- Connection form asks only PS4 IP; save fixes GoldHEN2121/anonymous/no password.
  Separate advanced conversion-seed recovery explains that it is not FTP setup.
- Pipeline0.5390 fixes empty-table/default-palette and descriptive Info annotations;
  frozen original54d4e/55106 import/prepare/independent verification passes with no
  host Python/media on PATH or console operations. Plugin remains0.8077.
- Full1647hosttests pass/124skip, seven release Rust tests and desktop/mobile browser
  fixtures pass. Packaging/runtime and native Windows checks recorded separately.
- GitHub Actions artifact downloads are ZIP containers around the NSIS.exe; public
  release assets can expose the .exe directly. No release is created here.

## 0.1.9 — Downloads log usability, not a public release

- Companion0.7.22: collapsible active/last log before queue/history, bounded scroll,
  reader-aware tail-follow, Jump to latest and unchanged full diagnostic exports.
- Pipeline0.5389/plugin0.8077 unchanged; retain bd45 and process-local Wayland fixes.
- Full1595hosttests pass/124skip, seven Rust tests pass, desktop/mobile browser
  fixture with80history entries passes. Actual image passes private Wayland
  pointer/EOF and isolated Ubuntu22.04 X11 normal window-close/backend-drain.
- Complete2331file AppDir,1744file sealed helper;467ELFs GLIBC<=2.35. Image
  179775992bytes SHA256989af8d60fd8b4b24b572c434fc24cf1c65f89229fdd6e212137df48f893a0a6.
- Windows native execution remains blocked on target environment; Wine is not
  native Windows evidence. No external CI, publication or PS4 actions performed.

## 0.1.8 — legacy wall-placeholder import fix, not a public release

- Bundle pipeline0.5389/companion0.7.21; native plugin unchanged0.8077.
- Skip only exact five-field all-zero legacy V2 wall sentinels, report counts,
  retain all meaningful walls/notes/timing and all other geometry guards.
- Unmodified public bd45 map now imports and independently verifies in frozen
  offline conversion:859/1001notes,102/109walls,3ExpertPlus placeholders skipped.
- All1593hosttests pass/124skip and seven Rust tests pass. Actual image passes
  private Wayland pointer regression and isolated-X11 UI/normal-close/drain.
 467ELFs remainGLIBC<=2.35. No PS4 operations, requeue or game launch.
- Source/license/platform distribution gates remain open. Image179767800bytes,
  SHA256caf7100aad06f6ec21cf65fd974ee8b6d714d8f64ebb1de93896afb3ddd113e8.

## 0.1.7 — process-local GTK cursor fallback, not a public release

- Reproduce the0.1.6 fatal GTK/Wayland `cursor_theme_name` assertion with private
  keyfile settings exporting cursor-size0 and an empty theme. The zero-size
  cursor shared-memory pool fails; missing theme assets alone was not the cause.
- Before creating windows, normalize only invalid GTK cursor settings inside
  this process. Prefer valid XCURSOR_SIZE/XCURSOR_THEME, otherwise24/default;
  retain already-valid settings. Do not write dconf/GSettings, force XWayland,
  disable WebKit sandboxing or alter any PS4 state.
- Rebuilt optimized native shell againstUbuntu22.04; complete image remains
  GLIBC<=2.35 across467ELFs and sealed frozen backend1744files is unchanged.
- Private nested Weston/Xvfb reproduces old crash; actual0.1.7 image survives
  same invalid settings and pointer input. Synthetic-parent exit drains backend
  via EOF; normal Wayland close is NOT established by that regression. Separate
  isolated-X11 test proves normal WM close/drain. Initial GTK/WebProcess cursor
  warnings can still appear before the parent fallback; fatal assertion absent
  in the tested case. User subsequently confirmed0.1.7 operational in Niri.
- Full1567hosttests pass/124skip;7Rust tests pass. Source/legal/platform release
  gates remain open. New image179775992bytes, SHA256
  29df35ba84989876795a2c89a008d5fb384576e36ef1c4824c5388531c1ce4cb.

## 0.1.6 — older Linux baseline candidate, not a public release

- Digest-pinned Ubuntu22.04 userspace without Docker/sudo/system installation;
  bounded safe rootfs extraction, isolated project-local build/run namespaces,
  pinned Rust1.90.0/CPython3.12.16, rebuilt helper/FFmpeg/codecs/native shell.
- Optimized release-profile AppImage179759608bytes (about171.4MiB) meets
  GLIBC<=2.35 across467ELFs. Reject private/symbolic
  unsupported GLIBC ABI, escaping paths and build-only ownership shim. Omit the
  generated libmvec companion so the runtime uses its matching GLIBC library.
- Actual-image UI/WM close/drain in a separate minimal Ubuntu runtime with no host
  /usr or build tools, plus modern-host smoke and isolated five-difficulty offline
  conversion without Python/media tools on PATH. Still uses host kernel/privateXvfb
  and extract-and-run; no broader distro/Wayland/FUSE claim.
- Actual artifact seeded-state restart retains settings, paused pending/history,
  older runtime and local recovery; not a full installer-upgrade/uninstall claim.
 1567hosttests/124skips,4Rust release tests, isolated/modern-host smoke all pass.
- Recover fsb5MIT notice verbatim from the upstream commit matching all five1.0
  source files. Bundle notice/provenance and refuse a changed installed dependency.
- Keep Windows execution, full source/license closure and
  installer/upgrade/uninstall/clean-machine tests as explicit release gates.

## 0.1.2 — optional static Linux media payload, not an installer

- Build minimal static FFmpeg8.0.1/ffprobe from pinned vendor-source/signature/key,
  no GPL/nonfree/autodetected codec libraries or network protocols. Retain LGPL
  text, license description, source lock and exact reproducible build command.
- Add optional exact media resource inventory, digest checks and executable modes;
  refuse partial, tampered and extra payloads before output creation. Source and
  frozen child tasks prefer their verified tools over PATH.
- A frozen five-difficulty synthetic V3 import succeeds without host Python or
  FFmpeg on PATH. Separate codec-library isolation is NOT established.1521host
  tests pass,124skips,1inherited warning. No PS4 operations from desktop tests.
- Codec libraries, complete third-party license/source review, installer layout
  and Windows/clean-machine validation remain gates.

## 0.1.1 — native Linux window and lifecycle, not an installer

- Compile and run the real OrBeats UI through the owned frozen helper; private
  Xvfb smoke proves normal WM close, backend exit and paused state preservation.
- Add bounded 30second readiness wait, startup/error status, backend-death monitor,
  idempotent close/stop, and explicit popup/download/external-navigation refusal.
  Do not force-kill active work or grant remote Tauri capabilities.
- Add signed/checksummed Arch prerequisites extracted under project `.tools`,
  reproducible Cargo environment and read-only WebKit development overlay.
  No system install, service/permission change or user-display interaction.
- Three Rust tests and1517host tests pass (124skips,1inherited warning). Native
  normal-close evidence is separate from frozen fake-publication tests; native
  failure/import coverage, media-tool bundle, installer and Windows remain gates.

## 0.1.0 — initial scaffold, not a packaged release

- Start Tauri2 OrBeats shell with owned-backend readiness and graceful-stop wiring.
- Add independently tested private-loopback session/shutdown admission adapter.
- No production webapp changes, bundled backend or successful native UI build yet.
- Cargo.lock generated; Linux build blocked by absent WebKitGTK/JSC4.1 development
  prerequisites. No system-wide package installation or publication performed.

## 0.1.0 prototype continuation — not a packaged release

- Wire the existing API/UI into owned private backend bootstrap and STOP/EOF
  lifecycle; persist paused queue/settings/recovery outside versioned resources.
- Add state ownership, curated resource integrity and frozen child-task dispatch.
- Build/test Linux PyInstaller helper without host Python/tools on PATH; test
  source/frozen close during fake publication with full commit/local recovery.
- Native media tools and their licenses, actual Tauri/Windows builds and polished
  startup/shutdown UX remain release gates. Linux shell still blocked by absent
  JavaScriptCoreGTK/WebKitGTK4.1 development prerequisites; no system changes.
