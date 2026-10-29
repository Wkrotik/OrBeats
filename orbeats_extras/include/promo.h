// Main-menu music-pack promotion only. No DLC, model or store hooks.
#pragma once
#include <stddef.h>
#include <stdint.h>
namespace OrBeatsExtras {
bool install_promo(uintptr_t base,void*(*resolve)(const char*),
                   bool(*executable)(const void*,size_t),void(*logger)(const char*));
bool promo_has_hooks();
} // namespace
