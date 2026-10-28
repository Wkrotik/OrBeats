# Memory Injection — Status Report (2026-07-23)

## 🔴🔴🔴 STATUS: DEAD END — Do Not Pursue

After 14+ plugin versions (v0.66–v0.8024) and 18+ experiments, memory injection is conclusively abandoned.

### Why It Failed

| Scan Target | Versions | Result |
|-------------|----------|--------|
| Klass pointer `0x2012007E0` in heap | v0.66–v0.8015 (10+ versions) | **0 objects found** — PS4 IL2CPP uses compressed/indirect klass pointers |
| UTF-16LE strings in GC heap (8–8.25GB) | v0.8017–v0.8024 (7 versions) | **0 strings found** — strings not in scannable heap |
| UTF-16LE strings in metadata mmap (10.5–10.8GB) | v0.8020–v0.8024 (4 versions) | **0 strings found** — string literals are heap-allocated, not in mmap |
| UTF-16LE strings in low memory (16MB–4GB) | v0.8024 (1 version) | **0 strings found** — pack bundles mmap'd here but no strings |
| UTF-16LE strings in extended heap (4–8GB) | v0.8024 (1 version) | **0 strings found** — no matching patterns |
| **Total pages scanned** | v0.8017–v0.8024 | **~15,000 pages (~960MB), 0 string matches** |

### Root Causes (Inferred)

1. **BeatmapLevelSO objects are lazily instantiated** — Created only when the song list UI renders, not during pack bundle load at startup
2. **System.String objects may be in non-scannable memory** — Could be in a GC generation or memory region not accessible via `try_read_mem`
3. **PS4 IL2CPP uses compressed pointers** — Klass-based object search fundamentally broken on this platform

### Last Commit with Memory Injection Code
- Commit `1586581` — reference if ever needed again
- Code removed in subsequent cleanup (v0.8025+)

### What We Know Works (Preserved)
- `try_read_mem()` with signal handlers — safe memory probing on PS4
- Feature flags system — all experimental features gated behind `features.json`
- Deploy path: `/data/GoldHEN/plugins/` (NOT `/data/GoldHEN/AFR/`)
- File-open sequence: system → pack bundles (#207–738) → song redirects (#740+) → scenes/shaders

---

## Historical Content Below (Preserved for Reference)

### Original Summary (Pre-Dead-End)

When pack bundle modification is blocked by dual validation (m_BundleSize AND m_Crc), fallback to **memory injection**: patch BeatmapLevelSO objects in RAM after Addressables loads and validates the pack bundle. This bypasses catalog CRC validation entirely.

**Key Insight:** Addressables validates CRC LAZILY (when contents accessed, not during LoadFromFile). This gives us a window to patch objects in RAM before the game reads their metadata.

## Architecture (Historical)

```
module_start()
  ├── load_redirects()              — file redirection table
  ├── install_fopen_hook()
  ├── install_open_hook()
  ├── register_song_metadata()      — 13 Rolling Stones entries
  ├── memory_inject_init()          ← REMOVED in v0.8025
  │     └── pthread_create()        — detached worker thread
  │           └── patch_worker()
  │                 ├── usleep(30s)  — wait for game init
  │                 ├── find_beatmap_level_so_klass()  — locate class by string search
  │                 ├── scan_for_beatmap_level_objects() — memory scan by klass ptr
  │                 └── patch_beatmap_level_object()  — in-place string overwrite
  └── notification
```

## Key Technical Details (Historical)

### Finding BeatmapLevelSO Class Metadata
1. Use `sceKernelGetModuleList()` to find Il2CppUserAssemblies module base
2. Search module segments for C string "BeatmapLevelSO"
3. Search for 8-byte pointer references to that string → these are `name` fields at Il2CppClass_1+0x10
4. Validate by checking surrounding fields (namespaze, byval_arg)
5. Result: the `BeatmapLevelSO_c` klass pointer

### Finding Objects in Memory
1. Search process memory (0x100000000–0x800000000) in 64KB pages
2. For each readable page, scan for 8-byte-aligned values matching klass pointer
3. Validate candidates by checking:
   - `_version` at +0x18 is a small integer (1–100)
   - `_levelID` at +0x20 is a valid pointer
   - String klass at _levelID[0] is a valid class pointer
   - `_songName` at +0x28 and `_songAuthorName` at +0x38 are valid pointers

### In-Place String Patching
- Managed strings (System_String_o) have format: klass(8) + monitor(8) + length(4) + chars(variable)
- Character data starts at offset 0x14 in UTF-16LE
- New string MUST fit within old capacity (length ≤ original)
- Write new length at +0x10, new chars at +0x14, zero-fill remainder
- This avoids GC complications entirely

## Implementation Files (Historical)

| File | Purpose |
|------|---------|
| `src/memory_inject.h` | Public API: init, register, SongMetadataEntry |
| `src/memory_inject.cpp` | Full implementation (~996 lines) |
| `src/main.cpp` | Integration: v0.66, includes metadata registration |
| `development/scripts/memory_inject_test.py` | Test script (Python simulation) |
| `development/scripts/memory_scan_implementation.md` | Design document |

## Verification (Historical)

The implementation uses the **exact** struct layouts verified from the IL2CPP dump:
- `BeatmapLevelSO_Fields` at `il2cpp.h:381156`
- `BeatmapLevelSO_o` at `il2cpp.h:381195`
- `System_String_Fields` at `il2cpp.h:67167`
- `System_String_o` at `il2cpp.h:67207`
- `Il2CppClass_1` at `il2cpp.h:38`
- `Il2CppObject` at `il2cpp.h:19`
