# Memory Injection — Heap Scanning Implementation Plan

## Overview

We need to scan the IL2CPP managed heap to find all loaded BeatmapLevelSO objects, then patch their fields with Espresso metadata. This bypasses Addressables CRC validation entirely.

## Key Challenges

1. **Finding the IL2CPP heap base address**
   - IL2CPP stores managed objects in a contiguous heap
   - We need to find where this heap starts in memory
   
2. **Scanning for objects by type signature**
   - Each object has a vtable pointer pointing to its class
   - We can scan for BeatmapLevelSO's vtable address to identify instances

3. **Patching fields safely**
   - Strings are managed objects with reference counting
   - Arrays have headers and element pointers
   - Need to maintain object integrity after patching

## Implementation Steps

### Step 1: Find IL2CPP Heap Base Address

**Approach:** Use `sceKernelGetModuleList()` to find the Il2CppUserAssemblies.prx module, then scan its BSS segment for heap metadata.

```cpp
// From il2cpp.h (hypothetical structure):
struct Il2CppDomain {
    void* assemblies;       // Loaded assemblies
    void* defaultDomain;    // Default domain
    void* classCache;       // Class cache
};

struct Il2CppHeap {
    uint8_t* heapBase;      // Base address of managed heap
    size_t heapSize;        // Total heap size
    void* nextObject;       // Next free object allocation pointer
    void* gcData;           // GC metadata
};
```

**Alternative:** Scan for known IL2CPP runtime structures (e.g., `il2cpp_runtime_class`) and work backward to find the heap.

### Step 2: Scan Heap for BeatmapLevelSO Objects

**Approach:** Iterate through all objects in the heap, check their vtable pointer against BeatmapLevelSO's class address.

```cpp
#define BEATMAP_LEVEL_SO_VTABLE_ADDR 0xXXXXXXX  // From il2cpp dump

struct Il2CppObject {
    void* klass;          // Pointer to class (vtable)
    void* monitor;        // Monitor/gc data
    union {
        void* gcData;     // GC tracking
        uintptr_t next;   // Linked list for free objects
    };
};

// Scan loop:
for (uintptr_t objAddr = heapBase; objAddr < heapEnd; objAddr += sizeof(Il2CppObject)) {
    Il2CppObject* obj = (Il2CppObject*)objAddr;
    
    if (obj->klass == BEATMAP_LEVEL_SO_VTABLE_ADDR) {
        // Found a BeatmapLevelSO!
        patch_beatmap_level(obj);
    }
}
```

### Step 3: Patch Object Fields

**BeatmapLevelSO Field Layout:**
```cpp
struct BeatmapLevelSO {
    PersistentScriptableObject _base;  // Base class (0x10 bytes)
    
    int32_t _version;                   // 0x18
    String* _levelID;                  // 0x20
    String* _songName;                 // 0x28
    String* _songSubName;              // 0x30
    String* _songAuthorName;           // 0x38
    String* _levelAuthorName;          // 0x40
    AudioClip* _previewAudioClip;      // 0x48
    float _beatsPerMinute;             // 0x50
    // ... more fields ...
};

// Patching:
void patch_beatmap_level(Il2CppObject* obj) {
    BeatmapLevelSO* bsl = (BeatmapLevelSO*)obj;
    
    // Allocate new strings (or modify existing ones)
    String* newLevelID = il2cpp_string_new("custom/espresso");
    String* newSongName = il2cpp_string_new("Espresso");
    String* newArtist = il2cpp_string_new("Sabrina Carpenter");
    
    // Patch fields
    bsl->_levelID = newLevelID;
    bsl->_songName = newSongName;
    bsl->_songAuthorName = newArtist;
}
```

### Step 4: Hook into Bundle Loading Pipeline

**Approach:** Hook `AssetBundle.LoadFromFile` (already done via AFR plugin), then after bundle loads, scan for BeatmapLevelSO objects and patch them.

```cpp
// In our open() hook:
static int open_hook(const char* path, int flags, ...) {
    // ... existing redirect logic ...
    
    if (is_pack_bundle(path)) {
        // Bundle is loading — wait for it to complete, then patch
        // This requires asynchronous handling or a callback
    }
}
```

**Alternative:** Use a timer/gc callback to patch objects after they're loaded.

## Current Status

- ✅ Test script created and verified (`memory_inject_test.py`)
- ⏳ Plugin skeleton created (`memory_inject_plugin.cpp`)
- ⏳ Heap scanning logic needs implementation
- ⏳ Field patching logic needs IL2CPP runtime integration
- ⏳ Hook integration with AFR plugin needed

## Next Steps

1. **Implement heap scanning** — Find IL2CPP heap base and scan for BeatmapLevelSO objects
2. **Test with simple patch** — Change song name only (doesn't require blob injection)
3. **Integrate into main plugin** — Add memory injection as fallback when pack bundle modification fails

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Heap layout changes between game versions | Make heap scanning configurable/patchable |
| String patching breaks reference counting | Use IL2CPP runtime API for string allocation |
| Hook timing issues (bundle not fully loaded) | Add delay or callback mechanism |
| Memory corruption from unsafe patches | Validate object integrity after patching |

## References

- [[il2cpp-dump-mode-selector-hook]] — BeatmapLevelSO field offsets and type IDs
- [[addressables-crc-validation-timing]] — When Addressables validates CRC
- [[memory-injection-addressables-bypass]] — Full memory injection approach details
