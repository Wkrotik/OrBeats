// CUSA12878/2.04 only. Never replace a controller or invoke agreement callbacks.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace OrBeatsExtras {
static const char kVersion[]="0.0007";
// Missing file hides the warning. An explicit SHOW token restores normal startup.
static const char kOptIn[]="ORBEATS_EXTRAS_HEALTH_V1\n";
static const char kShowHealth[]="ORBEATS_EXTRAS_SHOW_HEALTH_V1\n";
inline bool enabled(const unsigned char* bytes,size_t count) {
    if(!bytes)return count==0; // Caller passes NULL only for confirmed ENOENT.
    return count==sizeof(kOptIn)-1 && !memcmp(bytes,kOptIn,count);
}
inline uint64_t fnv(const unsigned char* p,size_t n) {
    uint64_t h=UINT64_C(14695981039346656037);
    for(size_t i=0;i<n;++i)h=(h^p[i])*UINT64_C(1099511628211);
    return h;
}
struct CodeSpec { size_t rva,bytes; uint64_t hash; };
static const CodeSpec kCode[]={
    {0x1d44b20,0xbd,UINT64_C(0xab2b66371b634888)},
    {0x1d65bd0,0x2c0,UINT64_C(0xea16169114a92116)},
    {0x1d66030,0xb4,UINT64_C(0x4733a94e6c3d0e0b)}
};
struct Api {
    void* (*object_class)(void*);
    const char* (*class_name)(void*);
    const char* (*class_namespace)(void*);
    void* (*class_field)(void*,const char*);
    size_t (*field_offset)(void*);
};
inline bool field(const Api& a,void* klass,const char* name,size_t offset) {
    void* f=a.class_field(klass,name);
    return f && a.field_offset(f)==offset;
}
inline bool exact_class(const Api& a,void* object,const char* name) {
    if(!object)return false;
    void* klass=a.object_class(object);
    if(!klass)return false;
    const char* n=a.class_name(klass);const char* ns=a.class_namespace(klass);
    return n && ns && !strcmp(n,name) && !ns[0];
}
// Called BEFORE the actual health view activation, after the game selects it.
// The startup coordinator inlines its resolver; never hook that unused helper.
inline bool prepare_health(const Api& a,bool opt_in,void* selected) {
    if(!opt_in || !a.object_class || !a.class_name || !a.class_namespace ||
       !a.class_field || !a.field_offset ||
       !exact_class(a,selected,"HealthWarningViewController"))return false;
    void* view=a.object_class(selected);
    if(!field(a,view,"_duration",0x88) || !field(a,view,"_requiresInteraction",0xb8) ||
       !field(a,view,"_dismissCoroutine",0xc0))return false;
    void* coroutine=NULL;memcpy(&coroutine,(unsigned char*)selected+0xc0,sizeof(coroutine));
    float seconds=0;memcpy(&seconds,(unsigned char*)selected+0x88,sizeof(seconds));
    unsigned char interaction=*((unsigned char*)selected+0xb8);
    // Refuse unexpected live state, NaN and unreasonable serialized defaults.
    if(coroutine || interaction!=1 || !(seconds>=0 && seconds<=120))return false;
    seconds=0.25f;
    memcpy((unsigned char*)selected+0x88,&seconds,sizeof(seconds));
    *((unsigned char*)selected+0xb8)=0;
    return true;
}
} // namespace
