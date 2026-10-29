# OrBeats 0.1.13 — release scope and evidence

**Release targets:** Windows x64 NSIS installer (`.exe`, no installer ZIP), Linux
x64 AppImage, `orbeats.prx` **0.8079**, and optional `orbeats_extras.prx`
**0.0009**. Webapp **0.7.28**; pipeline **0.5393**. No macOS, ARM, other game
region/patch, or arbitrary managed-mod support is claimed.

This is an early unsigned desktop release. Build/test evidence below is not a
claim of universal hardware support, independent security certification, or a
legal opinion. Known manual test gaps remain explicit rather than being marked
passed. Downloadable notices and source material accompany the binaries.

## Included changes

- Extras installation is a separate closed-title, full-readback, local-rollback
  transaction. It preserves the main plugin, song library and health settings.
- Official GitHub stable-release checks distinguish unavailable from up to date.
  Explicit plugin installation verifies size, SHA-256 and embedded version before
  entering the existing guarded installer. Desktop upgrades remain manual.
  Bundled-version checks do not pretend to inspect an offline console.
- Removed redundant sidebar text and theme button; theme remains in Settings.
  Desktop content scrolls separately from the sidebar. Only the authenticated
  main view is presented after startup; closing hides both webviews while the
  backend drains active work. Windows child jobs use `CREATE_NO_WINDOW`.
- Vendor source downloads retain pinned hashes and FFmpeg signature verification.
  The exact public signing key/signature are preserved offline, avoiding a flaky
  live metadata endpoint. No private key or unsigned fallback is used.

## Validation completed

- Full host suite: **1,865 passed / 124 skipped**, one inherited Starlette warning.
  Sanitized source checkout: **1,019 passed / 111 skipped** with the frozen-helper
  integration enabled. Hosted source CI has no owned game inputs and therefore
  has additional explicit skips. Seven native Rust release tests pass.
- Offline browser fixtures cover Extras and release states, confirmation/cancel,
  unavailable/offline honesty, wheel-scroll sidebar geometry and desktop/mobile
  regressions. Fake-FTP tests cover scoped installation, rollback and preservation.
- The final notice-bearing Linux AppImage is **179,968,504 bytes**, SHA-256
  `04f90047595cde753db2a78b568ac0942196a033fadb0bdbcbf822196fd6f32c`.
  Its 467 ELFs pass the GLIBC <= 2.35/no-private-GLIBC audit. Actual-image launch
  and WM-close in an isolated Ubuntu 22.04 userspace show one visible app window,
  no resurfaced closing window, graceful backend drain and a paused fresh queue.
  Offline synthetic import in that runtime, with empty PATH and no host Python
  or FFmpeg, verifies resource hashes, five difficulties and 529,200 samples.
- Windows uses a target-native hosted build: pinned source-built FFmpeg/Ogg/Vorbis,
  frozen-helper conversion/bootstrap/drain checks, MSVC tests, live-output tests,
  and NSIS generation. The release provenance identifies the exact successful run
  and asset hashes; an older run is never substituted as evidence for a new binary.

## Distribution material

The release includes `SHA256SUMS`, the app's `release-manifest.json`, and a
`release-provenance.json` identifying the actual build/test scope. Source/notices
archives are developer/compliance material, **not** ZIP wrappers around the
Windows download:

- Verbatim Python/wheel/native/Rust/SDK/runtime copyright and license notices;
  build-environment inventories are explicitly supersets, not a fabricated SBOM.
- Exact registry crate archives and available exact-version Python source
  distributions; Ubuntu source descriptors, upstream archives and distro patches.
- Source-built media locks/recipes, native Soundfile codec sources and Windows
  vcpkg patches, and the AppImage runtime source with its pinned FUSE recipe.
- A source-only OpenOrbis subset: no upstream sample Sony runtime modules,
  installers, game files, songs, dumps, personal profiles or console backups.

LGPL components retain their terms. Rebuild/relink and shared-library replacement
instructions accompany the source material; resource-hash validation is not a
prohibition on modifying/rebuilding a local distribution. The application's GPL
source is available at the release tag. No whole working directory or private Git
history is published.

## Known testing limits

- Windows interactive install/upgrade/uninstall, WebView2-first-run and actual GUI
  close behavior still require testing on a physical Windows machine. Native CI
  and source regression checks do not establish those manual results. The Windows
  installer is unsigned; no signing reputation or notarization is claimed.
- Linux tests use extract-and-run, Xvfb and the host kernel. Default FUSE launch,
  real Wayland/X11/graphics/audio, older kernels and a broader clean-distro matrix
  remain manual checks. Normal OS graphics, font and driver dependencies apply;
  "all Linux distributions" is not promised.
- Main custom-song operation and the Animals Hard/lighting fix were confirmed on
  the user's PS4. Extras health dismissal and anonymous read-only ScoreSaber
  retrieval were confirmed. The later top-ten/unprefixed-name change still needs
  a user check. No console was needed or modified during desktop release work.
- See `map-hardware-test-matrix.md` for gameplay/colour/Practice limits. Unsupported
  game variants or uncertain installations must fail closed, not be forced.

Repository publication follows verification of the curated assets, source/history
privacy review and release contents. Release preparation never requires making a
private repository public just to bypass an API permission problem.
