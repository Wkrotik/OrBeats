# Song Previews

**Status:** ✅ Working (pipeline v0.5357+, plugin v0.8048+) · **Feature flag:** `enable_song_previews`

## What it does

When you highlight a custom song in the song menu, Beat Saber plays a ~10 second
preview. Without this feature the menu plays the **stock song's** preview clip —
the name says your custom song while the audio is the original. With
`enable_song_previews` on, the preview is a cut of **the custom song's own audio**,
so the menu experience matches what you'll actually play.

## How the preview moment is chosen

1. **The mapper's choice, honored first.** BeatSaver maps can declare a
   `_previewStartTime` in their `Info.dat` — the author's own pick for where the
   song sounds like itself. When the map's source is available locally, that
   exact moment is used.
2. **The busiest-bar heuristic** (when no source is available): the pipeline
   scans the song's own deployed beatmaps for the densest 10-second window and
   snaps back to a 4-beat bar, so the preview starts musically. This always
   reflects the audio you'll hear in gameplay because it reads the exact
   deployed bundle.

Every preview is loudness-matched to the stock previews (no blasting menus),
fade-smoothed at both ends, and exactly 10.0 seconds.

## How it works (under the hood)

- Each music pack bundle already contains one preview AudioClip per song
  (`BeatmapLevelSO._previewAudioClip`). The pipeline appends a new FSB5 PCM16
  preview slice for every custom slot into the pack bundle's `.resource` stream
  and repoints the AudioClip at it in place — the same lossless audio format the
  full-song replacements use.
- Previews ride in a **separate bundle variant** (`…_pack_modes_previews_…`),
  so the feature is fully reversible: flipping the flag off and re-deploying
  returns the modes-only bundles (stock previews) without rebuilding anything.
- Any pack, any song — pack discovery, slot targeting, and preview generation
  are all data-driven from the deployed state and the song catalog. Nothing is
  hardcoded to specific packs.

## Batch deploys

Preview regeneration is automatically deferred: in a web-app batch, every
command except the last runs with `--skip-song-preview-management`, so previews
rebuild exactly once at the end (the flag is also available on the CLI for
manual chains). Each deploy additionally **dirty-checks** every pack — a
variant is only rebuilt when its music-pack modes bundle, its set of custom
songs, or any song's audio actually changed, so untouched packs cost seconds.

## Turning it on

```bash
# Enable (then re-deploy any song/pack so the preview variants ship):
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_song_previews=true

# Or from the web app: Feature Flags → enable_song_previews → Apply, then deploy.

# Disable (stock previews return after the next deploy):
python3 tools/full_custom_song_pipeline.py --features-only --set-feature enable_song_previews=false
```

The boot toast counts it: `(4/4 features ON)`.

## Validation

Post-deploy validation verifies each deployed pack bundle's actual CRC against
the deployed catalog — previews, mode buttons, and catalog can never drift
apart silently. `--verify-ps4` runs the same check on demand.
