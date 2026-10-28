# OrBeats desktop — Tauri 2 work in progress

**Working Linux native-window/frozen-backend prototype, not a finished installer.**
The Tauri window now compiles and runs the real UI on a private virtual display.
No PS4 operations,
settings migration from the live companion, publication or release were performed
by desktop tests. The ordinary web companion remains independent.

## Implemented

- `src-tauri/`: OrBeats shell/Cargo.lock. No shell/FS/IPC plugin permissions,
  remote-domain capability or global Tauri object is granted to the web page.
  It expects its **own frozen backend executable**, validates private loopback
  readiness and restricts navigation to that origin. No host-Python fallback,
  port8765 discovery, replacement or termination.
- `backend/entrypoint.py`: the real existing web UI/API behind authenticated
  Host/bootstrap/cookie/Origin middleware. Binds and keeps an owned
  `127.0.0.1:0` listener; emits one private readiness line. Diagnostics go to
  stderr; bootstrap URLs are not access-logged. All reads require a session.
- Writable profile state is separate from curated immutable/versioned runtime
  code. Kernel-held state ownership prevents simultaneous app instances against
  one profile. A new profile starts with loopback FTP settings, not checkout
  credentials. Settings, staged files, queue and local recovery survive restarts.
- STOP, parent-pipe EOF and ordinary SIGINT/SIGTERM close mutation admission,
  repeatedly pause the queue, drain admitted mutations/runner/active queue item,
  save the paused snapshot atomically and exit. The parent never force-kills an
  active publication. Force-kill, power loss and the existing explicit Cancel
  action are **not** equivalent to a tested graceful close.
- `tools/runtime_dispatch.py`: frozen helpers re-enter a bounded pipeline/batch/
  BeatSage dispatcher rather than attempting `frozen.exe script.py`. No arbitrary
  helper paths. Source checkouts retain their normal Python-script behaviour.
- `build_resources.py`: exact reviewed code/data inventory, hash/size validation,
  traversal/symlink/unexpected-file refusal, atomic versioned workspace creation.
  Never copy checkout credentials, songs, acquired templates, dumps, caches or
  console backups. Public license/upstream attribution remains included.
- `freeze_backend.py`: project-local PyInstaller **onedir helper prototype**.
  Tested Linux helper bootstraps the existing API with **PATH lacking Python and
  all host tools**, and its actual child dispatcher runs pipeline `--help`.
  Source and frozen close-during-fake-FTP-publication tests prove readback/commit,
  local rollback archival and no retained remote rollback, before normal exit.

## Build/test the helper prototype

Use the project virtualenv with the existing companion dependencies. Only install
build dependencies locally (never a system package change):

```sh
.venv/bin/python -m pip install -r desktop/requirements-build.txt
.venv/bin/python desktop/freeze_backend.py --output temp/desktop-frozen-new
# Choose a fresh project-local output directory for every build.
ORBEATS_TEST_FROZEN_BACKEND="$PWD/temp/desktop-frozen-new/dist/orbeats-backend/orbeats-backend" \
  .venv/bin/python -m pytest beat_saber_deluxe/tests/test_desktop_backend.py -q
```

Source-helper alternative: generate resources with
`desktop/build_resources.py --output temp/fresh-runtime`, then launch
`.venv/bin/python desktop/backend/entrypoint.py --state-dir temp/isolated-profile
--resources temp/fresh-runtime`. The private readiness URL belongs to that process;
never paste it into reports/logs. Close stdin or send STOP to finish safely.
Do not use these isolated prototype profiles to manage the console yet.

## Private protocol contract

The parent receives exactly one bounded JSON line:
`{"protocol":1,"url":"http://127.0.0.1:PORT/_desktop/bootstrap/SECRET"}`.
The one-use secret is exchanged for an HttpOnly/SameSite cookie and redirect to
`/`. Parent `STOP\n` or EOF initiates draining, not process termination. Pending
work restores **paused**. No auto-resume of console writes after any restart.

## Linux native development validation (0.1.3)

The native shell now compiles, its three Rust policy/lifecycle tests pass, and a
private-Xvfb smoke opens the real OrBeats UI through the frozen helper. Closing
its window drains/exits the owned backend and saves a paused queue. This uses a
fresh loopback-only profile, never the existing web companion's console settings.

Arch x86_64 development prerequisites are pinned in
`development/linux-build-lock.json`. The setup script verifies each package's
SHA256 and detached signature against the read-only host Arch public keyring,
extracts into project `.tools`, and relocates only local pkg-config paths. It
never installs a system package or changes permissions/services. Requires the
existing host GTK3/libsoup stack, Arch keyring, gpg/gpgv and Python3.14 for zstd.

```sh
.venv/bin/python desktop/development/setup_linux.py
. .tools/tauri-linux/build-env.sh
cargo test --locked --offline --manifest-path desktop/src-tauri/Cargo.toml
cargo build --locked --offline --manifest-path desktop/src-tauri/Cargo.toml
.venv/bin/python desktop/development/smoke_linux.py \
  --output temp/fresh-native-smoke \
  --backend temp/desktop-frozen-new/dist/orbeats-backend/orbeats-backend
```

Use fresh project-local smoke output. The smoke stages a symlink to the specified
frozen helper beside the debug shell (refuses a different existing backend), and
uses private Xvfb/Xauthority plus a read-only bubblewrap library overlay. This
supplies WebKit's compiled process paths without changing `/usr`. `/dev` and
`/proc` must be bound correctly; a first incomplete test namespace omitted them
and crashed in JavaScriptCore random initialization, not OrBeats registration.
No WebKit sandbox/JIT security switches are disabled. The existing user's display
and PS4 profile are untouched. This is a development harness, **not an installer**.

The shell has a 30second private-handshake deadline, useful startup/crash status,
backend-death monitoring, idempotent stop/close handling, and explicit rejection
of popups, downloads and navigation away from its private origin. Status text
persists across page load; readiness URLs never appear in it. A backend that
cannot stop is not killed to satisfy a window-close deadline.

## Remaining gates — no release claims
- Source-built FFmpeg and Xiph codec profiles now pass frozen offline conversion
  and explicit bundled-codec/independent decode tests. This is not full dependency
  closure: the earlier Arch helper requires GLIBC_2.44. The new Ubuntu22.04
  candidate meets GLIBC2.35 and isolated-userspace tests; complete legal/source
  review, broader clean-machine and Windows tests remain open. The optional native
  hash helper is not bundled; its checked Python fallback remains available.
- A verified installer/resource layout for the entire helper and native tools;
  the tested debug shell currently uses a development resource-directory symlink.
  No remote Tauri capabilities may be added as a packaging workaround.
- Automated native-window timeout/crash and close-during-actual-import coverage.
  Rust policy tests, normal native close, and source/frozen fake-publication close
  are distinct evidence—not proof of every native-window failure scenario.
- Windows build/runtime/signing and clean-machine Linux installer tests. Windows
  state locking code exists, but has not been validated on Windows.
- Existing legacy lftp/game-data extraction paths are not silently made portable;
  source desktop helpers refuse unsupported frozen task paths. No phone support.

Evidence is local/ignored under `temp/desktop-backend/`,
`temp/desktop-frozen-02/`, `temp/desktop-next/` and
`temp/desktop-native-smoke-final/` (native screenshot/result). Final full host
suite1517passed124skipped, one inherited warning; three Rust tests pass. These
are development outputs, not releases.

## Optional minimal static Linux media payload (0.1.2)

```sh
.venv/bin/python desktop/development/build_media_linux.py \
  --output temp/fresh-media-build --jobs 8
.venv/bin/python desktop/freeze_backend.py \
  --output temp/fresh-frozen-media --media temp/fresh-media-build/payload
```

This verifies the pinned FFmpeg8.0.1 source/signature/key and builds static
FFmpeg/ffprobe with no external codec autodetection, GPL/nonfree code or network
protocols. The signing identity was pinned from **vendor HTTPS**, not an
independently certified key. Keep the provenance distinction when reviewing
release supply-chain trust. No host packages are changed. Full source remains in
the local build output; any release still needs its source/license offer reviewed.

The optional payload has an exact seven-file manifest including LGPLv2.1,
LICENSE.md, source lock and reproducible build script/command. Resource assembly
rejects extra/partial/tampered payloads and preserves executable modes. Installed
runtime tools are prepended for both server and frozen task paths. Source-only
resources without media retain their previous inventory and behaviour.

A frozen offline synthetic V3 import decoded/resampled audio and produced five
validated difficulties/529200samples with host Python and FFmpeg absent from PATH.
Evidence `temp/desktop-media/offline-final/`; full suite1521passed124skipped.
**Codec libraries are not isolated yet**: ctypes Vorbis/Ogg lookup may still use
host libraries. Do not equate this success with clean-machine readiness or a
complete real-song install. The native-window smoke and this new tool-payload
smoke are separate tests; their combined installer has not been built.

## Source-built codec profile (0.1.3 development only)

```sh
.venv/bin/python desktop/development/build_codecs_linux.py \
  --media temp/desktop-media-build-01/payload --output temp/fresh-codecs
.venv/bin/python desktop/freeze_backend.py --output temp/fresh-frozen \
  --media temp/fresh-codecs/payload
ORBEATS_RUNTIME_ROOT="$PWD/temp/fresh-frozen/dist/orbeats-backend/_internal/runtime" \
  temp/fresh-frozen/dist/orbeats-backend/orbeats-backend \
  --desktop-check-codecs /path/to/compatible-original-vorbis.ogg
.venv/bin/python desktop/development/audit_payload.py \
  --payload temp/fresh-frozen/dist/orbeats-backend --output temp/fresh-audit.json
```

The diagnostic disables host codec discovery and checks actual loaded Xiph paths,
FSB creation and independent decode. It does not open FTP or reuse the live web
profile. Inventory accepts either no media, complete minimal FFmpeg, or the full
codec+legal profile—never a partial mixture. Failed owned codec loads do not fall
back to the host. Linux profile activation is explicit and platform-checked.

**Not release-ready:** the new baseline helper meets GLIBC2.35. The fsb5 notice
has been recovered from an exact-source upstream commit and is bundled with
provenance. Full source/license/platform/installer gates remain tracked in
[`docs/public-release-checklist.md`](../docs/public-release-checklist.md).
No artifact has been published or represented as a clean-machine installer.

## Windows + Linux installer preparation (0.1.4)

Both x64 targets are required for the first release. See
[packaging/README.md](packaging/README.md) for candidate-only NSIS/deb configs,
complete platform media inventories, Windows PE/DLL-loading checks and staging.
Windows execution is not yet tested. Linux native prototype tests pass, but
the baseline rebuild now passes isolated Ubuntu userspace checks; actual
clean-machine installers remain release gates.

## Primary Linux AppImage (0.1.5 prototype)

AppImage is now the primary Linux target, with deb optional and WindowsNSIS still
required. The actual image opens/closes correctly on a private display without
the project-local WebKit overlay, and its extracted frozen helper passes offline
conversion without host tools. See [packaging/APPIMAGE.md](packaging/APPIMAGE.md)
for pinned tools, sealed-backend finalization and evidence. The debug prototype
is retained as a reference only. The current **0.1.6 Ubuntu22.04 / GLIBC2.35**
AppImage passes the separate runtime and modern-host checks; see
[packaging/LINUX-BASELINE.md](packaging/LINUX-BASELINE.md). Broader clean-distro,
FUSE/Wayland/driver and legal/installer tests remain open, not silently waived.
