#pragma once
#include <stddef.h>
#include <stdint.h>
namespace OrBeatsExtras {
// Startup only, before view activation. No implicit console installation.
bool install_leaderboard(uintptr_t base,void*(*resolve)(const char*),bool(*executable)(const void*,size_t),void(*log)(const char*));
bool leaderboard_has_hooks();
} // namespace
