# OrBeats Extras changes

## 0.0003 — default health-warning suppression and native HTTPS transport

- Hide the health warning by default when Extras is enabled, as requested. Keep
  the native health-only coroutine path and all class/code/state checks intact.
- An explicit SHOW token restores the warning. Unreadable/malformed settings
  preserve ordinary startup; retain the older skip token for compatibility.
- Add a worker-thread-only ScoreSaber HTTPS transport with verified certificates,
  hostname/CA/date checks, bounded responses, phase timeouts, cancellation checks,
  no redirects, cookies, auth, score uploads or automatic retries.
- Test the actual transport against fake platform imports with ASAN/UBSan,
  including resource cleanup on failures and withholding partial results.
- This is not connected to a worker, selected chart or leaderboard UI yet, and
  has not been deployed or tested on PS4. The health screen may briefly appear
  before the native dismissal coroutine runs; no tracking or agreements bypass.

## 0.0002 — native leaderboard response handling

- Add a native ScoreSaber page decoder and bounded top-50/top-100 row assembly.
- Require original content SHA1, explicit Standard difficulty, consistent ranks,
  pagination, scores and totals. Refuse ambiguous fields and malformed responses;
  clear failed results. Sanitize player names for the game's text renderer.
- Vendor cJSON 1.7.19 with the unchanged MIT license, source hashes, a nesting
  limit and response-size bound. No external player pictures, login or uploads.
- Add native AddressSanitizer/UBSan regressions; retain the opt-in health hook.
- Console HTTPS, identity exchange, selection lifecycle, leaderboard UI and the
  Extras menu remain unfinished. This version has not been deployed to PS4.

## 0.0001 — health-only prototype and protocol research

- Add a fingerprinted, opt-in health-warning resolver hook using the game's own
  dismissal coroutine, without bypassing agreements or headset tracking.
- Add an anonymous Python ScoreSaber protocol probe and fake-network fault tests.
- This prototype has not been verified on hardware.
