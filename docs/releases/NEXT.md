# Next testing candidate — 0.1.20 (not published)

The user approved disabling unused native file-drop handlers, making setup work
more visible, and committing/pushing the validated changes for Windows CI.
No tag or public release; public latest 0.1.16 remains untouched.

- Desktop 0.1.20 / companion 0.7.36 / pipeline 0.5398.
- Main 0.8079 and Extras 0.0015 unchanged.
- Disable the unused Tauri native file-drop handler in BOTH status and main
  windows. Wine/Soda crashed in ole32!RevokeDragDrop before backend startup.
  Use the supported builder API, not a shipped binary patch, GPU/sandbox flags
  or changes to the user's original bottle. Ordinary DOM drag/drop is retained.
- Put a prominent setup activity panel above the instructions: animated,
  indeterminate loading bar, current phase and elapsed time. No fake percentage;
  respect reduced motion, stop on completion/error and ignore late status polls.
  Keep restoration obligations and scoped write confirmations unchanged.
- Regressions: both window builders, desktop/mobile bar visibility/placement,
  reduced motion, success/refusal cleanup and late-poll error preservation.

Validate full host/source-only/frozen tests and native builds, then retest the
actual newly built Windows shell in an isolated network-disabled Bottles copy.
Bottles startup success is not proof of real PS4 import or fresh extraction.
Private crash logs and copied prefixes stay out of source publication.

Local validation passed: 2,067 host tests, 1,218 tests on the actual curated source
export, 61 actual frozen-backend tests, seven native Rust tests and the native
Ubuntu 22.04 release build. Desktop/mobile browser fixtures passed, including
visible running/error/completed states, reduced motion and stale-poll guards.
Native Windows CI and source-built Bottles startup are still to be checked.
