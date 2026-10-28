// Exercise the actual native callbacks with fake SDK imports/IL2CPP objects.
#define main ui_standalone_main
#include "extras_ui_test.cpp"
#undef main
#include "../../../orbeats_extras/src/leaderboard.cpp"
#include <atomic>
#include <chrono>
#include <thread>
using namespace OrBeatsExtras;
static Klass characteristicK={"BeatmapCharacteristicSO",""}, baseK={"ViewController","HMUI"};
static Object characteristic(&characteristicK), standard(&stringK), level(&stringK);
static unsigned char stored_key[24],wire[158];static size_t position=0;
static bool file_available=true;static int stats=0,base_destroyed=0,original_processes=0;
static std::atomic<int> fetch_calls(0),cancelled_calls(0);
static std::atomic<bool> held(false);static std::thread::id ui_thread;
extern "C" int sceKernelOpen(const char* path,int,int){assert(std::this_thread::get_id()==ui_thread);if(!file_available || !strstr(path,"-score-source.bin"))return -1;position=0;return 1;}
extern "C" int64_t sceKernelRead(int fd,void* out,size_t count){assert(fd==1);size_t n=sizeof(wire)-position;if(n>count)n=count;memcpy(out,wire+position,n);position+=n;return (int64_t)n;}
extern "C" int sceKernelClose(int fd){assert(fd==1);return 0;}
extern "C" uint64_t sceKernelGetProcessTime(){return 1000000;}
namespace OrBeatsExtras {
void set_transport_logger(void (*)(const char*)){}
FetchResult fetch_scores(const char*,int,unsigned,bool(*)(void*),void*,ScoreBoard*){assert(false);return FetchResult::Network;}
}
static void pause(){std::this_thread::sleep_for(std::chrono::milliseconds(1));}
static FetchResult fake_fetch(const char* hash,int difficulty,unsigned count,bool(*cancel)(void*),void* context,ScoreBoard* out){
 assert(std::this_thread::get_id()!=ui_thread && strlen(hash)==40 && count==100);++fetch_calls;
 for(unsigned i=0;held && i<4000;++i){if(cancel(context)){++cancelled_calls;return FetchResult::Cancelled;}pause();}
 assert(!held);if(cancel(context)){++cancelled_calls;return FetchResult::Cancelled;}
 out->total=out->count=1;out->rows[0].rank=1;out->rows[0].score=difficulty*100;strcpy(out->rows[0].name,"Anonymous");return FetchResult::Ok;
}
static size_t lifecycle_offset(void* f){return !strcmp((const char*)f,"_serializedName")?0x30:offset(f);}
static void lifecycle_read(void* obj,void* f,void* out){
 assert(std::this_thread::get_id()==ui_thread);
 if(!strcmp((const char*)f,"_beatmapKey")){memcpy(out,stored_key,24);return;}
 if(obj==&characteristic && !strcmp((const char*)f,"_serializedName")){void* s=&standard;memcpy(out,&s,sizeof(s));return;}read(obj,f,out);
}
static void lifecycle_write(void* obj,void* f,void* value){assert(obj==&view && !strcmp((const char*)f,"_beatmapKey"));memcpy(stored_key,value,24);}
static int32_t text_length(void* o){return (int32_t)((Object*)o)->text.size();}
static const uint16_t* text_chars(void* o){static std::u16string s;s.clear();for(char c:((Object*)o)->text)s.push_back((char16_t)c);return (const uint16_t*)s.c_str();}
static const void* lifecycle_method(void* k,const char* n,int c){
 if(k==&viewK && !strcmp(n,"RefreshLevelStats") && !c)return (const void*)9;
 if(k==&baseK && !strcmp(n,"OnDestroy") && !c)return (const void*)10;
 return method(k,n,c);
}
static void* lifecycle_invoke(const void* m,void* self,void** args,void** exception){
 assert(std::this_thread::get_id()==ui_thread);if((uintptr_t)m==9){++stats;return NULL;}if((uintptr_t)m==10){++base_destroyed;return NULL;}return invoke(m,self,args,exception);
}
static void* parent_class(void* k){return k==&viewK?&baseK:NULL;}
static void original_input(void*,const void*){++original_processes;}
static void pump(){OrBeatsExtras::process(NULL,NULL);pause();}
static void until(std::atomic<int>& value,int target){for(unsigned i=0;i<4000 && value.load()<target;++i)pump();assert(value.load()>=target);}
static void board_score(int score){
 for(unsigned i=0;i<4000;++i){pump();if(published && ((Object*)published)->rows.size()==1 && ((Object*)((Object*)published)->rows[0])->score==score)return;}assert(false);
}
int main(){
 ui_thread=std::this_thread::get_id();reset();ui=api();write_log=diagnostic;ui.log=diagnostic;ui.parent=parent_class;
 ui.managed.field_get_offset=lifecycle_offset;ui.managed.field_get_value=lifecycle_read;ui.managed.field_set_value=lifecycle_write;
 ui.managed.string_length=text_length;ui.managed.string_chars=text_chars;ui.managed.class_get_method_from_name=lifecycle_method;ui.managed.runtime_invoke=lifecycle_invoke;
 hooks[4].StubPtr=(void*)original_input;ready=true;
 library=new BsdAdditive::RuntimeLibrary();library->count=1;
 const char* id="bsd_additive_aaaaaaaaaaaaaaaaaaaaaaaa";const char* hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
 library->songs[0].id=id;library->songs[0].sha256=hash;library->songs[0].difficulty_mask=31;
 memcpy(wire,"ORBSSRC1",8);memcpy(wire+8,id,37);memcpy(wire+45,hash,64);memset(wire+109,'c',40);wire[149]=31;uint64_t sum=source_checksum(wire,150);for(unsigned i=0;i<8;++i)wire[150+i]=(unsigned char)(sum>>(8*i));
 standard.text="Standard";level.text=id;BeatmapKey first={&characteristic,0,0,&level},last=first;last.difficulty=4;
 assert(worker.start(fake_fetch,sceKernelGetProcessTime));held=true;
 set_data(&view,&first,NULL);assert(stats==1 && !fetch_calls && !active);
 activate(&view,true,true,true,NULL);assert(active==&view && roots==1 && !scope.active && table.active);
 until(fetch_calls,1);set_data(&view,&last,NULL);held=false;board_score(900);assert(stats==2 && roots==1 && table.active);
 assert(((Object*)((Object*)published)->rows[0])->text=="[SS/PC] Anonymous");
 deactivate(&view,true,true,NULL);assert(!active && !roots);unsigned before=fetch_calls;
 activate(&view,false,true,true,NULL);board_score(900);assert((unsigned)fetch_calls==before); // cached but generation-safe
 // Unknown identity/stock/characteristic never queries or borrows the old board.
 file_available=false;set_data(&view,&last,NULL);assert(table.active && loading.text.find("reimport")!=std::string::npos);
 assert(((Object*)published)->rows.empty());file_available=true;
 standard.text="OneSaber";set_data(&view,&last,NULL);assert(loading.text.find("Standard")!=std::string::npos);
 standard.text="Standard";level.text="ost_song";set_data(&view,&last,NULL);assert(loading.text.find("identity")!=std::string::npos);level.text=id;
 for(unsigned i=0;i<30;++i)pump();assert((unsigned)fetch_calls==before);
 // Rejecting a new view must also release/cancel the previous active view.
 view.k=&otherK;activate(&view,false,true,true,NULL);assert(!active && !roots);view.k=&viewK;
 // Invalid new-key/schema also invalidates a pending request before returning.
 held=true;last.difficulty=2;set_data(&view,&last,NULL);activate(&view,false,true,true,NULL);until(fetch_calls,(int)before+1);
 sony_active=true;set_data(&view,&first,NULL);until(cancelled_calls,1);sony_active=false;held=false;
 for(unsigned i=0;i<20;++i)pump();assert(table.active);
 destroy(&view,NULL);assert(!active && !roots && base_destroyed==1);
 deactivate(&view,true,true,NULL);assert(!roots && !active);
 ready=false;worker.stop();delete library;library=NULL;
 assert(diagnostics.find("leaderboard SetData callback entered")!=std::string::npos);
 assert(diagnostics.find("leaderboard activation callback entered")!=std::string::npos);
 assert(diagnostics.find("ScoreSaber reply: result=0 rows=1 total=1")!=std::string::npos);
 assert(diagnostics.find("ScoreSaber rows published to managed table")!=std::string::npos);
 assert(original_processes>0);reset();return 0;
}
