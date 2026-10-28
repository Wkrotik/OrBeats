# OrBeats Extras changes

## 0.0004 — anonymous leaderboard integration

- Connect verified HTTPS/decoder to one native worker, a latest-selection mailbox
  and eight bounded TTL cache entries. Cancel/invalidate on chart/view changes;
  no managed objects cross threads and no stale/partial board is published.
- Replace the existing game's leaderboard lifecycle for this candidate. Build
  genuine managed ScoreData/List rows on the UI thread, label names `[SS/PC]`,
  hide PSN-only scopes and preserve base binder cleanup/original input processing.
  No Sony subscriptions, account flow or score upload is added by this panel.
- Support verified imported Standard charts, up to100 rows, with clear missing
  identity/unsupported chart/empty board/HTTP error/rate-limit status. Stock/DLC
  and other characteristics do not query guessed or mismatched identities.
- Add optional original-content SHA1 exchange in pipeline0.5392/source companion
  0.7.27, bound to the exact installed descriptor; safely add it on reimport.
  No library-format or main-plugin change. Old imports need the new sidecar.
- Add actual callback/worker/table/identity ASAN/UBSan tests and exact owned code
  checks. Release/debug native builds are local evidence only. Default health
  auto-dismiss remains unchanged from0.0003; no additional Extras menu/settings.
- Not deployed or PS4-tested. TLS, rendering/controller scrolling, coexistence,
  startup health behavior and a rebuilt desktop package remain release gates.

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
