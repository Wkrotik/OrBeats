#include "promo.h"
#include "promo_profile.h"
#include <GoldHEN/Detour.h>
#include <atomic>
#include <string.h>
namespace OrBeatsExtras {
namespace {
// Resolved off the loader thread; invoked only inside the game's UI callback.
struct PromoApi {
    void* (*object_class)(void*);
    const char* (*class_name)(void*);
    const char* (*class_namespace)(void*);
    void* (*class_parent)(void*);
    void* (*class_field)(void*,const char*);
    size_t (*field_offset)(void*);
    void (*field_read)(void*,void*,void*);
    const void* (*method)(void*,const char*,int);
    void* (*invoke)(const void*,void*,void**,void**);
    uint32_t (*root)(void*,bool);
    void (*unroot)(uint32_t);
};
static PromoApi promo_api={};
static Detour promo_hook;
static std::atomic<bool> promo_hooked(false);
static void (*promo_log)(const char*)=NULL;
static void report(const char* text){if(promo_log)promo_log(text);}
static bool named(void* object,const char* name,const char* ns) {
    if(!object)return false;void* klass=promo_api.object_class(object);if(!klass)return false;
    const char* n=promo_api.class_name(klass);const char* space=promo_api.class_namespace(klass);
    return n && space && !strcmp(n,name) && !strcmp(space,ns);
}
static bool button_type(void* object) {
    // Unity prefabs may use a Button subclass; require its actual UI.Button
    // ancestry, not just an arbitrary component with a gameObject getter.
    if(!object)return false;
    void* klass=promo_api.object_class(object);
    for(unsigned depth=0;klass && depth<16;++depth,klass=promo_api.class_parent(klass)) {
        const char* n=promo_api.class_name(klass);const char* ns=promo_api.class_namespace(klass);
        if(n && ns && !strcmp(n,"Button") && !strcmp(ns,"UnityEngine.UI"))return true;
    }
    return false;
}
struct PromoRoots {
    uint32_t handles[6];size_t count=0;
    bool keep(void* p){if(!p || count==6)return false;uint32_t h=promo_api.root(p,true);if(!h)return false;handles[count++]=h;return true;}
    ~PromoRoots(){while(count)promo_api.unroot(handles[--count]);}
};
static bool invoke(const void* method,void* object,void** args,void** result=NULL) {
    if(!method || !object)return false;void* exception=NULL;
    void* value=promo_api.invoke(method,object,args,&exception);
    if(exception)return false;if(result)*result=value;return true;
}
static void* component_object(void* object) {
    const void* getter=promo_api.method(promo_api.object_class(object),"get_gameObject",0);
    void* result=NULL;
    return invoke(getter,object,NULL,&result)?result:NULL;
}
static bool hide_promo(void* self) {
    if(!named(self,"MainMenuViewController",""))return false;
    PromoRoots roots;if(!roots.keep(self))return false;
    void* klass=promo_api.object_class(self);
    void* banner_field=promo_api.class_field(klass,"_musicPackPromoBanner");
    void* button_field=promo_api.class_field(klass,"_musicPackPromoButton");
    if(!banner_field || !button_field || promo_api.field_offset(banner_field)!=0xc0 ||
       promo_api.field_offset(button_field)!=0xb8)return false;
    void* banner=NULL;void* button=NULL;
    promo_api.field_read(self,banner_field,&banner);promo_api.field_read(self,button_field,&button);
    if(!named(banner,"MusicPackPromoBanner","") || !button_type(button) ||
       !roots.keep(banner) || !roots.keep(button))return false;
    // Read only the explicit serialized references. No global object search,
    // guessed hierarchy paths, parent hiding or model/entitlement modification.
    void* menu_go=component_object(self);if(!roots.keep(menu_go))return false;
    void* banner_go=component_object(banner);if(!roots.keep(banner_go))return false;
    void* button_go=component_object(button);if(!roots.keep(button_go))return false;
    if(!named(menu_go,"GameObject","UnityEngine") || !named(banner_go,"GameObject","UnityEngine") ||
       !named(button_go,"GameObject","UnityEngine") || menu_go==banner_go || menu_go==button_go)return false;
    // Resolve every operation before the first mutation; a missing second
    // method must not produce a half-hidden tile. The two may share a GO.
    const void* set_banner=promo_api.method(promo_api.object_class(banner_go),"SetActive",1);
    const void* set_button=promo_api.method(promo_api.object_class(button_go),"SetActive",1);
    if(!set_banner || !set_button)return false;
    bool active=false;void* args[]={&active};
    if(!invoke(set_button,button_go,args))return false;
    return banner_go==button_go || invoke(set_banner,banner_go,args);
}
static void promo_activate(void* self,bool first,bool added,bool enabling,const void* method) {
    // Preserve all stock menu listeners and the original async promo model.
    // The verified17-byte prefix has no RIP-relative operands or branches.
    Detour_Stub(&promo_hook,void(*)(void*,bool,bool,bool,const void*),self,first,added,enabling,method);
    report(hide_promo(self)?"main-menu music-pack promotion hidden":"main-menu promo schema/invocation refused; no broader menu changes");
}
} // namespace
bool promo_has_hooks(){return promo_hooked.load();}
bool install_promo(uintptr_t base,void*(*resolve)(const char*),
                   bool(*executable)(const void*,size_t),void(*logger)(const char*)) {
    if(promo_hooked.load() || !base || !resolve || !executable)return false;
    promo_log=logger;
    for(size_t i=0;i<sizeof(kPromoCode)/sizeof(kPromoCode[0]);++i) {
        const CodeSpec& code=kPromoCode[i];
        if(code.rva>UINTPTR_MAX-base){report("promo code range refused");return false;}
        const unsigned char* p=(const unsigned char*)(base+code.rva);
        if(!executable(p,code.bytes) || fnv(p,code.bytes)!=code.hash){report("promo 2.04 profile mismatch/conflicting hook; unchanged");return false;}
    }
#define PROMO_RESOLVE(member,type,name) promo_api.member=(type)resolve(name);if(!promo_api.member){report("promo IL2CPP API unavailable; unchanged");return false;}
    PROMO_RESOLVE(object_class,void*(*)(void*),"il2cpp_object_get_class")
    PROMO_RESOLVE(class_name,const char*(*)(void*),"il2cpp_class_get_name")
    PROMO_RESOLVE(class_namespace,const char*(*)(void*),"il2cpp_class_get_namespace")
    PROMO_RESOLVE(class_parent,void*(*)(void*),"il2cpp_class_get_parent")
    PROMO_RESOLVE(class_field,void*(*)(void*,const char*),"il2cpp_class_get_field_from_name")
    PROMO_RESOLVE(field_offset,size_t(*)(void*),"il2cpp_field_get_offset")
    PROMO_RESOLVE(field_read,void(*)(void*,void*,void*),"il2cpp_field_get_value")
    PROMO_RESOLVE(method,const void*(*)(void*,const char*,int),"il2cpp_class_get_method_from_name")
    PROMO_RESOLVE(invoke,void*(*)(const void*,void*,void**,void**),"il2cpp_runtime_invoke")
    PROMO_RESOLVE(root,uint32_t(*)(void*,bool),"il2cpp_gchandle_new")
    PROMO_RESOLVE(unroot,void(*)(uint32_t),"il2cpp_gchandle_free")
#undef PROMO_RESOLVE
    Detour_Construct(&promo_hook,DetourMode_x64);
    if(!Detour_DetourFunction(&promo_hook,base+kPromoCode[0].rva,(void*)promo_activate)){
        report("promo activation detour failed; unchanged");return false;
    }
    promo_hooked.store(true);report("main-menu promo hiding installed; stock activation preserved");return true;
}
} // namespace
