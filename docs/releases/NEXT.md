# Next release — unreleased changes

0.1.20 is published from exact tested commit
`a83d7424ed8626c2c46f73c06e308a12c890dd03`.

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
