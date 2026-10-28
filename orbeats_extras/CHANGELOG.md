# OrBeats Extras changes

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
