# V3 lighting milestone and subsequent expansion

**Current local expansion:** plugin0.8075/pipeline0.5385/app0.7.17 now implements
the previously listed feasible categories. See [expanded-map support and exact
remaining limits](native-map-expansion.md). It is not PS4-tested/installed;0.8074
remains installed. The sections below describe the historical0.8073 milestone.

## Why these maps were refused

`colorBoostBeatmapEvents` toggles the normal/boosted light palettes.
`lightColorEventBoxGroups` distributes colour, brightness and transitions over
numbered groups of lights. `lightRotationEventBoxGroups` distributes rotation
patterns. These are standard Beat Saber V3 data, not proof of Chroma or Noodle
Extensions. OrBeats' original converter only preserved basic events and refused
advanced fields rather than silently deleting authored lights.

CUSA12878 patch 2.04 has the V3 save-data classes, their converter classes, and
WeaveEnvironment in its owned Addressables catalog. This establishes a viable
implementation path, not console playback proof for an arbitrary custom map.

## Local candidate: plugin 0.8073 / pipeline 0.5383 / app 0.7.15

- Validate and retain bounded V3 boost events, colour boxes, rotation boxes,
  filters, authored group IDs and the basic-event compatibility flag. Never
  remap a group ID to whichever lights happen to exist in the template stage.
- Boost event beats use the existing piecewise BPM-to-seconds conversion. Boxes
  initially require constant actual BPM (redundant same-BPM markers are fine).
  Scale group beats, relative base-event beats and beat-distribution widths
  uniformly; do not change brightness/rotation distributions or random seeds.
  Nonlinear tempo cannot be fixed by retiming only the group's starting beat:
  individual lights receive distributed times, including eased patterns.
- Box maps initially require explicit **WeaveEnvironment**, resolved from InfoV2
  and any per-difficulty environment index. Mixed per-difficulty environments
  are refused: this candidate has one environment token per song. Basic-only
  maps retain the earlier stock fallback unless the same song needs Weave.
- Serialize independent per-difficulty lightshows and independently reopen and
  compare both chart and lightshow payloads. Restore native omitted-scalar zero
  defaults in sparse V3 input, without inventing absent difficulties or objects.
- Optional `BSDALIB2` adds a bounded `stock`/`WeaveEnvironment` token per song.
  The native decoder accepts both versions; constructor arguments use the actual
  `EnvironmentName` value-struct ABI and verify the resulting field. Songs without
  an explicit environment keep byte-identical `BSDALIB1` encoding. Existing
  descriptor content and files are not rewritten when appending a V2 entry.
- Settings publishes `library_format: 2` only for an environment-aware binary;
  imports verify the existing full active ELF/capability SHA and refuse these
  maps on older capability profiles before new-song uploads. Refuse a downgrade
  that cannot read an existing environment-aware library. Keep closed-title,
  immutable file staging, manifest-last publication and rollback protections.
- Colour-scheme overrides are still **not** imported. Engine stage palettes are
  used. This is not a claim of exact desktop visual parity or a mod loader.

### Validation evidence (not hardware proof)

Synthetic tests exercise boost timing across BPM changes; uniform relative-box
scaling; native-zero defaults; malformed nested fields, enum gaps and budgets;
per-difficulty UnityFS lightshow readback/corruption; host/native mixed V1/V2
libraries; native managed environment construction; old-plugin refusal; and
normal installer append/idempotence while preserving old descriptors.

Actual map **4f7e2, Looping the Rooms**, reopens with **614 notes, 73 arcs,
8 boost events, 780 colour-box groups and 714 rotation-box groups**, explicit
WeaveEnvironment, and original-packet Vorbis. The bundle is **7,547,864 bytes**.
Independent calculations compare absolute seconds for group/base-event beats
and distribution widths, plus unchanged filters and group IDs. Source audio,
map archives and game metadata remain ignored local inputs.

Final full host suite: **1,364 passed, 124 skipped**, one inherited Starlette
warning. Release and DEBUG plugin candidates compile without warnings;
desktop/mobile browser fixtures pass. Playback, visible light-group
behaviour, Practice Mode seeking, and no stock-song regression still need the
user's console test. Updating the plugin and retrying the failed map must happen
with Beat Saber fully closed and FTP enabled. No automatic launch or retry.

## Historical follow-up list after0.8073 (now implemented locally)

| Feature | Evidence / work still needed |
| --- | --- |
| More stock environments | The game has many environments. Review their availability, route them explicitly, and test authored group IDs/layouts; never substitute or rename groups blindly. |
| V3 chains (`burstSliders`) | Native `BurstSliderData` exists. Validate chain geometry, slice/squish semantics and timing; preserve objects in bundle, menu statistics and native registration. Ordinary V3 arcs are already supported. |
| V3 translation boxes and FX boxes | Native classes/converters exist. Audit their nested structures, distributions, enum bounds and environment-specific components. Translation/FX still refuse. |
| Changing-BPM event-box shows | Preserve each distributed light's absolute timing, potentially expanding distributions with the actual environment's group membership; a group-start-only transform is incorrect. |
| One Saber / No Arrows | Engine characteristics exist, but our importer/native route only creates Standard. Need per-characteristic content, keys, statistics and UI/lookup validation, not relabelled Standard. |
| 90/360-degree maps | Native rotation-event data exists. Need correct characteristic/environment, rotation orientation and timing across gameplay, obstacles/arcs and Practice Mode. Current rotation fields refuse. |
| More V4 conversion | Current converter handles bounded V4 notes/bombs/walls and sample-region timing. V4 arcs/chains, authored lightshows and rotation need explicit indexed-data conversion into reviewed native representations. Runtime NJS events may need extra semantics; class existence is not sufficient. |
| Custom colour palettes | Native colour-scheme fields exist, but author/player override precedence and boost colours need correct construction/rooting and console tests. Ignored cosmetics are reported, not presented as supported custom lighting. |
| Song offsets / wider timing bounds | The engine has offsets, but audio, BPM/sample coordinates, previews and all object endpoints must stay aligned; removing a guard alone is not support. |

The table records the gaps at0.8073, not the current local feature status.
They were converter/runtime integration gaps, not all equal in difficulty.
Chains, more reviewed environments and custom colour schemes are plausible
next increments after the Weave console test. V4 lighting and nonlinear BPM
box distributions need more work.

**Not in the same category:** Chroma/Noodle Extensions/Mapping Extensions and
custom Unity environments need mod behaviours/assets absent from this plugin.
They are not made compatible simply because the PS4 has ordinary V3 classes.
A newer unsupported game's features may require genuinely newer engine behaviour.

## Console staging and first hardware result

User readiness confirmed; plugin **0.8073** installed with full canonical ELF
readback, capability/profile match and retained rollback. The normal companion
queue then imported only **4f7e2** successfully. Library is now **25 songs**;
all **24** previous descriptors and the existing features/plugins.ini bytes are
unchanged. Reopened remote bundle (**7,571,472 bytes**) retains the exact normalized
notes, arcs and all three lighting collections; the installed template explains
the size difference from the earlier local quick-test-template proof. Cover and
preview also pass full readback. Runtime log archived without clearing.
Queue paused with no pending work, **68** history entries (previous67 unchanged).
The assistant did not launch the game. Evidence is ignored local
`temp/lighting-console-test/`.

The user subsequently reports that **Looping the Rooms worked correctly on PS4
and showed background lighting** on plugin0.8073. This is a successful first
hardware gameplay/visible-lighting test. The user does not know the authored
reference appearance, so exact visual parity, every event-box effect and boost,
Practice Mode seeking and stock-song regression are not independently confirmed.
