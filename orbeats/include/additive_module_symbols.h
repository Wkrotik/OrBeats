// Exp292: resolve public names through an explicit kernel module handle.
// No global libc lookup, guessed API RVA or direct managed allocation fallback.
#pragma once
#include <stdint.h>
#include <string.h>
namespace BsdAdditive {
typedef int32_t (*ModuleLookup)(int32_t, const char*, void**);
typedef bool (*AddressValidator)(const void*, const void*);
inline void* module_symbol(int32_t handle, const char* name, ModuleLookup lookup,
                           AddressValidator validate, const void* context) {
    if (handle < 0 || !name || strncmp(name, "il2cpp_", 7) != 0 || !name[7] ||
        !lookup || !validate || !context) return NULL;
    void* address = NULL;
    if (lookup(handle, name, &address) != 0 || !address || !validate(context, address)) return NULL;
    return address;
}
} // namespace BsdAdditive
