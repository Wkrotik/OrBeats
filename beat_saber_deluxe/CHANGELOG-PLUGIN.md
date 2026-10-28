## [0.8077] — bounded environment palette array candidate

- Accept both the declared UnityEngine.Object[] and the covariant requested
  EnvironmentInfoSO[] result for FindObjectsOfTypeAll(Type). Continue checking
  rank1, SZARRAY bounds/header/length, <=256entries, every exact object class,
  matching environment and duplicate ambiguity before any repository publication.
- Separate element/rank diagnostics and log safe rank/type/count/header evidence.
  Do not treat the earlier compound array-layout failure as proof of which guard
  failed. This candidate requires a new PS4 test; recovery is not yet established.
- Sanitizer coverage includes both accepted array types plus wrong element,
  bounds, rank, header/API length mismatch, corrupt entry and existing failures.

## [0.8076] — authored palettes over environment defaults (hardware test pending)

- Fix valid null BeatmapBasicData colour overrides: resolve the matching already
  loaded EnvironmentInfoSO via the unique public Resources.FindObjectsOfTypeAll(Type)
  API and its genuine ColorSchemeSO/ColorScheme. Copy only into a new per-map
  scheme; preserve all unprovided environment colours and source assets.
- Keep strict field/type/array/duplicate/GC/constructor/readback guards. Missing
  APIs or matching environment refuse with explicit palette-environment stages;
  never invent colours, load scenes, strip authored colours or bypass publication.
- Add sanitizer regression with null stock override + six authored colours and
  failure-path/stock-preservation tests. Installed/readback-verified with27songs,
  unchanged library/features/INI and local rollback only. Hardware recovery is
  pending user confirmation; no game launch or reimport was performed.

## [0.8075] — expanded native map runtime (historical)

- Optional presentation/mode profiles retain loudness/offsets/palettes and stock
  OneSaber/NoArrows/90Degree/360Degree instances, gated by actual ELF markers.
  Genuine managed constructors/readback and stock ownership guards retained.

## [0.8074] — OrBeats artifact identity

- Build orbeats.prx and orbeats_debug.prx with matching module identity; player
  notifications remain OrBeats / By Wkrotik. The active console name is always
  orbeats.prx. No chart, library, gameplay or stock/DLC changes.

## [0.8073] — explicit reviewed lighting environment (local candidate)

- Decode both legacy BSDALIB1 and optional environment-aware BSDALIB2. Route
  reviewed WeaveEnvironment through the actual EnvironmentName value-struct ABI,
  root its string, verify constructor readback, and log the owned level's route.
  Absent tokens retain stock fallback; arbitrary environments fail closed.
- Preserve existing64-song budget, stock/DLC repositories, registration rollback,
  bounded raw media handling and By Wkrotik notifications. No mod runtime.
- Release/DEBUG build and native managed/wire regressions pass. Not installed or
  console-playback validated yet; see docs/lighting-and-format-support.md.

## [0.8072] — bounded media preparation and explicit credit

- Preflight menu media with an8KiB streaming checksum buffer instead of caching
  every raw cover/preview before hooking. Build managed media on the existing
  Unity caller, keeping only one song pair plus playlist art, then immediately
  free those raw files before the next song. Registration still waits for all
  managed media and retains existing all-repository checks/rollback.
- Log exact failing path/stage/kernel code/actual bytes/hash, including allocation
  failures. A failure stops this startup attempt with stock repositories unchanged;
  do not repeatedly allocate on later LoadAll callbacks after a failure.
- User's14-song files verified intact29355554B. Maximum retained raw files for
  that set drops to2896765B, excluding Unity's own texture/audio memory. This
  addresses accumulated raw-memory scaling; missing-playlist console fix is not
  yet hardware-confirmed, and no specific nativeheap limit has been proven.
- Enabled/disabled player notifications now say By Wkrotik; diagnostic variant
  identity remains in logs. Both release and DEBUG rebuilt. No auto-install.

## [v0.8071] — simplified OrBeats player notifications (local candidate)

- Use OrBeats in boot and in-game toggle notifications. Enabled boot toast shows
  product/version and Wkrotik only; remove DEBUG and redundant ON text. Explicit
  disabled/official-songs-only recovery message remains. Diagnostic/release builds
  still exist; their identity stays in logs, not player-facing boot notifications.
- Preserve GPL/upstream attribution in source/distribution, all flags, stock data,
  manifest ABI and the existing64-song candidate cap. No new capacity increase.
- Release and DEBUG native builds pass without compiler/linker warnings; full host
  regressions pass. Not installed on console; last verified installed0.8068 still
  uses its matched capability profile (8songs), not this candidate's64-song cap.

## [v0.8070] — OrBeats branding, local candidate

- Adopt the user-selected OrBeats name in startup logs and ON/OFF notifications.
- Keep Wkrotik attribution, protocol, paths, IDs and recovery flags unchanged.
- Not deployed or hardware-validated yet.

## [v0.8069] — overnight candidate

- Expand matched parser/publication bounds to 64 entries and 131072 manifest bytes;
  extend GC-root budget and host regressions without claiming 64-song hardware parity.
- Introduce the initial product-branded, count-free runtime notifications.
- DEBUG/release builds and host tests pass; no overnight PS4 deployment.

## [v0.8068] — 2026-10-26

- Read bounded v1 companion library at deferred setup; retain two-song defaults only
  when absent, refuse invalid/incomplete present libraries before hooks/publication.
- Derive own paths/assets and per-song routing/media/metadata from validated records;
  preserve current playlist art/order, exact-ID/free-membership guards and rollback.
- Local regression coverage includes eight generated levels; new native path still
  requires user-observed hardware validation. v0.8067 two-song playback is confirmed.

## [v0.8067] — 2026-10-25 (Exp310, two-song test)

- Keep Wake Me Up and add reviewed Cities / Throttle / VoltageO (BeatSaver4ebb2)
  as two independent entries in the SAME first-position Custom Songs pack.
- Batch repository publication/verification/rollback and exact local/free-ID policy;
  per-song metadata, native media cache, difficulty mask and load/existence routing.
- Keep Cities Hard/Expert/Expert+ only (no fabricated Easy/Normal). Vanilla BPM
  baking preserves note/light/wall endpoint seconds; no mod geometry discarded.
- Sample-domain preview trimming fixes Ogg/resampler extra-block mismatch. Cities
 20s preview and cover are independent, playlist icon remains shared.
- Both descriptors and full bundle hashes are still compile-reviewed; NOT a general
  additive companion/library installer. No stock/DLC entitlement broadening.
- Local1063 tests pass including sample-accurate fractional Ogg regressions,
  both native builds clean;0.8067 DEBUG installed+fullreadback, freshcapture active.
  Hardware two-song validation still pending.

## [v0.8066] — 2026-10-25 (Exp309)

- Put the own independent-ID Custom Songs pack first in each prepared repository;
  preserve official relative order and lookup identity. Exact game menu retains
  OST order before DLC concatenation; no UI detour or name prefix.
- Keep duplicate-stock diagnostic proof appended (first-wins stock lookup).
- Remove startup feature counter and calculation, retain version/DEBUG, kill-switch
  state, Wkrotik fork and Chris Primeish upstream credits. Feature flags still exist.
- 0.8065 own cover/pack selection/audio preview and song playback confirmed by user
  m08604; new ordering/notification build still needs a separate hardware check.
- 1034 host tests pass; DEBUG/release builds clean; 0.8066 DEBUG deployed and
  full canonical ELF verified. Additive ON-only flags/media/gameplay unchanged.

## [v0.8065] — 2026-10-25 (Exp307, local corrective candidate)

- Avoid ambiguous Sprite.Create arity3: pinned PS4 metadata has internal textureless and public textured overloads with same name/count. Use unique5-argument Texture2D/Rect/Vector2/float/uint overload instead.
- Read back Sprite.texture and require original Texture2D before publishing artwork/pack. Refuse null/wrong/exception/missing getter rather than allow pack-detail null texture crash.
- Correct native mocks to model real arity3 collision; add null/wrong texture and getter failure regressions. Pixel size unchanged; not established as crash cause.
- Exp3060.8064 menu crash archived and additive OFF restored. Exp308 explicitly authorized: corrective build installed+verified, additiveON-only for captured test; hardware menu result PENDING. No automatic launch, legacy flag or playlist-order changes.

## [v0.8064] — 2026-10-25 (Exp305)

- Own menu media for reviewed additive level only, separate user-provided pack icon; managed Unity creation/validated preview references, bounded no-retry title cache, unchanged stock media and gameplay bundle.
- Wkrotik additive-fork credit in plugin log and ON/OFF notifications, retain Chris Primeish upstream credit.
-1026host tests pass124skip; hardware media/UI untested, existing additive OFF gate retained. No general additive CLI/webapp installer yet.

## v0.8063 —2026-10-25 (development, Exp303)
- Bind one full independently stored vanilla map Wake Me Up (BeatSaver437d), with
  real artist/duration/BPM and per-difficulty notes/bombs/walls/NJS/jump offsets.
- Rename default additive group Custom Songs; no one-pack-per-song requirement.
-1006passed124skipped incl native sanitizer stats regressions. Hardware/audio
  success unproven; old stock lookup/paid-content checks still unchanged.

## v0.8062 — 2026-10-25 (development, Exp301)
- Correct omitted free/local registration for ONLY fixed self-authored proof IDs.
  Contains/Add/Remove with boxed bool API, GC roots, membership readback, rollback
  on later publication failure and verified repeat path; no platform/DLC hooks.
-0.8061 hardware had metadata/12seconds but gray/download/Buy, not playback.
-997passed124skipped; hardware fix pending; OFF until user-ready capture.

## v0.8061 —2026-10-25 (experimental, Exp300)
- Independent fixed-profile level/dictionary/basic-data construction using managed
  APIs, new-ID/original lookup preservation and publication readback/rollback.
- Exact-ID-only native bundle/existence path wrappers preserve stock calls, real
  async outcomes and cancellation; extra class-value-size API/layout guard.
- Optional exact generated bundle gate; absent retains stock proof, bad refuses.
- Reuses stock art/menu preview/mapper labels intentionally for first content test.
-996passed124skip, native sanitizers/mutation/wrapper/file/profile regressions;
  hardware independent-content playback remains UNPROVEN. Existing approved
  enable_additive_song_packs OFF default; no new entitlement/global hook changes.

## Exp299 note — 2026-10-25 (NO plugin change/version bump)
- Host-only independent bundle CLI added; pipeline0.5368/991tests124skip. Plugin
  source0.8060 purchase-button correction remains local; installed0.8059 unchanged.
- No custom-level registration/path hook shipped; do not claim a new song playable.

# Plugin Changelog — Beat Saber Deluxe

All notable changes to the GoldHEN plugin (`beat_saber_deluxe.prx`) are documented here.

**Version scheme:** Increment by **0.0001** per experiment (e.g. v0.80 → v0.8001 → v0.8002). This gives ample room to iterate before reaching v1.00.

## v0.8059 — 2026-10-25 (development candidate, Exp295/296)
- Fix actual managed-reference setter ABI: pass repository object itself, not
  pointer-to-pointer. Counts retain scalar address. Klog startup fault and owned
  export disassembly independently establish why0.8058 stored native stack slots.
- Retain originals with GC roots, read back references/count after publication,
  restore on mismatch and distinguish failed rollback from unchanged failures.
- Correct synthetic setter ABI; RED old-code and mutation regression now catch
  the former bug.962host tests124skip, ASan+UBSan and clean debug/release builds.
- Exp296: rebuilt962pass124skip, installed/readback verified; user confirms extra normal pack/single stock song and log confirms reference publication. Playback, distinct level IDs and custom maps NOT verified; awaiting final close/log archive/OFF cleanup.

## v0.8058 — 2026-10-25 (unreleased, Exp293 HARDWARE CRASH)
- Hardware result overrides candidate validation: repository-published log then
  crash; cause unknown. Additive disabled on console; do not retest yet.
- Hardware0.8057 resolved all20 APIs and reached post-LoadAll; pack refused with
  generic Incompatible. No registration/UI success.
- Correct known ctor ordering: allPacksCount initialized AFTER LoadAll returns.
  Keep zero field untouched until caller initializes it; positive reload count
  derives from validated loaded-array length+1, avoiding stale-count drift.
- Add per-guard stage, repository, three array counts and model-count diagnostic.
  Preserve all managed/class/offset/array/exception/old-lookup validation gates.
- 960host tests124skipped, native sanitizer zero-count ctor/reload and specific
  refusal tests, clean release/debug builds pass. Hardware candidate pending.

## v0.8057 — 2026-10-25 (local unreleased, Exp292)
- Correct additive API lookup: identify unique exact Il2CppUserAssemblies.prx
  module, resolve public names through sceKernelDlsym with explicit handle,
  reject null/error/nonlocal/nonexecutable function addresses. No offset fallback.
- Exp291 generic libc RTLD_DEFAULT resolver refused first API; all20 APIs have
  statically verified NID exports in owned PRX. Live corrected lookup NOT tested.
- Keep OFF-default experiment, bounded retries, known-method fingerprints and
  managed registration logic. Log20 resolved APIs separately from hook/pack success.
- 959 host tests passed124skipped; native ASan/UBSan lookup-policy checks and clean
  release/debug builds pass. Installed0.8056 remains unchanged; no UI/playback proof.

## v0.8056 — 2026-10-25 (local unreleased, Exp 289)
- Add user-approved OFF-default enable_additive_song_packs experiment, global
  kill-switch gated. A new ordinary BSD Additive Proof pack references one owned
  stock level; does not create a distinct ID or load custom maps.
- Guard post-LoadAll hook by partial code fingerprints and20 required public
  IL2CPP symbols. Missing/incompatible => no guessed API fallback. Managed
  constructors/roots/barriers; build3 fresh repositories, verify original pack
  prefix + old level/level->pack mappings before publish. DLC unchanged.
- Prototype refuses with replacements/metadata/mode/previews enabled. Existing
  defaults preserved. Version/debug banner+7-feature toast synchronized with UI.
- Native synthetic ASan/UBSan success/idempotence/failure tests pass; clean
  release/debug builds pass. NO console installation, API/ABI/GC/UI/gameplay proof.


## [v0.8055] — 2026-10-19
### Changed — Fresh-install defaults (Exp 281, user directive): ALL feature flags default ON
- **A fresh install now works out of the box.** When `features.json` is absent (a clean console — after Clear PS4 or a brand-new user), the plugin boots with **every feature ON** (redirects, metadata swaps, mode buttons, previews, the M11 in-game toggle, the M12 game-data extractor) instead of the old all-OFF-absent-kill-switch behavior. The user's words: "These feature flags should all default to ON on a fresh install." The `enable_plugin` kill switch remains the master off. The pipeline's `DEFAULT_FEATURES` and the webapp's `DEFAULTS_TRUE`/`KNOWN_FLAGS` mirror this exactly — the three must stay in sync (the sync rule is now in CLAUDE.md §2).
- Also fixes a missed M12 edit found by the user mid-validation: the webapp's `KNOWN_FLAGS` never gained `enable_game_data_extractor` (a failed edit call that was never re-applied) — the flag was invisible on the Feature Flags tab. Now present + the fresh-install defaults render it ON.

## [v0.8054] — 2026-10-19
### Added — M12: the in-console game-data extractor (eliminates the PC-side dump requirement for users)
- **`enable_game_data_extractor` feature flag** (defaults false; console-maintenance tooling like the M11 hotkey — deliberately NOT gated by the enable_plugin kill switch). When armed, the plugin reads `game_data_requests.txt` (web-app/pipeline-owned: one relative path per line) and **stream-copies each requested file from the game's own decrypted mounts to `game_data/` in the AFR dir during a normal boot** — the game reads its assets from `/archive/mount/point/Media/...` and `/app0/Media/...` (log-proven: 1,067 + 1,073 opens in the archived boot logs; both prefixes tried per file).
- **What it extracts:** the exact files the pipeline needs — per-slot template bundles (~13MB each), the target packs' `_pack_assets_all_` bundles, and `aa/catalog.json`. ~658MB for a full 5-pack/47-song loadout (vs the 4.9GB dump); ~140MB per pack; one ~13MB file per single-song addition. **Legally clean:** per-user extraction from their own console; the repo ships only tooling.
- **Idempotence + retries:** `game_data_status.txt` (plugin-owned) records one extracted path per line; already-done files are skipped on later boots; failures append `ERR <rel> <reason>` lines that never match a request line, so they **retry automatically on the next boot**. Line-exact matching (a rel that is a suffix of another can never false-match as done).
- **Robustness:** mkdir-p chain for the target layout; 256KB static copy buffer (zero stack pressure); once-per-boot state; per-file logging with byte counts + which mount served each file; generous summary line. All extraction I/O via direct `sceKernelOpen` (bypasses our own open-hook — no redirection interference).
- Boot toast now counts **N/6 features**; the `features:` boot log line + the ARMED lines gain the extractor.
- **PS4-side extraction feedback (Exp 281b, user request):** when an extraction run actually produced files, the plugin sends a notification — "BSD: game data ready — N file(s) extracted — pull them from the web app" — the user's in-VR cue that the web app can pull. Silent on already-extracted boots (the common case).

## [v0.8053] — 2026-10-16
### Added — M11 HARDWARE-CONFIRMED (Exp 278f)
- **🎉 THE HOTKEY WORKS ON REAL HARDWARE — both directions.** The v0.8052 debug build's log (archived: `v0.8052_hotkey_hardware_success.txt`, 3 boot sessions) confirms every layer: eboot-GOT hijacks install each session (`scePadRead` at open #1, `sceMoveReadStateRecent` at VR init, orig=0x80081db00), the call form is **4-arg** (shadPS4's SDK signature correct), and the Move button + trigger 2-second combo fired `enable_plugin flipped to false (OFF)` from inside VR, then — after a restart into the OFF state with the hotkey STILL ARMED (the one-way-door design working) — `flipped to true (ON)`. User-confirmed in-game; the notification is AUDIBLE in VR even when the popup is not visible.
- **Debug-variant indicator (user request):** the boot toast and the log banner now carry a ` DEBUG` suffix when running the DEBUG=1 build (`PLUGIN_VARIANT`) — logs and in-game toasts always show WHICH build produced them. The release build reports plain `v0.8053` (verified: zero DEBUG strings in the release binary).
- Release build redeployed to the console (production posture restored after the debug test round).
### Known design note (no action)
- The debug build's raw-word change-logging budget (40 lines) exhausts instantly on live tracking data — the accelerometer/gyro words churn every frame. Future button diagnostics should compare only the button words (+0x18/+0x1A). Irrelevant to the release build (diagnostics are VERBOSE_LOG-gated) and to the now-confirmed feature.

## [v0.8052] — 2026-10-16
### Fixed — v0.8051 black-screen hang RCA (Exp 278e): GOT HIJACKING replaces code Detour
- **THE HANG:** the v0.8051 hardware test hung the game at a black screen before the VR screen. The log showed the GOT resolution WORKED (eboot.bin base 0x400000; scePadRead slot bound → "hooked at 800439fe0") — and then ZERO padRead diagnostics: the **Detour trampoline over scePadRead's real code corrupted its non-relocatable prologue (dense RIP-relative library code) and the first call killed the calling thread**. Two more discoveries from the same log: **PS4 JUMP_SLOT imports bind LAZILY** (the move slot held the sentinel `0xeffffffe000001a0` — encoding the relocation index 0x1A0 — until the game's first call binds it; the file-initial values are the in-eboot PLT resolver stub addresses 0x1822480/0x18224b0), so the move hook must WAIT for binding.
- **THE FIX — GOT HIJACKING:** overwrite the slot VALUE with the hook's address after `sceKernelMprotect`ing the RELRO page RW (atomic aligned 8-byte write — no races; readers see old-or-new, both valid), restore the page protection, and have the hook call the SAVED original pointer directly. **No trampoline, no code patching, no relocation risk** — the entire crash class is structurally eliminated. Hijack guards: reject unbound values, reject lazy PLT-stub values inside the eboot's text span, require mapped-readable validation, mprotect failure aborts cleanly (never crash the game for a hotkey). Move retry budget 2000 opens (slot binds at VR init); pad budget 100 (bound at open #1).
### Changed — release-performance policy (user directive)
- **All per-call diagnostics (raw-word dumps, change logging, retry progress) are DEBUG-BUILD ONLY** (`#ifdef VERBOSE_LOG`, the Makefile's `DEBUG=1` flag). The release build logs one-time events only (hotkey ARMED, eboot base, hijack installed, form detected, ERROR give-ups, toggle flips, cooldown notes) and its hot path is a handful of instructions — **form detection is now CACHED** (no per-call sceKernelQueryMemoryProtection syscalls after the first detection).
- The debug build (deployed for this hardware round via `--debug-logging`) carries the full diagnostics: every button press lights up the log with the raw SceMoveData words, confirming/correcting the +0x18/+0x1A button-bit layout empirically.

## [v0.8051] — 2026-10-16
### Fixed — v0.8050 hardware failure RCA (Exp 278d): the definitive hook-resolution mechanism
- **NID dlsym ALSO finds nothing** (the v0.8050 log: 100 failed attempts for BOTH `q1cHNfGycLI` and the readable name) — `dlsym(RTLD_DEFAULT)` cannot see kernel-loaded Sony SPRX exports AT ALL on PS4; it only ever resolved `il2cpp_string_new` because that symbol is exported by a game module (Il2CppUserAssemblies.prx / eboot).
- **THE FIX: resolve system-library functions via the EBOOT'S GOT.** The eboot's import slots (vaddrs taken from its JMPREL relocations, type R_X86_64_JUMP_SLOT — precomputed from the decrypted dump: `sceMoveReadStateRecent` → GOT RVA 0x1c634e8, `scePadRead` → 0x1c63500) hold the final resolved function addresses, written by the OS module loader at bind time. The plugin finds `eboot.bin` by name via `sceKernelGetModuleList` (it is module[0] from the very first open — log-verified), reads `*(uint64_t*)(base + rva)`, validates the value as mapped readable code via `sceKernelQueryMemoryProtection`, and Detours the resolved address — hooking the LIBRARY function itself, which catches calls from any module.
- Removed the (hardware-proven dead) dlsym calls for system libraries; all retry/give-up/latch/combo/diagnostic machinery unchanged.

## [v0.8050] — 2026-10-15
### Fixed — v0.8049 hardware failure RCA (Exp 278b/278c)
- **ROOT CAUSE of the L3+R3 hotkey never firing: `dlsym(RTLD_DEFAULT, "scePadRead")` FAILED** — the boot log showed 100 failed attempts then "ERROR: scePadRead never found". **Sony system libraries export functions under their NIDs, not readable names** (the game imports scePadRead as NID `q1cHNfGycLI`); readable-name dlsym only ever worked in this codebase for eboot-exported symbols like `il2cpp_string_new`. All hooks now resolve **BY NID first** (readable name kept as fallback): scePadRead = `q1cHNfGycLI`, sceMoveReadStateRecent = `f2bcpK6kJfg` (both NIDs verified from the game's own import table via the Exp-278 eboot NID decode).
- **Give-up spam fix:** after 100 failed attempts the retry loop now sets a gave-up flag and stops — v0.8049 re-logged its ERROR line on every subsequent file open.
### Changed — hotkey moved to the Move controller (user-directed redesign)
- **New combo: hold the Move BUTTON + TRIGGER together for 2 full seconds** (user-chosen — a combination used nowhere else in Beat Saber; the DS4 is ignored by the game in VR mode, confirmed by the user's hardware test). **Primary hook: `sceMoveReadStateRecent`** — the ONLY Move state read in the eboot's imports (`sceMoveReadStateLatest` is not imported), so Unity's runtime reads both Moves through it every frame.
- **Move button bits reconstructed from the game's own enum** (dump.cs `PSVRDeviceManager.PSMoveButton`: Select=1, [2=trigger — skipped by the game because it reads the trigger via GetPSMoveAnalog], Move=4, Start=8, Triangle=16, Circle=32, Cross=64, Square=128): **Move button = 0x4, trigger digital bit = 0x2**; SceMoveData layout per shadPS4Plus's SDK-derived OrbisMoveData (**button_data u16 @ +0x18, trigger analog u16 @ +0x1A**; trigger counts as held via its digital bit OR analog > 0x80).
- **Signature ambiguity handled safely at runtime:** shadPS4 documents sceMoveReadStateRecent as 4-arg (handle, timestamp, data, out_count) — the hook validates which register holds the output buffer via `sceKernelQueryMemoryProtection` (the v0.8045-proven signal-free technique; an int arg fails RW-pointer validation) and passes ALL FOUR registers through, so either a 3-arg or 4-arg form works; unknown forms pass through untouched.
- **Shared combo detector:** both Move handles interleave their per-frame polls — a 250 ms poll-gap window keeps one handle's non-combo polls from resetting a hold the other handle sustains; release latch + 3 s global cooldown prevent double-fires from the two hook paths (pad path kept as a secondary DS4 path, now NID-resolved).
- **Empirical offset confirmation built in:** the Move hook logs the first 10 calls raw plus every data-word change (capped at 40 lines) — a button press lights up the boot log, confirming/correcting the +0x18/+0x1A offsets from the first hardware boot even if the layout guess were wrong.

## [v0.8049] — 2026-10-14
### Added
- **M11: In-game global plugin toggle — L3+R3 hotkey (Exp 278).** Hold **L3+R3 together for 2 full seconds** on a DualShock 4 and the plugin flips its own global state (`enable_plugin` inside `features.json`) — no PC required to switch between all-custom and 100% stock Beat Saber. Gated behind the new `enable_in_game_plugin_toggle` feature flag (defaults false). Verified research: Beat Saber polls pads via native `scePadRead` (the eboot imports it; `scePadReadState` is NOT imported; Moves are read via the separate `libSceMove`, so a Move physically cannot set the L3/R3 bits) — the hook is `dlsym(RTLD_DEFAULT, "scePadRead")` + GoldHEN Detour, lazily installed from `open_hook()` (the proven il2cpp_string_new pattern; libScePad loads with the game).
- **Accidental-trigger protection (user requirement):** the combo must be CLEAN — `buttons == L3|R3` EXACTLY (0x0006; any other digital bit — face, shoulder, dpad, touchpad click — resets the hold), held a full 2 s timed by `sceKernelGetProcessTime()` (µs), with a release latch requiring the combo to be let go before the next toggle can fire. Jostling a DS4 mid-swing cannot satisfy it.
- **Persist-only semantics (user-approved):** the hotkey edits `features.json` for the NEXT boot — `"enable_plugin": true↔false` flipped IN PLACE (surgical byte edit via memmove, preserving every other key/byte) — and notifies "BS Deluxe: Plugin ENABLED/DISABLED — restart game to apply". The CURRENT session's behavior NEVER changes (boot-time flags govern runtime as always), eliminating every mixed-state hazard (mode buttons can never point at unloaded stock data mid-session). The pipeline's Exp-248 pull-before-push reads the LIVE file, so in-game flips flow into webapp/ps4_state/pipeline deploys automatically.
- **One-way-door prevention (deliberate):** the hotkey is gated ONLY by `enable_in_game_plugin_toggle` — NOT by the `enable_plugin` kill switch. A user who toggled OFF must be able to flip back ON from the couch; the kill switch disables game-behavior features (redirects/metadata/modes/previews), not the plugin's own control surface. Only `enable_in_game_plugin_toggle=false` disables the hotkey.
- **Diagnostics for the hardware test:** first 8 scePadRead calls logged (handle/num/return/buttons — answers "does the game poll a boot-connected DS4 every frame?" from the boot log), a liveness counter every 10,000 calls, install/not-found retry logging, and a boot-time "hotkey ARMED" line. Key-absent `enable_plugin` edge case handled by rewriting the file with all known keys.
- **Boot toast now counts 5 features** (`(N/5 features ON)`); the FEATURE FLAGS boot log line now includes song_previews and in_game_plugin_toggle.

## [v0.8048] — 2026-10-09
### Added
- **`enable_song_previews` feature flag (M10, Exp 269).** Parsed from features.json like its siblings (`enable_song_previews` → `g_feature_song_previews`); logged in the features boot line; counted in the boot toast (now N/4). The song-menu preview swap itself is pure pipeline data (preview AudioClips inside the deployed pack bundle) — the plugin's role is the redirect-set switch: the Exp-222 pack-assets/catalog gate now serves the patched bundle pair when EITHER `enable_beatmap_mode_mapping` OR `enable_song_previews` is ON; both OFF skips the pair so the stock bundle + origin catalog load (no CRC crash — Exp 180 invariant preserved). The redirect VALUE already names the variant matching the flag state at deploy time.

## [v0.8047] — 2026-09-24
### Fixed
- **Non-ASCII song titles never matched their metadata replacement (Exp 228 — '…Baby One More Time').** Three-part root cause: (1) the pipeline wrote `song_metadata.json` with `ensure_ascii=True`, shipping the key as the 6-ASCII-byte escape `…` — the plugin's byte-verbatim `parse_json_pairs` compared those literal bytes; (2) the game's UTF-16 title (U+2026 ellipsis) folds to `?` in `extract_utf16_string`; (3) no amount of unescaping alone fixes the fold mismatch. Fixes: `json_unescape_inplace()` unescapes `\uXXXX`/`\n`/`\\` etc. in parsed keys/values (backward compat with already-deployed escaped files); `fold_utf8_to_ascii()` folds loaded KEYS through the same projection as extraction (BMP char → 1 `?`, astral → 2 `?` — an exact byte-for-byte mirror) so comparison succeeds for ANY Unicode title; values stay raw UTF-8 (display strings).
- **`create_il2cpp_string` (manual fallback) wrote mojibake for non-ASCII replacement values:** one UTF-16 code unit per BYTE (`…` → two code units). Now decodes UTF-8 → code points → UTF-16LE properly; malformed bytes and astral chars fold to `?`. `il2cpp_string_new` (primary path) already handled UTF-8 correctly.

## [v0.8046] — 2026-09-19
### Fixed
- **`enable_beatmap_mode_mapping` was DECORATIVE (Exp 222 audit):** the flag was read, logged, and counted but gated NOTHING — which is why the mode selector worked while the flag was silently absent ("2/3 feature flags"). It now genuinely gates the feature: when OFF, the open-hook redirect loop skips `pack_assets` bundle redirects AND the `catalog` redirect, so the game loads STOCK pack bundles (Standard-only preview sets, no extra mode buttons) while per-song customs (audio + Standard beatmaps) keep working. The catalog skip is required by the Exp 180 invariant: the patched catalog's m_Crc/m_BundleSize describe the PATCHED pack bundles — serving it against stock bundles fails Unity's CRC validation and crashes the pack scan.
- The "beatmap_mode_mapping is OFF" startup log line now describes the real behavior (pack bundle + catalog redirects skipped) instead of claiming "extra mode sets hidden" with no implementation behind it.
- **Gating contract enforced by tests:** new `TestFeatureFlagGatingAudit` (5 tests) pins that all four flags have behavioral gates — including `test_no_flag_is_decorative`, which fails if any `g_feature_*` variable has no conditional use outside `load_features`.

## [v0.8045] — 2026-09-19
### Changed
- **Single compressed boot notification** (Exp 221): the version banner and the feature-flag status are now ONE toast — `BS Deluxe v0.8045 (ON) / By Chris Primeish / (3/3 features ON)` — because the PS4VR headset switch-over swallows the second toast when the headset is already powered on at launch (user-verified: both toasts appear only when launching with the headset off). Kill switch OFF variant: `BS Deluxe v0.8045 (OFF) / By Chris Primeish / (official songs only)`. The v0.8044 two-toast format is superseded.

## [v0.8044] — 2026-09-19
### Added
- **Startup feature-flag status notification** — a second toast right after the version banner shows the plugin's overall state and enabled-flag count at a glance:
  - Kill switch ON: `BSD Plugin enabled\n<N>/3 feature flags ON` (counts `enable_custom_song_replacements` + `enable_song_metadata_modification` + `enable_beatmap_mode_mapping`).
  - Kill switch OFF: `BSD Plugin DISABLED\nOfficial songs only (0/3 flags active)` — instantly visible that the plugin is inert before browsing to any song.
- The `FEATURE FLAGS:` log line now includes `plugin=ON|OFF` alongside the three per-feature flags.
- **Plugin version bump** to v0.8044.

## [v0.8043] — 2026-09-18
### Added
- **Global kill switch `enable_plugin`** (runtime feature flag in `features.json`). When explicitly `false`, ALL plugin behavior is inert: no `redirects.json` redirects fire (stock song bundles and stock pack bundles load), and all song-metadata swap hooks (TMP set_text/SetText, MoveNext, metadata replacement) return the stock values untouched. The plugin still loads and logs (so `bs_log.txt` shows `DISABLED: enable_plugin is false`), but the game plays 100% official content.
- **Default semantics:** `enable_plugin` defaults TRUE when the key is absent (unlike every other flag, which default false) — a missing features.json keeps a fully-deployed setup working, and only an explicit `false` disables the plugin.
- Pipeline command pair (v0.5339+):
  - Disable everything, play official songs: `python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=false`
  - Re-enable the custom setup: `python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_plugin=true`
  - Takes effect on the next game boot (features.json is read at plugin startup). No plugins.ini edit, no PS4 clean, no file removal.
- **Plugin version bump** to v0.8043.

## [v0.8042] — 2026-09-14
### Added
- **Runtime feature flag `enable_beatmap_mode_mapping`** — parsed from `features.json` at startup, stored in `g_feature_beatmap_mode_mapping`. Gates the visibility of extra mode sets (OneSaber, NoArrows, 90Degree) in pack bundle `_previewDifficultyBeatmapSets`. When OFF (default when missing), all songs show only Standard mode — safe for partial pack deployments where only some songs are custom. When ON, custom songs with patched mode sets show all 4 modes; stock songs (unpatched) show only Standard. This prevents crashes when selecting non-Standard modes on unmodified songs.
- **Plugin version bump** to v0.8042.

## [v0.8040 (RE-RESTORED to a8a06f0)] — 2026-08-18
### Reverted
- **Startup-crash fix (Exp 193):** after Exp 192 a different model regressed `src/main.cpp` (commits `311c6ff` v0.8049, `9326177`/`a47918e` v0.8050 360Degree purge, `e18921b` re-enabled RAM mode injection) → `cb2ed1a` instant crash at startup with NO plugin notification. Chris's manual revert to v0.8040 (`298bbd2`) still crashed (corrupted, non-baseline source).
- **Restored `src/main.cpp` to the exact stable baseline `a8a06f0`** (the v0.8051-parent used successfully across Exp 176–192, and in the Aug-17 clean boot). GoldHEN Detour API hooks for fopen/open/close + TMP_Text/MoveNext metadata hooks; `enable_beatmap_mode_mapping` ignored (no RAM scan, no freeze, no crash). Rebuilt → valid FSELF (105,200 B), deployed to `/data/GoldHEN/plugins/`.
- **Asset layer verified clean** (so the revert is the real fix): catalog dataIndexes 0 invalid, all 4 patched packs + the typo-hash duplicate load in UnityPy, `redirects.json` 43 entries sane, 7 "missing-source" slots still have `*_v3.bundle` on PS4.

## [v0.8040 (RESTORED)] — 2026-08-06
### Reverted
- **Startup-crash fix:** v0.8050/v0.8051 caused an **instant crash at launch with no plugin notification** (Exp 176). Root cause: the v0.8050 "cleanup" rewrote `src/main.cpp` to use a **manual 12-byte `memcpy` absolute-jump hook** (`install_hook` on `sys_open`) and re-enabled `src/hooks.cpp` in the Makefile (it had been `filter-out`'d in every stable build). Writing over the live `open` prologue without a trampoline → CE-34878-0. The `cb2ed1a` `sceKernelMprotect` attempt did not help.
- **Restored plugin source to the exact v0.8051-parent baseline `a8a06f0` (v0.8040):** `src/main.cpp` (795 lines, GoldHEN `Detour_Construct`/`Detour_DetourFunction` API for fopen/open/close + TMP_Text/MoveNext metadata hooks), `src/hooks.cpp` (excluded from build again), `Makefile` (`filter-out src/crt_patch.cpp src/hooks.cpp src/main_printf_backup.cpp`).
- Build: 88,752 bytes. All 365 tests pass. Deployed to PS4.
### Removed
- Legacy memory-scan machinery was NOT reintroduced — v0.8040 already predates the Phase 2 scan experiments (Exp 160+). The mode-mapping feature flag (`enable_beatmap_mode_mapping`) is simply ignored by v0.8040 (no scan, no freeze, no crash).

## [v0.8051] — 2026-08-04
### Changed
- **Removed legacy memory injection scan** — Cleaned all memory-scanning logic and scan-worker threads from `src/main.cpp`, fixing the multi-minute startup freeze.
- Version bump v0.8050 → v0.8051.
- ⚠️ **REVERTED 2026-08-06** — this build crashed Beat Saber instantly at startup (manual `memcpy` hook architecture). See v0.8040 (RESTORED) above.

## [v0.8050] — 2026-08-04
### Changed
- **Purged all 360Degree mode support** across plugin (`src/main.cpp`), pipeline, tools, and test suites, aligning with PS4 physical single-camera (~90°) tracking limitations.
- Retained 4 valid modes: `Standard`, `OneSaber`, `NoArrows`, `90Degree`, gated behind the existing `enable_beatmap_mode_mapping` / `g_feature_beatmap_mode_mapping` feature flag.
- Version bump v0.8049 → v0.8050. All tests passing.

## [v0.8049] — 2026-08-03
### Changed
- **Removed strict bundle-open gate on MoveNext scan trigger** — v0.8048's `g_mode_pack_last_open` bundle-open guard prevented the scan from firing when navigating song lists because the pack bundle open happened before the final cell render sequence. Moving to v0.8049 allows the scan to fire immediately on the first MoveNext occurrence without strict dependency on a subsequent pack bundle open event.
- **Audio preview preservation** — Verified that synchronous heap scans inside `open_hook` break audio preview streaming threads; mode scan triggering is kept strictly decoupled in `MoveNext` and song-start hooks.
- Version bump v0.8048 → v0.8049. Build 105,120 bytes. 361/361 pytest pass.
### Changed
- **Scan trigger timing fix (v0.8047 test result: scan fired before any pack BeatmapLevelSO was deserialized)** — the v0.8047 log (`v0.8047_scan_diag.txt`, 893 lines) proved the root cause was **timing, not scan logic or offsets**: the scan ran from the FIRST MoveNext call (open #731), but the selected pack's bundle only (re)opened at `[OPEN #792]`/`#794` — AFTER all 22 song cells had rendered. Every BeatmapLevelSO offset (0x18/0x20/0x98, verified against `dump.cs` TypeDefIndex 11680) was correct; the objects simply didn't exist in the GC heap yet. So v0.8048:
  - **Tracked pack data loads** — `open_hook` now records the last `*_pack_assets_all_*.bundle` open that happens **after** the first MoveNext (`g_mode_pack_last_open`). Startup catalog opens (before any MoveNext) only CRC-check bundles and are ignored.
  - **Gated MoveNext trigger** — `mode_try_patch_from_move_next` only fires the scan when a fresh pack data load occurred since the last scan (`g_mode_pack_last_open > g_mode_scan_last_open`).
  - **Retryable failures** — `mode_patch_all` no longer permanently sets `g_mode_preview_done = -1` on the klass-not-found / no-BSL / no-charSO paths. Failures now stay retryable, bounded by `MODE_MAX_ATTEMPTS` (4). This fixes the v0.8047 one-shot bug where a single too-early scan permanently disabled the feature.
  - **Song-start fallback trigger (v0.77-proven)** — `open_hook` also fires the scan when a `BeatmapLevelsData` path opens (custom song load), where v0.77 found 17 BSL candidates. Shares the same 4-attempt budget.
  - **Re-entrancy guard** — `g_mode_scan_in_progress` prevents the scan from re-triggering itself through the nested `log_write` → `open_hook` calls.
  - **MoveNext hook decoupled from metadata flag** — the hook (and mode trigger) now install and run when EITHER `song_metadata_modification` or `beatmap_mode_mapping` is on; the metadata replacement block stays gated on its own flag.
- Version bump v0.8047 → v0.8048. Build 105,120 bytes. 361/361 pytest pass.

## [v0.8047] — 2026-08-01
### Changed
- **Deeper mode-scan diagnostics (v0.8046 test result: all 25,443 candidates failed the preview-array check)** — v0.8046 found 12 candidates but every one was rejected by `mode_preview_arr_ok` (arrfail=25443, strfail=0). Candidate addresses (0x1C2–0x1D5xxxxx) + `lid=0x3BA3D70A...` (packed floats) identified them as **serialized pack-bundle data in RAM, not live managed objects**. v0.8047 changes the scan to prove this:
  - **v0.77-proven pointer upper bound** — levelID/songName/authorName must be `[16MB, 512GB]` (was unbounded above) to kill float/plain-data false positives (e.g. `0x3BA3D70A3BA3D70A`).
  - **Reordered checks** — the levelID **string extraction now runs BEFORE the preview-array check** (v0.8046 ran it after, so `strfail` was always 0 and nothing ever hit it).
  - **Klass-hit bucketing** — counters split `klass(mod)` (0x80000000–0x90000000) vs `klass(8g)` (0x200000000–0x210000000) so the log shows which range produces the false positives.
  - **`mode_preview_arr_ok` failure breakdown** — now returns a failure stage (1=arrptr, 2=arrklassRd, 3=arrklassRng, 4=len, 5=first, 6=elemKlass, 7=char, 8=diffs); the summary line reports counts per stage and the first 8 failures are logged with the levelID string.
  - **Raw-object dumps** — `[MODE] raw64@0x...` logs the first 64 bytes of up to 4 candidates for manual field-offset verification against the DummyDll layout (BLS_OFFSET_* constants may be wrong for v2.04).
- Version bump v0.8046 → v0.8047. Build 105,120 bytes. 361/361 pytest pass.

## [v0.8046] — 2026-07-31
### Fixed
- **"BeatmapLevelSO klass not found" (v0.8045 test result)** — v0.8045 no longer crashed (syscall probing confirmed working, `prot=0x3`), but the scan found no valid objects. Two bugs fixed:
  - **`mode_extract_string` length-selection bug** — `len = (len_10 valid && len_14 == 0) ? len_10 : len_14` always picked garbage `len_14`, because for a real IL2CPP string `len_14` is the first two UTF-16 chars combined (e.g. `0x00740053`), never 0. So every levelID extraction failed and the klass find returned nothing. Now mirrors `extract_utf16_string`'s proven fallback chain (use `len_10` unless `len_14` is a plausible length in `(0,256)`).
  - **Scan range too narrow** — v0.8045 scanned 16MB–4GB + 8–8.25GB; v0.77's proven scan that found 17 candidates covered 16MB–64GB. Low range widened to 16MB–64GB at 1MB page reads (same ~64K syscall count as the old 4GB@64KB, so the stutter stays brief); high 8–8.25GB range kept at 64KB.
- **1MB scan buffer moved off the stack** — `g_mode_scan_page` static global (v0.78 lesson: a 1MB stack buffer crashes the plugin).
### Added
- **Scan diagnostics** — `mode_find_beatmap_level_so_klass` now logs `[MODE]   cand klass=... @... ver=... lid=...` for the first 12 candidates passing the klass+version+pointer checks, plus a summary `[MODE] Scan diag: ok=N klass=N ver=N ptrs=N arrfail=N strfail=N` on failure — so the next test log shows exactly which structural check rejects candidates (and where they live).
- **Region-jump optimization** — when a page read fails (hole/partial mapping), the scan jumps to the next mapping boundary via `sceKernelQueryMemoryProtection` instead of stepping page-by-page.

## [v0.8045] — 2026-07-31
### Fixed
- **Instant crash when entering Solo song list (v0.8043/v0.8044 regression, root cause finally confirmed)** — both the worker-thread scan (v0.8043) and the synchronous in-hook scan (v0.8044) crashed with CE-34878-0 inside `mode_find_beatmap_level_so_klass()`. The crash log (`v0.8044_crash_sync.txt`) shows the scan started but the game died during it. Root cause: the proven-safe v0.74–v0.8008 scans ran from the **open()/redirect song-start hook** (GC quiescent), but the v0.8043/44 scans run during **song-list rendering**, when the game's GC actively throws page-protection SIGSEGV/SIGBUS faults on its own threads. Our process-wide handlers hijacked those faults → `siglongjmp` to the scan stack → instant crash, regardless of which thread ran the scan.
- **Signal-handler memory probing eliminated entirely** — `mode_try_read()`/`mode_extract_string()`/`extract_utf16_string()` now use **`sceKernelQueryMemoryProtection`** (a real libkernel syscall that queries the mapped range + protection of an address without faulting). This removes the whole class of "process-wide handler hijacks game GC faults" crashes, including the per-call `sigaction` in `extract_utf16_string`.
- **Safe self-test + fail-closed** — before scanning, the plugin verifies `sceKernelQueryMemoryProtection` returns sane results for a known-good address. If it's a stub (like mincore/msync), the mode scan is disabled cleanly (log message) instead of risking a crash.
### Removed
- `mode_install_handlers()`/`mode_restore_handlers()`/`mode_fault_handler()`, `g_mode_jmpbuf`, `g_old_segv`, `g_old_bus`, `g_mode_handlers_installed`, `g_extract_jmp_buf`, and the `<setjmp.h>`/`<signal.h>` includes.
### Changed
- Scan still triggers from the MoveNext hook during song-list rendering, but is now signal-free so it no longer depends on GC being quiescent.

## [v0.8044] — 2026-07-31
### Fixed
- **Instant crash when entering Solo song list (v0.8043 regression)** — the background scan worker thread installed process-wide SIGSEGV/SIGBUS handlers; while they were active, the game's own GC page-protection faults on the main thread were hijacked and `siglongjmp`'d into the worker's stack → instant crash. Reverted to the proven v0.74–v0.8008 pattern: **synchronous scan on the game thread** inside the MoveNext hook (game pauses ~1-2s once).
- **Per-page sigaction overhead removed** — handlers are now installed once via `mode_install_handlers()` for the whole scan and restored once by `mode_restore_handlers()`; `mode_try_read()`/`mode_extract_string()` take the fast path when handlers are already installed.
### Changed
- Removed the pthread worker thread and `-lpthread` from the Makefile.
- Widened BeatmapCharacteristicSO neighbor scan from ±2MB to ±16MB (characteristic SOs live in a shared bundle and may be farther apart).

## [v0.8043] — 2026-07-31
### Fixed
- **Mode scan trigger never fired** — v0.8042 required the runtime `BeatmapLevel.levelID` to start with `"custom/"`, but it is the original pack ID (e.g. "StartMeUp"). Trigger now fires on ANY song `BeatmapLevel` from the MoveNext hook.
- **Patch filter skipped everything** — v0.8042 only patched `BeatmapLevelSO` objects whose `_levelID` starts with `"custom/"`; pack `BeatmapLevelSO` objects carry original IDs. Now ALL found `BeatmapLevelSO` objects are patched (every pack on this PS4 is fully custom).
### Changed
- **Klass discovery is structural, not anchored** — `mode_find_beatmap_level_so_klass()` no longer needs a known levelID; it finds the first object matching klass-range + version 1-50 + valid `_levelID`/`_songName`/`_songAuthorName` pointers + a structurally valid `_previewDifficultyBeatmapSets` array (new `mode_preview_arr_ok()` guard, also applied in the collector to reject false positives).
- Added diagnostic logging of every found BeatmapLevelSO levelID/address.
- ⚠️ **NOT USER-TESTABLE — instant crash when entering Solo** (worker-thread signal hijack). Superseded by v0.8044.

## [v0.8042] — 2026-07-30
### Added
- Phase 2: BeatmapLevelSO memory injection for mode preview data
- Scans IL2CPP heap for BeatmapLevelSO objects matching custom song levelID
- Finds all 5 BeatmapCharacteristicSO by klass matching + serializedName validation
- Builds new _previewDifficultyBeatmapSets array with 5 mode entries at runtime
- Triggers once from MoveNext hook when first custom song cell renders
- Gated behind g_feature_beatmap_mode_mapping (enable_beatmap_mode_mapping flag)

## [v0.8041] — 2026-07-28
### Added
- **Feature flag `g_feature_beatmap_mode_mapping`** — parsed from `features.json` `enable_beatmap_mode_mapping` key. No runtime behavior in this release (pipeline-side only in v0.5307). Gating scaffold for Phase 2 (plugin runtime mode injection).

## [v0.8040] — 2026-07-27
### Fixed
- **Case-insensitive metadata matching** — `find_metadata_replacement()` now trims trailing spaces before comparison. Game uses different casing than expected (e.g. "all the good girls go to hell" vs "All The Good Girls Go to Hell", "Mess it Up" vs "Mess It Up").
### Changed
- **Pipeline reads exact song names from `beat_saber_song_ids.json`** — `manage_song_metadata()` now resolves slot IDs to exact game strings via `_lookup_song_name()`. No more manual casing guesswork.
- **`beat_saber_song_ids.json` copied to `beat_saber_deluxe/`** — Pipeline can access authoritative song names directly.

## [v0.8040] — 2026-07-26

## [v0.8039] — 2026-07-26
### Changed
- **Hooked `MoveNext()` instead of `SetDataFromLevelAsync`** — RVA `0x1D377C0`. The async wrapper at `0x1D36940` is a trampoline that gets inlined by `AsyncVoidMethodBuilder.Start<T>()` — our hook never fired (zero log entries). `MoveNext()` is where the actual work happens: reads `BeatmapLevel.songName`/`songAuthorName` and assigns to TMP_Text fields.
- State machine layout: `<>4__this` at 0x28, `beatmapLevel` at 0x30. Hook modifies BeatmapLevel fields at the start of `MoveNext()` before original reads them.

## [v0.8038] — 2026-07-26
### Added
- **Hooked `LevelListTableCell.SetDataFromLevelAsync`** — RVA `0x1D36940`. Modifies `BeatmapLevel.songName` (offset 0x20) and `songAuthorName` (offset 0x30) in-place BEFORE the original async method runs. The UI reads our replacement from the data source, bypassing the TMP_Text re-rendering issue.
### Approach
- This is the **data source modification** approach — instead of hooking text output methods (set_text/SetText), we modify the BeatmapLevel object that the UI reads from. Since BeatmapLevel fields are `readonly` (only enforced at compile time), we can write directly to the memory.
- The SetDataFromLevelAsync hook fires for each song list cell, reads the BeatmapLevel, and replaces songName/songAuthorName before the cell is populated.

## [v0.8037] — 2026-07-26
### Added
- **Second hook: `TMP_Text.SetText(string, bool)`** — RVA `0x2D3E1D0`. Song list uses `SetText()` for song name text instead of `set_text()` property setter. Both hooks now fire for song name and artist text.
- **Shared replacement logic** — Extracted `apply_metadata_replacement()` function used by both hooks. Reduces code duplication.
### Known Limitations
- **Song list names still not visible** — SetText hook fires and replacements are applied (log confirms), but song list still shows original names. Song list likely re-renders from a data model after our hook fires, overwriting the replacement. Need to investigate the rendering pipeline.

## [v0.8036] — 2026-07-26
### Added
- **External `song_metadata.json` loading** — Replaces hardcoded 13-entry `SONG_REPLACEMENTS[]` array with data-driven metadata loaded from `/data/GoldHEN/AFR/CUSA12878/song_metadata.json`. Two flat tables: `song_names` and `song_artists`.
- **`load_song_metadata()`** — Reads JSON file using same pattern as `load_redirects()`. Parses `"song_names"` and `"song_artists"` sections separately via `parse_json_pairs()`.
- **`find_metadata_replacement()`** — Searches song names first, then artists. Returns replacement string for hook callback.
- **`free_metadata()`** — Cleans up allocated metadata arrays on plugin unload.

### Changed
- **Feature flag gating** — Metadata loading only occurs when `enable_song_metadata_modification` is `true` in `features.json`. Hook still fires but skips replacement when flag is off.
- **Song replacement format** — Combined "CustomName / CustomArtist" format for song names. Artist field blanked for single-artist packs (e.g., "The Rolling Stones" → " ").

### Known Limitations
- Artist replacement is global — "The Rolling Stones" → " " affects all Rolling Stones songs, which is correct for single-artist packs but may show blank artist for all songs in the pack.
- Combined "Name / Artist" format in song name field — works but is a workaround for inability to replace artist independently.
- Deferred: Field-aware replacement (Phase 2) will fix artist accuracy for multi-artist packs.

## [v0.8035] — 2026-07-24
### Fixed
- **Remove free() of replacement strings** — set_text stores string reference internally for deferred rendering. Freeing caused use-after-free → "?" in song details.
- **Try il2cpp_string_new() first** — Uses IL2CPP runtime to create GC-managed strings. Falls back to manual create_il2cpp_string if not found.
- **Enhanced diagnostic logging** — Logs `this` pointer for replacements (identifies song name vs artist fields), hex dump of original string bytes for layout diagnosis.

## [v0.8034] — 2026-07-24
### Added
- **Phase 3: String replacement** — Creates new IL2CPP System.String with replacement text using klass pointer from original. Passes replacement to original `set_text` call. Frees allocated memory after call returns.

## [v0.8033] — 2026-07-24
### Fixed
- **Signal-protected string extraction** — `extract_utf16_string` now uses sigsetjmp/siglongjmp to catch SIGSEGV when `value` is not a valid IL2CPP string. v0.8032 crashed because hook fires for ALL TMP_Text.set_text calls, not just strings.

## [v0.8032] — 2026-07-24
### Added
- **String reading + match detection** — Phase 1 now reads UTF-16LE string from value parameter and checks against 14-song replacement table. Logs matches. DetourMode_x64 confirmed safe.

## [v0.8031] — 2026-07-24
### Fixed
- **Minimal hook callback** — Removed all string reading from hook. Phase 1 diagnostic only: log that hook fired with pointer values. Also switched from DetourMode_x32 to DetourMode_x64 (open/close hooks use x64 successfully).

## [v0.8030] — 2026-07-24
### Fixed
- **Stop retry after hook installed** — Added `g_tmp_hook_installed` flag to prevent double-hooking. v0.8029 crashed at attempt 4 because it installed the detour twice.

## [v0.8029] — 2026-07-24
### Fixed
- **Retry TMP_Text hook installation** — Module discovery now retries on each open() call (up to 50 attempts). First 3 attempts and every 20th logged. Skips early opens (<10) when only system modules visible.

## [v0.8028] — 2026-07-24
### Fixed
- **Deferred TMP_Text hook installation** — Moved from `module_start()` to `open_hook()`. At plugin load time only 3 modules visible; by first file open, all IL2CPP modules loaded. Single-shot flag prevents re-attempt.

## [v0.8027] — 2026-07-24
### Fixed
- **IL2CPP module buffer too small** — Increased `OrbisKernelModule` buffer from 64 to 256. PS4 loads more than 64 modules, causing `find_il2cpp_module_base()` to miss `Il2CppUserAssemblies`. Added diagnostic logging: logs all 20+ module names when IL2CPP module not found.

## [v0.8026] — 2026-07-24
### Added
- **TMP_Text.set_text hook** — Phase 1 of TextMeshPro UI hooking approach. Hooks `TMPro.TMP_Text::set_text(string)` (RVA `0x2D35BE0`) using `DetourMode_x32` to intercept song name/artist text in the UI. Currently logs all intercepted text matching the 13 Rolling Stones replacement table. Gated behind `enable_song_metadata_modification` feature flag. Uses `find_il2cpp_module_base()` to locate `Il2CppUserAssemblies` module and compute hook target address at runtime.

## [v0.8025] — 2026-07-23
### Changed
- **Removed all memory injection code** — Memory injection approach abandoned after 14+ versions (v0.66–v0.8024) found 0 strings across all memory regions. Removed: `memory_inject.cpp`, `memory_inject.h`, `register_song_metadata()`, and all related trigger/init code. Plugin now only handles file redirects via `open()` hook. Last commit with memory injection code: `1586581`.
- **Preserved `enable_song_metadata_modification` feature flag** — Flag kept in `features.json` and pipeline for future use when a new approach is implemented. Defaults to `false` (disabled).

## [v0.8024] — 2026-07-23
### Changed
- **Scan four memory ranges** — Added low memory (16MB–4GB) and extended heap (4GB–8GB) to scan. Pack bundles may be memory-mapped or read into buffers in low memory where Il2Cpp assemblies load (~2GB). Increased timeout to 15s for wider scan.

## [v0.8023] — 2026-07-23
### Changed
- **Trigger scan at BeatmapLevelsData redirect** — Changed trigger from `therollingstones_pack_assets_all` (OPEN #738) to first `BeatmapLevelsData` redirect (OPEN #740). BeatmapLevelSO objects are deserialized lazily — only when the game reads song data. At pack load, objects aren't in GC heap yet.

## [v0.8022] — 2026-07-23
### Changed
- **Scan BOTH GC heap AND metadata mmap** — v0.8021 only scanned ±256MB around metadata (0x293280000), but strings are in the GC heap (0x200000000–0x210000000). Now scans both ranges sequentially: GC heap (256MB) then metadata (512MB). Total ~768MB within 10s timeout.

## [v0.8021] — 2026-07-23
### Changed
- **Scan trigger moved to Rolling Stones pack load** — Changed trigger from first `pack_assets_all` (OPEN #207) to `therollingstones_pack_assets_all` (OPEN #738). Previous scan fired at startup but the target pack bundle doesn't load until much later. BeatmapLevelSO objects with song names are in the pack bundle, so scan must fire after it loads.

## [v0.8020] — 2026-07-22
### Changed
- **Scan metadata region directly** — Changed scan range from 4GB–17GB (13GB, never reached) to ±256MB around metadata base (0x293280000). Covers 512MB, completes in ~10s. Previous scan only reached ~400MB before timeout.
- **Comprehensive file-open logging** — Logs every file open with sequential counter and original path. Shows full load sequence including redirects.

## [v0.8019] — 2026-07-22
### Added
- **Diagnostic redirect logging** — Logs every redirect with sequential counter (`[REDIR #N]`) to map the file open sequence and timing. Helps identify the right trigger point for string scanning.

## [v0.8018] — 2026-07-22
### Fixed
- **Reduced scan timeout from 5s to 2s** — Prevents multi-minute black screen caused by repeated scans
- **Removed redirect-triggered retries** — Each of 32 redirects was re-triggering the scan, causing 160s of blocking. Now only scans once on pack_assets_all detection.
- **Scan once, no retry** — On failure, marks as done (`g_patching_done = -1`). Strings are not in memory at startup; they only load when the song list UI renders.

## [v0.8017] — 2026-07-21
### Fixed
- **Removed background thread** — `scePthreadCreate` inside `open_hook` callback causes CE-34878-0 crash. Replaced with synchronous `patch_strings_by_content()` call with signal handlers installed around it. No thread creation in hook context.
- **5-second scan timeout** — The synchronous scan uses `sceKernelGetProcessTime()` inside `patch_strings_by_content` to abort after 5 seconds if no strings found. Prevents indefinite hook blocking.

## [v0.8016] — 2026-07-21
### Changed
- **String content search via background thread** — Complete pivot from klass-pointer approach (broken after 10+ versions). Now searches for exact UTF-16LE song name strings ("Start Me Up", "The Rolling Stones") directly in memory. Runs in a background thread via `sceKernelStartThread` (non-blocking, scans every 100ms for up to 30 seconds). Gated behind `enable_song_metadata_modification` feature flag.
- **Removed klass-based scanning** — The klass pointer `0x2012007E0` was NEVER found as the first 8 bytes of any page in 4GB–17GB (262K pages). PS4 IL2CPP uses compressed/indirect klass pointers. Do not pursue further.

## [v0.8015] — 2026-07-21
### Fixed
- **Wide-range heap scan** — Scan range expanded from 8GB–8.25GB (256MB) to 4GB–17GB (13GB). The BeatmapLevelSO objects were never in the 256MB window — diagnostics confirmed 0 raw matches across 4,380 pages. The wider range covers the full possible IL2CPP heap on PS4.
- **Restored pack bundle detection** — Re-added `pack_assets_all` detection in `open_hook` so the scan fires at startup when the pack loads (before song list UI reads metadata). `memory_inject_try_patch` has internal guard — only scans once.
- **Disabled string content search** — The fallback string content search scanned 4GB–16GB (12GB) and caused the multi-minute freeze. Skipped entirely — the wider klass-based scan should find objects directly.
- **60-second scan timeout** — Hard limit prevents indefinite freezes even with the wider range.

## [v0.8014] — 2026-07-20
### Fixed
- **Removed pack bundle detection** — `strstr("pack_assets_all")` was matching bundles loaded at game startup (before user agreement screen), triggering a full scan immediately and causing a multi-minute black screen. Reverted to redirect-only triggering.
- **Scan timeout** — 30-second hard limit on the klass-based scan. Aborts gracefully and logs elapsed time. Prevents indefinite freezes.
- **Enhanced scan diagnostics** — Logs page addresses and first8 bytes every 256 pages, logs every raw klass match with exact address, and logs range boundaries at scan start. Will help diagnose why 0 objects were found in v0.8013.

## [v0.8013] — 2026-07-20
### Added
- **Pack bundle detection** — `open_hook` now triggers `memory_inject_try_patch()` when `pack_assets_all` bundles are opened (user selects a pack), not just on per-song redirects. This fires the scan when BeatmapLevelSO objects are actually loaded into RAM.
- **String length offset probing** — Pattern matcher now tries offsets 0x10, 0x14, 0x18, 0x1C to find `_stringLength` in System_String objects, instead of hardcoding 0x10. Handles PS4's non-standard mono layout (16-byte monitor field). Logs which offset succeeds.

## [v0.8012] — 2026-07-19
### Added
- **Feature flags system** — Reads `/data/GoldHEN/AFR/CUSA12878/features.json` at plugin startup. Two flags:
  - `enable_custom_song_replacements` (default: `false` if missing) — Gates all song redirects in `open_hook`. When OFF, the plugin loads but no bundle redirects fire, so the game plays original songs.
  - `enable_song_metadata_modification` (default: `false` if missing) — Gates memory injection (`register_song_metadata` + `memory_inject_init`). When OFF, no RAM patching occurs.
- **Pipeline integration** — `--set-feature key=value` flag in the pipeline writes features.json locally and deploys it to PS4 via FTP.

## [v0.8011] — 2026-07-19
### Changed
- **Optimized string search** — 8× faster: uses 8-byte granularity with a uint32 length lookup table instead of 2-byte granularity with 13-length loops. Target: ~200ms instead of ~18s for the GC heap scan.
- **Dual-format string matching** — Now checks BOTH UTF-16LE (standard .NET) AND UTF-8 (possibly used by PS4) patterns in a single pass. Each string has two uint64 fingerprints checked at every 8-byte aligned position.
- **Expanded search range** — Covers from 0x200000000 (GC heap start) to `metadata_base + 64MB` (~0x297280000), covering the full 2.3GB range including the gap that was previously unscannable. Single pass, no separate metadata range scan needed.
- **Gap scan remains disabled** — No separate gap scan; the single large-range pass uses try_read_mem at 64KB granularity, which quickly skips unmapped pages.

## [v0.8010] — 2026-07-19
### Changed
- **DIRECT STRING SEARCH APPROACH** — Completely new method: instead of finding BeatmapLevelSO objects by klass pointer, search for song name/author strings by their UTF-16LE content in memory and patch them directly. This bypasses the need to find BeatmapLevelSO objects entirely.
- **Removed gap scan** — The 2GB gap scan (v0.8009) caused 60-second soft lock. Replaced with the much faster string search in the GC heap and metadata ranges.
- Added original song names/artists to SongMetadataEntry (`orig_song_name`, `orig_song_author_name`) for content-based search.
- Added `patch_strings_by_content()` function that scans memory for known UTF-16LE strings and overwrites them with replacement text.

### Files Changed
- memory_inject.h — Added `orig_song_name`, `orig_song_author_name` to SongMetadataEntry
- memory_inject.cpp — Added `patch_strings_by_content()`, forward declaration, integration into `memory_inject_try_patch()`
- main.cpp — Updated `register_song_metadata()` with original names

## [v0.8009] — 2026-07-19
### Added
- **Gap scan on retry** — When the close hook retries the object scan, it now also searches the 2GB gap between the primary GC heap range (0x200000000-0x210000000) and the metadata address (~0x293280000). BeatmapLevelSO objects may be allocated on the GC heap at addresses above 0x210000000, which wasn't covered by any previous scan range.
- Added `g_wide_scan` flag that enables the gap scan range (SCAN_END_ADDR → metadata_base) only during retry, avoiding extra delay on the initial scan.

## [v0.8008] — 2026-07-19
### Added
- **Close hook retry mechanism** — Added a `close()` hook that retries the MEMINJ object scan after a file is closed. When the initial scan (triggered by `open()`) finds the BeatmapLevelSO_c klass but 0 BeatmapLevelSO objects, it caches the klass address and schedules a retry. The retry uses the cached klass (skipping the ~9s metadata magic search) and only runs the object scanner, which should find the BeatmapLevelSO objects that were created between the open() and close() calls.

### Changed
- **Memory injection retry support** — `memory_inject_try_patch()` now detects retry calls via `g_cached_klass`, skipping the klass search and pattern matcher entirely on retry.

## [v0.8007] — 2026-07-19
### Added
- **Il2CppClass struct hex dump** — When the broader search finds the BeatmapLevelSO name pointer in memory, dumps the 32 bytes at the suspected klass struct start: `[0x00]=klass [0x08]=image [0x10]=name [0x18]=ns/td`. This will verify whether the `name` field is actually at offset 0x10 or at a different position in the struct. 0 raw matches in v0.8006 suggests either a timing issue or wrong offset assumption.

## [v0.8006] — 2026-07-19
### Added
- **Diagnostic klass match counter** — `scan_for_beatmap_level_objects()` now logs the number of raw klass pointer matches found (even those that fail validation) via `[MEMINJ] Klass diag: N raw matches, M validated`. This will tell us if BeatmapLevelSO objects exist but are being rejected by validation.
- **Extended object scan range** — Added a second scan range around the metadata address (±2MB to +16MB) when `g_metadata_base` is known. BeatmapLevelSO objects may be allocated in memory near the metadata rather than in the main GC heap range.
- Added `g_metadata_base` static global to persist metadata address across the klass search and object scanner.

## [v0.8005] — 2026-07-19
### Added
- **Broader klass pointer search fallback** — After module segment search fails, searches the GC heap range (0x200000000-0x210000000) and memory near the metadata itself for 8-byte pointers to the "BeatmapLevelSO" string. The Il2CppClass struct may be dynamically allocated outside the module data segment.
- **metadata_base now function-scoped** — Saved at function scope so it's available for both the string address computation and the broader fallback search.

## [v0.8004] — 2026-07-19
### Fixed
- **Klass pointer search now scans ALL module segments** — Removed `if (!segs[s].is_readable) continue;` filter that was skipping the data segment (Seg[1] at 0x84AC0000). The data segment is where Il2CppClass structs live, but it's incorrectly flagged as `is_readable=0` in sceKernelGetModuleInfo results. `try_read_mem` with signal handlers can safely read from any segment.
- **Metadata magic search confirmed working** — v0.8003 found patch global-metadata.dat at 0x293280000 (version 31), but the klass pointer search couldn't find the string reference because it never scanned the data segment.

## [v0.8003] — 2026-07-19
### Added
- **global-metadata.dat magic search** — New function `search_for_patch_metadata()` that finds the patch global-metadata.dat in memory by searching for its magic bytes (`0xFAB11BAF`) across all readable memory. When found (version 31, string count > 1M), computes the runtime address of the "BeatmapLevelSO" string within it and uses the existing Il2CppClass pointer search to locate the BeatmapLevelSO_c klass in the data segment. This solves the root problem: "BeatmapLevelSO" is only stored in the patch global-metadata.dat, not in the module text/data segments.

## [v0.8002] — 2026-07-19
### Changed
- **Hex dump of lid pointer header** — Replaced int32 STRDEBUG with full 32-byte hex dump of the object at `lid` (4 × uint64_t). Shows klass pointer, monitor field, and suspected _stringLength field at all potential offsets. Enables definitive identification of System_String layout on PS4 by inspection.

## [v0.8001] — 2026-07-19
### Changed
- **STRDEBUG expanded to ALL pointer-level candidates** — Removed `chk_ptrs <= 3` limit. Now logs every candidate that passes klass+version+pointers checks, providing full diagnostic data for the 45 candidates found in v0.80.
- **Enhanced candidate logging** — Added candidate object address (`obj=0x...`) and `lid+0x18` value to STRDEBUG output for deeper System_String layout analysis on PS4.

## [v0.80] — 2026-07-19
### Fixed
- **False positive rejection in pattern matcher** — Added `klass != lid/sn/an` check to reject 17 false positives found at 0x802Axxxx (kernel/system memory below module base). These garbage structs coincidentally matched the BeatmapLevelSO field layout but had klass == lid, which a real object never has.
- **Widened klass range check** — Accept klass in both module space (0x80000000-0x90000000) and GC heap (0x200000000+). Il2CppClass structs may be allocated on the GC heap in some configurations.
- **Extended pattern scan to GC heap range** — Added second scan loop covering 0x200000000-0x210000000 (8GB-8.25GB) where the IL2CPP GC heap is typically mapped on PS4. Previously the pattern scan only searched 16MB-4GB, missing the GC heap entirely.

## [v0.79] — 2026-07-19
### Added
- **STRDEBUG logging in pattern matcher** — Dumps raw values at `lid+0x10` and `lid+0x14` for the first 3 candidates that reach `chk_ptrs` level. Used to determine the correct System_String._stringLength offset on PS4 (may differ from standard IL2CPP layout).

## [v0.78] — 2026-07-19
### Fixed
- **Pattern matcher stack buffer overflow** — Changed `PATTERN_SCAN_STEP` from 0x100000 (1MB) to 0x10000 (64KB). The 1MB `uint8_t page[PATTERN_SCAN_STEP]` stack buffer exceeded the PS4 thread's ~256KB stack limit. Every `try_read_mem` call faulted on the invalid stack destination buffer, resulting in "0 mapped pages" across the entire scan range. The original code used 64KB pages (SCAN_STEP) — this was safe. The pattern matcher inherited the wrong constant.
- **Max scan range reduced** — PATTERN_SCAN_MAX from 64GB to 4GB (still covers module segments and likely heap regions).

## [v0.77] — 2026-07-19
### Added
- **Pattern matcher diagnostic counters** — Added per-check failure counters (klass, version, ptrs, strlen) to identify which field validation check is rejecting BeatmapLevelSO candidates. Output: `[MEMINJ] Pattern diag: N pages (M mapped). klass=K ver=V ptrs=P strlen=S`

## [v0.76] — 2026-07-19
### Fixed
- **String pointer validation threshold lowered from 4GB to 16MB** — The IL2CPP heap on PS4 may be below 4GB. The pattern matcher's validation rejected ALL objects because their string field pointers (lid, sn, an) were below the 0x100000000 (4GB) threshold. Changed to 0x1000000 (16MB) to match try_read_mem bounds.
- **Scan range expanded** — PATTERN_SCAN_MIN lowered from 1GB to 16MB, PATTERN_SCAN_MAX raised from 32GB to 64GB. Previous range may have missed heap locations below 1GB.

## [v0.75] — 2026-07-19
### Changed
- **Pattern matcher scan range expanded** — Changed from limited heap (64MB at 0x200000000) to wide range (1GB-32GB, 1MB pages, 32-byte granularity). The IL2CPP heap address on PS4 is unverified; previous range may have missed objects entirely.
- **Key discovery** — "BeatmapLevelSO" class name string is NOT in Il2CppUserAssemblies module; it's only in global-metadata.dat loaded at runtime. Confirmed via PS4 game dump analysis.

## [v0.74] — 2026-07-19
### Changed
- **Signal handlers installed once per scan** — Moved from per-`try_read_mem` call (5 syscalls per read) to once at start of `memory_inject_try_patch()` and restored at end. ~524K fewer syscalls per full heap scan.
- **Heap scan range reduced** — SCAN_END_ADDR changed from 0x400000000 (8GB) to 0x210000000 (256MB). Reduces iterations from 131K pages × 8192 checks to 4K pages × 8192 checks. ~33M vs ~1B checks.
- **Pattern matcher limited to first 64MB** — Only scans first 64MB of heap (not full 8GB) to find klass via field layout.
- **Double scan eliminated** — Combined klass discovery and object scanning logic. String search is tried first, fallback to pattern matcher in limited range, then object scan only once with klass.
### Fixed
- **Black screen hang on song select (v0.73)** — Caused by scanning the full 8GB heap range synchronously in the hook callback (~1B checks per scan, double-scanned). Now completes in ~33M checks with optimized signal handler setup.

## [v0.73] — 2026-07-19
### Fixed
- **Class string "BeatmapLevelSO" not found in Il2CppUserAssemblies** — The string is NOT present in the module's .text segment (only segment returned by `sceKernelGetModuleInfo`). Added `find_beatmap_level_objects_by_pattern()` as fallback: scans the IL2CPP GC heap for objects matching BeatmapLevelSO field layout (version range, valid pointer ranges) instead of requiring klass string search. Extracts klass pointer from the first validated object.
### Added
- **Pattern-based klass finding** — New function `find_beatmap_level_objects_by_pattern()` searches heap objects by struct field layout signature rather than by class name string. This bypasses the need for the "BeatmapLevelSO" C string in module data.

## [v0.72] — 2026-07-19
### Fixed
- **REAL root cause of "Class string not found"** — `try_read_mem()` had a bounds check rejecting addresses below 0x100000000 (4GB). PS4 modules (Il2CppUserAssemblies) are loaded at ~0x80000000 (2GB), so ALL segment reads were rejected by the bounds check before any probing method could be tested. This affected v0.66 through v0.71.
- **Lower bound changed** from 0x100000000 (4GB) to 0x1000000 (16MB) to accept module segment addresses (~2GB) while still rejecting near-null pointers.
- **Upper bound changed** from 0x8000000000 (32GB) to 0x2000000000 (128GB) for safety margin.
- **Signal-handler approach retained** from v0.71 — `sigaction`/`sigsetjmp`/`siglongjmp` remain the memory probing mechanism once address passes bounds check.
### Changed
- Bounds check constants in `try_read_mem()`.

## [v0.71] — 2026-07-19
### Changed
- **Signal-handler-based memory probing** — Replaced `msync()` / `mincore()` with `sigaction(SIGSEGV)` + `sigaction(SIGBUS)` + `sigsetjmp`/`siglongjmp`. Installs handlers per call, tries `memcpy`, restores original handlers. Faults are caught by the handler and longjmp back safely.
- **`#ifdef VERBOSE_LOG` diagnostics** — Build with `DEBUG=1` to log segment addresses, sizes, protections, and per-chunk read status.
- **Fixed plugin deploy path** — Plugin was being uploaded to `/data/GoldHEN/AFR/CUSA12878/` (asset redirect directory) instead of `/data/GoldHEN/plugins/` (where `plugins.ini` points).

## [v0.70] — 2026-07-17
### Changed
- Replaced `mincore()` with `msync(MS_ASYNC)` for memory validation. msync returns 0 if all pages are mapped, -1 with ENOMEM otherwise. Also fixes anonymous page checking.

## [v0.69] — 2026-07-17
### Fixed
- Guard timer removed from memory injection. Trigger now fires on ANY redirect.
- Lock released on failure so retry is possible.
- Memory injection now called correctly in hook.

## [v0.68] — 2026-07-17
### Fixed
- Removed `pack bundle` redirect from `redirects.json` (was causing CE-34878-0 boot crash).
- Log write now uses static buffer (was using stack garbage).
- Thread removed, memory injection runs inside hook context (not pthread).

## [v0.67] — 2026-07-17
### Fixed
- CE-34878-0 crash: Removed `pthread_create`/`pthread_detach` (FreeBSD init race).
- Memory injection now runs synchronously inside `open_hook` callback.
- `mincore()` guards memory reads for safe page probing.

## [v0.66] — 2026-07-17
### Added
- **Memory injection module** — New `src/memory_inject.cpp` + `src/memory_inject.h` patches BeatmapLevelSO objects in RAM after Addressables load, bypassing catalog size + CRC validation.
- **Architecture:** Worker thread waits 30s for game init, scans Il2CppUserAssemblies module for "BeatmapLevelSO" string → finds klass pointer → scans GC heap for objects → patches string fields in-place.
- **Metadata table:** 13 Rolling Stones replacement songs with custom names, artists, and level IDs.
- **String field patching:** In-place UTF-16LE overwrite of song name, artist, level ID. New text must fit within original capacity.

## Exp304 —2026-10-25 (NO plugin source/version change)
Full-map gameplay succeeds on0.8063; own song cover/menu preview prepared HOST
ONLY. Native Unity/managed media binding still pending; no new plugin deployed.
