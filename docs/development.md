# Development

[← OrBeats](../README.md)

## Reports and contributions

Use the [issue chooser](https://github.com/Wkrotik/OrBeats/issues/new/choose):

- **Bug report:** versions, reproduction, expected/actual behavior and sanitized
  evidence. Installation failures include the failed step and observed recovery.
- **Feature request:** the problem, proposed behavior and success criteria.
- **Compatibility / test report:** successful or failed setups and measurements,
  distinguishing installation/readback from browsing, previews and actual gameplay.

The released 64-song cap is an implementation bound, not a measured PS4 maximum.
Do not disable safety guards or exceed your installed build's supported limits
just to file a test report. Mark untested steps and unknown versions honestly.
All issues are public: redact personal data and secrets; do not upload game files,
songs, saves, dumps or backups. Discuss suspected vulnerabilities privately with
the maintainer rather than exposing exploit details in a public issue.

Pull requests have a short validation/compatibility checklist. State what was
and was not tested, preserve installation/recovery guards and upstream licensing,
and keep private inputs out of the patch. Documentation-only PRs need no version bump.

## Source layout

| Directory | Purpose |
| --- | --- |
| `orbeats/` | Main plugin, conversion pipeline, companion backend and host tests |
| `orbeats_extras/` | Separate optional Extras plugin and development probes |
| `desktop/` | Tauri shell, curated backend packaging and platform tooling |
| `docs/` | Architecture, compatibility and release documentation |

Inherited console filenames in migration readers are intentional. Keep existing
pack IDs, library formats and local recovery data compatible when changing the
source layout. Upstream attribution and GPL notices must remain intact.

## Run the companion from source

Use Python 3.12+ and FFmpeg on PATH. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r orbeats/requirements-companion.txt
.venv/bin/python orbeats/webapp/server.py
```

On Windows, use `py -3` to create the environment and `.venv\Scripts\python.exe`
for the remaining commands. Open **http://127.0.0.1:8765**. This source server is
separate from the packaged desktop backend. A native plugin must be built before
source Settings can offer it for installation.

The optional checksum helper can be built with an installed GCC/Clang-compatible
compiler via `orbeats/development/scripts/build_native_hash.py`; the Python
fallback uses the same checksum when it is absent. Source audio conversion uses
open-source Vorbis/Ogg libraries where available, with PCM fallback. Packaged
media tools and their notices are covered by the [desktop docs](../desktop/README.md).

## Build and test

Use the project-local OpenOrbis/GoldHEN toolchain setup in `.devcontainer/`.
The main plugin's Makefile is in `orbeats/`; Extras has its own Makefile and
[development notes](../orbeats_extras/README.md). No general mod loader is shipped.

Run the complete local host suite:

```sh
bash orbeats/development/scripts/run_additive_host_tests.sh
```

[Source-only CI](../desktop/development/source-ci-tests.json) is a deliberately
smaller subset. Tests relying on user-owned game inputs are not grounds for
shipping those inputs. See [desktop packaging](../desktop/README.md) for frozen
backend, native shell, installer and clean-userspace validation.

## Artwork

The supplied root [`icon.svg`](../icon.svg) is the single source for product
artwork. SVG is used directly in the UI and README; native desktop resources and
Unity/the PS4 shell require transparent PNG/ICO derivatives.

With local `rsvg-convert` (librsvg) and Pillow available:

```sh
.venv/bin/python desktop/development/generate_branding.py
```

Commit the generated assets together. Rendering tools are development-only, not
runtime dependencies. Documentation screenshots use isolated sample data, never
personal queue history, console addresses or copyrighted game bundles.

## Changes and distribution

Commit completed features after regression tests. Distinguish host tests, native
builds, deployment readback and user-observed hardware behavior. Never deploy
while the title is running or launch it on someone else's behalf.

Keep game dumps, source songs, configuration, logs and local backups out of Git.
The [release checklist](public-release-checklist.md) tracks installer, license and
corresponding-source gates. Current progress belongs there and in changelogs,
not in the project's introduction.
