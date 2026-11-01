# Next candidate — 0.1.18 (not published)

Commit, push and native Windows CI are approved for this testing candidate.
No tag or public release: Windows user testing and separate approval remain required.
The public 0.1.16 release assets must not be replaced.

- Desktop 0.1.18 / companion 0.7.34 / pipeline 0.5397.
- Main 0.8079 and Extras 0.0015 unchanged; no new plugin/hardware parity claim.
- Move Setup from permanent navigation to the Console & settings header; retain
  automatic incomplete first setup. Show transfer/conversion stages and elapsed
  time, reject duplicate checks, and save bounded private setup diagnostics.
- Fix Windows template cleanup: UnityPy receives bytes with the source stream
  already closed, not a retained path reader. The published Windows helper under
  Wine reproduced WinError 32 on temporary source.bundle; changing the loader
  made the same real read-only checker succeed. This is not native Windows proof.
  Strict schema validation, independent readback and cleanup errors remain enabled.
- Distinguish a confirmed import lock from FTP listing/creation permission errors.
  An abandoned lock's original cause remains unknown; no age-based auto-recovery.
- Add Installation recovery below Updates. Require explicit confirmation that
  Beat Saber and all writers on every computer are stopped. Refuse local busy/
  queue/setup/origin violations, unreadable/unstable library state, nonempty locks
  or pending staging/rollback files, including orphan owned-media directories.
  Archive inspection locally, recheck state, then remove only the empty lock.
  Preserve songs/plugins/backups; never automatically retry an import. Another
  computer's writer activity cannot reliably be detected by this app.
- One explicitly authorized empty-lock recovery was completed on the user's
  console with unchanged manifest and no other console writes or automatic retry.
- Source-safe and actual frozen smokes cover template-reader lifetime and scoped
  empty-lock recovery without game assets or network operations. Existing native
  Windows CI runs these plus the real nested worker launch/refusal tests.

Validation before commit: 2,062 host tests, 1,213 sanitized-source tests and 58
actual Linux frozen-backend tests passed, plus desktop/mobile offline browser
checks. Native Windows CI and the affected user's import remain to be checked.
Fresh-console raw-stock extraction still lacks user-observed hardware proof.
Private console inspection archives, caches and logs are excluded from publication.
