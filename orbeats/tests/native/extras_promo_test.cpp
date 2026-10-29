// Actual production callback/installer; fake managed objects and detour boundary.
#define ORBEATS_TEST_DETOUR_IMPL
#include <assert.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <sys/mman.h>
#include <unistd.h>
#include "../../../orbeats_extras/src/promo.cpp"
using namespace OrBeatsExtras;
struct Class { const char* name;const char* ns;Class* parent=NULL; };
struct Object { Class* klass;Object* go;bool active=true; };
static Class menu_class={"MainMenuViewController",""},banner_class={"MusicPackPromoBanner",""},
 button_class={"Button","UnityEngine.UI"},game_class={"GameObject","UnityEngine"},wrong_class={"Other",""};
static Class derived_class={"NoTransitionsButton","",&button_class},cyclic_class={"OtherButton",""};
static Object menu_go={&game_class,NULL},banner_go={&game_class,NULL},button_go={&game_class,NULL},
 menu={&menu_class,&menu_go},banner={&banner_class,&banner_go},button={&button_class,&button_go};
static Object* banner_ref=&banner;static Object* button_ref=&button;
static Object solo={&button_class,NULL},online={&button_class,NULL},party={&button_class,NULL},campaign={&button_class,NULL};
static std::string scenario,logs;static unsigned originals=0,mutations=0,root_calls=0,live_roots=0,hook_calls=0;
static unsigned fail_root=0;static bool detour_fail=false;static const char* missing_symbol=NULL;
static uintptr_t expected_hook=0;static void* captured_callback=NULL;
static const char banner_field[]="_musicPackPromoBanner",button_field[]="_musicPackPromoButton";
static void log_line(const char* text){logs+=text;logs+='\n';}
static void* klass(void* p){return ((Object*)p)->klass;}
static const char* name(void* p){return ((Class*)p)->name;}
static const char* space(void* p){return ((Class*)p)->ns;}
static void* parent(void* p){return ((Class*)p)->parent;}
static void* field_fake(void* c,const char* n){assert(c==&menu_class);if(scenario=="field-missing")return NULL;if(!strcmp(n,banner_field))return (void*)banner_field;if(!strcmp(n,button_field))return (void*)button_field;assert(false);return NULL;}
static size_t offset(void* f){return scenario=="field-offset"?0x20:f==banner_field?0xc0:0xb8;}
static void field_read_fake(void* self,void* f,void* out){assert(self==&menu);void* p=f==banner_field?banner_ref:button_ref;memcpy(out,&p,8);}
static const void* method(void*,const char* n,int count){
 if(!strcmp(n,"get_gameObject")){assert(count==0);return scenario=="getter-missing"?NULL:(void*)1;}
 assert(!strcmp(n,"SetActive") && count==1);return scenario=="setter-missing"?NULL:(void*)2;
}
static void* invoke_fake(const void* m,void* p,void** args,void** exception){
 assert(originals>0); // No managed object invocations before original activation.
 if(m==(void*)1){assert(!args);if(scenario=="getter-throws"){*exception=(void*)3;return NULL;}return ((Object*)p)->go;}
 assert(m==(void*)2 && args && !*(bool*)args[0]);
 if(scenario=="setter-throws"){*exception=(void*)3;return NULL;}
 assert(p==&banner_go || p==&button_go);((Object*)p)->active=false;++mutations;return NULL;
}
static uint32_t root(void* p,bool pin){assert(p && pin);++root_calls;if(root_calls==fail_root)return 0;++live_roots;return root_calls;}
static void unroot(uint32_t h){assert(h && live_roots);--live_roots;}
static void original(void* self,bool first,bool added,bool enabling,const void* m){
 assert(self==&menu && added && !enabling && m==(void*)0x1234);assert(first==(originals==0));
 ++originals;banner_go.active=button_go.active=true;
}
void* Detour_DetourFunction(Detour* d,uint64_t target,void* callback){
 ++hook_calls;assert(target==expected_hook);captured_callback=callback;if(detour_fail)return NULL;d->StubPtr=(void*)original;return d->StubPtr;
}
static void* resolve(const char* symbol){
 if(missing_symbol && !strcmp(symbol,missing_symbol))return NULL;
#define SYMBOL(n,f) if(!strcmp(symbol,"il2cpp_" n))return (void*)f;
 SYMBOL("object_get_class",klass) SYMBOL("class_get_name",name) SYMBOL("class_get_namespace",space) SYMBOL("class_get_parent",parent)
 SYMBOL("class_get_field_from_name",field_fake) SYMBOL("field_get_offset",offset) SYMBOL("field_get_value",field_read_fake)
 SYMBOL("class_get_method_from_name",method) SYMBOL("runtime_invoke",invoke_fake)
 SYMBOL("gchandle_new",root) SYMBOL("gchandle_free",unroot)
#undef SYMBOL
 assert(false);return NULL;
}
static uintptr_t image_begin=0,image_end=0;
static bool executable(const void* p,size_t n){uintptr_t a=(uintptr_t)p;return a>=image_begin && a<=image_end && n<=image_end-a;}
__attribute__((no_sanitize("function"))) static int call_jit(void* p){return ((int(*)())p)();}
static void prefix_test(const unsigned char* owned){
 const unsigned char prefix[]={0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56,0x41,0x55,0x41,0x54,0x53,0x48,0x83,0xec,0x48};
 assert(!memcmp(owned,prefix,sizeof(prefix)));
 // Execute a synthetic17-byte prologue and SDK-style absolute-jump stub.
 // No private function body and no relative instruction relocation.
 const unsigned char tail[]={0x48,0x83,0xc4,0x48,0x5b,0x41,0x5c,0x41,0x5d,0x41,0x5e,0x41,0x5f,0x5d,0xb8,0x2a,0,0,0,0xc3};
 size_t page=(size_t)sysconf(_SC_PAGESIZE);auto* memory=(unsigned char*)mmap(NULL,page,7,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(memory!=MAP_FAILED);
 memcpy(memory,prefix,sizeof(prefix));memcpy(memory+17,tail,sizeof(tail));auto* stub=memory+128;memcpy(stub,prefix,17);
 stub[17]=0xff;stub[18]=0x25;memset(stub+19,0,4);uintptr_t continuation=(uintptr_t)(memory+17);memcpy(stub+23,&continuation,8);
 assert(call_jit(memory)==42 && call_jit(stub)==42);assert(!munmap(memory,page));
}
int main(int argc,char** argv){
 assert(argc>=2);scenario=argv[1];promo_log=log_line;
 if(scenario=="owned-profile"){
  assert(argc==3);FILE* f=fopen(argv[2],"rb");assert(f);assert(!fseek(f,0,SEEK_END));long size=ftell(f);assert(size>0);rewind(f);
  std::vector<unsigned char> image((size_t)size);assert(fread(image.data(),1,image.size(),f)==image.size());fclose(f);
  image_begin=(uintptr_t)image.data();image_end=image_begin+image.size();uintptr_t base=image_begin+0x4000;expected_hook=base+kPromoCode[0].rva;
  prefix_test((const unsigned char*)expected_hook);
  for(const auto& code:kPromoCode){auto* p=(unsigned char*)(base+code.rva);assert(fnv(p,code.bytes)==code.hash);*p^=1;
   assert(!install_promo(base,resolve,executable,log_line) && !promo_has_hooks() && !hook_calls);*p^=1;}
  const char* symbols[]={"object_get_class","class_get_name","class_get_namespace","class_get_parent","class_get_field_from_name","field_get_offset","field_get_value","class_get_method_from_name","runtime_invoke","gchandle_new","gchandle_free"};
  for(auto n:symbols){std::string full="il2cpp_"+std::string(n);missing_symbol=full.c_str();assert(!install_promo(base,resolve,executable,log_line) && !hook_calls);}
  missing_symbol=NULL;detour_fail=true;assert(!install_promo(base,resolve,executable,log_line) && !promo_has_hooks());detour_fail=false;
  assert(install_promo(base,resolve,executable,log_line) && promo_has_hooks() && hook_calls==2);
  assert(!install_promo(base,resolve,executable,log_line) && hook_calls==2 && !root_calls);
  assert(captured_callback==(void*)promo_activate);promo_activate(&menu,true,true,false,(void*)0x1234);
  assert(originals==1 && mutations==2 && !live_roots);return 0;
 }
 if(scenario=="profile-range" || scenario=="profile-overflow"){
  assert(!install_promo(scenario=="profile-overflow"?UINTPTR_MAX:1,resolve,executable,log_line));assert(!hook_calls && !root_calls && !promo_has_hooks());return 0;
 }
 promo_api={klass,name,space,parent,field_fake,offset,field_read_fake,method,invoke_fake,root,unroot};promo_hook.StubPtr=(void*)original;
 if(scenario=="wrong-view")menu.klass=&wrong_class;
 if(scenario=="wrong-banner")banner.klass=&wrong_class;
 if(scenario=="derived-button")button.klass=&derived_class;
 if(scenario=="cyclic-button"){cyclic_class.parent=&cyclic_class;button.klass=&cyclic_class;}
 if(scenario=="wrong-button")button.klass=&wrong_class;
 if(scenario=="null-banner")banner_ref=NULL;
 if(scenario=="null-button")button_ref=NULL;
 if(scenario=="menu-alias")banner.go=&menu_go;
 if(scenario=="bad-gameobject")banner_go.klass=&wrong_class;
 if(scenario=="null-class")banner.klass=NULL;
 if(scenario=="null-name")banner_class.name=NULL;
 if(scenario=="shared")button.go=&banner_go;
 if(scenario.find("root-")==0)fail_root=(unsigned)atoi(scenario.c_str()+5);
 promo_activate(&menu,true,true,false,(void*)0x1234);assert(originals==1 && !live_roots);
 bool success=scenario=="normal" || scenario=="repeat" || scenario=="shared" || scenario=="derived-button";
 if(success){
  assert(!banner_go.active && (scenario=="shared" || !button_go.active));assert(mutations==(scenario=="shared"?1u:2u));
  // Async loading/setup changes children only in the owned profile. A child
  // becoming active does not re-enable its inactive component root.
  bool child_active=true;assert(!(child_active && banner_go.active));
  if(scenario=="repeat"){promo_activate(&menu,false,true,false,(void*)0x1234);assert(originals==2 && mutations==4 && !live_roots && !banner_go.active && !button_go.active);}
 }else assert(!mutations && banner_go.active && button_go.active);
 assert(menu_go.active && solo.active && online.active && party.active && campaign.active);assert(!logs.empty());return 0;
}
