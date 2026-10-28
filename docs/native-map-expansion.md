# Expanded vanilla-map candidate

**Local candidate:** plugin **0.8075**, pipeline **0.5385**, companion **0.7.17**.
**Not installed or hardware-tested.** The user's PS4 remains on0.8074. The earlier
0.8073 Looping the Rooms gameplay/visible-lighting result does not validate these
new paths. No console changes or automatic retries belong to this request.

## Does this PS4 game support V4?

Yes: the acquired CUSA12878 patch2.04 metadata has native
`BeatmapSaveDataVersion4.BeatmapSaveData` (TypeDef12099, current4.1.0), indexed
arcs/chains, `njsEvents`/`njsEventData`, native lightshow data (TypeDef12115),
and sample-domain AudioData loaders. This is stronger evidence than assuming a
PC feature works on PS4; it is still not a successful custom-map hardware test.

V4 is primarily an indexed storage/schema change: repeated object definitions
are stored once and referenced by index. It does not inherently add better music,
more difficult notes or better graphics. Arcs/chains and elaborate lightshows also
exist in V3. Dynamic note-jump-speed events are a meaningful additional gameplay
capability when authored. A particular chart benefits from the features it uses,
not from the version number alone.

Public format references:
- https://bsmg.wiki/mapping/map-format/beatmap.html
- https://bsmg.wiki/mapping/map-format/lightshow.html

Do not blindly accept every field from the newest public specification. This
PS4 V4 class has object rotation lanes, but **does not have** the separate newer
`spawnRotations`/`spawnRotationsData` fields. Those still refuse. V3 early/late
rotation events have their own native preservation path.

## Implemented locally

| Previously missing category | Candidate implementation |
| --- | --- |
| More stock environments | Explicit catalog-reviewed names, beyond Weave, through the actual EnvironmentName ABI. Never rename authored group IDs to fit a substitute. Multiplayer/tutorial environments are excluded. Runtime refuses unavailable environment/characteristic objects. Catalog availability is not proof of every visual layout. |
| V3 chains | Geometry, slice count/squish and references validated; chain heads/tails and menu cuttable counts retained. Advanced ordinary V3 can be encoded as native indexed V4 without flattening its beat domain. |
| V3 translation/FX boxes | Translation distributions retained. V3 integer/float/bool FX are validated and kept as native V3; table type, easing and every index are checked. No conversion of integer FX into float FX. |
| Changing-BPM event-box lighting | Native beat-domain objects plus one shared AudioData sample/BPM timeline. This leaves distributed/eased times for the engine; retiming only group starts is not used. Difficulties with incompatible native BPM timelines refuse. |
| V4 arcs/chains | Preserve native index tables/events, both endpoints, note references, rotations and chain slices. Validate even unused metadata rows and aggregate budgets. |
| V4 lighting | Native basic/boost events, keyword routing, colour/rotation/translation/float-FX boxes and filters, rather than empty-lightshow-only conversion. |
| V4 dynamic NJS | Validate indexed delta/previous/easing metadata and resulting speed bounds; retain native events. Hardware gameplay remains pending. |
| OneSaber / NoArrows | Distinct per-characteristic files, real game keys and independent difficulty masks/statistics. Not Standard relabelling. |
| 90Degree / 360Degree | Native V4 object rotation lanes and native V3 early/late rotation events. V2 types14/15 convert only in explicit rotational characteristics using the documented0..7 degree table, then preserve native V3 semantics. |
| Authored colour palettes | InfoV2 legacy colour overrides and InfoV4 schemes; clone a genuine managed ColorScheme with its constructor, root it, preserve unoverridden values, and verify results. Never mutate the stock scheme. Player override precedence still requires hardware verification. |
| Offsets / loudness / previews | Bounded song offsets and authored loudness passed through the genuine level constructor; AudioData LUFS/sample regions validated. Separate V4 preview tracks decoded independently, not replaced with a main-song excerpt. |

## Packaging, library and upgrade protections

- Preserve source beat-domain chart/lightshow data for native payloads. AudioData
  sample indices are resampled once to the actual stored audio rate/frame count;
  beat boundaries and LUFS regions are retained. Ordinary supported audio still
  prefers compatible original Vorbis packets, with validated PCM fallback.
- Reopen the UnityFS output, all gzip chart/lightshow TextAssets and the shared
  AudioData TextAsset. Compare expected native JSON, object counts, characteristic
  routes and media. Inspect every actual template reference; do not assume all
  difficulties exist in the source bundle.
- Keep unchanged legacy V1/V2 library encoding when new fields are absent.
  Optional **BSDALIB3** adds presentation; **BSDALIB4** adds four non-Standard
  characteristic masks and their five independent statistics records. The native
  decoder accepts all four formats. Existing descriptors re-encode identically.
- Optional ELF capability markers `ORB_NATIVE_MAPS_V1`, `ORB_PRESENTATION_V1`
  and `ORB_MODES_V1` govern import and advertised library format. Verify the
  active canonical ELF hash, not just a version string or an assumed capability.
  Refuse unsupported imports before file uploads and refuse incompatible plugin
  downgrades for an existing higher-format library.
- Characteristic selection searches bounded genuine stock repositories for actual
  BeatmapCharacteristicSO references. Missing characteristics refuse the batch
  before publication. No fabricated ScriptableObject or guessed registered mode.
- Library UI reports each real characteristic/difficulty, including mode-only
  maps with no Standard charts. Discovery compatibility remains an archive-
  unverified metadata hint, not a guarantee of PS4 playback.
- Closed-title checks, serialized transactions, local recovery archives, immutable
  song files and library-last publication remain in force. No permanent remote
  backup accumulation is reintroduced.

## Deliberate remaining restrictions

- No Chroma, Noodle Extensions, Mapping Extensions, Cinema, custom Unity
  environments or unknown runtime requirements. Do not silently strip their
  gameplay/visual behaviours.
- One environment per song. Distinct per-difficulty environments refuse.
- One palette per difficulty rank within a song; conflicting palettes for the
  same difficulty across characteristics refuse instead of picking one silently.
- No unsupported future V4 fields such as separate spawn-rotation arrays. No
  geometry beyond the validated vanilla bounds and no nonempty V2/V3 waypoints.
- Native advanced difficulties share one verified sample/BPM timeline. Different
  per-difficulty BPM-region layouts refuse, even if the music file is shared.
- Existing finite bounds remain: audio up to600seconds,64library entries and
  131072manifest bytes, authored offset within±10seconds, validated per-array and
  aggregate object budgets. These are limits, not an unlimited-capacity claim.
- Source/group availability, player colour/environment override precedence,
  dynamic-NJS feel, headset rotation/obstacle alignment, Practice seek and stock
  regression need hardware tests. Passing fake managed API and schema tests
  does not prove those effects on the console.

## Validation record

**Final host result:1460passed,124skipped**, one inherited Starlette deprecation
warning (65.28seconds). Release/DEBUG builds emitted no warnings. Scoped Ruff
and Ty checks for the new helpers/V4 importer pass; a broad exploratory Ty run
found unrelated legacy/research diagnostics and is not claimed as clean. Offline
desktop/mobile browser fixtures pass; they do not connect to the PS4.

See ignored local `temp/map-expansion/` for full regression output, clean
release/DEBUG builds, lint and desktop/mobile offline browser evidence. The host
suite includes real reopened UnityFS fixtures, native ASAN/UBSAN registration and
wire readers, mixed legacy/new library roundtrips, mode-only and multi-mode maps,
explicit old-capability refusal, malformed indices/enums/budgets, audio/LUFS
resampling, palette cloning without stock writes, and missing-mode atomic refusal.
No private game metadata or downloaded music is staged or distributed.

## Real InfoV4 follow-up: Here Come the Cats (555fe)

After user-confirmed Bloom/Looping regression playback, pipeline **0.5386** adds
bounded unprefixed InfoV4 per-difficulty cosmetic colour/label normalization. Known
colours override schemes through the existing palette path; unknown custom-data
keys (including requirements) and malformed RGBA still refuse. Labels remain
reported as not displayed rather than being claimed as native UI support.

The real map also exposed two erroneous restrictions: arc tail-metadata colour
is not used by this PS4 native loader (owned ArcItemConverter.Convert RVA0x9E57C0
reads head x/y/c/d and tail x/y/d), so it need not equal the head colour. Both
metadata references remain checked. AudioData and decoded audio differ by exactly
one sample; the existing one-sample duration tolerance is now compared using
integer sample units, preventing boundary float cancellation. Larger differences
and invalid BPM/sample-region bounds still refuse.

1480 host tests pass,124skip; native builds, scoped lint/type checks and offline
browser checks pass. A normal queue install, with title verified closed, preserved
all26prior entries and did not change plugin0.8075 or INI/features/capability. The
27th entry is555fe ExpertPlus,787notes,18V4arcs,2675basic lighting events and six
palette fields. Independent remote UnityFS readback equals the source chart and
lightshow. Game was not launched; **555fe hardware playback remains pending**.
Do not confuse this map's arcs/basic lights with a chains/dynamic-NJS test.
