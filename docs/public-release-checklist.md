# Release readiness — desktop 0.1.13

**Targets:** Windows x64 NSIS installer (`.exe`, not a ZIP), Linux x64
AppImage, `orbeats.prx` 0.8079 and `orbeats_extras.prx` 0.0009. No macOS/ARM
support is claimed. Pipeline 0.5393; webapp 0.7.28.

The owner has authorized source commit/push, release publication and making the
repository public **after** the release is ready. That permission is not itself
proof that these technical/distribution gates passed. The repository must remain
private while publication is incomplete. Only the audited source-only checkout
is pushed; no game inputs, dumps, songs, console backups or personal profiles.

## Current preparation

- Extras installation is a separate closed-title/readback/local-rollback
  transaction. It preserves the main plugin, library and existing health settings.
- Official stable GitHub release checks distinguish unavailable from up to date.
  Explicit plugin downloads require the release manifest's size, SHA-256 and
  embedded version before reaching the existing guarded installer. App upgrades
  remain manual. Checks compare bundled plugin versions, not unchecked PS4 state.
- Removed the redundant sidebar text/theme button (theme remains in Settings).
  Desktop content scrolls independently of the sidebar. The startup view is hidden
  before the authenticated main view appears; closing hides both views while the
  backend drains active mutations. Windows child jobs use CREATE_NO_WINDOW.
- Offline browser fixtures cover confirmations, Extras/version display, release
  and unavailable states, sidebar wheel scrolling and existing desktop/mobile UI.
- New final AppImage: 179,902,968 bytes, SHA-256
  `52c60618f35d5746d67c6d4c7d8cf0f393f74fd98fcb7c76202bf90592c67cca`.
  All 467 ELF files pass GLIBC <= 2.35 and no-private-GLIBC checks. Actual image
  launch/WM-close in an isolated Ubuntu 22.04 runtime proves one visible app view,
  no resurfaced close window, graceful backend drain and a fresh paused queue.
- GitHub SSH fetch/push works. The configured API token authenticates the owner
  but returns 404 for this private repository (also through GitHub MCP). Release
  creation/asset download/visibility administration need authorized repository API
  access. Do not make the repository public early to work around this.
- `desktop/packaging/stage_release.py` curates exact assets/checksums/feed manifest
  into a fresh local folder. Missing Windows/Linux output is explicitly incomplete.
  This tool never publishes, copies a whole working directory or claims legal or
  installer lifecycle approval.

## Confirmed hardware scope

Custom songs and Animals Hard/lighting repair were confirmed on the user's PS4.
Extras health-warning dismissal and anonymous read-only ScoreSaber retrieval were
confirmed; the later top-ten/unprefixed-name change still needs a user check.
This does not establish every authored colour/Practice/stock feature combination.
See `map-hardware-test-matrix.md`. Other game regions/patches, arbitrary managed
mods and custom environments remain unsupported.

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

1. **Windows end-to-end installation and lifecycle.** Earlier private Actions
   builds passed native source-built media, frozen synthetic import/bootstrap/
   drain, seven MSVC tests and NSIS generation. The real-map live-output regression
   and its encoding/buffering fix are retained. A new 0.1.13 target-native build is
   required; older CI is not proof for these closing/Extras changes.
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
5. **Public documentation and access.** Keep supported-game/feature limits,
   closed-title/local recovery requirements, unsigned Windows trust expectations
   and checksums explicit. The owner's publication approval is already granted;
   do not ask for it again. Resolve the private-repository API permission blocker,
   verify all final assets, then publish and only afterward change visibility.

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

Latest complete local host validation: **1859 passed / 124 skipped**, with one
inherited Starlette warning, using the final frozen helper. Seven Rust release
tests and 32 focused release/Extras regressions pass. The same final AppImage
also passes native launch/close on the modern host, plus an offline frozen
five-difficulty/12-second synthetic import in the isolated Ubuntu runtime with
empty PATH and no host Python/FFmpeg (529200 samples). No console write occurs. Actual-image synthetic prior-state restart retains
settings/paused pending/history/older runtime/local recovery. This adds a real
artifact-level preservation check, not a full installer-upgrade/uninstall claim.
