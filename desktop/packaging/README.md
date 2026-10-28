# Dual-platform installer candidates

User-approved scope: **Windows x64 and Linux x64**. These files prepare candidates,
not a public release. No automatic publisher, updater or external CI run is added.

| Target | Initial installer | Proposed supported baseline | Still needs proof |
|---|---|---|---|
| `windows-x64` | NSIS `.exe`, current user | Windows 10/11 x64 with Microsoft WebView2 | Real song installation with visible logs; interactive installer, upgrades and uninstall |
| `linux-x64` | **AppImage primary**, optional `.deb` | Ubuntu 22.04+ / compatible Linux with GLIBC >=2.35 and normal graphics/font runtime | Broader clean-machine/FUSE/driver and upgrade validation |

See [AppImage assembly and local evidence](APPIMAGE.md). A real development
AppImage now passes local launch/close and offline conversion; it is not a public
release.

The current Linux0.1.10 image is built against Ubuntu22.04, with all467ELFs
meeting GLIBC<=2.35 and separate minimal-userspace launch/close tests. Older
Arch0.1.5 needed GLIBC2.44 and was superseded. An ABI audit and private-display
test are not universal Linux compatibility or public-release approval. ARM and macOS are not claimed targets. AppImage portability must still be tested.

Windows' embedded WebView2 **bootstrapper needs an internet connection** if the
runtime is absent. It does not make the installer fully offline. Review Microsoft
runtime distribution terms before shipping it. Neither platform requires a user
Python installation; the target-native frozen helper/media must be bundled.

## Target media profiles

`desktop/backend/media_profiles.py` enumerates exact base/full payloads for each
OS. The public candidate stager requires the full codec profile. Linux recipes
are available; private native Windows source/media/frozen/NSIS builds passed in
Actions run40674610679. Actual Windows song installation still needs diagnosis;
new0.1.10 output fixes are a candidate, not a claim that this symptom is resolved.

- Linux tools: `media/bin/ffmpeg`, `ffprobe`; `media/lib/libogg.so.0`,
  `libvorbis.so.0`, `libvorbisenc.so.2`.
- Windows tools: `media/bin/ffmpeg.exe`, `ffprobe.exe`;
  `media/lib/libogg-0.dll`, `libvorbis-0.dll`, `libvorbisenc-2.dll`.
- Exact legal/source recipe inventories and hashes are required, not just binaries.
- Windows PE validation checks x64/PE32+ and EXE-vs-DLL kind. Host freezing and
  execution reject the other platform's profile. Linux fixtures retain the
  established ELF check; actual helper staging also requires x86_64.
- Windows DLL loading is limited to the app's DLL directory and System32, never
  CWD/PATH. Native Windows frozen synthetic import exercised this loader; broader
real-map and installer lifecycle tests remain required.

## Stage a candidate (does not build or install it)

From repository root, using a **fresh** project-local output:

```sh
.venv/bin/python desktop/packaging/stage_candidate.py \
  --target linux-x64 \
  --backend temp/TARGET-FROZEN/dist/orbeats-backend \
  --output temp/linux-installer-candidate
```

For Windows use target `windows-x64` and a Windows-produced frozen folder.
The staging format can be checked cross-platform; native execution cannot.
The stager refuses mixed/incomplete media, wrong helper type, escaping links,
private console profiles/game inputs and oversized payloads. It copies/readback-
checks the frozen tree and emits `candidate-manifest.json` and
`tauri-candidate.json`. Relative internal file aliases are flattened.

On the appropriate clean build target, a reviewed/pinned Tauri CLI can consume:

```sh
cargo tauri build --config /absolute/path/to/tauri-candidate.json
```

Run from `desktop/src-tauri`. Both profiles parse against the actual locked Tauri
configuration types. No successful installer build is implied by that parser
check. The base Tauri config deliberately keeps bundling disabled.

## Release gates

1. Target-native, pinned build inputs and complete dependency/source notices.
2. Compatible OS ABI for native shell, Python and every included shared library.
3. Offline fixture conversion and Vorbis round-trip without host tools/codecs.
4. Native window readiness, error handling and graceful close on both targets.
5. Install/upgrade/uninstall tests preserving settings, paused queue/history and
   local recovery archives; never auto-start pending console uploads.
6. Real PS4 safety regression and supported-map limitations in user documentation.
7. Windows signing/SmartScreen policy and artifact checksums/provenance.
8. **Separate user approval** before commit/push, CI mutation, tagging or publishing.

Current validation includes local actual-AppImage launch/close and offline
conversion, plus Windows profile/PE/config fixtures only.
No Windows runtime or clean-baseline Linux installer is claimed to pass.
