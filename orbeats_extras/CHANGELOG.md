# OrBeats Extras changes

## 0.0015 — retain promotion hiding; withdraw experimental saber offset

- Return to the user-confirmed0.0010 feature set: promotion hiding, health
  auto-dismiss and read-only top-ten ScoreSaber display. Remove all saber-offset
  hooks, resource/template queries, menu controls and setting-file access from
  the build. Versions0.0011–0.0014 never produced visible controls in testing.
- Keep the exact promo implementation/profile and independent health/leaderboard
  behavior. Do not delete any existing console setting, log, save or song data.
- Version advances to0.0015 to distinguish the withdrawal build from test builds;
  this does not claim a new successful offset implementation.

## 0.0010 — hide the main-menu music-pack promotion

- Hide the identified music-pack promotion banner and its button by default
  when Extras is enabled. Preserve original main-menu activation/listeners and
  async loading; no stock/DLC catalog, ownership, store or playlist changes.
- Resolve only the two serialized promo references, verify their managed types
  and field offsets, root temporary objects, and deactivate their GameObjects
  after original activation. Refuse menu-root aliases or unavailable methods.
- Guard exact 2.04 activation/async/banner code fingerprints. The verified
  activation prefix contains complete nonrelative instructions, so the SDK
  original-call stub requires no custom relocation. Profile/API failures do not
  prevent independent health/leaderboard initialization. Refuse live unload if
  the promo hook alone is installed.
- Native sanitizer regressions cover original-call ordering, repeat activation,
  shared GameObjects, Button subclasses, schema/method/exception/root failures,
  cleanup and protected ordinary menu objects. Owned-code tests verify all four
  fingerprints and execute a synthetic SDK-style activation stub.
- User confirmed the promotion is hidden on the tested PS4 with0.0010. No layout
  reflow or replacement tile is promised. Build itself does not deploy or publish.

## 0.0009 — top ten scores and unprefixed names

- User confirms0.0008 displays ScoreSaber rows on PS4; health auto-dismiss is
  already confirmed. The stock visible panel has no usable scrollbar in that
  test, so deliberately request only the top10 instead of fetching100 rows.
- A single API page returns up to12 rows; retain at most10, preserving original
  ranks/scores/names/full-combo flags. Fewer available scores remain valid.
- Remove the added [SS/PC] prefix from player names; keep ScoreSaber identified
  in status text and documentation. No login, PSN scores or uploads are added.
- Regress the worker’s literal10-row request, one-page transport/truncation,
  managed name/rank/score publication, lifecycle and cleanup. Keep health,
  certificates, identity verification, cancellation and cache behavior unchanged.
- Local validation is separate from subsequent upload and PS4 confirmation.


## 0.0008 — remove the unsupported DNS retry-policy requirement

- Hardware0.0007 now shows the error text. Its log identifies the setup blocker:
  sceHttpSetResolveRetry returns0x804311fe before any request is sent. Do not
  attribute this pre-request failure to internet, clock or TLS verification.
- Remove that optional DNS policy setter and its production ABI declaration.
  Keep platform resolver defaults; no application retry loop. Mandatory phase
  timeouts, cooperative cancellation/deadline and all TLS0xbd checks remain.
- Regress with a canary setter returning the exact hardware error: assert it is
  never called while verified fake requests paginate100 rows. The same error
  on TLS configuration or mandatory DNS timeout must still fail before send.
- Retain hardware-confirmed health auto-dismiss, visible statuses, diagnostic
  privacy and scoped cleanup. No console/library/main-plugin/settings changes.
- Local candidate only. Removing the observed setup blocker does not establish
  successful PS4 HTTPS, populated rows or controller scrolling.


## 0.0007 — HTTPS diagnostics and active status panel

- User confirms health auto-dismiss on hardware0.0006. Retain that exact hook.
- Animals identity and callbacks work, but native fetch returns Network. Log
  failing SDK operations and hexadecimal results plus available request errno
  and TLS verification details, without hashes, player data, URLs or bodies.
- Keep certificate/hostname/date/CA verification and SNI enabled. No TLS bypass,
  shared Net reinitialization, background retry loop or arbitrary endpoint.
- Keep the empty managed table parent active before showing loading/status text.
  Hiding the table may also hide a child loading control in the game prefab.
- Regress setup failures, send/TLS errors, unavailable diagnostic APIs, no logger,
  privacy and resource cleanup. Native and UI fake tests are not console proof.
- Local diagnostic candidate only: no network root cause or successful PS4
  score display established yet; no console files changed during development.

## 0.0006 — health activation repair and callback diagnostics

- Hardware0.0005 installs both hooks but user still acknowledges the warning and
  sees a blank leaderboard. Owned native disassembly shows startup inlines the
  resolver: hook the health view activation, not the unused resolver helper.
- Preserve the original activation, class/field/state guards and native0.25s
  dismissal. Do not call agreement, coordinator-completion or tracking handlers.
- Explicitly relocate the verified activation prefix: preserve its RIP-relative
  byte comparison, RAX, flags and continuation without a truncated displacement.
  Keep the SDK original-byte restore stub intact and refuse live unload.
- Log selection/activation/input-pump and managed schema/method faults, statuses,
  native reply outcome and row publication. No player names/hashes/body logging.
- Execute the production trampoline on synthetic native code under host memory
  sanitizers; retain real callback/UI/worker/transport and exact-profile tests.
- Local candidate only: health behavior and the unresolved leaderboard path still
  require PS4 validation. No plugin deployment, map or library changes.

## 0.0005 — deferred guarded startup

- Hardware 0.0004 logged `unique game module unavailable; no hooks installed`;
  neither health nor leaderboard hooks ran. Wait off the loader thread for up to
  ten seconds for the exact unique IL2CPP module, instead of checking only once.
- No retry or relaxed matching for invalid/ambiguous modules, code signatures,
  missing exports or conflicting hooks. Module enumeration errors are logged.
- Cancel and join startup before unload; continue refusing live unload once any
  game hook has been installed. No detached startup thread.
- Repair permissions only on the opened own append-only log descriptor; retain
  old diagnostics. Log worker entry, policy, module base and installation result.
- Actual module_start/module_stop tested with deterministic fake SDK scheduling,
  delayed module availability, timeout, malformed/duplicate modules, cancellation,
  failed creation/join and diagnostic errors. UI/network tests remain separate.
- Hardware validation of 0.0005 is still required; no map/library changes.

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
