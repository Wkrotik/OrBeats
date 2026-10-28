// Exp305 reviewed local menu files; SHA256 readback required during deployment.
#pragma once
#include "additive_menu_media.h"
namespace BsdAdditive {
struct MenuFileSpec { const char* path;size_t bytes;uint64_t fnv; };
static const MenuFileSpec kMenuSong={"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c-media/song-cover.png",617420,UINT64_C(0x1ab799b728d9a5d5)};
static const MenuFileSpec kMenuPack={"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c-media/pack-cover.png",31229,UINT64_C(0xb6e22c9bd7164ae1)};
static const MenuFileSpec kMenuPreview={"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c-media/preview.wav",1764078,UINT64_C(0xbb80cd0da9fcc60e)};
} // namespace
