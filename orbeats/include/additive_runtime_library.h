// Bounded v1/v2 companion wire format. Decode bytes explicitly; never map structs.
#pragma once
#include "additive_environments.h"
#include "additive_library_profile.h"
#include "additive_probe_profile.h"
#include <stdio.h>
namespace BsdAdditive {
static const char kLibraryPath[]="/data/GoldHEN/AFR/CUSA12878/additive/library.bin";
static const size_t kLibraryMaxBytes=131072;
struct RuntimeLibrary {
    ReviewedSong songs[kMaxGeneratedLevels];size_t count;
    char ids[kMaxGeneratedLevels][81],titles[kMaxGeneratedLevels][256],authors[kMaxGeneratedLevels][256];
    char paths[kMaxGeneratedLevels][256],assets[kMaxGeneratedLevels][128],hashes[kMaxGeneratedLevels][65];
    char covers[kMaxGeneratedLevels][256],previews[kMaxGeneratedLevels][256];
    char environments[kMaxGeneratedLevels][64];
    const char* approved[kMaxGeneratedLevels];
    ProbePresentation presentations[kMaxGeneratedLevels];
    ProbeModes modes[kMaxGeneratedLevels];
    void defaults(){count=kReviewedSongCount;for(size_t i=0;i<count;++i){songs[i]=kReviewedSongs[i];approved[i]=songs[i].id;}}
};
struct LibraryReader {
    const unsigned char* p;size_t n;bool ok;
    uint32_t u32(){if(n<4){ok=false;return 0;}uint32_t v=0;for(int i=0;i<4;++i)v|=uint32_t(p[i])<<(8*i);p+=4;n-=4;return v;}
    uint64_t u64(){uint64_t lo=u32(),hi=u32();return lo|(hi<<32);}
    float real(){uint32_t v=u32();float f;memcpy(&f,&v,4);return f;}
    bool text(char* out,size_t capacity){
        uint32_t size=u32();if(!ok||!size||size>=capacity||size>n){ok=false;return false;}
        // Validate canonical UTF8, excluding NUL/control/surrogate/overlong data.
        size_t i=0;while(i<size){unsigned c=p[i++];if(c<32||c==127){ok=false;break;}
            if(c<128)continue;unsigned need=0,value=0,minimum=0;
            if(c>=0xc2&&c<=0xdf){need=1;value=c&31;minimum=0x80;}
            else if(c>=0xe0&&c<=0xef){need=2;value=c&15;minimum=0x800;}
            else if(c>=0xf0&&c<=0xf4){need=3;value=c&7;minimum=0x10000;}
            else{ok=false;break;}
            if(need>size-i){ok=false;break;}
            while(need--){unsigned b=p[i++];if((b&0xc0)!=0x80){ok=false;break;}value=(value<<6)|(b&63);}
            if(!ok||value<minimum||value>0x10ffff||(value>=0xd800&&value<=0xdfff)){ok=false;break;}
        }
        if(!ok)return false;memcpy(out,p,size);out[size]=0;p+=size;n-=size;return true;
    }
};
inline bool library_float(float f,float low,float high){return f==f&&f>=low&&f<=high;}
inline bool decode_library(RuntimeLibrary& out,const unsigned char* bytes,size_t size){
    if(size<24||size>kLibraryMaxBytes||(memcmp(bytes,"BSDALIB1",8)&&memcmp(bytes,"BSDALIB2",8)&&memcmp(bytes,"BSDALIB3",8)&&memcmp(bytes,"BSDALIB4",8)))return false;
    const bool v4=!memcmp(bytes,"BSDALIB4",8);
    const bool v3=v4||!memcmp(bytes,"BSDALIB3",8);
    const bool v2=v3||!memcmp(bytes,"BSDALIB2",8);
    LibraryReader r={bytes+8,size-8,true};uint32_t length=r.u32();uint64_t digest=r.u64();
    if(length!=r.n||probe_fnv_update(UINT64_C(14695981039346656037),r.p,r.n)!=digest)return false;
    size_t count=r.u32();if(count>kMaxGeneratedLevels)return false;
    // No paths/asset names supplied by the manifest: derive from exact own ID.
    // Call only on fresh storage. A failure never exposes partial count.
    out.count=0;
    for(size_t i=0;i<count;++i){ReviewedSong& s=out.songs[i];s={};
        if(!r.text(out.ids[i],81)||!r.text(out.titles[i],256)||!r.text(out.authors[i],256)||!r.text(out.hashes[i],65))return false;
        if(strlen(out.ids[i])!=37||strncmp(out.ids[i],"bsd_additive_",13)||strlen(out.hashes[i])!=64)return false;
        for(size_t j=13;j<37;++j)if(!((out.ids[i][j]>='0'&&out.ids[i][j]<='9')||(out.ids[i][j]>='a'&&out.ids[i][j]<='f')))return false;
        for(size_t j=0;j<64;++j)if(!((out.hashes[i][j]>='0'&&out.hashes[i][j]<='9')||(out.hashes[i][j]>='a'&&out.hashes[i][j]<='f')))return false;
        for(size_t j=0;j<i;++j)if(!strcmp(out.ids[i],out.ids[j]))return false;
        s.id=out.ids[i];s.title=out.titles[i];s.author=out.authors[i];s.sha256=out.hashes[i];
        snprintf(out.paths[i],256,"/data/GoldHEN/AFR/CUSA12878/additive/%s.bundle",s.id);
        snprintf(out.assets[i],128,"%sBeatmapLevelData.asset",s.id);
        snprintf(out.covers[i],256,"/data/GoldHEN/AFR/CUSA12878/additive/%s-media/song-cover.png",s.id);
        snprintf(out.previews[i],256,"/data/GoldHEN/AFR/CUSA12878/additive/%s-media/preview.wav",s.id);
        s.path=out.paths[i];s.asset=out.assets[i];
        s.bytes=r.u32();s.fnv=r.u64();s.bpm=r.real();s.duration=r.real();s.preview_duration=r.real();s.difficulty_mask=r.u32();
        if(s.bytes<1||s.bytes>200000000||!library_float(s.bpm,1,1000)||!library_float(s.duration,1,1800)||
           !library_float(s.preview_duration,1,30)||s.preview_duration>s.duration||(!s.difficulty_mask&&!v4)||s.difficulty_mask>31)return false;
        for(size_t d=0;d<5;++d){ProbeDifficulty& p=s.difficulties[d];uint32_t notes=r.u32(),bombs=r.u32(),walls=r.u32();
            p.njs=r.real();p.jump_offset=r.real();if(notes>200000||bombs>200000||walls>200000)return false;
            p.notes=(int32_t)notes;p.bombs=(int32_t)bombs;p.obstacles=(int32_t)walls;
            if(s.difficulty_mask&(1u<<d)){if(!library_float(p.njs,.1,100)||!library_float(p.jump_offset,-20,20))return false;}
            else if(notes||bombs||walls||p.njs!=0||p.jump_offset!=0)return false;
        }
        s.cover={out.covers[i],r.u32(),r.u64()};s.preview={out.previews[i],r.u32(),r.u64()};
        if(!s.cover.bytes||s.cover.bytes>6000000||s.preview.bytes<44||s.preview.bytes>6000000||!r.ok)return false;
        if(v2){
            if(!r.text(out.environments[i],64))return false;
            if(reviewed_environment(out.environments[i]))s.environment=out.environments[i];
            else if(strcmp(out.environments[i],"stock"))return false;
        }
        if(v3){
            ProbePresentation& profile=out.presentations[i];profile={};
            profile.lufs=r.real();profile.offset=r.real();
            if(!library_float(profile.lufs,-100,100)||!library_float(profile.offset,-10,10))return false;
            bool used=profile.lufs!=-14||profile.offset!=0;
            for(size_t d=0;d<5;++d){ProbePalette& palette=profile.palettes[d];palette.mask=r.u32();
                if(palette.mask>511)return false;if(palette.mask)used=true;
                if(!v4&&!(s.difficulty_mask&(1u<<d))&&palette.mask)return false;
                for(size_t c=0;c<9;++c)if(palette.mask&(1u<<c))for(size_t k=0;k<4;++k){
                    palette.colors[c][k]=r.real();if(!library_float(palette.colors[c][k],0,1))return false;
                }
            }
            if(used)s.presentation=&profile;
        }
        if(v4){ProbeModes& modes=out.modes[i];modes={};modes.flags=r.u32();if(modes.flags>15)return false;
            if(!s.difficulty_mask&&!modes.flags)return false;
            for(size_t mode=0;mode<4;++mode)if(modes.flags&(1u<<mode)){
                modes.masks[mode]=r.u32();if(!modes.masks[mode]||modes.masks[mode]>31)return false;
                for(size_t d=0;d<5;++d){ProbeDifficulty& v=modes.stats[mode][d];v.notes=(int32_t)r.u32();v.bombs=(int32_t)r.u32();v.obstacles=(int32_t)r.u32();v.njs=r.real();v.jump_offset=r.real();
                    if(v.notes<0||v.notes>100000||v.bombs<0||v.bombs>100000||v.obstacles<0||v.obstacles>100000||!library_float(v.njs,0,100)||!library_float(v.jump_offset,-20,20))return false;
                    if(modes.masks[mode]&(1u<<d)){if(v.notes<1||v.njs<.1)return false;}
                    else if(v.notes||v.bombs||v.obstacles||v.njs||v.jump_offset)return false;
                }
            }
            uint32_t active=s.difficulty_mask;for(size_t mode=0;mode<4;++mode)active|=modes.masks[mode];
            for(size_t d=0;d<5;++d)if(!(active&(1u<<d))&&out.presentations[i].palettes[d].mask)return false;
            if(modes.flags)s.modes=&modes;
        }
        out.approved[i]=s.id;
    }
    if(!r.ok||r.n)return false;out.count=count;return true;
}
inline const ReviewedSong* library_song(const RuntimeLibrary& lib,const Api& a,void* id){
    for(size_t i=0;i<lib.count;++i)if(ascii_equals(a,id,lib.songs[i].id))return &lib.songs[i];return NULL;
}
} // namespace
