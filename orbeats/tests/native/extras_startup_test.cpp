// Actual module entry/startup/logger paths with a deterministic SDK task queue.
// No fake-managed UI here: lifecycle/UI and network workers have separate tests.
#include <assert.h>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <fcntl.h>
#include <orbis/libkernel.h>
#include <orbis/_types/errors.h>
#include "health.h"
static std::string scenario,logs;
static unsigned lists=0,sleeps=0,creates=0,joins=0,installs=0,chmods=0,closes=0;
static void*(*pending)(void*)=nullptr;
static bool hooked=false,promo_hooked_fake=false,show_warning=true,join_error=false;
static unsigned promo_installs=0;
static unsigned char image[16];
static size_t read_offset=0;
extern "C" int sceKernelOpen(const char* path,int flags,int){
    if(flags==O_RDONLY){assert(std::string(path).find("health.txt")!=std::string::npos);read_offset=0;return show_warning?2:ORBIS_KERNEL_ERROR_ENOENT;}
    assert(std::string(path).find("orbeats-extras.log")!=std::string::npos);
    assert((flags&O_APPEND) && !(flags&O_TRUNC));return scenario=="log-open"?-1:1;
}
extern "C" int64_t sceKernelRead(int fd,void* bytes,size_t cap){
    assert(fd==2);size_t left=sizeof(OrBeatsExtras::kShowHealth)-1-read_offset;size_t n=cap<left?cap:left;
    memcpy(bytes,OrBeatsExtras::kShowHealth+read_offset,n);read_offset+=n;return n;
}
extern "C" int64_t sceKernelWrite(int fd,const void* p,size_t n){assert(fd==1);logs.append((const char*)p,n);return n;}
extern "C" int sceKernelClose(int fd){assert(fd==1 || fd==2);++closes;return 0;}
extern "C" int sceKernelMmap(void*,size_t,int,int,int,int64_t,void**){assert(false);return -1;}
extern "C" int sceKernelMunmap(void*,size_t){assert(false);return -1;}
extern "C" int sceKernelFchmod(int fd,int mode){assert(fd==1 && mode==0644);++chmods;return scenario=="chmod"?-1:0;}
extern "C" int sceKernelGetModuleList(OrbisKernelModule* out,size_t cap,size_t* count){
    assert(cap==256);++lists;if(scenario=="list-error")return -1;
    if(scenario=="count-bound"){*count=257;return 0;}
    if(scenario=="timeout" || scenario=="sleep-error" || (scenario=="late" && lists<3)){*count=0;return 0;}
    *count=scenario=="duplicate"?2:1;out[0]=5;out[1]=6;return 0;
}
extern "C" int sceKernelGetModuleInfo(OrbisKernelModule,OrbisKernelModuleInfo* info){
    assert(info->size==sizeof(*info));if(scenario=="info-error")return -1;
    memset(info,0,sizeof(*info));strcpy(info->name,"Il2CppUserAssemblies.prx");
    if(scenario=="name-invalid")memset(info->name,'x',sizeof(info->name));
    info->segmentCount=scenario=="segments-zero"?0:scenario=="segments-bound"?5:1;
    info->segmentInfo[0]={image,sizeof(image),scenario=="rx"?1:5};return 0;
}
extern "C" int sceKernelDlsym(OrbisKernelModule,const char*,void** out){*out=nullptr;return -1;}
extern "C" int sceKernelUsleep(uint32_t us){assert(us==20000);++sleeps;return scenario=="sleep-error"?-1:0;}
extern "C" int scePthreadCreate(OrbisPthread* id,const void*,void*(*fn)(void*),void* arg,const char* name){
    ++creates;assert(!arg && !strcmp(name,"OrBeatsInit"));if(scenario=="create-error")return -1;
    assert(!pending);pending=fn;*id=(OrbisPthread)1;return 0;
}
static void run_pending(){assert(pending);auto fn=pending;pending=nullptr;fn(nullptr);}
extern "C" int scePthreadJoin(OrbisPthread id,void**){assert(id==(OrbisPthread)1);++joins;if(join_error)return -1;if(pending)run_pending();return 0;}
namespace OrBeatsExtras {
bool install_leaderboard(uintptr_t base,void*(*)(const char*),bool(*executable)(const void*,size_t),void(*logger)(const char*)){
    assert(base==(uintptr_t)image && executable(image,sizeof(image)));++installs;logger("fake leaderboard success");hooked=scenario!="promo-only";return hooked;
}
bool leaderboard_has_hooks(){return hooked;}
bool promo_has_hooks(){return promo_hooked_fake;}
bool install_promo(uintptr_t base,void*(*)(const char*),bool(*executable)(const void*,size_t),void(*logger)(const char*)){
    assert(base==(uintptr_t)image && executable(image,sizeof(image)));++promo_installs;
    promo_hooked_fake=scenario!="promo-refused";logger("fake promo initialized");return promo_hooked_fake;
}
}
#include "../../../orbeats_extras/src/main.cpp"
static unsigned char health_view[0xc8];static bool wrong_health_class=false;
static void* health_class(void* p){return p;}
static const char* health_name(void*){return wrong_health_class?"EulaViewController":"HealthWarningViewController";}
static const char* health_namespace(void*){return "";}
static void* health_field(void*,const char* name){return (void*)name;}
static size_t health_offset(void* name){
 if(!strcmp((char*)name,"_duration"))return 0x88;
 if(!strcmp((char*)name,"_requiresInteraction"))return 0xb8;
 if(!strcmp((char*)name,"_dismissCoroutine"))return 0xc0;return 0;
}
static unsigned original_activations=0;static bool expected_armed=false;
static void original_health(void* self,bool first,bool added,bool enabling,const void* method){
 assert(self==health_view && first && added && !enabling && method==(void*)0x123);
 ++original_activations;float duration;memcpy(&duration,health_view+0x88,4);
 assert(duration==(expected_armed?0.25f:5.0f));assert(health_view[0xb8]==(expected_armed?0:1));
}
int main(int argc,char** argv){
    assert(argc==2);scenario=argv[1];
    if(scenario.find("health-callback")==0){
        using namespace OrBeatsExtras;float duration=5.0f;memcpy(health_view+0x88,&duration,4);health_view[0xb8]=1;
        api={health_class,health_name,health_namespace,health_field,health_offset};health_original=(void*)original_health;
        skip_health=scenario!="health-callback-disabled";wrong_health_class=scenario=="health-callback-class";
        if(scenario=="health-callback-coroutine"){void* coroutine=(void*)0x456;memcpy(health_view+0xc0,&coroutine,8);}
        expected_armed=scenario=="health-callback";health_activate(health_view,true,true,false,(void*)0x123);
        assert(original_activations==1 && !creates && !lists);
        assert(logs.find(expected_armed?"auto-dismiss armed":"preserving warning")!=std::string::npos);return 0;
    }
    if(scenario=="health-guard")show_warning=false;
    assert(module_start(0,nullptr)==0);assert(creates==1);
    if(scenario=="create-error"){
        assert(!pending && !startup_started && !installs && !lists);assert(logs.find("creation failed")!=std::string::npos);return 0;
    }
    assert(startup_started && pending && !lists && !installs); // loader never blocked
    assert(module_start(0,nullptr)==0 && creates==1); // no duplicate startup worker
    if(scenario=="cancel"){
        assert(module_stop(0,nullptr)==0);assert(!pending && !lists && !installs && joins==1);assert(logs.find("cancelled")!=std::string::npos);return 0;
    }
    if(scenario=="join-error"){
        join_error=true;assert(module_stop(0,nullptr)==-1 && startup_started);
        join_error=false;assert(module_stop(0,nullptr)==0 && !startup_started && !installs);return 0;
    }
    run_pending();
    if(scenario=="timeout")assert(lists==501 && sleeps==500 && !installs && logs.find("deadline expired")!=std::string::npos);
    else if(scenario=="sleep-error")assert(lists==1 && sleeps==1 && !installs && logs.find("wait failed")!=std::string::npos);
    else if(scenario=="late")assert(lists==3 && sleeps==2 && installs==1 && logs.find("game module ready")!=std::string::npos);
    else if(scenario=="duplicate" || scenario=="list-error" || scenario=="count-bound" || scenario=="info-error" || scenario=="name-invalid" || scenario=="segments-zero" || scenario=="segments-bound" || scenario=="rx"){
        assert(lists==1 && !sleeps && !installs && logs.find("invalid or ambiguous")!=std::string::npos);
    }else assert(lists==1 && !sleeps && installs==1);
    if(scenario=="health-guard")assert(!installed && logs.find("code signature mismatch")!=std::string::npos);
    if(scenario=="log-open")assert(logs.empty() && !chmods);
    else if(scenario=="chmod")assert(logs.find("permission repair failed")!=std::string::npos && logs.find("0.0015")!=std::string::npos && chmods && closes);
    else assert(chmods && logs.find("0.0015")!=std::string::npos);
    assert(promo_installs==installs);
    if(scenario=="promo-only")assert(promo_hooked_fake && !hooked);
    if(scenario=="promo-refused")assert(!promo_hooked_fake && hooked);
    assert(module_stop(0,nullptr)==((hooked || promo_hooked_fake)?-1:0));assert(joins==1 && !startup_started);
    return 0;
}
