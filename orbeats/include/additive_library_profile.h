// Exp310 bounded reviewed two-song test. NOT a runtime library/import protocol.
// Private source/audio/bundles remain ignored. SHA256+full FTP readback required.
#pragma once
#include "additive_probe_level.h"
#include "additive_menu_profile.h"
namespace BsdAdditive {
struct ReviewedSong {
 const char *id,*title,*author,*path,*asset,*sha256;
 size_t bytes;uint64_t fnv;
 float bpm,duration,preview_duration;uint32_t difficulty_mask;
 ProbeDifficulty difficulties[5];MenuFileSpec cover,preview;
 const ProbeModes* modes = NULL;
 const ProbePresentation* presentation = NULL;
 const char* environment = NULL; // Explicit reviewed v2 routing; NULL preserves stock fallback.
};
static const ReviewedSong kReviewedSongs[]={
 {
  "bsd_additive_e3195d81452f3550696b607c","Wake Me Up","Avicii","/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c.bundle","bsd_additive_e3195d81452f3550696b607cBeatmapLevelData.asset","305d527c61902fb069f37e63b2223ef74ada5cf65cac1636f1c502e543741fa6",
  44181622,UINT64_C(0x48c20bf1c7fb2be),124.0f,249.43249433106575f,10,31,
  {{312,0,15,11,1},{438,12,3,10,0},{709,108,13,12,0},{1118,0,0,14,0},{1311,120,14,18,0}},
  {"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c-media/song-cover.png",617420,UINT64_C(0x1ab799b728d9a5d5)},{"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_e3195d81452f3550696b607c-media/preview.wav",1764078,UINT64_C(0xbb80cd0da9fcc60e)}
 },
 {
  "bsd_additive_376607927402e50fcf6ab89f","Cities","Throttle","/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_376607927402e50fcf6ab89f.bundle","bsd_additive_376607927402e50fcf6ab89fBeatmapLevelData.asset","5a25da74a66eacd36bb2f50546c24e29f49e703684ae417b32957e80d17f2d01",
  32237054,UINT64_C(0xd0c45c91c5e83670),114.0f,181.81086167800453f,20,28,
  {{0,0,0,0,0},{0,0,0,0,0},{189,0,289,11,-0.532f},{350,0,311,12.5f,-0.784f},{414,0,331,14,-0.982f}},
  {"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_376607927402e50fcf6ab89f-media/song-cover.png",127966,UINT64_C(0x7ea22112fd1f6520)},{"/data/GoldHEN/AFR/CUSA12878/additive/bsd_additive_376607927402e50fcf6ab89f-media/preview.wav",3528078,UINT64_C(0x77c08e480e6e56e8)}
 },
};
static const size_t kReviewedSongCount=sizeof(kReviewedSongs)/sizeof(kReviewedSongs[0]);
static const char* const kReviewedIds[]={"bsd_additive_e3195d81452f3550696b607c","bsd_additive_376607927402e50fcf6ab89f"};
inline const ReviewedSong* reviewed_song(const Api& api,void* id){
 for(size_t i=0;i<kReviewedSongCount;++i)if(ascii_equals(api,id,kReviewedSongs[i].id))return &kReviewedSongs[i];
 return NULL; // stock, unknown and prefix-only IDs are NEVER redirected
}
} // namespace
