#include <orbis/libkernel.h>
#include <orbis/_types/errors.h>
#include <GoldHEN/Detour.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "health.h"
#include "leaderboard.h"

namespace {
using namespace OrBeatsExtras;
static Detour hook;
static bool installed=false,skip_health=false;
static Api api={};
static OrbisKernelModule handle=0;
static OrbisKernelModuleInfo module={};
static const char kConfig[]="/data/GoldHEN/plugins/orbeats-extras-health.txt";
static const char kLog[]="/data/GoldHEN/plugins/orbeats-extras.log";
static void log(const char* message) {
    int fd=sceKernelOpen(kLog,O_WRONLY|O_CREAT|O_APPEND,0644);
    if(fd<0)return;
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
static bool find_module() {
    OrbisKernelModule handles[256];size_t count=0;unsigned matches=0;
    if(sceKernelGetModuleList(handles,256,&count)<0 || count>256)return false;
    for(size_t i=0;i<count;++i){
        OrbisKernelModuleInfo info={};info.size=sizeof(info);
        if(sceKernelGetModuleInfo(handles[i],&info)<0 ||
           !memchr(info.name,0,sizeof(info.name)) || strcmp(info.name,"Il2CppUserAssemblies.prx"))continue;
        if(++matches>1 || !info.segmentCount || info.segmentCount>4)return false;
        module=info;handle=handles[i];
    }
    return matches==1;
}
static void* resolve_hook(void* self,const void* method) {
    void* selected=Detour_Stub(&hook,void*(*)(void*,const void*),self,method);
    if(prepare_health(api,skip_health,self,selected))log("health-only native auto-dismiss armed");
    return selected;
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
}
extern "C" int module_start(size_t argc,const void* args) {
    (void)argc;(void)args;
    if(installed)return 0;
    log("OrBeats Extras 0.0004: anonymous ScoreSaber and health-only auto-dismiss");
    skip_health=read_skip_health();
    if(!find_module()){log("unique game module unavailable; no hooks installed");return 0;}
    uintptr_t base=(uintptr_t)module.segmentInfo[0].address;
    install_leaderboard(base,symbol,executable,log);
    if(!skip_health){log("health warning kept by setting or invalid configuration; no health hook");return 0;}
    for(size_t i=0;i<sizeof(kCode)/sizeof(kCode[0]);++i){
        if(kCode[i].rva>UINTPTR_MAX-base){log("invalid code range");return 0;}
        const unsigned char* p=(const unsigned char*)(base+kCode[i].rva);
        if(!executable(p,kCode[i].bytes) || fnv(p,kCode[i].bytes)!=kCode[i].hash){
            log("2.04 code signature mismatch/conflicting hook; disabled");return 0;
        }
    }
    api.object_class=(void*(*)(void*))symbol("il2cpp_object_get_class");
    api.class_name=(const char*(*)(void*))symbol("il2cpp_class_get_name");
    api.class_namespace=(const char*(*)(void*))symbol("il2cpp_class_get_namespace");
    api.class_field=(void*(*)(void*,const char*))symbol("il2cpp_class_get_field_from_name");
    api.field_offset=(size_t(*)(void*))symbol("il2cpp_field_get_offset");
    if(!api.object_class || !api.class_name || !api.class_namespace || !api.class_field || !api.field_offset){
        log("required IL2CPP exports unavailable; disabled");return 0;
    }
    // The verified first15 bytes are whole instructions with no RIP/relative operands.
    Detour_Construct(&hook,DetourMode_x64);
    if(!Detour_DetourFunction(&hook,base+kCode[0].rva,(void*)resolve_hook)){
        log("detour install failed");return 0;
    }
    installed=true;log("health-only resolver hook installed; no agreement or tracking hooks");
    return 0;
}
extern "C" int module_stop(size_t argc,const void* args) {
    (void)argc;(void)args;
    // No live unload: a game thread may still be in our callback/trampoline.
    if(installed || leaderboard_has_hooks()){log("live unload refused; close title before disabling Extras");return -1;}
    return 0;
}
