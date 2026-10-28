# In-Game Global Plugin Toggle

**Status:** ✅ Working — hardware-confirmed 2026-10-16 (plugin v0.8049+; current v0.8053) · **Feature flag:** `enable_in_game_plugin_toggle`

**Demo:** [Demo video — the Move button + trigger hotkey toggling the plugin off and back on](https://youtu.be/NsUhL8NioCA) (more demos in [docs/demos.md](../../docs/demos.md))

## What it does

Hold **the Move button and the trigger together for 2 full seconds** on a PlayStation
Move controller and the plugin flips its own global state. A PS4 notification tells you
the new state, and **restarting Beat Saber applies it**. No PC, no FTP, no web app —
switch between your full custom loadout and 100% stock Beat Saber entirely from the couch.

- **Plugin ON** → all custom songs, mode buttons, previews, and metadata swaps active.
- **Plugin OFF** → the game plays 100% official content on the next boot (all redirects,
  metadata swaps, mode buttons, and previews disabled). Your deployments stay on the
  console, untouched — nothing is uninstalled.

## How to enable

One-time setup (pick either):

- **Web app:** Feature Flags tab → `enable_in_game_plugin_toggle` → Apply.
- **CLI:**
  ```bash
  python3 tools/full_custom_song_pipeline.py \
      --features-only --set-feature enable_in_game_plugin_toggle=true
  ```

Requires plugin v0.8049 or newer (deployed via `--deploy-plugin` or any `--deploy-full`).
Fresh-install defaults (Exp 281): the flag is **ON by default** — a fresh install
has the hotkey armed from the first boot.

## Using the hotkey

1. Play normally with your Move controllers — **no DualShock 4 is needed** (the game
   ignores it in VR mode; the hotkey runs entirely on the Move path).
2. Press and hold the **Move button** (the large thumb button under the sphere) **and
   the trigger together** — both at the same time.
3. Keep holding for **2 full seconds**. You'll hear the PS4 notification *sound* (in VR
   the notification itself may not be visible — the sound is your confirmation).
4. The notification reads: `BS Deluxe: Plugin ENABLED` or `BS Deluxe: Plugin DISABLED`,
   both followed by `Restart game to apply`.
5. **Restart Beat Saber.** The next boot runs in the new state and the launch toast
   confirms it (`(5/5 features ON)` or `(OFF)` / `official songs only`).

### Why a restart?

The flip is **persist-only**: it edits `features.json` on the console for the *next*
boot and never changes the current session mid-game. This is deliberate — pack bundles,
the Addressables catalog, and mode buttons all load at boot, and changing them live
could desync the game's loaded state. The hotkey is a configuration switch, not a
live toggle.

### The one-way door — deliberately

The hotkey keeps working **even when the plugin is toggled OFF**. If it didn't, a user
who toggled OFF could never re-enable without a PC — the feature would be a one-way
door. The kill switch disables all game-behavior features (redirects, metadata, modes,
previews), not the plugin's own control surface. The **only** way to disable the hotkey
itself is `enable_in_game_plugin_toggle=false`.

### Accidental-trigger protection

The combination is used nowhere else in the game, and three guards make accidental
triggers effectively impossible:

- **Clean combo:** the Move button and trigger must be the ONLY buttons held — any other
  button bit resets the hold.
- **Full 2-second hold**, timed continuously — a tap does nothing.
- **Release latch:** after a toggle fires, the combo must be fully released before the
  next can arm (plus a 3-second cooldown).

## Debug variant

The plugin ships in two builds: the **release build** (lean, one-time logging only) and
the **debug build** (`--deploy-plugin --debug-logging`) which logs every pad/Move read
and raw data words. The launch toast and log banner always show which build is live —
the debug build reports its version as `v0.8053 DEBUG`. Redeploy the release build any
time with plain `--deploy-plugin`.

## Troubleshooting

- **No notification sound after holding 2 s:** confirm the flag is on (boot toast shows
  `N/5` — the hotkey counts as one of the five features) and that you held *both* buttons
  together for the full 2 seconds with no other buttons.
- **Toggled but nothing changed:** the flip only applies after a restart — that's by
  design (see above).
- **In VR you can't see notifications:** listen for the notification *sound*; the state
  is also written to `bs_log.txt` (`[TOGGLE] enable_plugin flipped to ...`).
- **The web app still shows the old state:** the flag flip is visible in the web app's
  Feature Flags tab after a refresh (the pipeline always reads the live `features.json`).

## How it works (under the hood)

- The hotkey listens on the game's own per-frame Move reads: `sceMoveReadStateRecent`
  (called every frame for both Move controllers for tracking). The plugin resolves the
  function through the eboot's GOT and hijacks the import slot — no code patching.
- Button bits come from the game's own `PSVRDeviceManager.PSMoveButton` layout:
  trigger = bit 0x2, Move button = bit 0x4, read from `SceMoveData` at offset +0x18
  (trigger analog at +0x1A, used as a fallback signal).
- The toggle writes `features.json` **in place**, flipping only the `enable_plugin`
  value and preserving every other key — the same file the pipeline and web app manage,
  so in-game flips show up everywhere and survive pipeline deploys (the pipeline always
  pulls the live file before pushing).
- No threads, no signal handlers, no code modification: the hook calls the original
  function directly, and the steady-state cost is a handful of instructions per frame.
- Durable engineering notes live in the knowledge base: `ps4-controller-input-from-plugin`
  (how to hook PS4 input from a GoldHEN plugin) and `in-game-plugin-toggle` (design).

## Rollback / disable

```bash
python3 tools/full_custom_song_pipeline.py \
    --features-only --set-feature enable_in_game_plugin_toggle=false
```

Hotkey gone on the next boot; every other feature is untouched. The toggle itself only
ever writes the `enable_plugin` key inside `features.json`, so no deployed bundles,
catalog, or redirects are ever at risk.
