# Private source repository and candidate CI

The private `Wkrotik/OrBeats` repository starts with a reviewed source-only snapshot,
not inherited history. The original local checkout/history is untouched. The
exporter is `beat_saber_deluxe/development/scripts/prepare_source_repository.py`;
its output must be a fresh `.publication/` directory. Review and commit/push are
separate operations. Never add private game templates, song ZIPs, catalog dumps,
console profiles/backups, agent conversations, built binaries or caches.

## GitHub Actions

Only `.github/workflows/private-build.yml` is active in the export. There is no
Pages deployment, tag-triggered release, public publication or PS4 operation.
Actions are pinned to commits, prerequisites are installed only on disposable
GitHub-hosted runners, and artifacts expire after seven days. Windows runs consume
private Actions minutes; the workflow is bounded by job deadlines, not scheduled.

- Linux runs the **declared source-only regression subset** listed in
  `desktop/development/source-ci-tests.json`, then builds the plugin using pinned
  OpenOrbis/GoldHEN sources. This is not the complete owned-input local suite.
- Windows builds FFmpeg/Ogg/Vorbis from pinned source, verifies FFmpeg's signature,
  freezes the native Python helper, exercises a synthetic import with only Windows
  System32 on PATH and a private loopback bootstrap/STOP sequence, then builds/tests
  the MSVC shell and an **unsigned NSIS testing candidate**.
- Private Actions artifacts contain only the candidate, native plugin and bounded
  synthetic build reports. They are not public releases or legal/platform approval.
- A report-only job writes bounded build-log excerpts to `latest.json` on the
  private `ci-status` branch. Only this job has repository write permission. Build
  jobs are read-only and checkout does not retain credentials. This permits reading
  CI results through the existing repository API without opening issue forms,
  adding access tokens to the checkout or uploading personal logs.

Still required separately: real Windows GUI and fresh install/upgrade/uninstall
checks, clean-device testing, full dependency/corresponding-source obligations,
signing/reputation policy, and explicit approval before making a public release.
The source-only suite's legacy/catalog/template gaps remain listed explicitly;
replace them with synthetic fixtures rather than uploading owned assets.
