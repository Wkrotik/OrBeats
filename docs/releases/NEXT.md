# Next release — unreleased changes

0.1.20 is published from exact tested commit
`a83d7424ed8626c2c46f73c06e308a12c890dd03`.

## Sidebar cleanup (web interface 0.7.37)

Remove the redundant sidebar version label, its one-use ping request and styles.
The old “App” label displayed the web interface version (0.7.36), not desktop
0.1.20. Desktop/plugin version checks remain in Settings → Check updates; the
backend ping endpoint remains available for diagnostics.

This is a separate NEXT-release commit, not part of the published 0.1.20 binaries.
The owner explicitly requested no additional Windows CI build for this cleanup.
Local browser regressions check the absent footer and preserved Settings version
output; no tag, release, console write or automatic update is created here.
