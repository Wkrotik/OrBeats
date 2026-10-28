# First public release gates — preparation only

**Targets: Windows x64 NSIS + Linux x64 AppImage, deb optional.** No publication,
tag or system installation is authorized by this checklist. User separately
authorized a private source repository/push and GitHub Actions for testing; see
[private builds](private-builds.md). This is not public-release permission.
Current source: plugin0.8077 / pipeline0.5391 / web0.7.24 / desktop0.1.11.
User confirms0.1.7 Wayland repair,0.1.8 bd45 installation and Windows0.1.9
plugin detection.0.1.10 adds deterministic worker output, the owned SVG logo,
revised progress/scrolling, IP-only GoldHEN settings and two bounded map fixes.
Neither new actual Windows installation success nor those maps' playback is
claimed; no automatic console retry or new native plugin feature.

## Confirmed functional milestone

The user confirms0.8077 restores Custom Songs and Here Come the Cats plays
correctly;27existing songs were preserved. This does not prove exact authored
colour parity, Practice seeking, stock regression or every feature combination.
See `map-hardware-test-matrix.md`; mods/custom environments remain out of scope.
Do not widen compatibility claims simply because packaging changes.

## Linux packaging milestones actually completed

- Native UI with owned private authenticated backend, fresh profile, graceful
  close/drain and paused restart; no public network server or remote Tauri powers.
- Pinned static FFmpeg8.0.1/ffprobe + source-built Ogg1.3.6/Vorbis1.3.7, licenses,
  source locks/build recipes; upstream codec checks and independent FSB decode.
  Explicit owned codec loading refuses partial/tampered inventories and failed
  loads, rather than falling back to foreign host codecs.
- Primary AppImage, optionaldeb configs parsed by actual locked Tauri types;
  pinned CLI/linuxdeploy/output tools, project-local only.
- Sealed backend restored after linuxdeploy's ELF rewriting, full readback and
  manifest checks preserved. No private game data, profile or songs copied.
- **New0.1.6 candidate rebuilt inside Ubuntu22.04 / GLIBC2.35**: Rust1.90.0,
  CPython3.12.16, shell/helper/media/codec builds, all467AppDir ELFs meet the numeric
  ABI bound with no `GLIBC_PRIVATE`. Omit the generated GLIBC libmvec companion;
  the runtime's matching libc supplies it. Do not bundle laptop libc.
- Optimized release-profile native shell and actual final image open/close in a separate minimal Ubuntu22.04 userspace
  with normal graphics/fonts/CA but no host `/usr`, GTK/WebKit, Python, FFmpeg or
  build tools; normal DNS/hosts config is read-only-mounted, live discovery renders.
  Same image also passes modern Arch-host window/close test.
  Extracted-image offline conversion verifies hashes and five-difficulty12s audio
  inside the separate runtime with empty PATH. No PS4 writes or webqueue changes.

See [Linux baseline recipe/evidence](../desktop/packaging/LINUX-BASELINE.md) and
[AppImage assembly](../desktop/packaging/APPIMAGE.md). Earlier Arch0.1.5 artifact
requiredGLIBC2.44; it is a reference, not the current release candidate.

## Remaining blocking gates

1. **Windows end-to-end installation and lifecycle.** Private Actions run
   40674610679 passed native source-built media, frozen synthetic import/private
   bootstrap/drain, seven MSVC tests and unsigned NSIS0.1.9 generation. The user
   opened it and confirmed plugin detection, but reported a real installation
   appearing stuck with no output.0.1.10 fixes encoding/buffering and adds a native
   live-output regression; its new CI and actual installation still need checking.
   Interactive installer/upgrade/uninstall, WebView2-first-run and state/recovery
   preservation remain gates; CI generation is not blanket installer approval.
2. **Complete license/source closure.** The baseline helper audit inventories
   18Python metadata sets, not a complete SBOM/legal approval. fsb5-1.0's missing
   notice is now recovered from an exact-source upstream commit, bundled with
   provenance, and validated against all five installed source files at build time.
   Review Python/stdlib, compiler and wheel runtimes,
   Rust crates, standalone Python, GTK/GStreamer/WebKit and AppImage tooling.
   Provide notices/corresponding source and satisfy static FFmpeg/glibc and other
   relink/source obligations. No fabricated license text or metadata-only approval.
3. **Linux runtime matrix.** Current tests use extract-and-run, privateXvfb and
   the host kernel. Check defaultFUSE launch, actual clean supported distro/VM,
   realX11/Wayland/graphics/audio/preview and older kernel/driver compatibility.
   State normal OS graphics/font dependencies honestly, not "every Linux distro".
4. **Release/installer quality.** Optimized Linux build now passes; test fresh install,
   update/uninstall preserving settings/queue/recovery, discovery/audio, offline
   imports and controlled fakeFTP install/remove/readback, close during publication,
   interrupted recovery and restart paused. Source/frozen tests already cover many
   cases but do not replace testing each final platform artifact. Decide signing/
   trust documentation, provide checksums/provenance and independent artifact scan.
5. **Public documentation and user approval.** Bounded compatibility/known limits,
   closed-title requirement, local rollback/recovery, versions/changelog, private
   file scan, no telemetry or automatic upload/publish/tag/release. Ask for final
   distribution approval only after remaining gates are clearly accounted for.

## Current local evidence (never upload output directories wholesale)

- `temp/linux-baseline/`: setup/package/build logs,467ELF audit, Rust tests,
  final actual-image window/close and offline-conversion summaries.
- `temp/linux-baseline-work/source/temp/appimage-baseline-release-sealed-01/`:
  final0.1.6 AppImage, SHA256SUMS and assembly report. The directory also contains
  build tools/AppDir/reports; it is **not** a public asset folder.
- `temp/appimage-baseline-release-network-smoke/`,
  `temp/appimage-baseline-release-modern-smoke/`,
  `temp/appimage-baseline-release-offline-proof/`: final image test evidence.
- Previous codec closure details: `temp/desktop-release-prep/`,
  `temp/desktop-codecs-build-02/`, `temp/desktop-codecs-native-smoke/`.

Static audits explicitly keep legal/clean-machine approval false. Baseline userspace
success is meaningful progress, not authorization or readiness to publish.

Latest complete local host validation:1617passed127skipped with1inherited Starlette warning;
seven Rust release tests pass. Actual-image synthetic prior-state restart retains
settings/paused pending/history/older runtime/local recovery. This adds a real
artifact-level preservation check, not a full installer-upgrade/uninstall claim.
