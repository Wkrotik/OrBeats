# OrBeats Extras

Optional, separate GoldHEN plugin for **Beat Saber PS4 CUSA12878 / patch 2.04**.
It adds anonymous ScoreSaber viewing and a health-warning convenience option.
OrBeats custom-song playback does not depend on Extras.

**Health auto-dismiss is hardware-confirmed on 0.0006. Anonymous leaderboard
viewing is not yet hardware-validated.** On Animals, the native selection and
input-pump callbacks accept the map identity, but the request returns `Network`
before scores are received. Successful hook installation is not end-to-end proof.

The local **0.0007 diagnostic candidate** records the failing PS4 HTTPS call,
its hexadecimal result, and available HTTP/TLS error details. It does not log
player names, original hashes, URLs or response bodies, disable certificate
verification, or install permissive TLS callbacks. A logged network failure alone
does not establish whether DNS, connection, TLS or an SDK setup call failed.

The status path now reactivates the emptied table's GameObject before displaying
loading or error text: the loading control may be below that parent in the game
prefab. Fake-platform tests cover this ordering; actual PS4 visibility still needs
confirmation. No songs, library, main-plugin or health-policy files are changed
by this candidate. The proven 0.0006 health activation hook is retained.

## Anonymous leaderboard

Extras reuses the game's existing leaderboard panel rather than adding another
menu or mod loader. For an imported **Standard** chart with a verified original
map identity, it displays up to **100 public ScoreSaber scores**. Names are
prefixed **`[SS/PC]`**: these are PC/ScoreSaber scores, **not PSN rankings**.
There is no login, player identification, upload, avatar fetch, Friends or Around
Me feature. PSN-only scope controls are hidden while this replacement is active.

- The companion records SHA1 of the original `Info.dat` and its referenced charts
  **before conversion**. Extras never infers a ScoreSaber hash from a generated
  level ID or a converted bundle. The 158-byte `ORBSSRC1` sidecar is bound to the
  exact installed ID, bundle SHA256 and Standard difficulty mask, with a wire
  checksum to detect corruption (not an authentication/signature claim).
- New imports write/read back that optional identity before `library.bin` is
  published. Reimporting an existing song can add the identity without replacing
  its descriptor or changing existing PCM/media. Conflicting identities refuse
  overwrite. The library wire format and normal OrBeats playback are unchanged.
- Existing songs without the identity show a reimport explanation. Reimport with
  pipeline **0.5392 / source companion 0.7.27 or newer**, with the title closed.
  The previously built **0.1.12 AppImage predates this integration**; the new
  frozen backend is a development build, not a rebuilt desktop installer yet.
- Stock/DLC IDs, other characteristics and missing identities do **not** borrow a
  different chart's scores. A missing board, invalid reply, network failure and
  an actual empty board have separate messages. Not every map has a board.

A single native worker handles verified HTTPS and bounded JSON decoding. Only
copied hashes/difficulties/results cross threads; managed allocations and table
updates run in the game's UI input loop. Changing charts, leaving or destroying
the view invalidates its generation, so late responses cannot replace a newer
selection. Managed score rows publish only after all rows are constructed.

The bounded eight-entry cache keeps successful results for two minutes, rate
limits for one minute and other failures for 15 seconds. Reselect after the
relevant interval to retry; there are no automatic retry loops. Individual SDK
calls have timeouts, but cancellation cannot instantly interrupt a blocked call.

## Health warning

The health warning is **auto-dismissed by default when Extras is enabled**, via
its original native coroutine after 0.25 seconds. It may briefly appear. Extras
adjusts only the identified health view's interaction flag and duration; it does
not skip a whole coordinator, acknowledge an agreement, bypass tracking or
recentering, or invoke agreement-completion callbacks.

To retain the ordinary warning, place exactly this token and **one newline** in
`/data/GoldHEN/plugins/orbeats-extras-health.txt`:

```text
ORBEATS_EXTRAS_SHOW_HEALTH_V1
```

A confirmed absent setting selects auto-dismiss. Unreadable, empty, malformed or
extra-byte settings preserve the ordinary warning. The older
`ORBEATS_EXTRAS_HEALTH_V1` token remains compatible. Extras never creates or
changes this file automatically. There is no additional settings/menu UI in this
initial scope.

## Safety and installation boundary

- Requires exact owned game-code fingerprints and managed class/field profiles.
  Mismatched code or an existing conflicting hook refuses installation. Health
  and leaderboard profile checks are independent; inspect the log for refusals.
- The leaderboard replacement never registers the original Sony callbacks or
  starts its PSN requests. It retains the base view's binder cleanup. This is not
  a blanket disabling of PSN elsewhere in the game.
- HTTPS uses server/hostname/CA/date verification plus SNI. No certificate-accept
  callback, credentials, cookies, redirects or authentication. Old console CA
  stores, firmware TLS support and the clock can cause a real request to fail;
  **never disable certificate checks to work around that**.
- Close the title before installing/updating plugin files or song identities.
  Do not live-load or unload this candidate. Once a hook has been installed,
  module stop refuses live unload because a callback/worker may still be active.
  Disable it only with the title closed, then start the title normally yourself.
- Intended artifact: `orbeats_extras.prx`, separate from `orbeats.prx`. It has no
  companion installer yet. Build does not upload, enable an INI entry or launch
  the game. Preserve unrelated plugin entries; coexistence with other UI hooks
  must be tested, not assumed.
- Logs append to `/data/GoldHEN/plugins/orbeats-extras.log`. Preserve them after
  the first test, including failures.

## Build and validation

Use the project's pinned OpenOrbis/GoldHEN toolchain:

```sh
export OO_PS4_TOOLCHAIN="$PWD/.tools/openorbis/OpenOrbis/PS4Toolchain"
make -C orbeats_extras
make -C orbeats_extras DEBUG=1
```

Host ASAN/UBSan regressions exercise the **actual production** decoder, transport,
worker, managed table builder and view lifecycle. Fake SDK/IL2CPP imports verify
resource/root cleanup, cancellation, cache expiry/eviction, stale selection
rejection, managed exceptions/allocation failure, original input processing,
base cleanup, original-hash exchange and no partial result publication. They do
not simulate Unity rendering or prove controller usability. Owned-binary code
fingerprint checks explicitly skip in source-only CI.

Before treating this integration as console-ready, check: ordinary startup and
health option; all stock/custom songs still work; verified HTTPS; correct chart,
difficulty, rank, score and scrolling; rapid selection changes; leaving/reopening
the view; missing identity/board/network; and coexistence with enabled plugins.
The runtime manifest is read at title startup; no live library refresh is added.

JSON uses pinned **cJSON 1.7.19 (MIT)** with its unchanged license/source hashes,
512 KiB response cap and nesting limit 16. Narrow HTTP declarations in
`include/ps4_http.h` fill incomplete pinned-SDK prototypes; ABI references are
recorded in the source and prior changelog. No reference implementation is copied.

The development-only Python protocol probe remains useful independently:

```sh
python3 orbeats_extras/development/scoresaber.py ORIGINAL_MAP_SHA1 ExpertPlus --count 100
```

See [research and source references](../docs/plugin-expansion-research.md).
