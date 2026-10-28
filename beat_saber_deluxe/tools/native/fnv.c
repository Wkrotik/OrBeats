/* OrBeats FNV-1a wire checksum; GPL-3.0, see the repository LICENSE. */
#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT uint64_t orbeats_fnv1a64(const unsigned char *data, size_t length) {
    uint64_t value = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < length; ++i) {
        value = (value ^ data[i]) * UINT64_C(1099511628211);
    }
    return value;
}
