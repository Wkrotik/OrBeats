# Plugin branding and selected native extensions — feasibility notes

> Initial scope is now implemented locally in OrBeats Extras0.0004: anonymous
> Standard-chart scores in the existing panel plus default health auto-dismiss.
> It is not PS4-validated. The separate menu, richer settings and further ports
> below remain research/future work. See [current scope and limits](../orbeats_extras/README.md).


Status: research, not a mod-support announcement. Current target is owned PS4
CUSA12878 patch2.04 / native IL2CPP. Research made no console changes. Subsequent user-authorized0.8078 upload
completed with the title closed; appearance is awaiting the user test. No game
was launched automatically.

## Branding implemented locally

Plugin0.8078 changes the custom pack's display name to **OrBeats**, keeping its
existing internal pack ID `bsd_additive_stock_proof_v1` and song/library IDs.
The cover is the owned desktop logo resized to512px, embedded in the plugin.
Song artwork/audio and the remote library are not rewritten. The old pack-cover
file is no longer the source for this plugin-owned cover.

The startup toast uses the exact same PNG, exported atomically to
`/data/GoldHEN/plugins/orbeats-logo.png` when the plugin starts. Existing matching
bytes need no rewrite. Partial writes, failed verification or rename leave the
previous target alone; a failure falls back to an ordinary notification rather
than blocking registration. A pre-existing staging file is not deleted. Its
SceNotificationRequest file-URI rendering still needs a hardware test.

## Primary sources and confidence

- [ScoreSaber/pc-mod](https://github.com/ScoreSaber/pc-mod/tree/875564d27c0989030c5202267ccf0ea9addcd87a),
  inspected revision875564d27c0989030c5202267ccf0ea9addcd87a.
- [Aeroluna/Heck](https://github.com/Aeroluna/Heck/tree/3bbcaf6733f6faa688a70b296b4d83c92c1f5dc8),
  inspected revision3bbcaf6733f6faa688a70b296b4d83c92c1f5dc8, includes Chroma
  and Noodle Extensions. Both repositories actually contain MIT licenses;
  retain their copyright/permission notices if code is reused. This does not
  license proprietary game assets, shaders or other dependencies automatically.
- Exact owned game metadata confirms the native classes/signatures listed below.
  Metadata/RVAs identify candidates, not safe executable hooks or tested UI.
- Anonymous live ScoreSaber HTTP requests establish read access from this host;
  they do not establish PS4 TLS/certificate/network compatibility or a service SLA.

No third-party code was incorporated into the plugin during this investigation.

## Anonymous leaderboard viewing: feasible, not a PC DLL drop-in

The user requirement is deliberately **read-only**: no account creation, platform
login, player authentication, uploads, replay recording or personal ranking.
PC ScoreSaber includes those other systems; we do not need to port them.

The older public endpoint was exercised with only a User-Agent and Accept header,
no Authorization, session header or cookie:

```
GET https://scoresaber.com/api/leaderboards?ranked=true&limit=1
GET https://scoresaber.com/api/leaderboard/by-hash/{hash}/scores?difficulty={rating}&gameMode={mode}&page={page}
```

Live example at research time: board51175 / map hash
`8AF82A87167070A08EC63DBA0459C829C2954067`, Normal, `SoloStandard`.
Page1 returned ranks1–12, page2 returned13–24 and page9 returned97–108.
Requests with limit50/100 still returned metadata `itemsPerPage:12`.
Therefore top50 needs5 pages and top100 needs9 pages, truncating locally.
Fetch on selection with caching/cancellation, not once per frame. Respect rate
limits/429/Retry-After, enforce timeouts/response-size limits and use stale-cache
or an explicit unavailable state rather than hanging the menu.

Current PC source uses a newer API too:
`GET /api/v2/leaderboards/hash/{hash}/{mode}/{difficulty}/scores`.
Its generated client accepts optional session headers. Anonymous requests worked
at the HTTP level, but returned an empty `data` array for this board even while
the older endpoint returned32281 scores. Do not assume API versions are
interchangeable or interpret that empty result as proof a map has no scores.
The observed older endpoint is a better first proof-of-concept target.

Primary source paths:
- `src/Features/Leaderboards/Domain/ScoreSaberBeatmapKey.cs`
- `src/Features/Leaderboards/Services/LeaderboardQueryService.cs`
- `src/Core/Api/ScoreSaberApiClient.cs`
- `src/Core/Api/Generated/ScoreSaberApiGeneratedClient.cs`

### Map identity is the important integration change

ScoreSaber needs the **original map content SHA1**, characteristic/gameMode and
exact difficulty. Ratings Easy/Normal/Hard/Expert/ExpertPlus are1/3/5/7/9, not
our native0..4 enum. Standard is `SoloStandard`; other characteristics must be
mapped explicitly, never silently treated as Standard.

Our downloader already verifies BeatSaver's content hash: SHA1 of Info.dat plus
referenced chart bytes in Info order, NOT the ZIP hash. Conversion can change
metadata, beats, audio and IDs. Our generated `bsd_additive_*` level IDs and
bundle SHA256 are NOT valid replacements for the original map hash.
`beatsaver-metadata.json` exists at acquisition, but a runtime-readable,
versioned ID→original-hash/characteristic/difficulty contract is still needed.
Older installed songs would need verified provenance migration, not guessed
hashes or a title-based search. A missing/unknown map must say unavailable.
Stock/DLC matching is a separate problem; modern PC `ost_` identities do not
prove the older API has a corresponding chart for every PS4 stock song.

### Reuse the existing game leaderboard UI

Owned metadata provides:
- `PlatformLeaderboardViewController.SetData(in BeatmapKey)` RVA0x1C26290;
  `.DidActivate`0x1C264F0; `.DidDeactivate`0x1C26ED0; `.RefreshAsync`0x1C284D0.
  It currently gates on Sony availability; simply supplying rows later is not
  enough if its own request/empty-state callbacks can overwrite them.
- `LeaderboardTableView.ScoreData(int score, string playerName, int rank, bool fullCombo)`
  constructorRVA0x1B93CD0.
- `LeaderboardTableView.SetScores(List<LeaderboardTableView.ScoreData> scores, int specialScorePos)`
  RVA0x1B93BD0.

A first native prototype can populate genuine ScoreData/list objects and reuse
rows/scrolling, without injecting a desktop C# mod or inventing a managed class.
Keep it explicitly labelled **ScoreSaber / PC scores — read-only**. Disable
Around Me/Friends/upload controls instead of pretending we have an account.
Keep vanilla local scores intact. Sanitize player names (including TMPro rich
text), bound name length/score/rank/counts, and do not fetch arbitrary avatar URLs
for the first version. Convert JSON on a worker; create/modify Unity objects only
on the game/UI thread with managed roots, selection generations and cancellation.

A direct PS4 HTTPS GET needs a real certificate-validating network probe first.
If platform TLS cannot reach this service reliably, an optional companion-fed
cache is a fallback—not equivalent to an autonomous console plugin. Do not
solve TLS trouble by globally disabling certificate verification.

## An owned menu/settings button: plausible first native UI prototype

`MainMenuViewController` has real Button fields including `_optionsButton`0xB0,
and `.DidActivate(bool,bool,bool)` RVA0x1C40FC0. Existing settings navigation is
`SettingsNavigationController` with `.DidActivate`RVA0x1B87C70. There is no
established PS4 mod-settings registration API here.

Prefer a clearly separate **OrBeats Extras** entry/view, not replacing or
relabeling a stock option. Reuse an existing button/panel prefab, set layout and
controller navigation deliberately, and remove only our objects when the view
is destroyed. Any cloning must prevent the original button's serialized action
from firing. `RemoveAllListeners` alone does not remove persistent UnityEvent
listeners. Either construct a genuine owned event/delegate through verified ABI,
or intercept only the exact owned button at its native press route and forward
all unrelated buttons unchanged. This remains a design choice, not implemented.
Resolve exact overloads/signatures and validate code bytes for2.04 before hooking;
a name/argument-count match alone is insufficient, as our Sprite overload bug
already demonstrated. No Unity access from network/background threads.

## Startup health/straight-ahead prompt

Owned `HealthWarningFlowCoordinator` contains separate language, region, EULA,
privacy, health, explicit-content, age and end-of-life views. The narrow health
completion handler is `HandleHealthWarningViewControllerDidFinish()`
RVA0x1D45D50; `.DidActivate` is0x1D43B70. The entire coordinator must NOT simply
be skipped, since it also handles first-run agreements and other prerequisites.

An opt-in convenience feature could invoke the existing completion path only
when the actual health view is active and prerequisites are satisfied. First
establish which part of “look straight” is required pose/recenter initialization;
preserve valid tracking and a manual recenter option. Do not blindly remove all
VR warnings or auto-accept EULA/privacy/age screens. No skip implemented yet.

## Selected mod ports, without a general mod loader

PC Chroma and Noodle Extensions are not loadable PS4 DLLs. Their project files
reference Harmony/IPA, CustomJSONData, Heck's tracks/events/animation machinery,
Unity game assemblies and platform-specific presentation hooks. We would need
native replacements for the portions we choose—not a wholesale loader.

### Chroma: the sensible earlier target, but define the subset

Already-supported vanilla V3 light boxes and static map palettes are NOT Chroma.
A useful first subset would be explicitly inventoried legacy/modern light RGB,
per-light-ID routing and the interpolation/easing those maps actually use.
Chroma also supports environment lookup/duplication/transforms, custom materials,
geometry, animated tracks and object colour changes. Many “requires Chroma” maps
need some of these too; a colour-only port cannot claim general Chroma support.

Useful primary source paths in Heck:
- `Chroma/HeckImplementation/CustomDataDeserializer.cs`
- `Chroma/Lighting/LightIDTableManager.cs`
- `Chroma/EnvironmentEnhancement/MaterialsManager.cs`
- `Chroma/EnvironmentEnhancement/EnvironmentMaterialsManager.cs`

Pipeline changes must retain required custom JSON/event data in a bounded native
sidecar/format and expose an exact feature capability. Our current strict refusal
must remain for anything outside that implemented subset. Do not strip a Chroma
requirement merely because the optional plugin is installed. PS4 environment IDs,
materials and native shader variants need validation; copying PC shader binaries
is neither a compatibility solution nor a licensing shortcut.

### Noodle Extensions: substantially larger, defer behind a real Chroma slice

This changes object transforms and animations, not just appearances: note/wall/
slider movement, jump timing, offsets, scale, dissolve, fake/non-interactable
objects, player tracks and gameplay/cut/obstacle interaction. It depends heavily
on shared track/point-definition/custom-event evaluation. A partial renderer
without matching hitboxes/scoring can make a chart unfair or unplayable.

See `NoodleExtensions/HarmonyPatches/Objects/NoteUpdateNoodlifier.cs`,
`NoodleExtensions/HeckImplementation/CustomDataDeserializer.cs`, and
`NoodleExtensions/Managers/NoodlePlayerTransformManager.cs`.
Keep Noodle-required maps refused until their exact semantics have a tested port.

## Recommended order / separate-plugin boundary

1. Hardware-check current0.8078 branding, no song/library migration needed.
2. Separate native UI prototype: one owned button/view, lifecycle cleanup and VR
   navigation, original menu unaffected.
3. Anonymous ScoreSaber request/cache/parser prototype plus verified map identity;
   then genuine table rows. No account or upload subsystem.
4. Optional, narrowly guarded health-view convenience toggle.
5. Inventory actual refused Chroma maps; select and implement one concrete feature
   slice with regression charts and new pipeline/runtime capability negotiation.
6. Reassess Noodle only after a trustworthy custom-data/animation foundation.

A second GoldHEN plugin for UI/leaderboards/conveniences fits this boundary.
OrBeats continues to own songs, publication, identity and media. Share a small
versioned contract rather than pointers or assumed hook order. Do not let two
plugins patch the same entry independently; namespace files/hooks, negotiate
capabilities, detect incompatible versions, and degrade without breaking songs.
This is a proposal, not an implemented loader or new plugin binary.
