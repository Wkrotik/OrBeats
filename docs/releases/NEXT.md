# Next release — unreleased changes

0.1.20 is published from exact tested commit
`a83d7424ed8626c2c46f73c06e308a12c890dd03`.

Desktop0.1.23 is a local Linux testing candidate containing the unreleased changes
below, not a published release. Main0.8079 and Extras0.0015 are unchanged.

## Existing-profile startup and clearer errors (pipeline0.5403 / web0.7.40)

- Existing completed imports avoid repeated first-setup navigation without
  claiming a validated local template. Pending restoration still forces Setup.
- Fix checkbox alignment and retain a 44px click target on desktop/mobile.
- Handle strictly validated legacy editor cursor/bookmark aliases. Explain
  unsupported authored geometry/lighting, mod dependencies and retained score
  identity conflicts; no object dropping, score overwrite or silent clamping.

## Faster batch management and import fixes (pipeline0.5402 / web0.7.39)

- One transaction removes a confirmed selection; no concurrent manifest writers.
- Use the setup-validated local conversion template instead of repeated FTP copies.
- Handle authored high-BPM bursts, signed arc tangents, provenance aliases,
  empty reserved V2 fields and independently rounded audio sample endpoints.
- Bound the menu preview, not gameplay audio or chart timing.
- Hide known incompatible maps; retain unknown results. Details can download and
  check walls without installing, with results tied to the exact revision hash.
- Geometry outside reviewed bounds, unreviewed chain counts and mod-dependent
  effects still refuse rather than being altered or silently discarded.

## Import preflight and InfoV4 palettes (pipeline 0.5401)

Support documented eight-digit RGBA hexadecimal palette colors, including
BeatSaver557e1 (Never Forget You), while preserving exact channel values and the
existing strict legacy-object/mod requirements validation.

Before conversion, recognize the same downloaded BeatSaver key and selected
revision in installed map provenance. Verify the installed bundle/cover/preview
and stable library, then report already installed without regenerating files.
Do not mistake a matching title, a different revision, local optional metadata,
compiled migration defaults or corrupt files for a proven installed version.
Unproven inputs retain full conversion and immutable collision checks.

BeatSaver557a6 (eyes) authors wall layer3. The owned PS4 2.04 native V4 converter
maps layers other than0/1/2 to floor-level Base. Keep its refusal, with an explicit
explanation; accepting the input would silently change wall geometry. Native wall
support would require separately validated runtime work, not looser host bounds.
No native/web/desktop version change or PS4 playback claim.

## Branding cleanup (pipeline 0.5400, web interface 0.7.38)

Use OrBeats in HTTP client identifiers, backup-tool messages, example configuration,
current feature docs, new synthetic test-song attachments and legacy static setup/help.
The theme audio and previously installed songs are unchanged. The setup link targets the real
OrBeats release, not an invented renamed upstream zip. Mark inherited demo/release
references as historical instead of rewriting their original credits or banners.

Keep legacy plugin filenames and old-binary recognition for compatibility. The
native startup log/toast already says OrBeats; the log appends, so old names at its
start may be from previous launches. No native version bump, console contact or log
clearing. These changes are local and unreleased; Main remains0.8079.

## InfoV4 conversion fix (pipeline 0.5399, issue #4)

Accept Beatmapper's `_editors` authoring metadata in InfoV4 instead of rejecting
otherwise supported maps. Keep unknown/mod-dependent fields fail-closed. The
reported BeatSaver4cb6c map converts locally; independent bundle readback checks
all496 notes,49 bombs,4 walls and source timing. This is offline evidence, not a
PS4 playback claim. No published app or plugin is changed by this local fix.

## Sidebar cleanup (web interface 0.7.37)

Remove the redundant sidebar version label, its one-use ping request and styles.
The old “App” label displayed the web interface version (0.7.36), not desktop
0.1.20. Desktop/plugin version checks remain in Settings → Check updates; the
backend ping endpoint remains available for diagnostics.

This is a separate NEXT-release commit, not part of the published 0.1.20 binaries.
The owner explicitly requested no additional Windows CI build for this cleanup.
Local browser regressions check the absent footer and preserved Settings version
output; no tag, release, console write or automatic update is created here.
