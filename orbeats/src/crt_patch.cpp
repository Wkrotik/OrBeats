// CRT replacement data sections for PS4 PRX format.
// Replaces what crtlib.o normally provides, so we can define
// our own module_start/module_stop without symbol conflicts.

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

// module_start is defined in main.cpp — we call it from _init
extern "C" int module_start(size_t argc, const void *args);
extern "C" int module_stop(size_t argc, const void *args);

// --- .data.sce_module_param (required by create-fself for PRX) ---
// Content mirrors crtlib.o's _sceProcessParam data.
// Format: SceModuleParam structure.
struct __attribute__((packed)) SceModuleParam {
    uint32_t size;     // 0x18 = 24 bytes total
    uint32_t pad;      // 0
    uint64_t magic;    // module param magic
    uint64_t flags;    // module flags
};

static const SceModuleParam sce_module_param
__attribute__((section(".data.sce_module_param"), used)) = {
    .size = 0x18,
    .pad = 0,
    .magic = 0x000000013c13f4bf,
    .flags = 0x0000000000000051,  // bit 0=valid; create-fself adds bit 24 (PRX)
};

// --- .data (minimal CRT data) ---
// __dso_handle: used by libc++ for __cxa_atexit / destructor registration.
// The value is typically a pointer to itself.
static void* __dso_handle_trap
__attribute__((section(".data"), used)) = nullptr;

// _sceLibc: libc control block. Needed by libc on PS4.
// Contains heap/pthread params. NULL = defaults.
static void* _sceLibc
__attribute__((section(".data"), used)) = nullptr;

// --- _init / _fini ---
// GoldHEN calls _init when loading the plugin (not module_start).
// _init does PRX initialization then calls module_start for plugin init.
extern "C" void _init(void) {
    // ── Path Probe ────────────────────────────────────────────────────────
    // Try every candidate path on the PS4 to discover where the game process
    // has write access. Each working path gets a marker file; the first
    // working path also gets a full summary table of all attempts.

    struct { const char* path; int ok; } results[16];
    int n = 0, any_ok = 0;

    const char* paths[] = {
        "/data/custom/bs_deluxe/heartbeat.txt",
        "/data/heartbeat.txt",
        "/data/cache0001/heartbeat.txt",
        "/data/GoldHEN/heartbeat.txt",
        "/data/PS4Xplorer/heartbeat.txt",
        "/data/sce_logs/heartbeat.txt",
        "/tmp/heartbeat.txt",
        "/user/temp/heartbeat.txt",
        "/user/data/heartbeat.txt",
        "/user/savedata/heartbeat.txt",
        "/user/settings/heartbeat.txt",
        "/mnt/usb0/heartbeat.txt",
        "/mnt/usb1/heartbeat.txt",
        "/mnt/ext0/heartbeat.txt",
        NULL
    };

    for (int i = 0; paths[i]; i++) {
        FILE* f = fopen(paths[i], "w");
        results[n].path = paths[i];
        results[n].ok = (f != NULL);
        if (f) {
            any_ok = 1;
            fprintf(f, "WORKING PATH: %s\n"
                       "init was called by GoldHEN\n"
                       "Experiment 4f  oelf format\n",
                       paths[i]);
            fclose(f);
        } else {
            results[n].ok = 0;
        }
        n++;
    }

    // Write a full report to the first path that succeeded
    if (any_ok) {
        for (int i = 0; i < n; i++) {
            if (results[i].ok) {
                FILE* f = fopen(results[i].path, "w");
                if (f) {
                    fprintf(f, "=== Path Probe Report ===\n"
                               "Date:    2026-06-11\n"
                               "Plugin:  OrBeats\n"
                               "Exp:     4f (_init entry, .oelf)\n"
                               "\n"
                               "%-32s %s\n"
                               "-------------------------------- %s\n",
                               "Path", "Status",
                               "------");
                    for (int j = 0; j < n; j++) {
                        const char* st = results[j].ok ? "YES" : "NO";
                        fprintf(f, "%-32s  %s\n", results[j].path, st);
                    }
                    fclose(f);
                }
                break;
            }
        }
    }
    // ── End Path Probe ────────────────────────────────────────────────────

    module_start(0, NULL);
}

extern "C" void _fini(void) {
    module_stop(0, NULL);
}
