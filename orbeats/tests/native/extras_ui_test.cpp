#include "leaderboard_ui.h"
#include <assert.h>
#include <memory>
#include <string>
#include <vector>
using namespace OrBeatsExtras;
struct Klass { const char* name;const char* ns; };
static Klass viewK={"PlatformLeaderboardViewController",""}, tableK={"LeaderboardTableView",""}, loadingK={"LoadingControl",""}, scopeK={"IconSegmentedControl",""}, listK={"List`1","System.Collections.Generic"}, rowK={"ScoreData",""}, arrayK={"ScoreData[]",""}, stringK={"String","System"}, otherK={"Other",""};
struct Object {
 Klass* k;std::vector<void*> rows;std::string text;int score=0,rank=0;bool combo=false,active=true;
 explicit Object(Klass* value):k(value){}
};
static Object view(&viewK), table(&tableK), loading(&loadingK), scope(&scopeK), initial(&listK), array(&arrayK);
static std::vector<std::unique_ptr<Object>> allocated;
static void* published=NULL;static int special=0,roots=0,root_calls=0,alloc_calls=0,add_calls=0;
static int fail_root=0,fail_alloc=0,throw_add=0;static bool bad_offset=false,sony_active=false,missing_method=false;
static void* klass(void* o){return ((Object*)o)->k;}
static const char* name(void* k){return ((Klass*)k)->name;}
static const char* ns(void* k){return ((Klass*)k)->ns;}
static void* field(void*,const char* s){return (void*)s;}
static size_t offset(void* f){
 if(bad_offset)return 0;
 const char* n=(const char*)f;
 if(!strcmp(n,"_leaderboardTableView"))return 0x78;
 if(!strcmp(n,"_scopeSegmentedControl"))return 0x80;
 if(!strcmp(n,"_loadingControl"))return 0x88;
 if(!strcmp(n,"_scores"))return 0xe0;
 if(!strcmp(n,"_beatmapKey"))return 0xf0;
 if(!strcmp(n,"_getScoresAsyncRequest"))return 0xd0;
 if(!strcmp(n,"_getOnlineServicesAvailabilityCancelationTokenSource"))return 0xd8;
 if(!strcmp(n,"_items"))return 0x10;
 return 0;
}
static void read(void* obj,void* f,void* out){
 const char* n=(const char*)f;void* result=NULL;
 if(obj==&view){
  if(!strcmp(n,"_leaderboardTableView"))result=&table;
  if(!strcmp(n,"_scopeSegmentedControl"))result=&scope;
  if(!strcmp(n,"_loadingControl"))result=&loading;
  if(!strcmp(n,"_scores"))result=&initial;
  if(!strcmp(n,"_getScoresAsyncRequest") && sony_active)result=&view;
 }else if(!strcmp(n,"_items"))result=&array;
 memcpy(out,&result,sizeof(result));
}
static void* object_new(void* k){
 if(++alloc_calls==fail_alloc)return NULL;
 allocated.emplace_back(new Object((Klass*)k));return allocated.back().get();
}
static void* text_new(const char* text){void* o=object_new(&stringK);if(o)((Object*)o)->text=text;return o;}
static uint32_t keep(void*,bool pin){assert(pin);if(++root_calls==fail_root)return 0;++roots;return root_calls;}
static void release(uint32_t h){assert(h && roots>0);--roots;}
static int rank(void* k){return k==&arrayK?1:0;}
static void* elem(void*){return &rowK;}
static void* declaring(void* k){return k==&rowK?&tableK:NULL;}
enum Method {Ctor=1,Add,Row,Set,Hide,Show,GameObject,Active};
static const void* method(void* k,const char* n,int c){
 if(missing_method)return NULL;
 uintptr_t m=0;
 if(k==&listK && !strcmp(n,".ctor") && c==0)m=Ctor;
 if(k==&listK && !strcmp(n,"Add") && c==1)m=Add;
 if(k==&rowK && !strcmp(n,".ctor") && c==4)m=Row;
 if(k==&tableK && !strcmp(n,"SetScores") && c==2)m=Set;
 if(k==&loadingK && !strcmp(n,"Hide") && c==0)m=Hide;
 if(k==&loadingK && !strcmp(n,"ShowText") && c==2)m=Show;
 if(!strcmp(n,"get_gameObject") && c==0)m=GameObject;
 if(!strcmp(n,"SetActive") && c==1)m=Active;
 return (const void*)m;
}
static void* invoke(const void* method,void* self,void** args,void** exception){
 Object* o=(Object*)self;
 switch((uintptr_t)method){
 case Ctor:break;
 case Add:if(++add_calls==throw_add){*exception=&view;break;}o->rows.push_back(args[0]);break;
 case Row:o->score=*(int*)args[0];o->text=((Object*)args[1])->text;o->rank=*(int*)args[2];o->combo=*(bool*)args[3];break;
 case Set:assert(self==&table);published=args[0];special=*(int*)args[1];break;
 case Hide:o->text.clear();break;
 case Show:assert(!*(bool*)args[1]);o->text=((Object*)args[0])->text;break;
 case GameObject:return self;
 case Active:o->active=*(bool*)args[0];break;
 default:assert(false);
 }return NULL;
}
static UiApi api(){UiApi u={};auto& a=u.managed;a.object_get_class=klass;a.class_get_name=name;a.class_get_namespace=ns;a.class_get_field_from_name=field;a.field_get_offset=offset;a.field_get_value=read;a.class_get_method_from_name=method;a.object_new=object_new;a.runtime_invoke=invoke;a.class_get_rank=rank;a.class_get_element_class=elem;a.gchandle_new=keep;a.gchandle_free=release;a.string_new=text_new;u.declaring_type=declaring;return u;}
static void reset(){assert(!roots);allocated.clear();published=NULL;alloc_calls=root_calls=add_calls=0;fail_root=fail_alloc=throw_add=0;missing_method=bad_offset=sony_active=false;view.k=&viewK;loading.text.clear();scope.active=table.active=true;}
int main(){
 UiApi u=api();ScoreBoard board={};board.total=board.count=100;
 for(unsigned i=0;i<100;++i){board.rows[i].score=10000-(int)i;board.rows[i].rank=(int)i+1;board.rows[i].full_combo=true;strcpy(board.rows[i].name,"Player");}
 reset();assert(hide_scopes(u,&view));assert(!scope.active);
 assert(table_visible(u,&view,false) && !table.active);
 assert(status_text(u,&view,"ScoreSaber: loading PC scores"));assert(loading.text=="ScoreSaber: loading PC scores");
 assert(show_scores(u,&view,board));assert(!roots && special==-1 && loading.text.empty());
 auto* list=(Object*)published;assert(list->k==&listK && list->rows.size()==100);
 for(unsigned i=0;i<100;++i){auto* row=(Object*)list->rows[i];assert(row->k==&rowK && row->rank==(int)i+1 && row->score==10000-(int)i && row->combo && row->text=="[SS/PC] Player");}
 assert(table_visible(u,&view,true) && table.active);
 ScoreBoard empty={};assert(show_scores(u,&view,empty));assert(((Object*)published)->rows.empty() && !roots);
 for(int n=1;n<=201;++n){reset();fail_root=n;assert(!show_scores(u,&view,board));assert(!published && !roots);}
 for(int n=1;n<=201;++n){reset();fail_alloc=n;assert(!show_scores(u,&view,board));assert(!published && !roots);}
 reset();throw_add=50;assert(!show_scores(u,&view,board));assert(!published && !roots);
 reset();board.rows[80].rank=1;assert(!show_scores(u,&view,board));assert(!published && !roots);board.rows[80].rank=81;
 reset();memset(board.rows[80].name,'x',sizeof(board.rows[80].name));assert(!show_scores(u,&view,board));assert(!published && !roots);strcpy(board.rows[80].name,"Player");
 reset();bad_offset=true;assert(!show_scores(u,&view,board) && !published && !roots);
 reset();sony_active=true;assert(!show_scores(u,&view,board) && !published && !roots);
 reset();missing_method=true;assert(!show_scores(u,&view,board) && !published && !roots);
 reset();view.k=&otherK;assert(!show_scores(u,&view,board) && !published && !roots);
 reset();u.declaring_type=NULL;assert(!show_scores(u,&view,board) && !published && !roots);
 reset();return 0;
}
