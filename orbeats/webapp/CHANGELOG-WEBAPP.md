## 0.7.26 — transparent product artwork

## 0.7.28

- Install/check the bundled optional OrBeats Extras plugin independently from the
  song library. Closed-title verification, exact GoldHEN registration, full
  readback and local rollback archives also apply to Extras.
- Explicitly check the official GitHub release for desktop/main/Extras updates.
  Plugin downloads require the release manifest's SHA-256, size and embedded
  version before the normal safe installer runs. Offline is not "up to date";
  desktop upgrades remain a manual download, never automatic execution.
- Remove the redundant sidebar companion label/theme button (theme remains in
  Settings), and isolate desktop main-panel scrolling from the fixed sidebar.
- Desktop0.1.13 starts the main view hidden until its authenticated document loads,
  hides both views while safely draining on close, and suppresses Windows worker
  console windows. No active console publication is killed to close faster.

- Use the supplied icon.svg in the sidebar, hero and favicon, without the former
  rounded background tile. Native raster derivatives keep transparent backgrounds.
- No install, queue or library behavior changes.

## 0.7.24 — preserve useful failed-job reasons

- Failure summaries prefer the actual exception/refusal rather than PyInstaller's
  generic last wrapper line. Complete raw logs remain available unchanged.
- Package pipeline0.5391 compatibility fixes; no automatic retry, queue mutation,
  feature loss or console update. Desktop0.1.11/plugin0.8077.

## 0.7.23 — platform output, owned SVG and GoldHEN-only connection

- Live workers explicitly decode UTF-8 with replacement and retain lifecycle
  completion on output errors. Immediate startup line distinguishes spawn from
  a silent child; frozen children flush output before exit.
- Smooth compositor activity indicator replaces native indeterminate progress;
  reduced-motion and success/stopped states retained. Owned SVG replaces note glyph.
- Main connection form asks only IP and saves2121/anonymous/empty password.
  Local conversion-seed fallback stays in separate advanced recovery, not FTP form.
- No automatic subnet scan or installation retry. GoldHEN service discovery is a
  separate best-effort feature; manual IP remains the reliable supported path.

## [0.7.22] — reachable active/last installation log

- Move collapsible log directly after current job and before pending/history lists.
- Bound the panel height with independent scrolling; follow only at the tail,
  retain reader position on incoming output, offer Jump to latest, and preserve
  full diagnostic copy/save. No auto-open, page scrolling or focus theft.
- Keep last output available after completion/failure; reset tail-follow only for
  a new job. Preserve queue/history and require explicit start/retry as before.
- Desktop/mobile offline browser fixtures exercise80history entries,300loglines,
  scroll pause/jump, closed-panel preference, last-job heading and no JS errors.

## [0.7.21] — legacy placeholder compatibility

- Ship pipeline0.5389 and expose the count of exact all-zero V2 wall placeholders
  ignored during import in job output. No queue migration or automatic retries.
- Existing settings, library, history and recovery remain untouched.

## [0.7.20] — playlist array candidate version

- Reflect current plugin0.8077 in the existing version surfaces. No library schema,
  feature flags, queue changes or additional PS4 operations are introduced.

## [0.7.19] — private desktop backend integration

- Existing UI/API run behind private loopback bootstrap/session authentication;
  ordinary source companion remains independent. Isolate persistent writable
  settings, staged files, queue and recovery from curated immutable resources.
- STOP/EOF pauses work, closes mutation admission, drains active requests/jobs and
  saves the queue paused. Kernel-held state lock prevents duplicate desktop use.
- Source/frozen lifecycle and fake-publication tests pass; native Tauri window,
  bundled media tools and clean-machine Windows/Linux installers remain pending.
  No automatic PS4 writes/retries, release or publication.

## [0.7.18] — InfoV4 palette-import compatibility

- Companion reports pipeline0.5386 for the bounded per-difficulty colour fix.
  No queue retry, UI redesign or automatic console changes.

## [0.7.17] — expanded native-map metadata

- Report genuine characteristic/difficulty routes and native feature capability
  markers. Discovery compatibility remains an unverified metadata hint.

## [0.7.16] — complete OrBeats plugin migration

- Installer registers only orbeats.prx, preserves INI whitespace/comments and
  other plugins, and retires the recognized legacy binary in one rollbackable
  transaction. Duplicate/global/foreign-title registration fails closed.
- Settings explicitly describes local recovery archives rather than console
  backup retention. Queue state is not automatically resumed or retried.

## [0.7.15] — environment-aware plugin capability

- Plugin setup publishes library_format2 for environment-aware0.8073+ candidates,
  preserving actual ELF hash/version evidence and byte-preserving plugins.ini
  handling. Refuse downgrades that cannot read an installed environment-aware
  library. Ordinary descriptors retain BSDALIB1; no automatic song replacement.
- Notification simulator matches0.8073. No UI redesign or queue auto-resume.

## [0.7.14] — notification simulator alignment

- Legacy boot-notification preview matches local plugin0.8072 and By Wkrotik.
  No queue, backend-management or installation-format changes. Main companion
  continues to show installed-vs-available binary version separately.

## [0.7.13] — binary version evidence and once-only registration

- Settings can read the installed plugin version from its unique embedded startup
  banner and compare the active ELF hash with the capability file. Display local
  available version, verified capacity and registration state; never treat a
  filename, stale sidecar or missing banner as version proof. Detect concurrent
  binary/capability replacement; this is a disk check, not runtime-load proof.
- Publish matching version metadata on future plugin setups. Preserve an existing
  plugins.ini entry byte-for-byte on updates; append the missing title-scoped
  registration only once. Refuse duplicate/global/conflicting entries without
  auto-deleting unrelated configuration. Repeated-update regression checks that
  unchanged INI bytes are not uploaded again.

## [0.7.12] — detail backdrop and interrupted-operation diagnosis

- View details closes on a genuine outside click/tap, sharing Downloads' geometry
  guard. Padding, inside-to-outside drags and pointer cancellation do not dismiss it.
- Plugin/library management reports an existing .install-lock explicitly instead
  of a generic FTP550. Distinguish missing write access and failed lock inspection;
  never auto-clear another writer's or an interrupted operation's lock.

## [0.7.11] — compact rating metadata

- Move the discovery rating and adjacent vote count into the duration/BPM metadata
  row, inheriting its font, size and colour. Remove the separate rating block and
  Few votes/other status labels; unknown values use a dash rather than invented data.

## [0.7.10] — discovery evidence and opt-in library editing

- Remove misleading BeatSaver play/download counters (the sampled live API returns
  zero placeholders). Show the BeatSaver score with total votes and a Few votes
  hint below10 votes; absent vote metadata stays unavailable, not invented zero.
- Metadata-only compatibility badges: no known blockers / not compatible / needs
  validation. Known mods, non-Standard/mixed unsupported packs and explicit
  requirements disable queueing. Missing flags never become green; full archive
  validation remains authoritative, including formats/lighting/audio metadata
  cannot prove. Details explain the reason; titles/reasons remain escaped.
- Relative upload times now include weeks/months/years, with exact timestamp in
  the tooltip. Library selection is hidden until Edit selection; entire cards
  support pointer/Enter/Space selection and colour/ARIA state, without checkboxes.
  Done editing clears selection. Existing serial removal/queue guards retained.
- Align legacy notification simulator with the OrBeats0.8071 native candidate.

## [0.7.9] — bottom notifications, resilient queue and retry

- Replace the page-top notice with a solid, fixed bottom toast and accessible ×
  dismiss control. No page reflow, auto-scroll, autofocus or timeout. Keep the
  toast inside the frontmost modal's subtree and in the popover top layer so
  it remains clickable above Downloads and nested confirmations. Library removal
  outcomes use the toast; inline library progress/prerequisites stay contextual.
- Skip failed installations and continue serially. Keep explicit Pause/Cancel
  semantics and retain pending work if a competing runner is busy. Preserve a
  bounded error reason for each failed job before its log is replaced.
- Add Retry beside failed/cancelled installations; enqueue once with original
  title, preserve existing work/order, do not auto-start a paused queue. Expand
  bounded result history to128 so a full64-map batch keeps all failures retryable.
- Add explicit operator-only --restore-queue startup handoff: validate an idle
  paused snapshot and restore pending order/history without resuming console writes.
  No automatic persistent queue or unattended recovery is introduced.
- Exercise bottom-toast clicks above modal dialogs, escaped content, theme/mobile
  layout, failed-map retries, skip/continue, cancellation/manual pause, startup
  failure, handoff validation and64-map mixed-result queue lifecycle offline.

## [0.7.8] — visible removal guards and library multi-select

- Explain running jobs and paused/pending installation queues directly in Your
  Library, with an Open Downloads button. Disable removal while protected instead
  of silently sending its explanation to a closed activity popup.
- Add song checkboxes, Select all, Clear selection and Remove selected with one
  title-specific confirmation. Reuse the closed-title per-map DELETE transaction
  serially; stop on the first failure, report completed removals, refresh the
  manifest and retain selection of remaining songs. Unselected maps are untouched.
- Prevent concurrent clicks/refreshes during removal and prune stale selections on
  refresh. Preserve the queue; no automatic clearing, start or service restart.
- Guard confirmation lifetime through the browser's asynchronous close event so
  rapid cancel/reopen cannot inherit a later confirmation or duplicate deletion.
- Regress ordinary/compressed test-map deletion, final-map conversion-seed retention,
  paused-queue protection, selected-only serial work and partial-failure reporting.

## [0.7.7] — contained Downloads popup

- Lock background scrolling while a modal is open and contain scroll overshoot
  within dialogs. Closing a popup restores scrolling; nested confirmations remain
  modal. Clicking the Downloads backdrop dismisses it without changing the queue;
  clicks on padding and drags that start inside do not dismiss it.
- Exercise real wheel input and pointer dismissal at desktop/mobile sizes.

## [0.7.6] — one installation log

- Remove the duplicate raw diagnostic log display. Keep one readable installation
  log; Copy diagnostic log and Save report retain the complete unfiltered output.

## [0.7.5] — consistent UI assets and compact Downloads control

- Fingerprint CSS/JavaScript URLs by content in the uncached shell so a refreshed
  page cannot reuse older asset URLs for newly added controls.
- Bound the Downloads icon intrinsically and style its button as a compact sidebar
  row. Regress actual icon/button dimensions and opening/closing the popup.
- Default to Relevance at the top of Sort; order This week before This month.

## [0.7.4] — sidebar downloads and serial installation queue

- Add an explicit-start, service-owned queue. Install one map at a time; pause on
  failure/cancellation and retain remaining entries. Pause/clear never interrupts
  an active transaction. The queue survives browser closure, not service restart.
- Move installation activity into a sidebar download button and accessible popup.
  No page scrolling, bottom log section or routine top-of-page installation notices.
- Hide project paths, additive prefixes and library-retention chatter from the
  readable log; preserve full diagnostics for expansion, copy and export.
- Remove PS4 preview controls from library cards/details; discovery previews remain.
- Poll atomic job-aware progress with string IDs to avoid lost/repeated lines
  across queued jobs and JavaScript integer truncation. Block connection/plugin/
  library changes and competing job routes while the queue holds work.

## [0.7.3] — avoid unnecessary library-removal downloads

- When removing the final map, list for an already retained conversion template
  instead of downloading the entire template just to check its existence.
- If a seed must be retained, verify/read only the removed map's bundle, not its
  unrelated cover and preview. Keep manifest publication and deletion guards.
- Imports use pipeline 0.5375's bounded existing-file reads and optional native
  checksum acceleration; existing media checksum checks remain enabled.

## [0.7.2] — previews, library details and quieter confirmations

- Remove the redundant introductory strip and logo tagline; retain the discovery
  layout and add readable primary-button hover colors in light and dark themes.
- Click a cover to play/stop one shared preview, separately from View details.
  Installed artwork and checksum-verified WAV previews come directly from the
  PS4, without relying on search history. Serialize FTP management connections,
  cache private media responses and retry a transient cover failure once.
- Fix older-library Map information statistics and retain the saved BeatSaver
  information path for newer imports.
- Replace native browser warnings with small accessible in-page confirmations;
  Escape/Cancel abort the action. Backend closed-title/write guards are unchanged.
- Local fixture coverage only; real-console artwork and installation pending.

## [0.7.1] — OrBeats

- Adopt the user-selected OrBeats name across the application, report filename,
  documentation and matching native artifact verification.
- Preserve API routes, saved settings, console paths and library compatibility.

## [0.7.0] — companion redesign and management

- Add Discover, Your Library and Console & Settings with light/dark themes,
  responsive cards, full BeatSaver metadata and detailed installation logs.
- Read and remove actual PS4 entries; install locally built plugins using retained
  rollback and byte-preserving plugins.ini merging, without replacing other entries.
- Hide stored passwords, report unconfigured update feeds honestly, and refuse
  phantom migration maps or ambiguous/corrupt state.
- Escape remote metadata, validate image URLs, sequence search responses and
  reserve job starts atomically. Add desktop/mobile Chromium fixture regressions.
- Linux/local-browser tested; fresh PS4 management and other OS execution pending.

## [0.6.32] — 2026-10-26

- Existing Deploy/command preview use additive imports without a replacement slot;
  unsupported overrides are hidden, legacy incompatible batches refused.
- Retain song picking/job logs. UI redesign and additive management screens deferred.
  Keep the game closed during imports and restart afterwards; no live refresh.

## [0.6.31] — 2026-10-25 (Exp310)

- Mirror native v0.8067 identity in count-free notification preview/placeholder.
- Existing replacement installer unchanged. Two-song native experiment is not a
  general additive installer and is not exposed as one in the webapp.

## [0.6.30] — 2026-10-25 (Exp309)

- Match plugin0.8066 notification without feature-count UI, enumeration or stale
  placeholder. Preserve OFF recovery hint and author credits; test actual JS.
- No production additive installer claimed; PC companion is the next milestone.

## [0.6.29] — 2026-10-25

- Notification simulator mirrors plugin0.8064 and Wkrotik credit while preserving Chris Primeish upstream attribution. No new additive installer advertised.

##0.6.28 —2026-10-25 (development, Exp303)
- Mirror0.8063 native toast; no production playlist/importer UI or default change.

## 0.6.27 — 2026-10-25 (development, Exp301)
- Mirror0.8062 native toast. No production deploy/default/conversion change.

##0.6.26 —2026-10-25 (Exp300)
- Mirror candidate plugin0.8061 toast. No production additive importer/deploy UI or defaults change.

# Beat Saber Deluxe — Web App Changelog

The web app is a thin UI layer over the pipeline CLI (`tools/full_custom_song_pipeline.py`).
It never re-implements conversion, deploy, or validation logic — every deploy is a
subprocess argv call to the pipeline (plan:
`.agent/plans/web-app-song-conversion-pipeline-interface.md`).

## 0.6.24 (2026-10-25, local unreleased, Exp295)
- Mirror LOCAL0.8059 candidate toast; console remains0.8058/additive OFF.
- No deploy/conversion/default change; pipeline remains0.5367.

## 0.6.23 (2026-10-25, local unreleased, Exp293)
- Mirror candidate0.8058 plugin toast. No defaults/deploy/conversion changes.

## 0.6.22 (2026-10-25, local unreleased, Exp292)
- Mirror candidate plugin0.8057 toast version. No deploy/conversion/default change.
- New module-scoped API resolver remains local, not console-validated.

## 0.6.21 (2026-10-25, local unreleased, Exp 289)
- Surface approved OFF-default enable_additive_song_packs and explicit experimental
  stock-reference-only description. Adapter default remains false when absent;
  legacy flags keep their prior defaults. UI feature order/toast includes new flag.
- Toast mirrors plugin0.8056,7-feature denominator (legacy6 enabled by default).
- No automatic enabling/deploy/launch. Runtime API/ABI/UI/gameplay not console-tested.

## 0.6.20 (2026-10-24)
### Added — M13: Beat Sage + local song folder support (Exps 283-283e, plan: .agent/plans/beat_sage_and_local_song_folder_support.md)
- **The Pick a Song tab gains two sections + a persistent staged-songs list** (zero pipeline/plugin changes — both end at the pipeline's existing `--song-dir`):
  - **2 · Beat Sage (powered by beatsage.com)** — generate a map from ANY audio. Tier 1 (the web app drives their live-captured API: upload → poll at THEIR own UI's cadence, 3-failure budget → download → validate → stage) with the guided Tier-2 card (their site + our recommended options + the zip drop) as the always-works fallback; ANY failure auto-opens it. Rights checkbox required. The complete captured option surface is exposed: difficulties, modes, events, environment (16), and the **v1/v2 system selector** (live-measured: v1 only marginally denser).
  - **3 · Local songs** — live folder validation (per-problem errors with To-fix suggestions; V2/V3/V4) + map-zip drag-drop intake with zip-slip guarding; both stage into the persistent staged-songs list (survives restarts; dead paths auto-prune; old entries stats-upgrade lazily).
  - **Staged songs carry full chart statistics** (the user's "the more the better"): per-difficulty note counts, NPS average + PEAK (any-10s-window), bombs, walls, light events, chart span; map facts (BPM, environment, duration, cover art, mode-variant totals); the Beat Sage generation record; sparse-chart warnings with the density guidance (their Easy/Normal/Hard are ONE mellow band — density lives in Expert/Expert+; no slider exists on their service).
  - **🧪 The on-demand rights-clean test song** — `webapp/adapters/testsong.py` (100% mathematical synthesis, deterministic; the 48s default is byte-identical to the deployed "BSD Deluxe Theme") + `GET /api/songs/test-song` + a one-click button that fetches it, attaches it to the form, and pre-fills the title/artist (the button visibly disables + relabels through the flow; plain-download fallback).
- New endpoints: `/api/songs/validate-dir`, `/api/songs/stage-zip`, `/api/songs/staged` (+DELETE), `/api/beatsage/guide`, `/api/jobs/beatsage`; the Deploy tab accepts `song_dir` end-to-end (the pages-mode command builder emits `--song-dir` too). `python-multipart` + `quickjs` added to the requirements (the zip/audio uploads; the JS gates).
- **New test gates:** the quickjs JS-syntax gate (caught 2 real browser-killing bugs pre-merge), the boot-wiring test (EXECUTES the DOMContentLoaded wiring under a DOM shim — the only gate for the "page renders but clicks are dead" class), the staged-stats/zip-intake/beat-sage contract suites (57+ tests; the live-service contract test is BEATSAGE_LIVE-gated — CI never contacts them).

### Fixed (folds into 0.6.20 before release)
- **Beat Sage generation failed with "Invalid events specified"** (the user's field report): their "Lights" event checkbox is rejected by their own API with HTTP 400 in BOTH v1 and v2 (live-probed) — never offered; the accepted set (Bombs/DotBlocks/Obstacles) is pinned by tests. The user's exact request re-ran successfully (generated in 57s and staged).
- **The test-song button** no longer claims console state ("already on your console" — wrong for new users), its click is unmistakable (disable + relabel), and `index.html` ships `Cache-Control: no-store` — an open tab can never again mix a new shell with old JS (the diagnosed cause of "the button does nothing").
- **Deploy-page preview of local songs** and the confirm dialog show what's actually deploying (a staged folder vs a BeatSaver map).


## 0.6.19 (2026-10-20)
### Fixed — Exp 281f: the hybrid-dump proof run (the certainty audit)
- **"Use the extracted cache" now repoints EVERY dump consumer.** The user's certainty question ("we're absolutely certain the run used only the extracted files?") exposed a hybrid: the Setup Wizard had pinned `pack_modes.dump_dir` at their real `/workspace/ps4_dump`, so the successful run built the song template from the cache while the pack-patch step silently read the lizzo pack bundle + catalog from the real dump. The button now sets `pack_modes.dump_dir` to the cache alongside `game_dump_dir` (the response reports both).
- **The Setup Wizard's dump_root is now optional** — omitted defaults both dump paths to the local `game_data/` cache (the no-dump flow is the default posture). Users who HAVE a dump (developers/repair) can still pass its root explicitly.
- **The definitive proof:** with the real `/workspace/ps4_dump` physically hidden (renamed), the full deploy from the simulation completed cache-only — validation PASSED — proving the no-dump flow end-to-end (see the experiment log).


## 0.6.18 (2026-10-20)
### Changed — the Dump Guide becomes a big obvious numbered walkthrough (user UX request) + the two cache-following pipeline fixes
- **"The dump procedure could be a little clearer… a big obvious set of steps"** — Option A is now five clearly numbered, styled step cards: **STEP 1 · Request the data** (pack checkboxes + Select all/none + size estimate), **STEP 2 · Launch Beat Saber** ("watch for the BSD: game data ready notification — this page updates automatically"), **STEP 3 · Pull** (with a **live progress bar**: local-files / console-extracted-files, updating every second during the mirror), **STEP 4 · Save the cache** ("Use the extracted cache"), **STEP 5 · Deploy songs 🎉** (links to Find a Song). The active step is highlighted; completed steps dim with a done style. The old button row + status area remain for live feedback.
- **Two pipeline fixes (0.5365 folds) found by the user's cache-only deploy:** (1) **pack_modes.dump_dir now follows game_dump_dir** unless explicitly pinned — the "Use the cache" switch previously repointed only game_dump_dir, leaving the pack-modes builder hunting the old dump path ("Dump dir missing" — the pack patch silently skipped); (2) **absent redirects.json + a freshly-built local set = the new state for a clean console** (deploy it, don't refuse) — the Exp-246 refusal now fires only on genuine read failures, which raise a distinct RuntimeError. The anti-wipe gate is preserved and STRENGTHER. 5 new tests.


## 0.6.17 (2026-10-19)
### Fixed — the invisible extractor flag (user report) + fresh-install defaults (Exp 281)
- **`enable_game_data_extractor` was MISSING from `KNOWN_FLAGS`** — a missed edit from the M12 cycle (the user hit it live: "I don't see any mention of an extractor" on the Feature Flags tab). Now present; the tab renders all 7 flags.
- **All flags default ON when features.json is absent** (user directive: "These feature flags should all default to ON on a fresh install"). `DEFAULTS_TRUE` = every KNOWN_FLAG; a clean console renders with everything ON; the kill-switch description updated (it is no longer "the only flag that defaults ON"). Matches the plugin's v0.8055 absent-file defaults and the pipeline's all-True DEFAULT_FEATURES.
- `TOAST_VERSION` v0.8055.
### Fixed — Exp 281b (from the user's Request-extraction run)
- **The fresh-console bootstrap SAFETY NET:** the pipeline now runs `mkdir -p -f` on the AFR title dir before any AFR write (request puts, features.json deploys, bundle uploads) — after Clear PS4 the dir normally survives (the clean deletes files, not the dir), but the bootstrap makes every AFR write robust against a missing dir. (Live verification during this fix showed the user's Request extraction HAD landed — the true bug was the status read below.) 2 regression tests.
- **THE user-facing bug of this round: the game-data state readers misclassified absent as unreachable.** The user's Request extraction SUCCEEDED — but the post-job status read (game_data_status.txt absent: no boot had run yet) fell through to `ok=False`, and the UI declared "❌ PS4 unreachable" while the console was perfectly reachable. The status/requests readers now apply the Exp-280d absent doctrine (550 → ok=True + absent=True), and the invalid lftp variable `net:connect-timeout` ("no such variable" noise polluting every error message) is removed. The state now correctly shows "requested: 11 · extracted: 0 · pending: 11" on the live console.
- **The Dump Guide gains Select all / Select none** + a live size estimate (N packs · M slots · ~GB to extract) — "dump everything needed to run the pipeline for any target song at will" is now one click (the full 36-pack catalog ≈ 5GB across boots).
- **The web app now LISTENS while an extraction is pending:** the status line shows "⏳ Extraction pending — boot Beat Saber once" and auto-polls every 5s until the console's extraction completes (no clicking). Plus the PS4 side (plugin v0.8055): a notification — "BSD: game data ready — N file(s) extracted — pull them from the web app" — fires when an extraction run actually produced files.


## 0.6.16 (2026-10-19)
### Fixed — Exp 280d (from the user's Phase 0/1 run)
- **A clean console is now reported as a CLEAN SLATE, not a wall of errors.** After Clear PS4, every state read showed "⚠ Couldn't read … (get: Access failed: 550 … File unavailable)" — but a decisive 550 (file does not exist) is the CORRECT empty state. `fetch_remote_json` now classifies 550/no-such-file signatures as `ok=True, data=None` (absent — never retried, never an error); only genuine failures (connectivity, parse) stay errors. The **PS4 State tab shows a "✅ Clean slate" banner** with per-row "not present — clean slate (fresh install / after Clear PS4)" when all three state files are absent; the Full Loadout tab's post-clear warnings vanish (it renders the zero state cleanly). An absent AFR dir listing is the same clean state (`list_afr_dir`: ok=True, count=0, absent=True).
- **clean_slate now actually fires (Exp 280e):** the 550 classification landed in `fetch_remote_json`, but the redirect/feature READERS transform `data=None` into empty counts/defaults before the state endpoint saw it — so "absent" never propagated and the banner never showed. The absent flag now rides ON the `ReadResult` (surviving transformation); 3 tests pin the propagation (absent through the summary, absent through features, present-file → absent=False).
- **The backup script's Clean PS4 now removes the M10 preview-variant pack bundles** (`*_pack_modes_previews_assets_all_*.bundle`) — the modes-only pattern let all 5 survive the user's clean (found live: 5 stale bundles dated Oct 17 remained on the console) — plus M12's extractor files (`game_data_requests.txt`, `game_data_status.txt`, `game_data/*`). The Backup tab wraps this script; a re-clean after this fix produces a true clean slate.

- **The bundled plugin reports a REAL version number** (user request: "I still would want to see a version number for that bundled plugin"). In a release extraction there's no `src/` — `_plugin_version()` now extracts the version from the bundled PRX's boot banner string (`=== BS Deluxe v0.8054 started ===`), so the version badge and the ping report `v0.8054` instead of the opaque "bundled". 3 tests pin the extraction + graceful fallback + the ping carrying it.


## 0.6.15 (2026-10-19)
### Added — the plugin-only deploy surface (Exp 280b: the fresh-user bootstrap gap)
- **Deploy tab gains a "Plugin only" card** — `Deploy plugin` button + a **Debug logging** checkbox (deploys the DEBUG build; the boot toast self-identifies with a DEBUG version suffix). **Get Started step 5 also gains a one-click "Deploy plugin to PS4" button** (always the release build — the debug option is deliberately Deploy-tab-only). Behind `POST /api/jobs/deploy-plugin` → the pipeline's `--deploy-plugin` (source builds via make; release extractions fall back to the bundled `plugins/` binary per Exp 235 — no songs are touched).
- **Why it exists:** the M12 hardware checklist referenced a plugin-deploy surface that never existed — plugin deploys historically rode on song deploys (`--deploy-full`). The fresh-user flow exposed the chicken-and-egg: the game-data extractor lives in the plugin, but without a cache there is no song to deploy. The bootstrap order is now explicit: **plugin first**, then arm the extractor flag, then request/extract/pull, then songs.

### Fixed — Exp 280c (found via the user's live smoke test: Deploy Plugin → "❌ Not Found")
- **The ping now reports the versions of the RUNNING code (captured at import), never a fresh file read at request time.** A stale server process reading VERSION/main.cpp at request time reports the NEW version while serving OLD code — defeating the launcher's staleness check ("current" → reuse the stale server) and sending clicks to 404s. With import-time capture (`_capture_code_versions()`), a stale process honestly reports its own version, the launcher flags it STALE, and the stop-and-restart default takes over. 3 regression tests pin the class.


## 0.6.14 (2026-10-19)
### Added — M12: the "no dump required" flow (Dump Guide rework)
- **Dump Guide tab gains "Option A — Let the game extract it (recommended)":** a 5-step guided flow (arm flag → pick packs from live checkboxes → request → boot the game once → pull → use the cache) with live state polling (requested/extracted/pending/errors + local cache summary + whether the cache is active as game_dump_dir). "Option B" keeps the classic manual recipe for developers/repair.
- **New endpoints (thin layer — both operations are pipeline subprocesses):** `POST /api/jobs/game-data-request` (--request-game-data argv builder), `POST /api/jobs/game-data-pull` (--pull-game-data), `GET /api/game-data/state` (requests + status + cache + pending computation), `POST /api/game-data/use-cache` (points paths.game_dump_dir at the cache; refuses an empty cache with a fix message).
- **6th feature flag surfaced everywhere:** `enable_game_data_extractor` (KNOWN_FLAGS + a full FLAG_DESCRIPTIONS entry + the toast-simulation list — toast now reads N/6; TOAST_VERSION v0.8054).
- Job watching for the request/pull buttons (a compact direct poller into the status area with the job's tail lines + exit verdict).


## 0.6.13 (2026-10-17)
### Added — resilient + intelligent launcher (user directives, Exp 278h)
- **Port-collision handling that presents options instead of dying.** When the preferred port (default 8765) is busy, the launcher now IDENTIFIES the occupant — it pings `/api/ping` and can tell "Beat Saber Deluxe web app 0.6.12 (pipeline 0.5363, plugin v0.8053) — ⚠️ STALE: it predates this checkout" from an unknown process — then presents a menu:
  1. use the existing instance (opens it; nothing new started),
  2. start a FRESH instance on the next free port,
  3. STOP the running web app instance(s) (found by scanning `/proc` for this server.py) and start fresh on the preferred port.
  Smart defaults: a CURRENT instance → reuse it; a STALE one of ours → stop + restart on the same port (the exact pain that produced Errno 98: a long-running server process serving old code); an unknown occupant → never kill it, take the next port. Non-interactive contexts (stdin not a TTY) take the default automatically with a printed notice.
- **Every error message now carries a suggested course of action** ("To fix: …") — the all-ports-busy error tells you to stop instances (`ps aux | grep '[s]erver.py'` + kill) or pick a port with `--port`; a failed stop-and-rebind warns and falls back to the next free port automatically instead of crashing.


## 0.6.12 (2026-10-17)
### Fixed
- **Feature-flag description for `enable_in_game_plugin_toggle` polished** (user report of stale text): the repo description had been correct since 0.6.8, but the user's observation exposed TWO issues: (1) a long-running web-app server process from before the 0.6.8 change was still serving the old L3+R3 wording from memory — **restart the web app after pulling changes** (its FastAPI process holds code in memory; the UI won't see new descriptions until relaunch); (2) the description carried a hard-coded "(v0.8050)" version reference that stales with every bump — now removed in favor of "hardware-confirmed" phrasing, the VR notification-sound note, and a pointer to the full feature guide (docs/features/in-game-plugin-toggle.md).
- The feature doc gained the user's demo video (README + docs/demos.md already carried it).

## 0.6.11 (2026-10-16)
### Changed
- `TOAST_VERSION` bumped to v0.8053. The simulated boot toast now documents the debug-variant suffix convention (a real DEBUG build reports `vX DEBUG` in its toast/banner).

## 0.6.10 (2026-10-16)
### Changed
- `TOAST_VERSION` bumped to v0.8052 (GOT-hijack build). Note: this round deploys the DEBUG plugin variant (`--deploy-logging`) for full move-data diagnostics; `--deploy-plugin` restores the quiet release build after confirmation.

## 0.6.9 (2026-10-16)
### Changed
- `TOAST_VERSION` bumped to v0.8051 (GOT-resolution build; UI otherwise unchanged).

## 0.6.8 (2026-10-15)
### Changed
- **M11 hotkey description updated for the v0.8050 redesign** (Exp 278c): the hotkey is now **Move button + trigger held together for 2 seconds** (the user-verified reality: the DS4 is ignored by Beat Saber in VR mode; the new combo is used nowhere else in the game). `TOAST_VERSION` bumped to v0.8050.

## 0.6.7 (2026-10-14)
### Added
- **M11: 5th feature flag `enable_in_game_plugin_toggle` surfaced everywhere the app touches flags.** `KNOWN_FLAGS` (adapter), a full `FLAG_DESCRIPTIONS` entry (documents the L3+R3 2-second DS4 hotkey, the restart-to-apply semantics, and that the hotkey deliberately ignores the kill switch so it always works), the toast simulation's `FEATURE_FLAG_KEYS` + `FLAG_ORDER` (toast now reads N/5), `TOAST_VERSION` v0.8049, and the index.html static placeholder (5/5).

## 0.6.6 (2026-10-13)
### Added
- **Demos link (lower-left, both surfaces).** A small footer link — 🎬 Demos — opens the project's collected demo-video + screenshot gallery (`docs/demos.md` on the MAIN branch: <https://github.com/free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter/blob/main/docs/demos.md>). Mirrors the version badge's corner-chip styling (rounded on the outer edge, hidden when printing, hover accent); `target="_blank" rel="noopener"`. The main-branch URL is stable across releases and goes live the moment the feature PR merges (404s before that, by design).

## 0.6.5 (2026-10-12)
### Fixed
- **The Batch tab showed 0 example packs from an extracted release zip (latent since the first M9 release; Exp 270a).** The zip's layout is flat — `webapp/`, `docs/` sit at the zip root — but the adapter resolved example scripts one level above it. `paths.py` now probes both layout levels (`release_root_surname()` / `release_path()`) and every release-root consumer (batch dirs, runner cwd, backup paths, validator) is layout-agnostic. Verified from a clean extraction: 34 example packs parse; the dev checkout is unchanged.

## 0.6.4 (2026-10-10)
### Changed
- **Feature Flags tab tracks the 4th flag + the real toast format (M10).** `enable_song_previews` renders with a full description (its absence was the gap found while validating the user's live deploy); the simulated boot toast counts `N/4` (derived from the flag list length — never hardcoded again) and shows `v0.8048`. The Batch tab's runner now injects `--skip-song-preview-management` into all-but-the-last batch command (previews regenerate once at the end of a batch).

## [0.6.3] — 2026-10-08 (Exp 266)
### Fixed
- **Pages mode landed on the Setup Wizard instead of Get Started (found on the LIVE Pages deploy by the user, minutes after PR #5 merged).** Root cause: a landing race — `detectMode()`'s pages branch clicks the Get Started button (correct), but the `DOMContentLoaded` handler at the script's tail then runs `showPage("wizard")` UNCONDITIONALLY, and it fires after the script bottom — stomping the landing back to the wizard on every fast connection. The badge/banner/tab-hiding all worked (they're not overwritten later), which is exactly why the page LOOKED correct except for the landing. Fix: the DOMContentLoaded wizard landing is now mode-aware — `if (state.mode !== "pages") showPage("wizard")`; pages mode keeps the Get Started landing, local mode keeps the wizard. The hidden-tabs behavior the user noticed ("most of the tabs are missing") is the DESIGNED pages mode — the 6 backend-only tabs (PS4, Manage Songs, Loadout, Flags, Batch, Backup) can't function hosted and hide; verified all 12 buttons ship in the bundle with `local-only` markers. Proven with a browser-order headless simulation (startPage click → DOMContentLoaded guard → lands on startPage; local regression lands on wizard). Suite 807/807.

## [0.6.2] — 2026-10-07 (Exp 264)
### Fixed
- **Batch parser carried shell quoting into `--target` values** (found proving the user's failed multi-pack batch: the Britney pack's song 8 parsed as target `"Scream&Shout"` — literal quotes included — because the example scripts quote `&` for the SHELL and the parser's `\S+` regex captured the quotes as part of the slot name; the batch would have deployed to a garbage slot even after the pipeline's size-check fix). `parse_example_scripts()` now strips matching leading/trailing quotes via `_unquote()` — quotes are shell syntax, not slot names. All 34 packs re-verified: zero quoted targets remain; the Scream&Shout entry is `target: "Scream&Shout"` clean. 18 batch tests green.

## [0.6.1] — 2026-10-06 (Exp 263)
### Fixed
- **Dead-PS4 reads no longer take minutes to report "unreachable"** (Exp 263 finding, measured during release validation of webapp-0.6.0-alpha01: with the PS4 powered off, `/api/loadout` took ~3.5 min — 3 reads × 3 retries against a host lftp defaults kept retrying; a bare lftp call was measured at 12:14 min). The adapters' `_run_lftp` now sets `net:timeout 5`, `net:max-retries 1`, `net:connect-timeout 5` (the same dead read fails in 0.25s), and `fetch_remote_json` stops retrying once the error is a connectivity refusal ("No route to host" / "connection refused" / timeout / DNS) — retries remain for genuine transfer flakes. The PS4-state/Loadout tabs now surface "unreachable" in seconds instead of hanging the spinner for minutes. (Found while validating against a PS4 that was initially off; pipeline-side twin of this fix: none needed — the pipeline's reads are single-attempt with hard aborts.)

## [0.6.0] — 2026-10-06 (Exp 262)
### Added — the Get Started tab: hosted → full app in 5 guided steps
- **A guided download funnel for Pages visitors** (user request: "guide the
  user through downloading the latest release, extracting it, and running
  THAT web app for full functionality — as seamless as we can"): a new
  **Get Started** tab with a prerequisite checklist (interactive
  checkboxes: Python, jailbroken PS4 + GoldHEN FTP, Beat Saber 2.04, the
  decrypted dump with a Dump-Guide handoff link, same-network), a
  **Download the latest release** button (the `releases/latest` link —
  always current, no version updates needed), per-OS extract instructions,
  **per-OS run commands** (Windows/macOS/Linux tabs: `pip install -r
  requirements.txt` + `python webapp/server.py`, with the python-vs-python3
  and Store-redirect gotchas called out), and the wizard's 4-step finale.
- **Hosted visitors land on it**: the Pages bundle auto-opens Get Started,
  and the banner now leads with "Get Started takes you to the full app in
  ~2 minutes" — the planning-mode note and the command-builder alternative
  remain.
- The local backend gets the same tab (the handoff instructions live there
  for copy/paste convenience).
- Verified with a headless-DOM consumer test against the built bundle: nav
  wiring at load, auto-landing, relabel — plus local-mode regression.

## [0.5.5] — 2026-10-06 (Exp 261)
### Added — command-builder mode actually works on the hosted Pages site
- **The Deploy preview builds the exact pipeline command LOCALLY in pages
  mode** (the argv order mirrors `adapters/deploy.py` 1:1) — previously the
  preview called a backend endpoint that doesn't exist on the hosted site,
  so nothing appeared.
- **The Deploy button becomes "Copy deploy command"** in pages mode: copies
  the generated command (with clipboard fallback) + a note to run it on the
  machine with the ps4_dump + PS4.
- **Backend-only tabs hidden in pages mode** (PS4, Manage Songs, Full
  Loadout, Feature Flags, Batch, Backup/Restore — all require the local
  server), the wizard's Save-config button too, and the builder's injected
  pages-branch now carries the full setup (it previously returned early,
  skipping the relabel — found by a headless-DOM consumer-flow test).
- BeatSaver search, the Dump Guide (with dumper.cfg download), batch
  building + export, and the Feature Request composer all work hosted.

### Why deploys can never run on the hosted site (by design)
Browsers cannot read a local ps4_dump folder, run Python, or open FTP to
a PS4 — and GitHub Pages is static hosting. The hosted site is the
plan-and-onboard surface (find songs, learn the dump process, generate
exact commands); the release's `python3 webapp/server.py` is the surface
that actually deploys.

## [0.5.4] — 2026-10-06 (Exp 259)
### Changed
- **The example scripts now live at `docs/example-scripts/` in the REPO as
  well as the release** (moved from `.agent/docs/` — they're user-facing
  content and now the repo and release layouts are identical). The Batch
  parser's canonical path follows them; the legacy `.agent/docs/` location
  is still parsed for old checkouts (first-match wins). All references
  updated: README (script paths + chained examples + Batch description),
  the release packaging workflow (copies from the new location), the plan
  doc, the regression tests. Knowledge base updated.

## [0.5.3] — 2026-10-06 (Exp 258)
### Fixed
- **The Batch tab was EMPTY when run from an extracted release zip** (found
  in the alpha01 release audit): the script parser looked only at the repo
  layout (`.agent/docs/`), but the release zip ships the example scripts at
  `docs/example-scripts/`. The parser now checks both layouts (and an
  extracted zip's `beat_saber_deluxe/docs/example-scripts/`), first-match
  wins, no duplicates. Verified from the actual extracted alpha01 zip:
  34 packs, RS=11, BE=10, the 5-pack standard loadout = 47.
  (Superseded in 0.5.4/Exp 259: the scripts moved to docs/example-scripts/ in
  the REPO too, making the layouts identical.)

## [0.5.2] — 2026-10-04 (Exp 256)
### Fixed
- **The 5-pack multi-batch now counts 47, matching the PS4** (was 50):
  the Billie Eilish example script carried 3 songs that belong to the
  LIZZO pack (2 be loved / about damn time / cuz i love you — Lizzo stock
  slots with the same map IDs the Lizzo script already deploys). Removed
  from the BE `.sh` + companion `.md` (renumbered, count references fixed);
  the Lizzo script keeps them. Verified: the five scripts' unique slot set
  now EXACTLY equals the live PS4's 47 redirects (zero diff both ways);
  the multi-batch counter reads 11+10+11+9+6 = 47.

## [0.5.1] — 2026-10-04 (Exp 255)
### Added
- **Multi-pack batch deploys** (Batch tab, new section): a checkbox list of
  all 34 example packs with per-pack song counts; check any combination
  (e.g. the standard loadout: Rolling Stones, Billie Eilish, Britney
  Spears, Lizzo, Camelia = 50 songs), select all/none shortcuts, a live
  "N packs · M songs selected" counter, the deploy order previewed on the
  button tooltip, and a **Deploy selected music packs** button that runs
  them as ONE serial job — the web-app equivalent of chaining the example
  scripts (`script1.sh --no-prompt && script2.sh --no-prompt && …`),
  stopping at the first failure.

## [0.5.0] — 2026-10-04 (Exp 254)
### Added — the Batch tab
- **Pre-defined packs dropdown**: all 34 example-script packs, parsed LIVE
  from the example scripts (`docs/example-scripts/example_*.sh`, moved there
  from `.agent/docs/` in Exp 259; 296 song replacements — map IDs, target
  slots, and the custom song/artist names from the scripts' own comments).
  The scripts stay the single source of truth: the tab always shows exactly
  what the CLI runs.
- **Custom batch builder**: "Build a custom batch…" — add songs via the
  integrated BeatSaver search (native E/N/H filter + badges) or a
  map-ID + slot form; remove rows; name/describe; deploy.
- **Save / Load / Delete** custom batches as JSON files
  (`webapp/batches/`), with the format documented in the tab AND
  hand-editable anywhere: `{"format": "bsd-batch", "version": 1, "name":
  …, "songs": [{map_id, target, song_name, artist, audio, pad_fsb5,
  convert_to_v3}]}`.
- **Export / Import** via the browser's file dialogs — platform-agnostic by
  design (Windows/macOS/Linux browsers; nothing depends on server-side
  paths, so it also works in Pages mode for building batches).
- **Batch deploys run as ONE serial job**: `webapp/batch_runner.py` executes
  each song's `--deploy-full` in sequence through the single-job runner,
  streaming every line into the live console, STOPPING at the first failure
  (the exact `script1 && script2` semantics of the chained example scripts).
  All entries validated BEFORE anything deploys (a bad row starts nothing).

## [0.4.5] — 2026-10-04 (Exp 253)
### Fixed
- **Job panels now live at the TOP of long pages** (Manage Songs, Full
  Loadout) — they sat below the tables, invisible while a clear ran. The
  page scrolls to the panel on job start (spinner + live console in view
  immediately), and the Deploy progress row scrolls into view too.
- **Clear now refreshes the table at the right moment**: the panel's
  completion promise was fire-and-forget, so the refresh fired while the job
  was still running. `runJobWithPanel` now resolves when the job ENDS; the
  clear's refresh happens at completion.

### With pipeline v0.5354 (the "Stale" answer)
- `--clear-target-song` now removes EVERY casing variant of the slot bundle
  (deploy history wrote both `MessItUp_v3.bundle` and
  `messitup_v3.bundle`; the old clear removed only the literal-cased one —
  the leftover file, correctly detected, rendered as "stale" right after a
  clear). A cleared slot now genuinely shows **stock**.

## [0.4.4] — 2026-10-04 (Exp 252b)
### Fixed
- **The Deploy progress row still showed permanently** (and stayed after a
  deploy): it used the `hidden` ATTRIBUTE, but `.row { display: flex }`
  overrode the UA's attribute default (any author `display` beats it — the
  classic attribute-vs-specificity trap; yesterday's generic `.hidden`-class
  fix didn't cover it). Added `[hidden] { display: none !important; }` and
  the row now hides via BOTH class and attribute, toggled together. Sweep
  confirmed it was the only element in the trap.

## [0.4.3] — 2026-10-04 (Exp 252)
### Fixed
- **Job panels rendered permanently** ("Working…" + spinner on Full Loadout
  and Backup/Restore before any action): the stylesheet only had a
  `.page.hidden` rule — the generic `hidden` class had NO rule, so every
  non-page element relying on it displayed unconditionally. Added the
  standalone `.hidden { display: none; }` rule.
- **Backup dialog crash** (`Cannot set properties of null (setting
  'textContent')`): the Backup page's panel children used
  `backup-job-*` IDs while the shared panel machinery expects
  `<panelId>-*` (`backup-job-panel-*`) — the status assignment hit null.
  IDs aligned across the panel; all three panels' five children each now
  verified by a static audit + live serve check.

### Added
- **Deploy tab working-status**: a progress row (spinner + Deploying… + the
  song → slot label) shows during deploys; the Deploy button disables and
  relabels itself ("Deploying…"); both clear on completion.
- **Verify PS4 button feedback**: spinner + relabelled "Verifying…", the
  progress row, and the live console (previously silent).
- **PS4 tab loading spinner** while reading state.

## [0.4.2] — 2026-10-04 (Exp 251)
### Added
- **Version badge, lower-right corner** (user: "so I can tell when your
  changes have taken effect"): web app + pipeline + plugin versions, live
  from the server in local-backend mode (`/api/ping` now carries all three),
  baked into the Pages bundle at build time. Hidden when printing the
  loadout.

### Fixed
- **The Pages bundle 404'd its own JS/CSS** — `build_pages.py` copied assets
  to the bundle root but the HTML still referenced `/static/*`, so the entire
  app was dead at the Pages URL (the user's "is this change being served?"
  was exactly right: no JS ran at all, so the flags page — and everything
  else — was inert). The builder now rewrites the three references to
  root-relative, and the workflow's smoke-test asserts every referenced
  asset resolves in the bundle (this exact regression is pinned by tests).

## [0.4.1] — 2026-10-04 (Exp 250)
### Added
- **Live job feedback everywhere** (user request after finding the backup
  button silent mid-run): a shared job panel — spinner + Working… → ✅ Done /
  ❌ Failed status + the exact command + a live-streamed console — wired into
  Backup, Restore, and per-row Clear (Manage Songs + Full Loadout). The
  Backup button also disables + relabels itself ("Backing up…") so it can't
  be double-clicked; Apply (Flags) gets the same treatment. The Deploy page
  already streamed; it now shares the same visual language.
- **Simulated PS4 launch notification** (Flags page): a live toast preview in
  the plugin's exact boot format — `BS Deluxe vX (ON) / (N/3 features ON)`
  vs `(OFF) / (official songs only)` — recomputed as toggles flip, with a
  note explaining what the next boot will do with the current state.

### Fixed
- **CI lint was red on the PR** (blocking the merge): the Exp 245 lint-scope
  widening to `tests/` exposed ~180 pre-existing findings. All fixed
  (144 auto + hand-fixes); includes two real finds: a corrupted dev helper
  (`tests/quick_validation.py` — split `he vig_data` identifier, literal
  `\n` in source; now parses) and a typo'd assertion variable
  (`valid_rate` vs `validity_rate` in test_hevag_audio_compatibility — only
  fired on failure, i.e. exactly when you need it). Suite 770/770 green,
  lint clean across tools/ + webapp/ + tests/.
- Live backup run validated end-to-end through the panel flow (30 lines
  streamed, exit 0, zip created).

## [0.4.0] — 2026-10-03 (Exp 249)
### Added
- **Backups-folder browse button** (Backup/Restore tab): the path is now
  displayed and changeable — a server-side folder browser (dirs only),
  manual path entry, "use default" reset, and persistence across server
  restarts (`webapp_state.json`, gitignored — same treatment as
  `ps4_config.json`). Backup jobs pass `--out` to the backup script when the
  folder differs from the default; restore already took absolute paths.
  New endpoints: `/api/backup/dir` (GET/POST), `/api/backup/browse`.
  The backup script gained the `--out` flag (its hardcoded default is
  unchanged for CLI users).
- **Feature-flag independence note** in the Flags tab: song-list labels
  built before a metadata-flag change keep their old text until the list is
  re-entered (from the Exp 249 audit — cosmetic, self-healing).

## [0.3.1] — 2026-10-02 (Exp 248)

## [0.3.1] — 2026-10-02 (Exp 248)
### Fixed
- **Test-suite PS4 safety (the amplifier of the Exp 248 flags bug):** webapp
  endpoint tests previously started REAL pipeline subprocesses; one
  (`flags-apply`) pushed a stale local features.json over the user's live
  console, turning the metadata flag off in-game. ALL job-starting endpoint
  tests now run against a mocked runner that records argv (asserted —
  better coverage than before), and `tests/conftest.py` blocks lftp
  uploads suite-wide. The webapp itself needed no code change — its API
  already diffs against the live state; the pipeline fix (v0.5353
  pull-before-push for flags) closes the underlying hole.

## [0.3.0] — 2026-10-02 (Exp 247)

## [0.3.0] — 2026-10-02 (Exp 247)
### Added
- **Feature Flags tab** — live per-flag read (kill switch first, with
  detailed descriptions and the enable_plugin-defaults-TRUE rule), an Apply
  button that diffs against the live PS4 state and deploys only CHANGED
  flags through `--features-only` (refuses to apply blind if the live read
  fails; unknown flags rejected), pending badges, live job log.
- **Backup / Restore tab** — thin wrapper over
  `backup-beat-saber-deluxe-files.py` (the same script the CLI uses): list
  `ps4_backups/*.zip`, backup now (with optional `--clean-ps4` behind a hard
  confirm), per-row restore (backup names sanitized — no path traversal),
  cancel, live job log. The runner gained `start_script()` with the same
  single-job/streaming/cancel guarantees as deploys.
- **Feature Request tab** — composes a prefilled GitHub issue URL (title +
  details + optional app-state footer: mode and deployed-pack summary, never
  IPs or paths); preview then open on GitHub. Works in Pages mode (client-side).
- Runner: `pending_flags` hint so the Flags page can show pending state while
  a flags job runs.

### Fixed
- **Flag-key mismatch (live smoke catch):** the PS4 wire-format key is the
  PLURAL `enable_custom_song_replacements` (the pipeline's DEFAULT_FEATURES
  key); the adapter had the singular — the Flags page showed the flag
  default-OFF when the console had it ON. Corrected across adapter + server
  + tests.
- Old runner test asserted the pre-unification error string; updated.

## [0.2.0] — 2026-09-29 (Exp 245)

## [0.2.0] — 2026-09-29 (Exp 245)
### Added
- **Manage Songs tab** — music-pack dropdown → a table of every stock song
  (slot, stock name/artist) with the custom song installed over it
  (custom name/artist from live `song_metadata.json`), per-row **Clear**
  button (goes through `--clear-target-song <songID>` as a single-job
  subprocess; surgical-revert contract shown in the confirm dialog).
- **Full Loadout tab** — every music pack and song in the game with custom
  status, printable: save-the-page or print-to-PDF support (`@media print`
  stylesheet flips to a clean light document, hides interactive chrome);
  "only packs with customs" filter; per-row Clear buttons. The generated
  document doubles as a reference of the PS4's song loadout.
- `adapters/loadout.py` — the pure catalog × redirects × song_metadata merge
  (the metadata join is case/space-insensitive: the real catalog has
  `'You Should See Me In A Crown '` vs song_metadata
  `'You Should See Me In A Crown'`); `ps4.read_deployment_state()` — one
  banner-free read of BOTH state files with explicit per-source read errors
  (never rendered as "nothing deployed").
- `/api/loadout` + `/api/loadout/packs` endpoints (packs list works even
  with the PS4 offline — catalog-only).
- **GitHub Pages build** — `webapp/build_pages.py` stamps the same UI bundle
  with `data-mode="pages"` (instant command-builder mode: Deploy becomes
  "copy the generated command") + a mode banner; `.github/workflows/pages.yml`
  builds, smoke-tests, and deploys it to Pages on every push to main.
- CI/release coverage: webapp tests' deps (fastapi/uvicorn/httpx) added to
  `requirements-test.txt` (CI previously would have failed on the new tests);
  `ci.yml` + plugin-build lint now cover `webapp/` and `tests/`; the release
  workflow smoke-tests the webapp server (imports, routes, static files) and
  bundles `webapp/` into the release zip; CI_RELEASE.md documents the webapp
  section + Pages mode.

## [0.1.0] — 2026-09-29 (Exp 244)

## [0.1.0] — 2026-09-29 (Exp 244)
### Added
- Phase 1 skeleton (plan §5): FastAPI server (`webapp/server.py`, binds 127.0.0.1
  only) + static UI shell (Setup Wizard, Song Picker, Deploy) with local-backend /
  Pages command-builder mode detection (`/api/ping` heartbeat).
- Adapters, one module per pipeline subsystem: `adapters/config.py`
  (ps4_config.json read/write + validation + wizard dump validation with
  per-missing-piece errors and found-DLC confidence list), `adapters/beatsaver.py`
  (search/map-by-id via the public API), `adapters/deploy.py` (the 56-flag CLI
  surface → typed argv builder), `adapters/ps4.py` (banner-free FTP state reads),
  `adapters/runner.py` (single-job subprocess executor with SSE log streaming).
- Single-job rule: one pipeline job at a time (state files are transaction
  records — concurrent writers corrupt them, plan §9.4 invariant 2).
- Every PS4 read uses the `get`-to-temp-dir banner-free transport (never
  `lftp cat`) with first-`{`-to-last-`}` JSON extraction and retries
  (`.agent/llm-wiki-knowledge-base/lftp-ftp-pitfalls.md`, plan §9.4 invariant 3).
