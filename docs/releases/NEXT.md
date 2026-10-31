# Next release — scheduled for 0.1.16

User request: include the new OrBeats Extras feature in the next otherwise-needed
release; do not publish a release just for this feature. Existing v0.1.15 assets
must remain unchanged. This note does not authorize a new release on its own.

- Current local Extras version: 0.0015 (orbeats_extras/include/health.h).
- Feature: hide the main-menu music-pack promotion/banner and its button, while
  retaining health auto-dismiss and the read-only top-ten ScoreSaber display.
- orbeats_extras/CHANGELOG.md records user hardware confirmation for promotion
  hiding in 0.0010. Version0.0015 retains that feature set and withdraws the
  unsuccessful experimental saber-offset work from0.0011–0.0014. Do not advertise
  saber offsets or infer independent hardware validation of0.0015 from0.0010.
- At the next approved release, review the latest Extras state and validation,
  build/test it with that release, and include the same new Extras plugin in
  both desktop bundles and the standalone release download. Update the release
  manifest version/size/digest, relevant documentation and notices as needed;
  verify all packaged copies agree. Do not accidentally reuse the old0.0009
  plugin from v0.1.15 or old frozen desktop payloads.

The user subsequently approved release 0.1.16 with the issue #1 fix and this
Extras update. See 0.1.16.md for the release scope. Publication still requires
matching plugin copies, native validation and final release checks; no existing
0.1.15 assets are to be replaced.
