# Next local candidate — 0.1.19 (not published)

Commit/push and native Windows CI are approved for this testing candidate.
No tag or public release: Windows user testing and separate approval remain
required. Do not replace the public 0.1.16 release assets.

- Desktop 0.1.19 / companion 0.7.35 / pipeline 0.5398.
- Main 0.8079 and Extras 0.0015 unchanged.
- The affected user's 0.1.18 song installation succeeded. Setup logs showed
  native NumPy initialization inside an HTTP request thread; the first check
  eventually completed, while another log ended during native initialization.
  A 45-second stack dump is diagnostic, not cancellation or proof of deadlock.
- Move synthetic template conversion and native audio imports into a separate
  allowlisted, local-only helper process. Stream its phases and diagnostics;
  keep HTTP status requests responsive. Preserve strict conversion, independent
  readback, bounded files, byte-backed UnityPy loading and failed-worker refusal.
- Reuse an intact, hash-verified local template without FTP or another conversion.
  Refuse unnecessary extraction before opening FTP. Pending extraction settings
  still require explicit restoration on the correct console; never auto-clear
  that obligation or mark setup complete before restoration.
- Show state-aware controls: extraction disabled when a template is already ready
  or extraction is pending; finalization enabled only for pending restoration.
  Explain when steps 3 and 4 should be skipped.
- Add source/frozen/native-CI coverage for actual child dispatch, HTTP polling
  during native imports and invalid-template refusal, without game assets or FTP.

Local validation: 2,066 host tests, 1,217 sanitized-source tests and 60 actual
frozen-backend tests passed, plus desktop/mobile offline browser checks and an
actual frozen owned-template conversion. Native Windows CI/user retesting and
fresh-console extraction remain validation gates. Private logs, caches and
console inspection archives are never part of the source export.
