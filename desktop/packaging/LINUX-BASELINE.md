# Linux baseline optimized candidate0.1.6 — not a public release

The Linux primary artifact is AppImage; deb is optional. Windows x64 remains
required. This slice replaces the laptop-only GLIBC2.44 build with an actual
Ubuntu22.04 / GLIBC2.35 userspace build. It does **not** establish compatibility
with every distro, kernel, graphics driver, Wayland session or FUSE setup.

## Isolation and inputs

`desktop/development/setup_linux_baseline.py prepare --output .tools/NAME`
fetches the official Ubuntu22.04 amd64 OCI manifest/layer by the digests in
`desktop/development/linux-baseline-lock.json`, verifies hashes/sizes, and extracts
with traversal/special-file/whiteout/escaping-link guards. Absolute rootfs links
are rebased inside the project root. No Docker daemon, sudo or host installation.
`run --root .tools/NAME --work temp/SCRATCH -- COMMAND...` uses bubblewrap with
cleared environment, isolated user/PID/IPC/UTS namespaces, UID0 only inside that
namespace, and explicit project-local root/work mounts. No host home or `/usr`.
Network is available for package downloads; this is not a hostile-code sandbox.

For the build root, install Ubuntu signature-verified packages there:

- First `build-essential ca-certificates`, then `pkg-config libgtk-3-dev
  libwebkit2gtk-4.1-dev libsoup-3.0-dev libssl-dev libogg-dev libvorbis-dev
  patchelf xz-utils file binutils gnupg`, all with `--no-install-recommends` and
  `-o APT::Sandbox::User=root` for this single-ID namespace.
- Install `policy-rc.d` returning101 **inside that root** to prevent service starts.
- Old package postinst ownership of unmapped service/group IDs can return
  `EINVAL`. Compile `desktop/development/baseline_ownership.c` using that root's
  compiler, and preload it only for its package configuration/install commands.
  It suppresses only this build-root ownership-bookkeeping case, not other
  permission/path failures. It is never preloaded by or shipped with OrBeats.
- `baseline-toolchains-lock.json` records pinned Rust1.90.0 and standalone
  CPython3.12.16 vendor archives/checksums. Install only rustc, cargo and the
  x86_64 standard library inside the root, not the host toolchain directories.
  Verify archive hashes and use safe tar extraction before running install.sh.

APT signatures and exact package lists were recorded for the prototype. The APT
repository is not a frozen date snapshot; a bit-for-bit reproducible public build
still needs dependency/source closure, including the standalone Python toolchain.
Scratch `pip-install-report.json` records download hashes and `pip-freeze.txt`
records exact Python versions. Do not substitute the host's Python3.14 wheels.

Stage only the curated runtime `FILES`, own LICENSE and desktop source into
`temp/SCRATCH/source`; never recursively copy the full checkout, user profile,
private game input or `.tools`. A crates registry cache/index may be copied, but
not Cargo credentials or global configuration. Keep Cargo.lock and build locked.

## Build sequence inside the root

Use the project-local venv created with the pinned Python3.12 interpreter. Run:

1. `build_media_linux.py`, then `build_codecs_linux.py` to rebuild static FFmpeg
   and Xiph libraries **inside the baseline**, not by copying Arch-built binaries.
2. `freeze_backend.py --media ... --output ...` builds the helper. It omits the
   generated `libmvec.so.1`: that library references `GLIBC_PRIVATE` and must match
   the runtime's libc. The normal OS GLIBC package supplies it. Source-built
   codecs remain bundled; codec discovery is not relaxed.
   `build_legal.py` also verifies the recovered fsb5MIT notice/provenance against
   all five installed package source files and includes only these explicit notice
   files in the frozen helper. A changed dependency or notice fails the build.
3. Build/test the native Rust shell with the pinned Rust, `--locked`; use the
   Linux packaging config and pinned AppImage tools. `stage_candidate.py` creates
   the exact candidate resource mapping. Build Tauri's AppImage locally.
4. Run `seal_appimage.py` with the pristine helper. Tauri/linuxdeploy rewrites
   helper libraries, so never publish its initial image or disable runtime hashes.
5. `audit_linux_baseline.py --appdir temp/.../OrBeats.AppDir --output temp/...
   --maximum-glibc 2.35` checks **every ELF**, numeric and symbolic ABI tags,
   refuses `GLIBC_PRIVATE` and build-only/private files. It emits no legal or
   clean-machine approval. This audit complements actual runtime tests.

## Current 0.1.13 preparation

The same pinned baseline now produces desktop 0.1.13, with sealed helper1749files /
AppDir2336files. The final image is 179,902,968 bytes, SHA-256
`52c60618f35d5746d67c6d4c7d8cf0f393f74fd98fcb7c76202bf90592c67cca`;
all467ELFs still meet GLIBC<=2.35. Actual-image runtime testing verifies one
visible authenticated view and no resurfaced status view on ordinary close.
The backend drains, exits cleanly and leaves a fresh paused queue. This is a
local candidate, not a published release or blanket installer/legal approval.
See [current release checklist](../../docs/public-release-checklist.md).

## Earlier 0.1.6 candidate and evidence

- `temp/linux-baseline-work/source/temp/appimage-baseline-release-sealed-01/OrBeats_0.1.6_amd64.AppImage`
- **179,759,608 bytes**, SHA256
  `fd5a0e902c2da385776595892dcb560ae992abbafa74b7577c23be47d4103551`.
- Sealed helper1744files / AppDir2331files. All **467 ELF files** pass the numeric
  GLIBC<=2.35 and no-private-GLIBC ABI gate. Four locked Rust tests pass.
- `temp/appimage-baseline-release-network-smoke/native-smoke-result.json`: actual image
  in a **separate fresh Ubuntu22.04 runtime root**, no build tree or host `/usr`,
  real authenticated UI, privateXvfb, ordinary WM close and backend drain, paused
  fresh state, no PS4 writes, no development WebKit overlay or sandbox disabling.
- Runtime root contains base OS plus normal graphics/font/CA libraries: EGL/GL/
  GLES/Mesa, X11 dependencies, DBus, fontconfig/freetype/harfbuzz/fribidi and fonts.
  Normal DNS/hosts configuration is supplied read-only: OCI layers otherwise omit
  their runtime resolver and discovery fails with `Temporary failure in name
  resolution`. The final networked screenshot shows the live discovery feed.
  No host GTK/WebKit, Python, FFmpeg or development/compiler packages. It uses the
  host kernel and virtual X server; this is **not** a full clean-machine/VM claim.
- `temp/appimage-baseline-release-modern-smoke/native-smoke-result.json`: same final
  image also opens/closes on this newer Arch host, using bundled WebKit.
- `temp/appimage-baseline-release-offline-proof/result.json`: extracted actual image
  verifies runtime hashes and converts a synthetic five-difficulty12s chart,
 529200samples, inside the separate Ubuntu runtime with empty PATH and no host
  `/usr`/Python/FFmpeg. No FTP, no user profile, no PS4 writes.

Both native tests use `--appimage-extract-and-run`. Default/FUSE launch, real
Wayland/hardware drivers, distro/VM coverage, upgrade/
uninstall and complete legal/source closure remain gates. Test state is fresh;
existing web companion/queue and console are not modified by these probes.

The final shell is compiled with Cargo's **optimized release profile**, not the
previous debug profile. The image is about171.4MiB (17.7%smaller than the new
baseline debug candidate). `temp/linux-baseline/optimized-build.txt` records the
build and four passing release-profile Rust tests. Full host suite with this
helper: **1567passed124skipped**, one inherited Starlette deprecation warning.

`temp/appimage-baseline-release-seeded-state/native-smoke-result.json` also proves
an actual image launch/ordinary close with synthetic preexisting state: byte-exact
settings, pending entry/history unchanged and paused, older runtime and local
transaction recovery retained. This is a test-only seeded profile, **not** an
actual installer/uninstaller or old-executable-upgrade approval. The instrumented
private-Xvfb probe is `temp/linux-baseline/seeded-state-proof.py`; it never reads
the user's configuration and never starts the pending fixture job.
