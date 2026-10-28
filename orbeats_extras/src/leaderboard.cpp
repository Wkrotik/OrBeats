#include "leaderboard.h"
#include "leaderboard_profile.h"
#include "source_identity.h"
#include "worker.h"
#include <stdio.h>
#include "leaderboard_ui.h"
#include "../../orbeats/include/additive_runtime_library.h"
#include <orbis/libkernel.h>
#include <GoldHEN/Detour.h>
#include <fcntl.h>
#include <stdlib.h>
#include <new>
namespace OrBeatsExtras {
namespace {
struct BeatmapKey { void* characteristic; int difficulty; uint32_t padding; void* level_id; };
static_assert(sizeof(BeatmapKey)==24,"owned BeatmapKey ABI");
static UiApi ui={};static ScoreWorker worker;static Detour hooks[5];
static std::atomic<bool> ready(false),ever_hooked(false);static void(*write_log)(const char*)=NULL;
static BsdAdditive::RuntimeLibrary* library=NULL;
static void* active=NULL;static uint32_t active_root=0;static uint64_t selection=0;
static bool tick_logged=false;
static ScoreReply reply; // Main-thread only; never points into a worker buffer.
static void log(const char* value){if(write_log)write_log(value);}
static bool read_file(const char* path,unsigned char* bytes,size_t capacity,size_t& size) {
    size=0;int fd=sceKernelOpen(path,O_RDONLY,0);if(fd<0)return false;
    int64_t n=0;while(size<capacity && (n=sceKernelRead(fd,bytes+size,capacity-size))>0)size+=(size_t)n;
    int closed=sceKernelClose(fd);return n==0 && closed==0;
}
static bool ascii(void* text,char* out,size_t size) {
    if(!text)return false;int32_t count=ui.managed.string_length(text);
    if(count<=0 || (size_t)count>=size)return false;const uint16_t* chars=ui.managed.string_chars(text);if(!chars)return false;
    for(int i=0;i<count;++i){if(chars[i]<32 || chars[i]>126)return false;out[i]=(char)chars[i];}out[count]=0;return true;
}
static void cancel_view() {
    selection=worker.select(NULL);active=NULL;
    if(active_root){ui.managed.gchandle_free(active_root);active_root=0;}
}
static const char* identity(void* self,ScoreKey& key) {
    ViewParts parts;if(!view_parts(ui,self,parts))return "OrBeats Extras: incompatible leaderboard view";
    BeatmapKey selected={};ui.managed.field_get_value(self,parts.key_field,&selected);
    if(selected.difficulty<0 || selected.difficulty>4)return "Select a difficulty for ScoreSaber";
    if(!selected.characteristic || !BsdAdditive::named(ui.managed,ui.managed.object_get_class(selected.characteristic),"BeatmapCharacteristicSO"))return "ScoreSaber: unsupported characteristic";
    void* name_field=BsdAdditive::field(ui.managed,ui.managed.object_get_class(selected.characteristic),"_serializedName",0x30);
    if(!name_field || !BsdAdditive::ascii_equals(ui.managed,BsdAdditive::read_ref(ui.managed,selected.characteristic,name_field),"Standard"))return "ScoreSaber: Standard charts only";
    char id[81];if(!ascii(selected.level_id,id,sizeof(id)) || !own_level(id))return "ScoreSaber: original custom-map identity required (not PSN)";
    if(!library)return "ScoreSaber: verified OrBeats library unavailable";
    const BsdAdditive::ReviewedSong* song=NULL;
    for(size_t i=0;i<library->count;++i)if(!strcmp(library->songs[i].id,id)){song=&library->songs[i];break;}
    if(!song || !(song->difficulty_mask&(1u<<selected.difficulty)))return "ScoreSaber: chart not in the verified library";
    char path[256];snprintf(path,sizeof(path),"/data/GoldHEN/AFR/CUSA12878/additive/%s-score-source.bin",id);
    unsigned char raw[kSourceIdentityBytes+1];size_t size=0;
    if(!read_file(path,raw,sizeof(raw),size) || !source_identity(raw,size,id,song->sha256,song->difficulty_mask,key.hash))return "ScoreSaber: reimport this map with the updated companion to add its original identity";
    key.difficulty=1+2*selected.difficulty;return NULL;
}
static void begin(void* self) {
    if(active!=self)return;
    selection=worker.select(NULL);ScoreBoard empty={};
    if(!table_visible(ui,self,false) || !show_scores(ui,self,empty)){
        status_text(ui,self,"OrBeats Extras: leaderboard schema mismatch; scores hidden");log("leaderboard clear/managed schema failed");return;
    }
    // Empty managed rows are already published. Keep the panel active for
    // status text even if LoadingControl lives below the table GameObject.
    if(!table_visible(ui,self,true)){log("leaderboard status panel activation failed");return;}
    ScoreKey key={};const char* problem=identity(self,key);
    if(problem){status_text(ui,self,problem);return;}
    status_text(ui,self,"ScoreSaber: loading top 10 scores (read-only)");selection=worker.select(&key);
}
static void set_data(void* self,const BeatmapKey* key,const void*) {
    log("leaderboard SetData callback entered");
    if(!ready)return;
    if(active==self)selection=worker.select(NULL); // invalidate even a rejected new key
    if(!key)return;ViewParts parts;if(!view_parts(ui,self,parts))return;
    // Managed field API preserves barriers for references inside the value type.
    ui.managed.field_set_value(self,parts.key_field,(void*)key);
    invoke_ui(ui,self,"RefreshLevelStats",0,NULL);
    if(active==self)begin(self);
}
static void activate(void* self,bool first,bool added,bool enabling,const void*) {
    (void)first;(void)added;(void)enabling;log("leaderboard activation callback entered");
    if(!ready)return;cancel_view();
    ViewParts parts;if(!view_parts(ui,self,parts)){log("incompatible leaderboard activation; no PSN fallback");return;}
    active_root=ui.managed.gchandle_new(self,true);if(!active_root)return;active=self;
    if(!hide_scopes(ui,self)){status_text(ui,self,"OrBeats Extras: cannot hide PSN-only scopes");cancel_view();return;}
    begin(self);
}
static void deactivate(void* self,bool removed,bool disabling,const void*) {
    (void)removed;(void)disabling;
    log("leaderboard deactivation callback entered");
    if(active==self){ViewParts p;if(view_parts(ui,self,p))invoke_ui(ui,p.loading,"Hide",0,NULL);cancel_view();}
}
static void destroy(void* self,const void*) {
    if(active==self)cancel_view();
    if(!self || !ui.parent)return;
    // Preserve the base HMUI binder cleanup, but not Sony subscription teardown:
    // this replacement never registers Sony callbacks or starts their requests.
    void* klass=ui.managed.object_get_class(self);
    for(unsigned i=0;klass && i<12;++i,klass=ui.parent(klass)) {
        const char* name=ui.managed.class_get_name(klass);const char* ns=ui.managed.class_get_namespace(klass);
        if(name && ns && !strcmp(name,"ViewController") && !strcmp(ns,"HMUI")){
            const void* method=ui.managed.class_get_method_from_name(klass,"OnDestroy",0);bool threw=false;
            if(method)BsdAdditive::invoke(ui.managed,method,self,NULL,&threw);if(threw)log("base view cleanup threw");break;
        }
    }
}
static const char* failure(FetchResult value) {
    switch(value){
    case FetchResult::Missing:return "ScoreSaber: no board for this chart";
    case FetchResult::RateLimited:return "ScoreSaber: rate limited; retry by reselecting after one minute";
    case FetchResult::Deadline:return "ScoreSaber: request timed out";
    case FetchResult::Network:return "ScoreSaber: verified HTTPS unavailable; check internet, clock and firmware";
    default:return "ScoreSaber: response unavailable or invalid (no partial scores shown)";
    }
}
static void process(void* self,const void* method) {
    if(!tick_logged){log("leaderboard UI input pump callback entered");tick_logged=true;}
    // First15 bytes are whole instructions without RIP/relative operands.
    Detour_Stub(&hooks[4],void(*)(void*,const void*),self,method);
    if(!ready || !active || !worker.take(selection,reply))return;
    char message[160];snprintf(message,sizeof(message),"ScoreSaber reply: result=%u rows=%u total=%u",(unsigned)reply.result,reply.board.count,reply.board.total);log(message);
    if(reply.result==FetchResult::Ok) {
        if(!reply.board.count){status_text(ui,active,"ScoreSaber: no scores for this chart");return;}
        if(!show_scores(ui,active,reply.board) || !table_visible(ui,active,true))status_text(ui,active,"OrBeats Extras: managed table update failed");
        else log("ScoreSaber rows published to managed table");
    }else if(reply.result!=FetchResult::Cancelled)status_text(ui,active,failure(reply.result));
}
}
bool leaderboard_has_hooks(){return ever_hooked;}
bool install_leaderboard(uintptr_t base,void*(*resolve)(const char*),bool(*executable)(const void*,size_t),void(*logger)(const char*)) {
    write_log=logger;ui.log=logger;if(ever_hooked || !resolve || !executable)return false;
    for(size_t i=0;i<sizeof(kLeaderboardCode)/sizeof(kLeaderboardCode[0]);++i){
        const CodeSpec& code=kLeaderboardCode[i];if(code.rva>UINTPTR_MAX-base)return false;
        const unsigned char* p=(const unsigned char*)(base+code.rva);
        if(!executable(p,code.bytes) || fnv(p,code.bytes)!=code.hash){log("leaderboard profile mismatch/conflicting hook; unchanged");return false;}
    }
    const char* missing=NULL;if(!BsdAdditive::resolve_api(ui.managed,resolve,&missing)){log("leaderboard IL2CPP API unavailable");return false;}
    ui.declaring_type=(void*(*)(void*))resolve("il2cpp_class_get_declaring_type");ui.parent=(void*(*)(void*))resolve("il2cpp_class_get_parent");
    if(!ui.declaring_type || !ui.parent)return false;
    // Only the current runtime manifest, never compiled seed IDs or inferred hashes.
    unsigned char* bytes=(unsigned char*)malloc(BsdAdditive::kLibraryMaxBytes+1);size_t count=0;
    if(bytes && read_file(BsdAdditive::kLibraryPath,bytes,BsdAdditive::kLibraryMaxBytes+1,count)){
        library=new(std::nothrow) BsdAdditive::RuntimeLibrary();if(library && !BsdAdditive::decode_library(*library,bytes,count)){delete library;library=NULL;}
    }
    free(bytes);
    set_transport_logger(logger);
    if(!worker.start(fetch_scores,sceKernelGetProcessTime)){delete library;library=NULL;log("score worker start failed; no leaderboard hooks");return false;}
    void* callbacks[]={(void*)set_data,(void*)activate,(void*)deactivate,(void*)destroy,(void*)process};
    for(unsigned i=0;i<5;++i){
        Detour_Construct(&hooks[i],DetourMode_x64);
        if(!Detour_DetourFunction(&hooks[i],base+kLeaderboardCode[i].rva,callbacks[i])){
            for(unsigned j=0;j<i;++j)Detour_RestoreFunction(&hooks[j]);
            worker.stop();delete library;library=NULL;log("leaderboard detour failed; restored previous code");return false;
        }
        ever_hooked=true;
    }
    ready=true;log("anonymous ScoreSaber replacement installed; Standard custom charts; no Sony subscriptions or uploads");return true;
}
} // namespace
