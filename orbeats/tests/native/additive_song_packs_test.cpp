// Synthetic IL2CPP API model. No game data, PS4, network or live hooks.
#include "additive_song_packs.h"
#include "additive_probe_level.h"
#include "additive_probe_profile.h"
#include "additive_local_content.h"
#include "additive_library_profile.h"
#include <assert.h>
#include <stdlib.h>
#include <map>
#include <string>
#include <vector>
#include <stdio.h>
#include <algorithm>
using namespace BsdAdditive;
struct Field { size_t offset; };
struct Class { const char* name; int rank; Class* element; std::map<std::string,Field> fields; };
struct Repo { std::map<std::string,void*> packs, levels, level_packs; };
static Class model_c{"BeatmapLevelsModel",0,NULL,{}}, repo_c{"BeatmapLevelsRepository",0,NULL,{}},
 pack_c{"BeatmapLevelPack",0,NULL,{}}, level_c{"BeatmapLevel",0,NULL,{}},
 pack_array_c{"BeatmapLevelPack[]",1,&pack_c,{}}, level_array_c{"BeatmapLevel[]",1,&level_c,{}};
static Class key_c{"BeatmapKey",0,NULL,{}}, key_array_c{"BeatmapKey[]",1,&key_c,{}},
 characteristic_c{"BeatmapCharacteristicSO",0,NULL,{}}, basic_c{"BeatmapBasicData",0,NULL,{}},
 dict_c{"Dictionary`2",0,NULL,{}};
static Class entitlement_c{"BeatmapLevelsEntitlementModel",0,NULL,{}},set_c{"HashSet`1",0,NULL,{}},bool_c{"Boolean",0,NULL,{}};
static int set_contains,set_add,set_remove;
static int pack_ctor, repo_ctor, get_pack, get_level, get_level_pack;
static int palette_ctor,find_environments;
static Class environment_c{"EnvironmentInfoSO",0,NULL,{}},palette_so_c{"ColorSchemeSO",0,NULL,{}},
 resources_c{"Resources",0,NULL,{}},object_c{"Object",0,NULL,{}},
 object_array_c{"Object[]",1,&object_c,{}},
 environment_array_c{"EnvironmentInfoSO[]",1,&environment_c,{}},
 wrong_palette_array_c{"ColorSchemeSO[]",1,&palette_so_c,{}},
 rank2_environment_array_c{"EnvironmentInfoSO[,]",2,&environment_c,{}},
 runtime_type_c{"RuntimeType",0,NULL,{}};
static Class palette_c{"ColorScheme",0,NULL,{}};
static const size_t palette_offsets[]={0x34,0x44,0x68,0x78,0x88,0x9c,0xac,0xbc,0x54};
static int level_ctor, basic_ctor, dict_ctor, keys_method, get_basic, add_basic;
static bool bad_value_size=false;
static int32_t value_size(void*,uint32_t* alignment){*alignment=8;return bad_value_size?16:24;}
struct State {
 std::vector<void*> allocations; std::map<void*,std::u16string> strings;
 std::map<void*,Repo> repos; std::map<uint32_t,void*> roots;
 void* environments=NULL;int palette_fault=0;
 int allocs=0, fail_alloc=0, root_calls=0, fail_root=0, invokes=0, throw_at=0, writes=0;
 std::map<void*,std::map<std::string,bool>> sets;
 int writes_at_policy_start=0;
 int set_calls=0,set_throw_at=0,set_throw_after=0;bool drop_set_add=false,drop_set_remove=false,bad_boolean=false;
 bool overwrite=false, corrupt_array=false, swap_prepared_stock_order=false; uint32_t next_root=1;
 std::map<void*,std::map<int,void*>> basics;void* keys=NULL;
 int ref_writes=0, corrupt_ref_at=0, drop_ref_at=0; bool drop_count_once=false;
 ~State() { for (void* p: allocations) free(p); }
};
static State* s;
static void* alloc(Class* c, size_t size=160) {
 if (++s->allocs == s->fail_alloc) return NULL;
 void* p=calloc(1,size); assert(p); *(Class**)p=c; s->allocations.push_back(p); return p;
}
static void put(void* o,size_t offset,void* p) { memcpy((char*)o+offset,&p,8); }
static void* ref(void* o,size_t offset) { void* p;memcpy(&p,(char*)o+offset,8);return p; }
static void* klass(void* p) { return *(Class**)p; }
static const char* name(void* c) { return ((Class*)c)->name; }
static const char* ns(void* c) { if(c==&resources_c||c==&object_c)return "UnityEngine";if(c==&runtime_type_c)return "System";return c==&set_c?"System.Collections.Generic":c==&bool_c?"System":!strcmp(((Class*)c)->name,"Sprite")?"UnityEngine":""; }
static void* find_field(void* c,const char* name) {
 auto& fs=((Class*)c)->fields;auto i=fs.find(name);return i==fs.end()?NULL:&i->second;
}
static size_t offset(void* f) { return ((Field*)f)->offset; }
static void read(void* o,void* f,void* dest) {
 if(klass(o)==&palette_c){size_t n=offset(f)==0x31||offset(f)==0x64||offset(f)==0x98?1:16;memcpy(dest,(char*)o+offset(f),n);return;}

 size_t n=(klass(o)==&basic_c&&(offset(f)==0x10||offset(f)==0x14||(offset(f)>=0x28&&offset(f)<=0x34)))||(klass(o)==&level_c&&(offset(f)==0x10||offset(f)==0x14||(offset(f)>=0x48&&offset(f)<=0x60)))?4:(offset(f)==0x20&&klass(o)==&model_c)||(klass(o)==&pack_c&&(offset(f)==0x38||offset(f)==0x3c))?4:8;
 memcpy(dest,(char*)o+offset(f),n);
}
static void write(void* o,void* f,void* value) {
 ++s->writes;
 if(klass(o)==&model_c&&offset(f)==0x20){
  if(s->drop_count_once){s->drop_count_once=false;return;}
  memcpy((char*)o+offset(f),value,4);return;
 }
 // Exact PS4 export semantics: reference case stores value itself, whereas
 // scalar I4 dereferences value. Never model both as memcpy(dest,value,size).
 assert(std::find(s->allocations.begin(),s->allocations.end(),value)!=s->allocations.end() &&
        "reference field requires managed object, not native pointer-to-pointer");
 if(++s->ref_writes==s->drop_ref_at)return;
 if(s->ref_writes==s->corrupt_ref_at)value=s->allocations.front();
 put(o,offset(f),value);
}
static const void* method(void* c,const char* n,int args) {
 if(c==&set_c&&args==1){
  if(!strcmp(n,"Contains"))return &set_contains;
  if(!strcmp(n,"Add"))return &set_add;
  if(!strcmp(n,"Remove"))return &set_remove;
 }
 if(c==&resources_c&&!strcmp(n,"FindObjectsOfTypeAll")&&args==1)return s->palette_fault==2?NULL:&find_environments;
 if(c==&palette_c&&!strcmp(n,".ctor")&&args==13)return &palette_ctor;
 if(c==&level_c){
  if(!strcmp(n,".ctor")&&args==17)return &level_ctor;
  if(!strcmp(n,"GetBeatmapKeys")&&args==0)return &keys_method;
  if(!strcmp(n,"GetDifficultyBeatmapData")&&args==2)return &get_basic;
  if(!strcmp(n,"AddBeatmapBasicData")&&args==3)return &add_basic;
 }
 if(c==&basic_c&&!strcmp(n,".ctor")&&args==10)return &basic_ctor;
 if(c==&dict_c&&!strcmp(n,".ctor")&&args==0)return &dict_ctor;
 if(c==&pack_c&&!strcmp(n,".ctor")&&args==8)return &pack_ctor;
 if(c!=&repo_c||args!=1)return NULL;
 if(!strcmp(n,".ctor"))return &repo_ctor;
 if(!strcmp(n,"GetBeatmapLevelPackByPackId"))return &get_pack;
 if(!strcmp(n,"GetBeatmapLevelById"))return &get_level;
 if(!strcmp(n,"GetBeatmapLevelPackByBeatmapLevelId"))return &get_level_pack;
 return NULL;
}
static void* new_object(void* c) {return alloc((Class*)c,c==&palette_c?208:160);}
static void* new_array(void* c,size_t n) {
 void* p=alloc(c==&pack_c?&pack_array_c:&level_array_c,32+8*n);
 if(p) memcpy((char*)p+24,&n,8);return p;
}
static uintptr_t length(void* a) {if(a==s->environments&&s->palette_fault==21)return 0;size_t n;memcpy(&n,(char*)a+24,8);return n;}
static int rank(void* c) {return ((Class*)c)->rank;}
static void* elem(void* c) {return ((Class*)c)->element;}
static void barrier(void*,void** dest,void* p) {*dest=p;}
static uint32_t root(void* p,bool pin) {assert(pin);if(++s->root_calls==s->fail_root)return 0;uint32_t id=s->next_root++;s->roots[id]=p;return id;}
static void unroot(uint32_t h) {assert(s->roots.erase(h)==1);}
static void* string_new(const char* ascii) {
 void* p=alloc(NULL);if(!p)return NULL;std::u16string text;for(;*ascii;++ascii)text.push_back(*ascii);s->strings[p]=text;return p;
}
static int32_t string_length(void* p) {return (int32_t)s->strings.at(p).size();}
static const uint16_t* chars(void* p) {return (const uint16_t*)s->strings.at(p).data();}
static std::string key(void* p) {auto t=s->strings.at(p);return std::string(t.begin(),t.end());}
static void build_repo(void* object,void* array) {
 put(object,0x10,array);Repo r;void** packs=(void**)((char*)array+32);
 for(size_t i=0;i<length(array);++i){void* p=packs[i];assert(r.packs.emplace(key(ref(p,0x10)),p).second);
  void* a=ref(p,0x40);void** levels=(void**)((char*)a+32);
  for(size_t j=0;j<length(a);++j){auto k=key(ref(levels[j],0x18));
   if(s->overwrite){r.levels[k]=levels[j];r.level_packs[k]=p;}
   else {r.levels.emplace(k,levels[j]);r.level_packs.emplace(k,p);}
  }
 }
 s->repos[object]=r;
}
static void* invoke_mock(const void* m,void* object,void** args,void** exception) {
 if(m==&set_contains||m==&set_add||m==&set_remove){
  if(++s->set_calls==s->set_throw_at){*exception=object;return NULL;}
  bool present=s->sets[object].count(key(args[0]))!=0;
  bool result=present;
  if(m==&set_add){assert(s->writes==s->writes_at_policy_start);if(!s->drop_set_add)s->sets[object][key(args[0])]=true;result=!present;}
  if(m==&set_remove){if(!s->drop_set_remove)s->sets[object].erase(key(args[0]));result=present;}
  if(s->set_calls==s->set_throw_after){*exception=object;return NULL;}
  void* box=alloc(s->bad_boolean?&level_c:&bool_c,24);if(box)memcpy((char*)box+16,&result,1);return box;
 }
 if(++s->invokes==s->throw_at){*exception=(void*)1;return NULL;}
 if(m==&find_environments){assert(!object&&args&&klass(args[0])==&runtime_type_c);if(s->palette_fault==3){*exception=(void*)1;return NULL;}return s->environments;}
 if(m==&palette_ctor){
  memcpy((char*)object+8,(char*)args[0]+8,200);
  const int positions[]={2,3,5,6,7,9,10,11,12};
  for(int i=0;i<9;++i)memcpy((char*)object+palette_offsets[i],args[positions[i]],16);
  memcpy((char*)object+0x31,args[1],1);memcpy((char*)object+0x64,args[4],1);memcpy((char*)object+0x98,args[8],1);return NULL;
 }
 if(m==&keys_method)return s->keys;
 if(m==&dict_ctor)return NULL;
 if(m==&get_basic){int32_t d;memcpy(&d,args[1],4);if(key(ref(args[0],0x30))!="Standard")d+=100;auto i=s->basics[object].find(d);return i==s->basics[object].end()?NULL:i->second;}
 if(m==&add_basic){int32_t d;memcpy(&d,args[1],4);if(key(ref(args[0],0x30))!="Standard")d+=100;assert(!s->basics[object].count(d));s->basics[object][d]=args[2];return NULL;}
 if(m==&level_ctor){
  memcpy((char*)object+0x10,args[0],4);memcpy((char*)object+0x14,args[1],1);
  for(int i=2;i<=7;++i)put(object,0x18+8*(i-2),args[i]);
  for(int i=8;i<=14;++i)memcpy((char*)object+0x48+4*(i-8),args[i],4);
  put(object,0x68,args[15]);put(object,0x70,args[16]);return NULL;}
 if(m==&basic_ctor){
  memcpy((char*)object+0x10,args[0],4);memcpy((char*)object+0x14,args[1],4);
  memcpy((char*)object+0x18,args[2],8); // EnvironmentName VALUE struct
  put(object,0x20,args[3]);for(int i=4;i<=7;++i)memcpy((char*)object+0x28+4*(i-4),args[i],4);
  put(object,0x38,args[8]);put(object,0x40,args[9]);return NULL;}
 if(m==&pack_ctor){put(object,0x10,args[0]);put(object,0x18,args[1]);put(object,0x20,args[2]);put(object,0x28,args[3]);put(object,0x30,args[4]);memcpy((char*)object+0x38,args[5],4);put(object,0x40,args[6]);memcpy((char*)object+0x3c,args[7],4);return NULL;}
 if(m==&repo_ctor){build_repo(object,args[0]);
  if(s->swap_prepared_stock_order&&length(args[0])>2){
   void* first=ref(args[0],40);put(args[0],40,ref(args[0],48));put(args[0],48,first);
  }
  if(s->corrupt_array)put(object,0x10,NULL);return NULL;}
 Repo& r=s->repos.at(object);auto k=key(args[0]);
 auto& dict=m==&get_pack?r.packs:m==&get_level?r.levels:r.level_packs;
 auto i=dict.find(k);return i==dict.end()?NULL:i->second;
}
static Api api(){return {klass,name,ns,find_field,offset,read,write,method,new_object,invoke_mock,new_array,length,rank,elem,barrier,root,unroot,string_new,string_length,chars};}
struct Fixture {
 State state;void* model;void* source;void* level;void* original[3];void* old_arrays[3];
 Fixture(){s=&state;
  model_c.fields={{"ostAndExtrasBeatmapLevelsRepository",{0x10}},{"_allLoadedBeatmapLevelsRepository",{0x50}},{"_allExistingBeatmapLevelsRepository",{0x58}},{"allPacksCount",{0x20}}};
  repo_c.fields={{"_beatmapLevelPacks",{0x10}}};level_c.fields={{"levelID",{0x18}}};
  pack_c.fields={{"packID",{0x10}},{"_beatmapLevels",{0x40}},{"coverImage",{0x28}},{"smallCoverImage",{0x30}},{"packBuyOption",{0x38}},{"contentRating",{0x3c}}};
  level=alloc(&level_c);put(level,0x18,string_new("StockSong"));source=alloc(&pack_c);put(source,0x10,string_new("OST1"));
  void* levels=new_array(&level_c,1);put(levels,32,level);put(source,0x40,levels);
  model=alloc(&model_c);int32_t count=1;memcpy((char*)model+0x20,&count,4);
  for(int i=0;i<3;++i){old_arrays[i]=new_array(&pack_c,1);put(old_arrays[i],32,source);original[i]=alloc(&repo_c);build_repo(original[i],old_arrays[i]);put(model,i==0?0x10:i==1?0x50:0x58,original[i]);}
  put(model,0x18,source);state.allocs=state.root_calls=state.invokes=0;
 }
 void unchanged(){assert(state.writes==0);assert(ref(model,0x10)==original[0]);assert(ref(model,0x50)==original[1]);assert(ref(model,0x58)==original[2]);assert(ref(model,0x18)==source);assert(state.roots.empty());}
};
static const char* missing_api;
static void* resolve_mock(const char* n){return missing_api&&!strcmp(n,missing_api)?NULL:(void*)&name;}
static ProbeContext probe_context(){return {{kProbeLevelId,kProbeTitle,120,12,9},value_size};}
static void configure_probe(Fixture& f){
 auto& fields=level_c.fields;fields["_beatmapBasicDatas"]={0x70};fields["previewMediaData"]={0x68};
 fields["allMappers"]={0x38};fields["allLighters"]={0x40};fields["beatsPerMinute"]={0x48};fields["songDuration"]={0x5c};
 key_c.fields={{"beatmapCharacteristic",{16}},{"difficulty",{24}},{"levelId",{32}}};
 characteristic_c.fields={{"_serializedName",{0x30}}};
 basic_c.fields={{"noteJumpMovementSpeed",{0x10}},{"noteJumpStartBeatOffset",{0x14}},{"environmentName",{0x18}},
 {"beatmapColorScheme",{0x20}},{"notesCount",{0x28}},{"mappers",{0x38}},{"lighters",{0x40}}};
 void* ch=alloc(&characteristic_c);put(ch,0x30,string_new("Standard"));
 void* other=alloc(&characteristic_c);put(other,0x30,string_new("OneSaber"));
 put(f.level,0x70,alloc(&dict_c));put(f.level,0x68,alloc(NULL));
 put(f.level,0x38,alloc(NULL));put(f.level,0x40,alloc(NULL));
 size_t n=6;s->keys=alloc(&key_array_c,32+n*24);memcpy((char*)s->keys+24,&n,8);
 for(int i=0;i<6;++i){char* e=(char*)s->keys+32+i*24;void* c=i<5?ch:other;
  memcpy(e,&c,8);int32_t d=i%5;memcpy(e+8,&d,4);void* id=ref(f.level,0x18);memcpy(e+16,&id,8);
  if(i<5){void* b=alloc(&basic_c);put(b,0x18,string_new("DefaultEnvironment"));put(b,0x38,ref(f.level,0x38));put(b,0x40,ref(f.level,0x40));
   int32_t notes=999;memcpy((char*)b+0x28,&notes,4);s->basics[f.level][d]=b;}}
 s->allocs=s->invokes=s->root_calls=0;bad_value_size=false;
}
static void* unbox(void* p){return (char*)p+16;}
static int32_t bool_size(void* c,uint32_t* a){*a=1;return c==&bool_c?1:24;}
static void configure_local(Fixture& f){
 model_c.fields["_entitlements"]={0x48};
 entitlement_c.fields={{"_alwaysOwnedBeatmapLevelIds",{0x18}},{"_alwaysOwnedPacksIds",{0x20}}};
 void* e=alloc(&entitlement_c);put(f.model,0x48,e);
 for(int i=0;i<2;++i){void* set=alloc(&set_c);put(e,0x18+8*i,set);s->sets[set][i?"OST1":"StockSong"]=true;}
 s->allocs=s->root_calls=s->invokes=0;
}
static std::map<std::string,bool>& local_set(Fixture& f,int i){return s->sets[ref(ref(f.model,0x48),0x18+8*i)];}
static Result local_register(Fixture& f,Diagnostic* d){
 s->writes_at_policy_start=s->writes;
 Api a=api();ProbeContext ctx=probe_context();LocalContent local(a,unbox,bool_size);
 Result r=append_stock_pack(a,f.model,d,make_probe_level,&ctx,prepare_local_content,&local);
 return local.finish(r,d);
}
static void batch_contexts(ProbeContext (&contexts)[2]){
 for(size_t i=0;i<2;++i){const ReviewedSong& p=kReviewedSongs[i];
  contexts[i]={{p.id,p.title,p.bpm,p.duration,1,p.difficulties,p.author,p.difficulty_mask},value_size};}
}
static Result batch_register(Fixture& f,Diagnostic* d=NULL){
 Api a=api();ProbeContext contexts[2];batch_contexts(contexts);void* cs[]={&contexts[0],&contexts[1]};
 LocalContent local(a,unbox,bool_size,kReviewedIds,2);
 FactoryBatch batch={cs,kReviewedIds,2,prepare_local_content_many,&local};
 s->writes_at_policy_start=s->writes;
 Result result=append_stock_pack(a,f.model,d,make_probe_level,NULL,NULL,NULL,NULL,&batch);
 return local.finish(result,d);
}
// Different real stock packs, not just a one-element fixture: reordering must
// keep each original object and each original lookup, including a DLC sentinel.
static std::vector<void*> stock_sequence(Fixture& f) {
 std::vector<void*> packs{f.source};
 for(int i=1;i<4;++i){
  char id[32];snprintf(id,sizeof(id),"StockPack%d",i);
  void* pack=alloc(&pack_c);put(pack,0x10,string_new(id));
  snprintf(id,sizeof(id),"StockLevel%d",i);
  void* level=alloc(&level_c);put(level,0x18,string_new(id));
  void* levels=new_array(&level_c,1);put(levels,32,level);put(pack,0x40,levels);
  packs.push_back(pack);
 }
 for(int i=0;i<3;++i){
  f.old_arrays[i]=new_array(&pack_c,packs.size());
  for(size_t n=0;n<packs.size();++n)put(f.old_arrays[i],32+8*n,packs[n]);
  build_repo(f.original[i],f.old_arrays[i]);
 }
 int32_t count=(int32_t)packs.size();memcpy((char*)f.model+0x20,&count,4);
 s->allocs=s->root_calls=s->invokes=0;
 return packs;
}
static std::vector<void*> array_items(void* a){
 size_t n=0;memcpy(&n,(char*)a+24,8);std::vector<void*> result;
 for(size_t i=0;i<n;++i)result.push_back(ref(a,32+8*i));return result;
}
static void* palette_domain(){return s;}
static const void** palette_assemblies(void*,size_t* count){static const void* image=&environment_c;*count=1;return &image;}
static void* palette_image(const void* image){return (void*)image;}
static void* palette_find(void*,const char* ns_,const char* name_){
 if(s->palette_fault==1)return NULL;
 if(!strcmp(ns_,"UnityEngine")&&!strcmp(name_,"Resources"))return &resources_c;
 if(!*ns_&&!strcmp(name_,"EnvironmentInfoSO"))return &environment_c;return NULL;
}
static const void* palette_type(void* c){assert(c==&environment_c);return s->palette_fault==4?NULL:c;}
static void* palette_type_object(const void* c){assert(c==&environment_c);return s->palette_fault==5?NULL:alloc(&runtime_type_c);}
static PaletteApis palette_api(){return {palette_domain,palette_assemblies,palette_image,palette_find,palette_type,palette_type_object};}
static void* configure_environment_palette(){
 palette_c.fields.clear();const char* colors[]={"_saberAColor","_saberBColor","_environmentColor0","_environmentColor1","_environmentColorW","_environmentColor0Boost","_environmentColor1Boost","_environmentColorWBoost","_obstaclesColor"};
 for(int i=0;i<9;++i)palette_c.fields[colors[i]]={palette_offsets[i]};
 palette_c.fields["_overrideNotes"]={0x31};palette_c.fields["_overrideLights"]={0x64};palette_c.fields["_supportsEnvironmentColorBoost"]={0x98};
 void* base=alloc(&palette_c,208);float values[]={.125f,.25f,.5f,1};for(int i=0;i<9;++i)memcpy((char*)base+palette_offsets[i],values,16);
 environment_c.fields={{"_serializedName",{0x30}},{"_colorScheme",{0x20}}};palette_so_c.fields={{"_colorScheme",{0x18}}};
 void* so=alloc(&palette_so_c);put(so,0x18,base);void* env=alloc(&environment_c);put(env,0x20,so);put(env,0x30,string_new("DefaultEnvironment"));
 size_t count=s->palette_fault==6?2:1;void* all=alloc(&object_array_c,32+count*8);memcpy((char*)all+24,&count,8);put(all,32,env);s->environments=all;
 if(s->palette_fault==6){void* other=alloc(&environment_c);put(other,0x20,so);put(other,0x30,string_new("DefaultEnvironment"));put(all,40,other);}
 if(s->palette_fault==7)put(env,0x30,string_new("WeaveEnvironment"));
 if(s->palette_fault==8)put(so,0x18,NULL);
 if(s->palette_fault==9)put(env,0x20,NULL);
 if(s->palette_fault==10)environment_c.fields.erase("_serializedName");
 if(s->palette_fault==11)palette_so_c.fields.erase("_colorScheme");
 if(s->palette_fault==12){size_t wrong=257;memcpy((char*)all+24,&wrong,8);}
 if(s->palette_fault==13)put(all,32,so);
 if(s->palette_fault==14)s->environments=NULL;
 if(s->palette_fault==17)put(all,0,&environment_array_c);
 if(s->palette_fault==18)put(all,0,&wrong_palette_array_c);
 if(s->palette_fault==19)put(all,0,&rank2_environment_array_c);
 if(s->palette_fault==20)put(all,16,env);
 if(s->palette_fault==22){put(all,0,&environment_array_c);put(all,32,so);}

 return base;
}
int main(){
 // Real regression: the OST template has NO per-beatmap ColorScheme. Apply six
 // authored colours over the exact environment's genuine default, not stock writes.
 for(int fault=0;fault<=22;++fault){Fixture f;configure_probe(f);s->palette_fault=fault;void* base=configure_environment_palette();
  unsigned char before[208];memcpy(before,base,208);ProbeContext ctx=probe_context();PaletteApis e=palette_api();ctx.palette_apis=&e;
  ProbePresentation profile={};profile.lufs=-14;profile.palettes[4].mask=111;
  for(int i=0;i<9;++i){float rgba[]={.75f,.3f,.2f,1};memcpy(profile.palettes[4].colors[i],rgba,16);}
  ctx.spec.presentation=&profile;ctx.spec.difficulty_mask=16;
  if(fault==15)e.type_get_object=NULL;if(fault==16)ctx.palette_apis=NULL;
  Diagnostic d;Result r=append_stock_pack(api(),f.model,&d,make_probe_level,&ctx);
  assert(!memcmp(before,base,208));assert(s->roots.empty());
  for(int i=0;i<5;++i)assert(!ref(s->basics[f.level][i],0x20));
  if(fault&&fault!=17){assert(r!=Added);f.unchanged();continue;}
  assert(d.palette_rank==1&&d.palette_count==1&&d.palette_stored==1&&!d.palette_bounds);
  assert(!strcmp(d.palette_element,fault==17?"EnvironmentInfoSO":"Object"));
  if(r!=Added)fprintf(stderr,"null palette regression fault=%d result=%s stage=%s\n",fault,result_name(r),d.stage);
  assert(r==Added);void* level=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);void* scheme=ref(s->basics[level][4],0x20);
  assert(scheme&&scheme!=base);for(int i=0;i<9;++i){const void* expected=profile.palettes[4].mask&(1u<<i)?(void*)profile.palettes[4].colors[i]:(char*)base+palette_offsets[i];assert(!memcmp((char*)scheme+palette_offsets[i],expected,16));}
 }

 // Genuine stock OneSaber characteristic lookup, missing modes refuse atomically.
 for(int missing=0;missing<2;++missing){Fixture f;configure_probe(f);ProbeContext ctx=probe_context();
  ProbeModes modes={};modes.flags=missing?2u:1u;int idx=missing?1:0;modes.masks[idx]=16;
  modes.stats[idx][4]={12,0,0,13,0};ctx.spec.modes=&modes;ctx.characteristic_model=f.model;
  ctx.spec.difficulty_mask=0;
  Result r=append_stock_pack(api(),f.model,NULL,make_probe_level,&ctx);
  assert(s->roots.empty());
  if(missing){assert(r==Incompatible);f.unchanged();}
  else{assert(r==Added);void* level=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);
       assert(s->basics[level].size()==1&&s->basics[level].count(104));}
 }

 // Per-level loudness/offset and per-difficulty cloned palette. Never stock writes.
 for(int broken=0;broken<2;++broken){Fixture f;configure_probe(f);ProbeContext ctx=probe_context();
  palette_c.fields.clear();const char* names[]={"_saberAColor","_saberBColor","_environmentColor0","_environmentColor1","_environmentColorW","_environmentColor0Boost","_environmentColor1Boost","_environmentColorWBoost","_obstaclesColor"};
  for(int i=0;i<9;++i)palette_c.fields[names[i]]={palette_offsets[i]};
  palette_c.fields["_overrideNotes"]={0x31};palette_c.fields["_overrideLights"]={0x64};palette_c.fields["_supportsEnvironmentColorBoost"]={0x98};
  void* source=alloc(&palette_c,208);float base[]={.1f,.2f,.3f,1};for(int i=0;i<9;++i)memcpy((char*)source+palette_offsets[i],base,16);
  for(int d=0;d<5;++d)put(s->basics[f.level][d],0x20,source);
  unsigned char original[208];memcpy(original,source,208);
  ProbePresentation profile={};profile.lufs=-11;profile.offset=.125f;profile.palettes[0].mask=1;
  float authored[]={1,0,0,1};memcpy(profile.palettes[0].colors[0],authored,16);ctx.spec.presentation=&profile;
  if(broken)palette_c.fields.erase("_saberAColor");
  Result r=append_stock_pack(api(),f.model,NULL,make_probe_level,&ctx);
  assert(!memcmp(original,source,208));assert(s->roots.empty());
  if(broken){assert(r==Incompatible);f.unchanged();continue;}
  assert(r==Added);void* level=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);
  float lufs,offset;memcpy(&lufs,(char*)level+0x4c,4);memcpy(&offset,(char*)level+0x50,4);assert(lufs==-11&&offset==.125f);
  void* copy=ref(s->basics[level][0],0x20);assert(copy!=source&&!memcmp((char*)copy+0x34,authored,16));
  assert(!memcmp((char*)copy+0x44,base,16));assert(ref(s->basics[level][1],0x20)==source);
 }

 // Companion bound: eight independently named generated levels, one pack.
 {Fixture f;configure_probe(f);configure_local(f);stock_sequence(f);Api a=api();
  ProbeContext contexts[kMaxGeneratedLevels]={};void* pointers[kMaxGeneratedLevels];
  const char* approved[kMaxGeneratedLevels];char ids[kMaxGeneratedLevels][81];
  for(size_t i=0;i<kMaxGeneratedLevels;++i){
   snprintf(ids[i],sizeof(ids[i]),"bsd_additive_%024lx",(unsigned long)i);
   contexts[i].spec={ids[i],"Generated",kReviewedSongs[0].bpm,kReviewedSongs[0].duration,1,
    kReviewedSongs[0].difficulties,"Fixture",31};contexts[i].class_value_size=value_size;
   pointers[i]=&contexts[i];approved[i]=ids[i];
  }
  {LocalContent local(a,unbox,bool_size,approved,kMaxGeneratedLevels);
  FactoryBatch batch={pointers,approved,kMaxGeneratedLevels,prepare_local_content_many,&local};
  Diagnostic d;Result r=append_stock_pack(a,f.model,&d,make_probe_level,NULL,NULL,NULL,NULL,&batch);
  r=local.finish(r,&d);if(r!=Added)fprintf(stderr,"eight-level %s stage=%s allocs=%d\n",result_name(r),d.stage,s->allocs);
  assert(r==Added);}
  assert(s->roots.empty());
  for(int i=0;i<3;++i){void* repo=ref(f.model,i==0?0x10:i==1?0x50:0x58);
   auto& index=s->repos[repo];assert(array_items(ref(index.packs.at(kPackId),0x40)).size()==kMaxGeneratedLevels);
   for(size_t j=0;j<kMaxGeneratedLevels;++j){assert(index.levels.count(ids[j])&&local_set(f,0).count(ids[j]));}}
 }

 // EnvironmentName is one managed string inside a VALUE struct: constructor
 // receives its address, never the raw string pointer. Stock basics unchanged.
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.environment="WeaveEnvironment";
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Added);
  void* level=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);
  for(int d=0;d<5;++d){assert(key(ref(s->basics[level].at(d),0x18))=="WeaveEnvironment");
   assert(key(ref(s->basics[f.level].at(d),0x18))=="DefaultEnvironment");}
  assert(s->roots.empty());}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.environment="UnknownEnvironment";
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}
 // Exp310 actual 5-difficulty + 3-difficulty profiles in one new pack.
 {Fixture f;configure_probe(f);configure_local(f);auto stocks=stock_sequence(f);Diagnostic d;
  assert(batch_register(f,&d)==Added);assert(s->roots.empty());
  for(int i=0;i<3;++i){void* repo=ref(f.model,i==0?0x10:i==1?0x50:0x58);auto& r=s->repos[repo];
   auto p=array_items(ref(repo,0x10));assert(p.size()==stocks.size()+1);
   for(size_t j=0;j<stocks.size();++j)assert(p[j+1]==stocks[j]);
   assert(r.levels.at("StockSong")==f.level&&r.level_packs.at("StockSong")==f.source);
   void* pack=r.packs.at(kPackId);auto levels=array_items(ref(pack,0x40));assert(levels.size()==2);
   assert(levels[0]!=levels[1]&&levels[0]!=f.level&&levels[1]!=f.level);
   for(size_t j=0;j<2;++j){const auto& profile=kReviewedSongs[j];void* level=levels[j];
    assert(r.levels.at(profile.id)==level&&r.level_packs.at(profile.id)==pack);
    assert(key(ref(level,0x20))==profile.title&&local_set(f,0).count(profile.id));
    assert(s->basics[level].size()==(j==0?5:3));
    for(int d=0;d<5;++d){if(!(profile.difficulty_mask&(1u<<d))){assert(!s->basics[level].count(d));continue;}
     void* b=s->basics[level].at(d);int32_t n;memcpy(&n,(char*)b+0x28,4);
     assert(n==profile.difficulties[d].notes+profile.difficulties[d].bombs);}
   }
  }
  assert(local_set(f,1).count(kPackId)&&local_set(f,0).count("StockSong"));
  auto before=s->sets;int writes=s->writes;assert(batch_register(f,&d)==AlreadyPresent);
  assert(s->sets==before&&s->writes==writes&&s->roots.empty());
 }
 // Missing one published repository, wrong second ID or missing second lookup
 // must NOT enable routes or mutate the already-existing classification.
 for(int corruption=0;corruption<3;++corruption){Fixture f;configure_probe(f);configure_local(f);
  assert(batch_register(f)==Added);auto before=s->sets;int writes=s->writes;
  if(corruption==0)put(f.model,0x58,f.original[2]);
  if(corruption==1)s->repos[ref(f.model,0x50)].levels.erase(kReviewedIds[1]);
  if(corruption==2){void* p=s->repos[ref(f.model,0x50)].packs.at(kPackId);
   auto ls=array_items(ref(p,0x40));put(ls[1],0x18,string_new("bsd_additive_wrong"));}
  assert(batch_register(f)==VerificationFailed);assert(s->sets==before&&s->writes==writes&&s->roots.empty());
 }
 // The second factory must fail before ANY model/free-set mutation; invalid
 // batch shape, duplicate IDs and mismatched factory IDs are refused too.
 for(int bad=0;bad<7;++bad){Fixture f;configure_probe(f);configure_local(f);Api a=api();
  ProbeContext contexts[2];batch_contexts(contexts);void* cs[]={&contexts[0],&contexts[1]};
  const char* ids[]={kReviewedIds[0],kReviewedIds[1]};FactoryBatch b={cs,ids,2,NULL,NULL};
  if(bad==0)contexts[1].spec.difficulty_mask=0;
  if(bad==1)ids[1]=ids[0];if(bad==2)b.count=kMaxGeneratedLevels+1;
  if(bad==3)b.count=0;if(bad==4)cs[1]=NULL;
  if(bad==5)contexts[1].spec.level_id="bsd_additive_unreviewed";
  if(bad==6)ids[1]="StockSong";
  auto before=s->sets;assert(append_stock_pack(a,f.model,NULL,make_probe_level,NULL,NULL,NULL,NULL,&b)!=Added);
  assert(s->sets==before);f.unchanged();
 }
 // Roll back both new free-level IDs + pack after any publication failure.
 for(int n=1;n<=3;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;
  s->drop_ref_at=n;assert(batch_register(f)==PublicationRestored);assert(s->sets==before);
  for(int i=0;i<3;++i)assert(ref(f.model,i==0?0x10:i==1?0x50:0x58)==f.original[i]);assert(s->roots.empty());
 }
 // Three Contains + Add/Contains pairs: exceptions before/after mutation of
 // EACH owned ID are restored, including failure on the second-song insertion.
 for(int n=1;n<=9;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;
  s->set_throw_at=n;assert(batch_register(f)==ManagedException);assert(s->sets==before);f.unchanged();}
 for(int n: {4,6,8}){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;
  s->set_throw_after=n;assert(batch_register(f)==ManagedException);assert(s->sets==before);f.unchanged();}
 // Pre-existing membership must survive rollback (do not remove someone else's entry).
 {Fixture f;configure_probe(f);configure_local(f);local_set(f,0)[kReviewedIds[0]]=true;
  auto before=s->sets;s->drop_ref_at=2;assert(batch_register(f)==PublicationRestored);assert(s->sets==before);assert(s->roots.empty());}
 for(int n=1;n<=50;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;s->fail_alloc=n;
  Result r=batch_register(f);if(r!=Added){assert(r==AllocationFailed||r==Incompatible||r==VerificationFailed);assert(s->sets==before);f.unchanged();}else assert(s->roots.empty());}
 for(int n=1;n<=64;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;s->fail_root=n;
  Result r=batch_register(f);if(r!=Added){assert(r==AllocationFailed||r==Incompatible||r==VerificationFailed);assert(s->sets==before);f.unchanged();}else assert(s->roots.empty());}

 // Exp309: custom FIRST, official relative order/IDs and lookup objects intact.
 {Fixture f;configure_probe(f);auto stocks=stock_sequence(f);ProbeContext c=probe_context();
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Added);
  for(int i=0;i<3;++i){
   void* r=ref(f.model,i==0?0x10:i==1?0x50:0x58);void* a=ref(r,0x10);
   void* own=s->repos[r].packs.at(kPackId);assert(ref(a,32)==own);
   assert(length(a)==stocks.size()+1&&length(f.old_arrays[i])==stocks.size());
   for(size_t n=0;n<stocks.size();++n){
    assert(ref(a,40+8*n)==stocks[n]);assert(ref(f.old_arrays[i],32+8*n)==stocks[n]);
    void* level=ref(ref(stocks[n],0x40),32);auto id=key(ref(level,0x18));
    assert(s->repos[r].levels.at(id)==level&&s->repos[r].level_packs.at(id)==stocks[n]);
   }
  }
  assert(ref(f.model,0x18)==f.source);int writes=s->writes;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==AlreadyPresent);
  assert(s->writes==writes&&s->roots.empty());
 }
 // A .ctor that silently permutes stock entries cannot pass dict-only checks.
 {Fixture f;configure_probe(f);auto stocks=stock_sequence(f);ProbeContext c=probe_context();
  s->swap_prepared_stock_order=true;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==VerificationFailed);
  f.unchanged();
  for(int i=0;i<3;++i)for(size_t n=0;n<stocks.size();++n)
   assert(ref(f.old_arrays[i],32+8*n)==stocks[n]);
 }
 // Same-stock proof must remain LAST, despite new first-position behavior.
 {Fixture f;auto stocks=stock_sequence(f);assert(append_stock_pack(api(),f.model)==Added);
  for(int i=0;i<3;++i){void* r=ref(f.model,i==0?0x10:i==1?0x50:0x58);void* a=ref(r,0x10);
   for(size_t n=0;n<stocks.size();++n)assert(ref(a,32+8*n)==stocks[n]);
   assert(ref(a,32+8*stocks.size())==s->repos[r].packs.at(kPackId));
   assert(s->repos[r].level_packs.at("StockSong")==f.source);
  }
 }
 // New prepared-array order is checked BEFORE publication; corruption leaves
 // original multi-pack arrays/objects untouched, and roots are released.
 {Fixture f;configure_probe(f);auto stocks=stock_sequence(f);ProbeContext c=probe_context();
  s->corrupt_array=true;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==VerificationFailed);
  f.unchanged();
  for(int i=0;i<3;++i)for(size_t n=0;n<stocks.size();++n)
   assert(ref(f.old_arrays[i],32+8*n)==stocks[n]);
 }
 {Fixture f;Api a=api();assert(append_stock_pack(a,f.model)==Added);assert(f.state.writes==4);assert(f.state.roots.empty());
  for(int i=0;i<3;++i){void* r=ref(f.model,i==0?0x10:i==1?0x50:0x58);assert(r!=f.original[i]);assert(length(ref(r,0x10))==2);assert(ref(ref(r,0x10),32)==f.source);assert(f.state.repos[r].level_packs.at("StockSong")==f.source);assert(f.state.repos[r].levels.at("StockSong")==f.level);assert(f.state.repos[r].packs.count(kPackId));assert(length(f.old_arrays[i])==1);}
  assert(ref(f.model,0x18)==f.source);int32_t count;memcpy(&count,(char*)f.model+0x20,4);assert(count==2);
  assert(append_stock_pack(a,f.model)==AlreadyPresent);assert(f.state.writes==4);assert(f.state.roots.empty());}
 for(int n=1;n<=11;++n){Fixture f;f.state.fail_alloc=n;assert(append_stock_pack(api(),f.model)==AllocationFailed);f.unchanged();}
 for(int n=1;n<=16;++n){Fixture f;f.state.fail_root=n;Result r=append_stock_pack(api(),f.model);if(r!=Added){assert(r==AllocationFailed);f.unchanged();}else assert(n>15);}
 for(int n=1;n<=19;++n){Fixture f;f.state.throw_at=n;assert(append_stock_pack(api(),f.model)==ManagedException);f.unchanged();}
 {Fixture f;f.state.overwrite=true;assert(append_stock_pack(api(),f.model)==VerificationFailed);f.unchanged();}
 {Fixture f;f.state.corrupt_array=true;assert(append_stock_pack(api(),f.model)==VerificationFailed);f.unchanged();}
 {Fixture f;model_c.fields["allPacksCount"].offset=0x24;assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Fixture f;repo_c.fields.erase("_beatmapLevelPacks");assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Fixture f;put(f.model,0x50,NULL);assert(append_stock_pack(api(),f.model)==Incompatible);assert(f.state.writes==0);assert(f.state.roots.empty());}
 {Fixture f;Api a=api();a.runtime_invoke=NULL;assert(append_stock_pack(a,f.model)==Incompatible);f.unchanged();}
 {Fixture f;Api a=api();assert(append_stock_pack(a,NULL)==Incompatible);f.unchanged();}
 {Fixture f;pack_array_c.rank=2;assert(append_stock_pack(api(),f.model)==Incompatible);pack_array_c.rank=1;f.unchanged();}
 {Fixture f;put(f.old_arrays[0],16,f.model);assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Api a;const char* missing=NULL;missing_api="il2cpp_gc_wbarrier_set_field";assert(!resolve_api(a,resolve_mock,&missing));assert(!strcmp(missing,missing_api));missing_api=NULL;assert(resolve_api(a,resolve_mock,&missing));assert(complete(a));}
 {Fixture f;size_t count=512;memcpy((char*)f.old_arrays[0]+24,&count,8);assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Fixture f;size_t count=513;memcpy((char*)f.old_arrays[0]+24,&count,8);assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Fixture f;void* a=ref(f.source,0x40);size_t count=0;memcpy((char*)a+24,&count,8);assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 {Fixture f;int32_t bad=9;memcpy((char*)f.source+0x38,&bad,4);assert(append_stock_pack(api(),f.model)==Incompatible);f.unchanged();}
 // Custom proof is not a store product; preserve original pack's buy option.
 for(int32_t original_buy=0;original_buy<=1;++original_buy){Fixture f;
  memcpy((char*)f.source+0x38,&original_buy,4);
  assert(append_stock_pack(api(),f.model)==Added);
  for(int i=0;i<3;++i){void* r=ref(f.model,i==0?0x10:i==1?0x50:0x58);
   void* extra=f.state.repos[r].packs.at(kPackId);int32_t buy=-1;
   memcpy(&buy,(char*)extra+0x38,4);assert(buy==1 && "added proof pack must disable store buy option");}
  int32_t retained=-1;memcpy(&retained,(char*)f.source+0x38,4);assert(retained==original_buy);}
 // Actual constructor order: LoadAll returns before allPacksCount is assigned.
 {Fixture f;int32_t zero=0;memcpy((char*)f.model+0x20,&zero,4);Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Added);assert(f.state.writes==3);
  assert(!strcmp(d.stage,"published-constructor-count-deferred"));assert(d.pack_count==0);
  int32_t count=-1;memcpy(&count,(char*)f.model+0x20,4);assert(count==0);assert(f.state.roots.empty());
  // Simulate .ctor continuing: it reads the now-published loaded array count.
  count=(int32_t)length(ref(ref(f.model,0x50),0x10));memcpy((char*)f.model+0x20,&count,4);assert(count==2);
  assert(append_stock_pack(api(),f.model)==AlreadyPresent);assert(f.state.writes==3);
  // Simulate a later normal LoadAll rebuilding ORIGINAL repositories while the
  // readonly count still includes last run's extra pack. Do not increment to3.
  for(int i=0;i<3;++i)put(f.model,i==0?0x10:i==1?0x50:0x58,f.original[i]);
  assert(append_stock_pack(api(),f.model,&d)==Added);
  memcpy(&count,(char*)f.model+0x20,4);assert(count==2);assert(f.state.writes==7);
  assert(!strcmp(d.stage,"published-reload-count-updated"));assert(f.state.roots.empty());}
 {Fixture f;int32_t negative=-1;memcpy((char*)f.model+0x20,&negative,4);Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Incompatible);assert(!strcmp(d.stage,"model-count-range"));f.unchanged();}
 {Fixture f;int32_t huge=512;memcpy((char*)f.model+0x20,&huge,4);Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Incompatible);assert(!strcmp(d.stage,"model-count-range"));f.unchanged();}
 {Fixture f;model_c.fields["allPacksCount"].offset=0x24;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Incompatible);assert(!strcmp(d.stage,"model-count-field"));f.unchanged();}
 {Fixture f;repo_c.fields.erase("_beatmapLevelPacks");Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Incompatible);assert(!strcmp(d.stage,"repository-packs-field"));assert(d.repository==0);f.unchanged();}
 {Fixture f;put(f.model,0x50,NULL);Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==Incompatible);assert(!strcmp(d.stage,"repository-null"));assert(d.repository==1);assert(f.state.writes==0);assert(f.state.roots.empty());}
 // Independent ABI checks: reference input is direct, scalar input is address.
 {Fixture f;void* ff=find_field(&model_c,"_allLoadedBeatmapLevelsRepository");
  write(f.model,ff,f.original[1]);assert(ref(f.model,0x50)==f.original[1]);
  int32_t n=7;write(f.model,find_field(&model_c,"allPacksCount"),&n);
  int32_t got=0;read(f.model,find_field(&model_c,"allPacksCount"),&got);assert(got==7);}
 for(int i=1;i<=3;++i){Fixture f;f.state.drop_ref_at=i;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==PublicationRestored);
  assert(!strcmp(d.stage,"publication-reference-readback"));assert(d.repository==i-1);
  assert(ref(f.model,0x10)==f.original[0]);assert(ref(f.model,0x50)==f.original[1]);
  assert(ref(f.model,0x58)==f.original[2]);assert(f.state.roots.empty());}
 for(int i=1;i<=3;++i){Fixture f;f.state.corrupt_ref_at=i;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==PublicationRestored);
  assert(!strcmp(d.stage,"publication-reference-readback"));
  assert(ref(f.model,0x10)==f.original[0]);assert(ref(f.model,0x50)==f.original[1]);
  assert(ref(f.model,0x58)==f.original[2]);assert(f.state.roots.empty());}
 {Fixture f;f.state.drop_count_once=true;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==PublicationRestored);
  assert(!strcmp(d.stage,"publication-count-readback"));
  int32_t count=0;read(f.model,find_field(&model_c,"allPacksCount"),&count);assert(count==1);
  assert(ref(f.model,0x10)==f.original[0]);assert(ref(f.model,0x50)==f.original[1]);
  assert(ref(f.model,0x58)==f.original[2]);assert(f.state.roots.empty());}
 {Fixture f;f.state.corrupt_ref_at=2;f.state.drop_ref_at=3;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d)==PublicationUnsafe);
  assert(strstr(result_name(PublicationUnsafe),"unsafe; stop testing"));assert(f.state.roots.empty());}
 // Separate-ID generated song with NEW Standard-only basic data and counts.
 {Fixture f;configure_probe(f);ProbeContext ctx=probe_context();Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d,make_probe_level,&ctx)==Added);
  assert(f.state.roots.empty());
  for(int i=0;i<3;++i){void* r=ref(f.model,i==0?0x10:i==1?0x50:0x58);auto& repo=f.state.repos[r];
   assert(repo.levels.at("StockSong")==f.level);assert(repo.level_packs.at("StockSong")==f.source);
   void* created=repo.levels.at(kProbeLevelId);assert(created!=f.level);assert(key(ref(created,0x18))==kProbeLevelId);
   assert(key(ref(created,0x20))==kProbeTitle);assert(repo.level_packs.at(kProbeLevelId)==repo.packs.at(kPackId));
   assert(s->basics[created].size()==5);assert(ref(created,0x70)!=ref(f.level,0x70));
   for(int j=0;j<5;++j){void* b=s->basics[created].at(j);int32_t n=0;memcpy(&n,(char*)b+0x28,4);assert(n==9);
    assert(b!=s->basics[f.level].at(j));memcpy(&n,(char*)s->basics[f.level].at(j)+0x28,4);assert(n==999);
    assert(ref(b,0x18)==ref(s->basics[f.level].at(j),0x18));}
   float duration=0;memcpy(&duration,(char*)created+0x5c,4);assert(duration==12);}
  assert(key(ref(f.level,0x18))=="StockSong");assert(append_stock_pack(api(),f.model,&d,make_probe_level,&ctx)==AlreadyPresent);}
 // Explicit environment is rooted/passed as a value struct to NEW basics only.
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.environment="WeaveEnvironment";
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Added);
  void* created=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);
  for(int j=0;j<5;++j){assert(key(ref(s->basics[created].at(j),0x18))=="WeaveEnvironment");
   assert(key(ref(s->basics[f.level].at(j),0x18))!="WeaveEnvironment");}
  assert(s->roots.empty());}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.environment="ForeignEnvironment";
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}
 // New menu objects belong ONLY to generated level and own pack.
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();Class preview_type={"StaticPreviewMediaData",0,NULL,{}},sprite_type={"Sprite",0,NULL,{}};
  void* own_preview=alloc(&preview_type);void* own_sprite=alloc(&sprite_type);
  c.menu_media=own_preview;c.menu_preview_duration=10;
  void* original_preview=ref(f.level,0x68);void* original_cover=ref(f.source,0x28);
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c,NULL,NULL,own_sprite)==Added);
  void* r=ref(f.model,0x50);void* added=s->repos[r].levels.at(kProbeLevelId);void* pack=s->repos[r].packs.at(kPackId);
  assert(ref(added,0x68)==own_preview&&ref(pack,0x28)==own_sprite&&ref(pack,0x30)==own_sprite);
  float start=-1,duration=-1;memcpy(&start,(char*)added+0x54,4);memcpy(&duration,(char*)added+0x58,4);
  assert(start==0&&duration==10&&ref(f.level,0x68)==original_preview&&ref(f.source,0x28)==original_cover);}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.menu_media=f.level;c.menu_preview_duration=10;
  Diagnostic d;assert(append_stock_pack(api(),f.model,&d,make_probe_level,&c)==Incompatible);f.unchanged();}
 // Per-difficulty full-map metadata must not use nine notes/NJS10 everywhere.
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();ProbeDifficulty stats[5];
  for(int i=0;i<5;++i)stats[i]={kProbeNotes[i],kProbeBombs[i],kProbeObstacles[i],kProbeNjs[i],kProbeJumpOffset[i]};
  c.spec={kProbeLevelId,kProbeTitle,kProbeBpm,kProbeDuration,312,stats,kProbeAuthor};
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Added);
  void* level=s->repos[ref(f.model,0x50)].levels.at(kProbeLevelId);
  for(int i=0;i<5;++i){void* b=s->basics[level].at(i);int32_t n,cut,walls,bombs;float njs,off;
   memcpy(&n,(char*)b+0x28,4);memcpy(&cut,(char*)b+0x2c,4);memcpy(&walls,(char*)b+0x30,4);memcpy(&bombs,(char*)b+0x34,4);
   memcpy(&njs,(char*)b+0x10,4);memcpy(&off,(char*)b+0x14,4);
   assert(cut==stats[i].notes&&bombs==stats[i].bombs&&n==cut+bombs&&walls==stats[i].obstacles);
   assert(njs==stats[i].njs&&off==stats[i].jump_offset);}
  float duration;memcpy(&duration,(char*)level+0x5c,4);assert(duration==kProbeDuration);assert(s->roots.empty());}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();ProbeDifficulty stats[5];
  for(int i=0;i<5;++i)stats[i]={9,0,0,10,0};stats[3].njs=-1;c.spec.difficulties=stats;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}
 for(int n=1;n<=22;++n){Fixture f;configure_probe(f);ProbeContext c=probe_context();s->fail_alloc=n;
  Result r=append_stock_pack(api(),f.model,NULL,make_probe_level,&c);assert(r==AllocationFailed);f.unchanged();}
 for(int n=1;n<=27;++n){Fixture f;configure_probe(f);ProbeContext c=probe_context();s->fail_root=n;
  Result r=append_stock_pack(api(),f.model,NULL,make_probe_level,&c);if(r!=Added){assert(r==AllocationFailed);f.unchanged();}else assert(s->roots.empty());}
 for(int n=1;n<=51;++n){Fixture f;configure_probe(f);ProbeContext c=probe_context();s->throw_at=n;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==ManagedException);f.unchanged();}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();bad_value_size=true;Diagnostic d;
  assert(append_stock_pack(api(),f.model,&d,make_probe_level,&c)==Incompatible);assert(!strcmp(d.stage,"probe-key-array-class-size"));f.unchanged();bad_value_size=false;}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.level_id="StockSong";
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();c.spec.level_id="bsd_additive_collision";
  for(auto& pair:s->repos)pair.second.levels[c.spec.level_id]=f.level;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==VerificationFailed);f.unchanged();}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();key_c.fields["difficulty"].offset=28;
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}
 {Fixture f;configure_probe(f);ProbeContext c=probe_context();s->basics[f.level].erase(2);
  assert(append_stock_pack(api(),f.model,NULL,make_probe_level,&c)==Incompatible);f.unchanged();}

 // Local/free classification uses ONLY our bound IDs, before model writes.
 {Fixture f;configure_probe(f);configure_local(f);Diagnostic d;
  assert(local_register(f,&d)==Added);assert(local_set(f,0).count(kProbeLevelId));assert(local_set(f,1).count(kPackId));
  assert(local_set(f,0).count("StockSong")&&local_set(f,1).count("OST1"));assert(s->roots.empty());
  auto before=s->sets;int writes=s->writes;assert(local_register(f,&d)==AlreadyPresent);
  assert(s->sets==before&&s->writes==writes&&s->roots.empty());}
 // Any early core failure MUST leave membership entirely untouched.
 {Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;s->corrupt_array=true;Diagnostic d;
  assert(local_register(f,&d)==VerificationFailed);assert(s->sets==before&&s->set_calls==0);f.unchanged();}
 // Every ordinary call exception, including AFTER mutation, rolls back own additions.
 for(int n=1;n<=6;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;Diagnostic d;
  s->set_throw_at=n;assert(local_register(f,&d)==ManagedException);assert(s->sets==before);f.unchanged();}
 for(int n: {3,5}){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;Diagnostic d;
  s->set_throw_after=n;assert(local_register(f,&d)==ManagedException);assert(s->sets==before);f.unchanged();}
 {Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;s->drop_set_add=true;Diagnostic d;
  assert(local_register(f,&d)==VerificationFailed);assert(s->sets==before);f.unchanged();}
 // Model publication fails AFTER classification: restore model AND memberships.
 {Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;s->drop_ref_at=2;Diagnostic d;
  assert(local_register(f,&d)==PublicationRestored);assert(s->sets==before&&s->roots.empty());
  for(int i=0;i<3;++i)assert(ref(f.model,i==0?0x10:i==1?0x50:0x58)==f.original[i]);}
 {Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;
  local_set(f,0)[kProbeLevelId]=true;before=s->sets;s->drop_ref_at=2;Diagnostic d;
  assert(local_register(f,&d)==PublicationRestored);assert(s->sets==before&&s->roots.empty());}
 {Fixture f;configure_probe(f);configure_local(f);s->drop_ref_at=2;s->drop_set_remove=true;Diagnostic d;
  assert(local_register(f,&d)==PublicationUnsafe);assert(!strcmp(d.stage,"local-free-rollback-verification"));assert(s->roots.empty());}
 {Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;
  entitlement_c.fields["_alwaysOwnedPacksIds"].offset=0x28;Diagnostic d;
  assert(local_register(f,&d)==Incompatible);assert(s->sets==before);f.unchanged();}
 {Fixture f;configure_probe(f);configure_local(f);s->bad_boolean=true;Diagnostic d;
  assert(local_register(f,&d)==VerificationFailed);assert(s->set_calls==1);f.unchanged();}
 // New boxed bool allocations and context roots also fail safely.
 for(int n=1;n<=28;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;Diagnostic d;
  s->fail_alloc=n;Result r=local_register(f,&d);assert(r==AllocationFailed||r==VerificationFailed);
  assert(s->sets==before);f.unchanged();}
 for(int n=1;n<=36;++n){Fixture f;configure_probe(f);configure_local(f);auto before=s->sets;Diagnostic d;
  s->fail_root=n;Result r=local_register(f,&d);if(r!=Added){assert(r==AllocationFailed||r==Incompatible||r==VerificationFailed);assert(s->sets==before);f.unchanged();}else assert(s->roots.empty());}
 // Failed early API gate cannot authorize even our own ID; DLC ID rejected.
 {Fixture f;configure_local(f);Api a=api();Diagnostic d;LocalContent local(a,unbox,bool_size);
  assert(local.prepare(f.model,string_new("PaidDlcPack"),string_new(kProbeLevelId),&d)==Incompatible);
  assert(s->set_calls==0);}
 puts("additive synthetic success, idempotence, allocation/root/exception/metadata/lookup rollback checks passed");
}
