# OrBeats Extras — native PS4 prototype

Separate GoldHEN plugin for **CUSA12878 / patch 2.04**. It does not replace
OrBeats, redirect song files, manage the library, upload scores or authenticate
users. Version **0.0002** is local development, not a deployed/public release.

## Implemented locally

- A health-warning-only resolver hook. Exact game-code fingerprints and managed
  class/field checks must pass. The original controller selection is retained;
  only an identified health view's interaction flag and duration are adjusted to
  let its own native coroutine complete after 0.25 seconds. No direct agreement
  completion callbacks, recenter/tracking hooks or whole-coordinator bypass.
- Default **off**. The exact opt-in file `/data/GoldHEN/plugins/orbeats-extras-health.txt`
  must contain `ORBEATS_EXTRAS_HEALTH_V1` followed by a single newline. This file
  is not created automatically. Missing, malformed or extra bytes disable the hook.
- Required game module, RX code, exact classes/field offsets and expected initial
  view state are checked before patching/mutation. Existing conflicting hooks
  cause a refusal. No retained managed objects or background Unity calls.
- No live unload after installing a hook: close the title to disable the plugin.
  Logs append to `/data/GoldHEN/plugins/orbeats-extras.log`.
- A **development-only Python protocol probe** for anonymous top 50/100 ScoreSaber
  rows. It validates original map SHA1, difficulty, 12-row pagination, score order,
  bounded JSON/names, cancellation and deadline. Uses certificate-validating HTTPS,
  no credentials, cookies, redirects, score upload or automatic retries.

- A native C++ ScoreSaber decoder, linked into the PS4 build. It accepts bounded
  12-row pages, assembles up to 100 rows, rejects inconsistent pagination/ranks,
  and strips control/directional characters and TMPro markup from names without
  splitting UTF-8 characters. Malformed responses clear the output rather than
  leaving partial scores. Standard chart URLs require an original SHA1 and an
  explicit difficulty. JSON is parsed by pinned cJSON 1.7.19 (MIT), with a
  512 KiB response cap and nesting limit 16. Source hashes and the unchanged
  upstream license are in `third_party/cjson`.

**Not implemented yet:** native console HTTPS/cache, source-map SHA1 exchange
with OrBeats, selected-chart lifecycle, leaderboard rendering and an Extras menu.
The native plugin does not claim or display a working ScoreSaber leaderboard.
The Python probe is not a substitute for the required console transport.

## Validation and limits

Synthetic native health and score-decoding guards run with AddressSanitizer/UBSan.
Native score tests include 50/100-row assembly, UTF-8 names, duplicate schema keys,
invalid types, oversized/deep responses and failed-page output clearing. Captured
public ScoreSaber pages 2 and 9 also pass the same production C++ decoder; this is
not a PS4 network or rendering test. Code fingerprints
are compared with a locally owned game binary when available; that test explicitly
skips in the source-only repository. HTTP pagination/fault tests use fake pages.
Release and debug builds require the same pinned OpenOrbis/GoldHEN setup as OrBeats:

```sh
export OO_PS4_TOOLCHAIN="$PWD/.tools/openorbis/OpenOrbis/PS4Toolchain"
make -C orbeats_extras
make -C orbeats_extras DEBUG=1
```

This is **not hardware-verified**. In particular, whether the warning duration is
reassigned after controller resolution, whether its native auto-dismiss coroutine
completes, and coexistence with another UI hook require console testing. Failure
must preserve ordinary startup, not trigger a broader skip. No installation occurs
as part of this build.

Protocol probe (Standard charts only for this initial slice):

```sh
python3 orbeats_extras/development/scoresaber.py ORIGINAL_MAP_SHA1 ExpertPlus --count 100
```

Public data remain ScoreSaber/PC scores, not PSN rankings or a PS4 score-upload
integration. Service limits and chart availability may change. See
[`../docs/plugin-expansion-research.md`](../docs/plugin-expansion-research.md).
