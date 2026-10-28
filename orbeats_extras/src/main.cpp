#include <orbis/libkernel.h>
#include <orbis/_types/errors.h>
#include <GoldHEN/Detour.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <atomic>
#include "health.h"
#include "health_activation.h"
#include "leaderboard.h"

namespace {
using namespace OrBeatsExtras;
static Detour hook;
static void* health_original=NULL;
static bool installed=false,skip_health=false;
static std::atomic<bool> stopping(false);
static OrbisPthread startup_thread=NULL;
static bool startup_started=false;
static Api api={};
static OrbisKernelModule handle=0;
static OrbisKernelModuleInfo module={};
static const char kConfig[]="/data/GoldHEN/plugins/orbeats-extras-health.txt";
static const char kLog[]="/data/GoldHEN/plugins/orbeats-extras.log";
static void log(const char* message) {
    int fd=sceKernelOpen(kLog,O_WRONLY|O_CREAT|O_APPEND,0644);
    if(fd<0)return;
    // GoldHEN can create mode000 despite the open mode. Correct only our own
    // descriptor, before any write; never truncate or delete diagnostic history.
    if(sceKernelFchmod(fd,0644)<0){
        const char warning[]="own log permission repair failed\n";
        sceKernelWrite(fd,warning,sizeof(warning)-1);
    }
    sceKernelWrite(fd,message,strlen(message));sceKernelWrite(fd,"\n",1);sceKernelClose(fd);
}
static bool executable(const void* p,size_t n) {
    uintptr_t value=(uintptr_t)p;
    for(uint32_t i=0;i<module.segmentCount;++i){
        const OrbisKernelModuleSegmentInfo& s=module.segmentInfo[i];
        uintptr_t base=(uintptr_t)s.address;
        if((s.prot&5)==5 && value>=base && value-base<=s.size && n<=s.size-(value-base))return true;
    }
    return false;
}
static void* symbol(const char* name) {
    void* p=NULL;
    return sceKernelDlsym(handle,name,&p)==0 && p && executable(p,1)?p:NULL;
}
enum class ModuleState { Missing, Found, Refused };
static ModuleState find_module() {
    OrbisKernelModule handles[256];size_t count=0;unsigned matches=0;
    int result=sceKernelGetModuleList(handles,256,&count);
    if(result<0 || count>256){
        char text[128];snprintf(text,sizeof(text),"module enumeration refused: result=0x%x count=%llu",(unsigned)result,(unsigned long long)count);log(text);
        return ModuleState::Refused;
    }
    OrbisKernelModuleInfo selected={};OrbisKernelModule selected_handle=0;
    for(size_t i=0;i<count;++i){
        OrbisKernelModuleInfo info={};info.size=sizeof(info);
        result=sceKernelGetModuleInfo(handles[i],&info);
        if(result<0){
            char text[128];snprintf(text,sizeof(text),"module info refused: handle=%u result=0x%x",handles[i],(unsigned)result);log(text);
            return ModuleState::Refused;
        }
        if(!memchr(info.name,0,sizeof(info.name)))return ModuleState::Refused;
        if(strcmp(info.name,"Il2CppUserAssemblies.prx"))continue;
        if(++matches>1 || !info.segmentCount || info.segmentCount>4)return ModuleState::Refused;
        selected=info;selected_handle=handles[i];
    }
    if(!matches)return ModuleState::Missing;
    module=selected;handle=selected_handle;
    if(!executable(module.segmentInfo[0].address,1))return ModuleState::Refused;
    return ModuleState::Found;
}
static void health_activate(void* self,bool first,bool added,bool enabling,const void* method) {
    log("health activation callback entered");
    bool armed=prepare_health(api,skip_health,self);
    log(armed?"health-only native auto-dismiss armed":"health state/schema refused; preserving warning");
    ((void(*)(void*,bool,bool,bool,const void*))health_original)(self,first,added,enabling,method);
}
static bool read_skip_health() {
    unsigned char data[sizeof(kShowHealth)+1];size_t total=0;
    int fd=sceKernelOpen(kConfig,O_RDONLY,0);
    if(fd==(int)ORBIS_KERNEL_ERROR_ENOENT)return enabled(NULL,0);
    if(fd<0){log("health setting unreadable; preserving ordinary warning");return false;}
    int64_t n=0;
    while(total<sizeof(data) && (n=sceKernelRead(fd,data+total,sizeof(data)-total))>0)total+=(size_t)n;
    int closed=sceKernelClose(fd);
    return n==0 && closed==0 && enabled(data,total);
}
static void install_hooks() {
    uintptr_t base=(uintptr_t)module.segmentInfo[0].address;
    char message[160];
    snprintf(message,sizeof(message),"game module ready: handle=%d base=0x%llx segments=%u",(int)handle,(unsigned long long)base,module.segmentCount);
    log(message);
    if(stopping.load())return;
    bool leaderboard=install_leaderboard(base,symbol,executable,log);
    log(leaderboard?"leaderboard initialization completed":"leaderboard initialization refused; see preceding diagnostics");
    if(stopping.load())return;
    if(!skip_health){log("health warning kept by setting or invalid configuration; no health hook");return;}
    for(size_t i=0;i<sizeof(kCode)/sizeof(kCode[0]);++i){
        if(kCode[i].rva>UINTPTR_MAX-base){log("invalid code range");return;}
        const unsigned char* p=(const unsigned char*)(base+kCode[i].rva);
        if(!executable(p,kCode[i].bytes) || fnv(p,kCode[i].bytes)!=kCode[i].hash){
            log("2.04 code signature mismatch/conflicting hook; health disabled");return;
        }
    }
    api.object_class=(void*(*)(void*))symbol("il2cpp_object_get_class");
    api.class_name=(const char*(*)(void*))symbol("il2cpp_class_get_name");
    api.class_namespace=(const char*(*)(void*))symbol("il2cpp_class_get_namespace");
    api.class_field=(void*(*)(void*,const char*))symbol("il2cpp_class_get_field_from_name");
    api.field_offset=(size_t(*)(void*))symbol("il2cpp_field_get_offset");
    if(!api.object_class || !api.class_name || !api.class_namespace || !api.class_field || !api.field_offset){
        log("required IL2CPP exports unavailable; health disabled");return;
    }
    unsigned char relocated[kHealthTrampolineBytes];uintptr_t flag=0;
    const uintptr_t target=base+kCode[1].rva;
    if(!health_activation_trampoline((const unsigned char*)target,target,relocated,sizeof(relocated),flag)){
        log("health activation prefix relocation refused");return;
    }
    bool readable=false;
    for(uint32_t i=0;i<module.segmentCount;++i){
        const auto& part=module.segmentInfo[i];uintptr_t begin=(uintptr_t)part.address;
        if((part.prot&1) && flag>=begin && flag-begin<part.size)readable=true;
    }
    if(!readable){log("health activation flag outside readable game image");return;}
    if(sceKernelMmap(NULL,sizeof(relocated),7,0x1002,-1,0,&health_original)<0 || !health_original){
        health_original=NULL;log("health activation trampoline allocation failed");return;
    }
    memcpy(health_original,relocated,sizeof(relocated));
    // SDK's copied stub cannot relocate the RIP-relative CMP. Keep that stub
    // intact for restore semantics, but invoke our explicitly relocated copy.
    Detour_Construct(&hook,DetourMode_x64);
    if(!Detour_DetourFunction(&hook,target,(void*)health_activate)){
        sceKernelMunmap(health_original,sizeof(relocated));health_original=NULL;
        log("health activation detour install failed");return;
    }
    installed=true;log("health-only activation hook installed; no agreement or tracking hooks");
}
static void* initialize(void*) {
    // GoldHEN starts plugins before the game's IL2CPP image is necessarily
    // loaded. Wait off the loader thread, for absence only; never retry a
    // duplicate/invalid module or failed code guard. No managed/UI calls here.
    log("startup worker entered; waiting up to 10 seconds for unique game module");
    skip_health=read_skip_health();
    log(skip_health?"health policy: auto-dismiss":"health policy: show warning");
    for(unsigned attempt=0;attempt<=500;++attempt){
        if(stopping.load()){log("startup cancelled before module readiness");return NULL;}
        ModuleState state=find_module();
        if(state==ModuleState::Found){install_hooks();log("startup worker finished");return NULL;}
        if(state==ModuleState::Refused){log("module enumeration/identity invalid or ambiguous; no hooks installed");return NULL;}
        if(attempt==500)break;
        if(sceKernelUsleep(20000)<0){log("startup wait failed; no hooks installed");return NULL;}
    }
    log("game module readiness deadline expired; no hooks installed");
    return NULL;
}
}
extern "C" int module_start(size_t argc,const void* args) {
    (void)argc;(void)args;
    if(startup_started || installed || leaderboard_has_hooks())return 0;
    log("OrBeats Extras 0.0006: health activation and callback diagnostics");
    stopping.store(false);
    if(scePthreadCreate(&startup_thread,NULL,initialize,NULL,"OrBeatsInit")!=0){
        log("startup worker creation failed; no hooks installed");return 0;
    }
    startup_started=true;
    return 0;
}
extern "C" int module_stop(size_t argc,const void* args) {
    (void)argc;(void)args;
    // Cancel and join startup BEFORE considering unload. If any hook was
    // installed, still refuse live unload: callbacks may be executing.
    stopping.store(true);
    if(startup_started){
        if(scePthreadJoin(startup_thread,NULL)!=0){log("startup join failed; unload refused");return -1;}
        startup_started=false;startup_thread=NULL;
    }
    if(installed || leaderboard_has_hooks()){log("live unload refused; close title before disabling Extras");return -1;}
    return 0;
}
