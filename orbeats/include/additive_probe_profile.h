// Exp303 one verified full-map binding, NOT a general importer.
// Source: temp/additive-exp303-full-map/prepared/manifest.json (private source/audio).
// To test different content, regenerate and review a new profile; never edit stock.
#pragma once
#include <stdint.h>
#include <stddef.h>
namespace BsdAdditive {
static const char kProbeLevelId[] = "bsd_additive_e3195d81452f3550696b607c";
static const char kProbeTitle[] = "Wake Me Up";
static const char kProbePath[] = "/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c.bundle";
static const char kProbeAsset[] = "bsd_additive_e3195d81452f3550696b607cBeatmapLevelData.asset";
static const char kProbeSha256[] = "305d527c61902fb069f37e63b2223ef74ada5cf65cac1636f1c502e543741fa6";
static const size_t kProbeBytes = 44181622;
// Runtime accidental-corruption gate, NOT cryptographic authenticity. Deployment
// must separately verify the SHA256 manifest/full remote readback before publish.
static const uint64_t kProbeFnv64 = UINT64_C(0x48c20bf1c7fb2be);
static const char kProbeAuthor[] = "Avicii";
static const float kProbeBpm = 124, kProbeDuration = 249.43249433106575f;
static const int32_t kProbeNotes[5] = {312,438,709,1118,1311};
static const int32_t kProbeBombs[5] = {0,12,108,0,120};
static const int32_t kProbeObstacles[5] = {15,3,13,0,14};
static const float kProbeNjs[5] = {11,10,12,14,18};
static const float kProbeJumpOffset[5] = {1,0,0,0,0};
inline uint64_t probe_fnv_update(uint64_t state,const unsigned char* bytes,size_t n) {
    for(size_t i=0;i<n;++i) state=(state^bytes[i])*UINT64_C(1099511628211);
    return state;
}
} // namespace
