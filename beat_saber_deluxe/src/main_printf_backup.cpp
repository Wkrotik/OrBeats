// printf-based test — uses printf/klog instead of fopen for logging
// No fopen, no fself, no notification — just printf output
// If this works, the crash was from fopen/fprintf in early game init

#include <stdio.h>
#include <stddef.h>

extern "C" int module_start(size_t argc, const void *args) {
    (void)argc;
    (void)args;

    // Use printf/klog instead of fopen for logging
    printf("OrBeats: plugin loaded! module_start called\n");
    printf("OrBeats: format=FSELF, argc=%zu\n", argc);

    return 0;
}

extern "C" int module_stop(size_t argc, const void *args) {
    (void)argc;
    (void)args;
    return 0;
}
