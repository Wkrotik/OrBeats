# Linux AppImage — primary download, development prototype

The first Linux release will provide an **x86_64 AppImage** as its primary
Linux artifact; `.deb` remains optional. Windows x64 NSIS is still in scope.
`linux-x64.json` lists `appimage` first and bundles the GTK/GStreamer media
framework. Neither a container nor host Python/FFmpeg should be required by users.

## Current baseline candidate

Desktop0.1.6 is now rebuilt inside **Ubuntu22.04 / GLIBC2.35**, including the
shell, frozen Python3.12 helper, FFmpeg and codecs. All467ELFs meet that bound
without private GLIBC interfaces. The actual final image opens/closes in a
separate Ubuntu runtime with no host `/usr`/WebKit/Python/media tools and also
on the modern Arch host; isolated offline conversion passes. The recovered
fsb5MIT notice/provenance is included and checked against its exact source.
See [baseline recipe and final artifact](LINUX-BASELINE.md).

The optimized Linux release-profile image is now **179,759,608 bytes** and also
preserves synthetic prior settings/queue/recovery on restart. DefaultFUSE, full
clean-machine/Wayland/driver tests, Windows execution and complete legal/source closure remain open. Nothing is
published. Prior0.1.5 below is a retained development reference only.

## Earlier Arch prototype evidence

Desktop0.1.5 was assembled into a real type2 AppImage, **240,249,336 bytes**
(about229MiB, debug build). Its real authenticated window opened on a private
virtual X display **without the development WebKit filesystem overlay**, then
closed normally and drained the owned frozen backend with a fresh paused queue.
The actual image was also extracted and its frozen import task converted a local
12-second/five-difficulty fixture with no Python/FFmpeg on PATH. Resource hashes
passed. No real console profile or PS4 write was involved.

This proves local assembly/launch/close/offline conversion, **not release
portability**. Those earlier Arch artifacts depend on GLIBC2.44. The baseline
rebuild is now complete as described above; broader clean-distro X11/Wayland,
license/source closure and first-install/upgrade tests remain required. The WebKit sandbox was not disabled.

## Running an approved future AppImage

On a supported x64 Linux machine:

```sh
chmod +x OrBeats_VERSION_amd64.AppImage
./OrBeats_VERSION_amd64.AppImage
```

The ordinary AppImage runtime usually uses FUSE. Where FUSE is unavailable,
use the standard extraction-based launch without installing FUSE:

```sh
./OrBeats_VERSION_amd64.AppImage --appimage-extract-and-run
```

The latter path is the one actually tested here. It needs executable temporary
storage and sufficient disk space for extraction. AppImage is not a guarantee
for every distribution/CPU/graphics stack. The proposed GLIBC2.35 baseline is not
yet achieved; do not advertise it as a tested minimum or distribute this prototype.

## Reproducible development assembly

1. Build the complete Linux frozen backend/media/codec payload first; see
   `desktop/README.md`. Stage it with `stage_candidate.py --target linux-x64`.
2. Prepare **fresh** project-local AppImage tool copies:

   ```sh
   .venv/bin/python desktop/development/setup_appimage.py \
     --output .tools/appimage-build-N
   ```

   `appimage-linux-tools.json` pins CLI2.12.4, linuxdeploy07333c6, AppRun and
   the output plugin against their upstream GitHub release SHA256 digests.
   Verified originals remain separate from Tauri's mutable working cache.
   These are checksum pins, not a claim of independent signature verification.
3. On the native Linux build target, use the returned CLI/cache and target config
   to build and bundle. `patchelf` must be on build PATH for GTK/GStreamer plugins.
   Local tests used project `.venv/bin/patchelf`0.17.2 and the read-only WebKit
   build namespace; no system package installation. The GTK/GStreamer helper
   scripts embedded by Tauri and all newly bundled system libraries still require
   release dependency/license review.

   ```sh
   export XDG_CACHE_HOME="$PWD/.tools/appimage-build-N/cache"
   # Run from desktop/src-tauri with the reviewed native build prerequisites:
   /absolute/path/.tools/appimage-build-N/bin/cargo-tauri build \
     --config /absolute/path/temp/STAGED/tauri-candidate.json --bundles appimage
   ```

4. **Do not ship that initial image.** linuxdeploy rewrites every discovered ELF,
   including the backend codec resource files, invalidating their integrity hashes.
   Run the finalization recipe against the generated AppDir:

   ```sh
   .venv/bin/python desktop/packaging/seal_appimage.py \
     --appdir desktop/src-tauri/target/BUILD/bundle/appimage/OrBeats.AppDir \
     --backend temp/FROZEN/dist/orbeats-backend \
     --output temp/SEALED-CANDIDATE \
     --plugin .tools/downloads/appimage/linuxdeploy-plugin-appimage.AppImage
   ```

   It clones the generated AppDir into fresh output, replaces only its generated
   backend with the original verified frozen tree, corrects the generated
   `.DirIcon` link, checks complete byte-for-byte backend identity, then runs the
   pinned **output-only compression plugin**. It never alters the resource
   manifest or relaxes its checks. Private game/profile files and escaping links
   are refused. `SHA256SUMS` and `assembly-report.json` are emitted; the report
   explicitly records legal/baseline approval as false.
5. Test the **final** image, not merely the unpackaged native binary:

   ```sh
   .venv/bin/python desktop/development/smoke_linux.py \
     --output temp/APPIMAGE-SMOKE \
     --appimage temp/SEALED-CANDIDATE/OrBeats_VERSION_amd64.AppImage
   ```

   This uses a private Xvfb and fresh profile, no development WebKit overlay, no
   PS4 profile and no FUSE requirement. Never substitute sandbox-disabling flags.
   Separately test default FUSE launch and clean target machines before release.

## Earlier Arch local evidence (reference only, not published)

- `temp/desktop-appimage-final-02/OrBeats_0.1.5_amd64.AppImage`
- SHA256 `c41f8692927ef7ea550536850108ba1baeccdf48f13e00aeffb5386522938d4d`
- `temp/desktop-appimage-final-02/assembly-report.json`:1826sealed backend files,
  2595AppDir files, unchanged backend/resource hashes valid.
- `temp/appimage-native-smoke-final02/native-smoke-result.json`:actual window,
  WM close, owned backend exit, fresh queue paused, WebKit overlayfalse.
- `temp/appimage-offline-proof/result.json`:actual-image extraction, offline
  frozen conversion,529200samples,5difficulties,nohostPython/FFmpeg.

The build-output folder contains a tool copy, AppDir and reports for local
reproduction; it is **not** a release asset folder to publish wholesale.
