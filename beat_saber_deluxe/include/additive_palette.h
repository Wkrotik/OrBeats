// Owned 2.04 ColorScheme layout/13-argument copy ctor. Only generated copies.
#pragma once
namespace BsdAdditive {
// Only already-loaded genuine Unity environment assets. No scene load, hardcoded
// colours, synthetic SOs or guessed native calls. Used only for a null override.
struct PaletteApis {
    void* (*domain_get)();
    const void** (*domain_get_assemblies)(void*,size_t*);
    void* (*assembly_get_image)(const void*);
    void* (*class_from_name)(void*,const char*,const char*);
    const void* (*class_get_type)(void*);
    void* (*type_get_object)(const void*);
};
inline void* palette_class(const Api& a,const PaletteApis& e,const char* ns,const char* name){
    void* domain=e.domain_get();size_t count=0;if(!domain)return NULL;
    const void** assemblies=e.domain_get_assemblies(domain,&count);
    if(!assemblies||!count||count>256)return NULL;void* result=NULL;
    for(size_t i=0;i<count;++i){void* image=e.assembly_get_image(assemblies[i]);
        if(!image)continue;void* c=e.class_from_name(image,ns,name);if(!c)continue;
        const char* n=a.class_get_name(c);const char* space=a.class_get_namespace(c);
        if(!n||!space||strcmp(n,name)||strcmp(space,ns)||(result&&result!=c))return NULL;
        result=c;
    }return result;
}
inline bool palette_environment_equal(const Api& a,void* lhs,void* rhs){
    if(!lhs||!rhs)return false;int32_t n=a.string_length(lhs);
    if(n<=0||n>=64||a.string_length(rhs)!=n)return false;
    const uint16_t* l=a.string_chars(lhs);const uint16_t* r=a.string_chars(rhs);
    return l&&r&&!memcmp(l,r,(size_t)n*2);
}
inline Result environment_palette(const Api& a,Roots& roots,const PaletteApis* e,
                                  void* environment,void** output,Diagnostic* d){
    if(!e||!e->domain_get||!e->domain_get_assemblies||!e->assembly_get_image||
       !e->class_from_name||!e->class_get_type||!e->type_get_object)
        return refuse(d,"palette-environment-apis");
    void* ec=palette_class(a,*e,"","EnvironmentInfoSO");
    void* rc=palette_class(a,*e,"UnityEngine","Resources");
    if(!ec||!rc||!environment)return refuse(d,"palette-environment-classes");
    const void* type=e->class_get_type(ec);if(!type)return refuse(d,"palette-environment-type");
    void* reflection=e->type_get_object(type);if(!roots.keep(reflection))return AllocationFailed;
    const void* find=a.class_get_method_from_name(rc,"FindObjectsOfTypeAll",1);
    if(!find)return refuse(d,"palette-environment-find-method");
    bool threw=false;void* args[]={reflection};void* all=invoke(a,find,NULL,args,&threw);
    if(threw)return ManagedException;if(!roots.keep(all))return refuse(d,"palette-environment-array-null");
    void* ac=a.object_get_class(all);if(!ac)return refuse(d,"palette-environment-array-class");
    int rank=a.class_get_rank(ac);void* element=a.class_get_element_class(ac);
    const char* element_ns=element?a.class_get_namespace(element):NULL;
    const char* element_name=element?a.class_get_name(element):NULL;
    if(d){d->palette_rank=rank;d->palette_element=element_name;d->palette_element_ns=element_ns;}
    if(rank!=1)return refuse(d,"palette-environment-array-rank");
    size_t count=a.array_length(all),stored=0;void* bounds=NULL;
    memcpy(&bounds,(char*)all+16,8);memcpy(&stored,(char*)all+24,8);
    if(d){d->palette_count=count;d->palette_stored=stored;d->palette_bounds=bounds!=NULL;}
    if(bounds||stored!=count||count>256)return refuse(d,"palette-environment-array-layout");
    // A managed Object[] return declaration permits a covariant requested-type
    // SZARRAY. Only these two exact element identities are accepted; every entry
    // below must still be the genuine requested EnvironmentInfoSO class.
    const bool object_element=element_name&&element_ns&&
        !strcmp(element_name,"Object")&&!strcmp(element_ns,"UnityEngine");
    if(element!=ec&&!object_element)return refuse(d,"palette-environment-array-element");
    void* nf=field(a,ec,"_serializedName",0x30);void* cf=field(a,ec,"_colorScheme",0x20);
    if(!nf||!cf)return refuse(d,"palette-environment-layout");
    void* found=NULL;
    for(size_t i=0;i<count;++i){void* o=NULL;memcpy(&o,(char*)all+32+i*8,8);
        if(!o||a.object_get_class(o)!=ec)return refuse(d,"palette-environment-object-class");
        if(!palette_environment_equal(a,read_ref(a,o,nf),environment))continue;
        if(found&&found!=o)return refuse(d,"palette-environment-ambiguous");found=o;
    }
    if(!found)return refuse(d,"palette-environment-not-loaded");
    if(!roots.keep(found))return AllocationFailed;
    void* so=read_ref(a,found,cf);void* sc=so?a.object_get_class(so):NULL;
    if(!named(a,sc,"ColorSchemeSO"))return refuse(d,"palette-environment-scheme-so");
    void* sf=field(a,sc,"_colorScheme",0x18);if(!sf)return refuse(d,"palette-environment-scheme-layout");
    void* scheme=read_ref(a,so,sf);
    if(!scheme||!named(a,a.object_get_class(scheme),"ColorScheme"))return refuse(d,"palette-environment-scheme-null");
    if(!roots.keep(scheme))return AllocationFailed;*output=scheme;return Added;
}
inline Result copy_authored_palette(const Api& a,Roots& roots,void* source,const ProbePalette& palette,
                                    void** output,Diagnostic* d){
    if(!source||palette.mask>511)return refuse(d,"palette-source-or-mask");
    void* c=a.object_get_class(source);if(!named(a,c,"ColorScheme"))return refuse(d,"palette-source-class");
    const char* names[]={"_saberAColor","_saberBColor","_environmentColor0","_environmentColor1","_environmentColorW",
        "_environmentColor0Boost","_environmentColor1Boost","_environmentColorWBoost","_obstaclesColor"};
    const size_t offsets[]={0x34,0x44,0x68,0x78,0x88,0x9c,0xac,0xbc,0x54};
    float values[9][4];
    for(size_t i=0;i<9;++i){void* f=field(a,c,names[i],offsets[i]);if(!f)return refuse(d,"palette-color-layout");
        a.field_get_value(source,f,values[i]);
        if(palette.mask&(1u<<i))memcpy(values[i],palette.colors[i],16);
        for(size_t k=0;k<4;++k)if(!isfinite(values[i][k])||((palette.mask&(1u<<i))&&(values[i][k]<0||values[i][k]>1)))return refuse(d,"palette-color-bounds");
    }
    bool notes=false,lights=false,boost=false;
    const char* flags[]={"_overrideNotes","_overrideLights","_supportsEnvironmentColorBoost"};
    const size_t flag_offsets[]={0x31,0x64,0x98};bool* args_flags[]={&notes,&lights,&boost};
    for(size_t i=0;i<3;++i){void* f=field(a,c,flags[i],flag_offsets[i]);if(!f)return refuse(d,"palette-flag-layout");a.field_get_value(source,f,args_flags[i]);}
    if(palette.mask&259u)notes=true;if(palette.mask&252u)lights=true;if(palette.mask&224u)boost=true;
    const void* ctor=a.class_get_method_from_name(c,".ctor",13);if(!ctor)return refuse(d,"palette-copy-constructor");
    void* copy=a.object_new(c);if(!roots.keep(copy))return AllocationFailed;
    void* args[]={source,&notes,values[0],values[1],&lights,values[2],values[3],values[4],&boost,values[5],values[6],values[7],values[8]};
    bool threw=false;invoke(a,ctor,copy,args,&threw);if(threw)return ManagedException;
    for(size_t i=0;i<9;++i){float got[4];a.field_get_value(copy,field(a,c,names[i],offsets[i]),got);if(memcmp(got,values[i],16))return VerificationFailed;}
    *output=copy;return Added;
}
} // namespace
