// Exp305: bounded menu media, created through real managed Unity APIs ONLY on
// the game's LoadAll caller. No native-worker Unity calls, fabricated objects,
// delegates, Task blocking, address offsets or stock preview mutation.
#pragma once
#include "additive_song_packs.h"
namespace BsdAdditive {
struct MenuApis {
    void* (*domain_get)();
    const void** (*domain_get_assemblies)(void*,size_t*);
    void* (*assembly_get_image)(const void*);
    void* (*class_from_name)(void*,const char*,const char*);
    void* (*object_unbox)(void*);
    int32_t (*class_value_size)(void*,uint32_t*);
};
struct MediaBytes { const unsigned char* data; size_t size; };
inline uint16_t media_u16(const unsigned char* p){return (uint16_t)(p[0]|(p[1]<<8));}
inline uint32_t media_u32(const unsigned char* p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
inline bool preview_pcm(MediaBytes wav,const unsigned char** pcm,size_t* samples){
    if(!wav.data||wav.size<44||wav.size>6000000||memcmp(wav.data,"RIFF",4)||
       memcmp(wav.data+8,"WAVE",4)||media_u32(wav.data+4)!=wav.size-8)return false;
    bool format=false,data=false;size_t at=12;
    while(at+8<=wav.size){
        const unsigned char* h=wav.data+at;size_t n=media_u32(h+4);at+=8;
        if(n>wav.size-at)return false;
        if(!memcmp(h,"fmt ",4)){
            if(format||n<16||media_u16(wav.data+at)!=1||media_u16(wav.data+at+2)!=2||
               media_u32(wav.data+at+4)!=44100||media_u32(wav.data+at+8)!=176400||
               media_u16(wav.data+at+12)!=4||media_u16(wav.data+at+14)!=16)return false;
            format=true;
        }else if(!memcmp(h,"data",4)){
            if(data||n%4||n<176400||n>30*176400)return false;
            data=true;*pcm=wav.data+at;*samples=n/2;
        }
        at+=n;
        if(n&1){if(at==wav.size)return false;++at;}
    }
    return format&&data&&at==wav.size;
}
inline bool media_named(const Api& a,void* klass,const char* ns,const char* name){
    if(!klass)return false;
    const char* n=a.class_get_name(klass);const char* s=a.class_get_namespace(klass);
    return n&&s&&!strcmp(n,name)&&!strcmp(s,ns);
}
// Persistent handles intentionally last until title exit. Partial failures are
// bounded and NOT retried: Unity native resources cannot safely be destroyed
// from module_stop on an arbitrary thread. No repeated-load cache growth.
struct MenuMedia {
    void* preview=NULL;void* pack_sprite=NULL;int state=0;
    uint32_t handles[8]={};size_t handle_count=0;
    bool retain(const Api& a,void* o){
        if(!o||handle_count>=8)return false;
        uint32_t h=a.gchandle_new(o,true);if(!h)return false;
        handles[handle_count++]=h;return true;
    }
    void* find(const Api& a,const MenuApis& e,const char* ns,const char* name){
        size_t n=0;void* domain=e.domain_get();if(!domain)return NULL;
        const void** assemblies=e.domain_get_assemblies(domain,&n);
        if(!assemblies||!n||n>256)return NULL;
        void* result=NULL;
        for(size_t i=0;i<n;++i){
            void* image=e.assembly_get_image(assemblies[i]);if(!image)continue;
            void* c=e.class_from_name(image,ns,name);if(!c)continue;
            if(!media_named(a,c,ns,name)||(result&&result!=c))return NULL;
            result=c;
        }
        return result;
    }
    void* array(const Api& a,Roots& roots,void* elem,size_t n,size_t width){
        void* o=a.array_new(elem,n);if(!roots.keep(o))return NULL;
        void* c=a.object_get_class(o);size_t header=0;void* bounds=NULL;
        memcpy(&header,(char*)o+24,8);memcpy(&bounds,(char*)o+16,8);
        if(!c||a.class_get_rank(c)!=1||a.class_get_element_class(c)!=elem||
           a.array_length(o)!=n||header!=n||bounds||!width)return NULL;
        return o;
    }
    bool boolean(const Api& a,const MenuApis& e,Roots& roots,void* o){
        if(!roots.keep(o)||!media_named(a,a.object_get_class(o),"System","Boolean"))return false;
        void* p=e.object_unbox(o);return p&&*(unsigned char*)p==1;
    }
    int32_t integer(const Api& a,const MenuApis& e,Roots& roots,void* o){
        if(!roots.keep(o)||!media_named(a,a.object_get_class(o),"System","Int32"))return -1;
        void* p=e.object_unbox(o);int32_t value=-1;if(p)memcpy(&value,p,4);return value;
    }
    void* sprite(const Api& a,const MenuApis& e,Roots& roots,MediaBytes bytes,
                 void* texture_c,void* image_c,void* sprite_c,void* byte_c,bool* threw){
        if(!bytes.data||bytes.size<24||bytes.size>2000000||memcmp(bytes.data,"\x89PNG\r\n\x1a\n",8))return NULL;
        const void* ctor=a.class_get_method_from_name(texture_c,".ctor",2);
        const void* load=a.class_get_method_from_name(image_c,"LoadImage",2);
        // Exact PS4 dump has TWO Create(...,3) overloads: internal
        // (Rect,Vector2,float) creates WITHOUT texture and precedes the public
        // (Texture2D,Rect,Vector2). Name+arity3 is unsafe. Five args are unique
        // on this pinned build: (Texture2D,Rect,Vector2,float,uint).
        const void* create=a.class_get_method_from_name(sprite_c,"Create",5);
        const void* get_texture=a.class_get_method_from_name(sprite_c,"get_texture",0);
        const void* width=a.class_get_method_from_name(texture_c,"get_width",0);
        const void* height=a.class_get_method_from_name(texture_c,"get_height",0);
        if(!ctor||!load||!create||!get_texture||!width||!height)return NULL;
        void* texture=a.object_new(texture_c);if(!retain(a,texture))return NULL;
        int32_t small=2;void* args[]={&small,&small};invoke(a,ctor,texture,args,threw);if(*threw)return NULL;
        void* png=array(a,roots,byte_c,bytes.size,1);if(!png)return NULL;
        memcpy((char*)png+32,bytes.data,bytes.size);
        void* load_args[]={texture,png};void* ok=invoke(a,load,NULL,load_args,threw);
        if(*threw||!boolean(a,e,roots,ok))return NULL;
        void* w=invoke(a,width,texture,NULL,threw);if(*threw)return NULL;
        if(integer(a,e,roots,w)!=512)return NULL;
        void* h=invoke(a,height,texture,NULL,threw);if(*threw)return NULL;
        if(integer(a,e,roots,h)!=512)return NULL;
        float rect[]={0,0,512,512},pivot[]={0.5f,0.5f};
        float pixels_per_unit=100.0f;uint32_t extrude=0;
        void* create_args[]={texture,rect,pivot,&pixels_per_unit,&extrude};
        void* result=invoke(a,create,NULL,create_args,threw);
        if(*threw||!result||!media_named(a,a.object_get_class(result),"UnityEngine","Sprite")||!retain(a,result))return NULL;
        // Managed class/root != valid native artwork. The pack-detail screen
        // dereferences sprite.texture in Blur without a null guard. Refuse
        // BEFORE publication if construction returned a textureless/wrong sprite.
        void* attached=invoke(a,get_texture,result,NULL,threw);
        if(*threw||attached!=texture)return NULL;
        return result;
    }
    Result build(const Api& a,const MenuApis& e,MediaBytes song,MediaBytes pack,
                 MediaBytes wav,Diagnostic* d){
        if(state==1)return Added;
        if(state<0)return refuse(d,"menu-previous-build-failed-no-retry");
        state=-1;
        if(!complete(a)||!e.domain_get||!e.domain_get_assemblies||!e.assembly_get_image||
           !e.class_from_name||!e.object_unbox||!e.class_value_size)return refuse(d,"menu-public-apis");
        const unsigned char* pcm=NULL;size_t samples=0;
        if(!preview_pcm(wav,&pcm,&samples))return refuse(d,"menu-pcm-format");
        void* tc=find(a,e,"UnityEngine","Texture2D"),*ic=find(a,e,"UnityEngine","ImageConversion");
        void* sc=find(a,e,"UnityEngine","Sprite"),*rc=find(a,e,"UnityEngine","Rect");
        void* vc=find(a,e,"UnityEngine","Vector2"),*ac=find(a,e,"UnityEngine","AudioClip");
        void* bc=find(a,e,"System","Byte"),*fc=find(a,e,"System","Single");
        void* pc=find(a,e,"","StaticPreviewMediaData");
        if(!tc||!ic||!sc||!rc||!vc||!ac||!bc||!fc||!pc)return refuse(d,"menu-managed-classes");
        uint32_t align=0;
        if(e.class_value_size(rc,&align)!=16||align!=4||e.class_value_size(vc,&align)!=8||align!=4||
           e.class_value_size(fc,&align)!=4||align!=4||e.class_value_size(bc,&align)!=1||align!=1)
            return refuse(d,"menu-value-abi");
        const void* create=a.class_get_method_from_name(ac,"Create",5);
        const void* set=a.class_get_method_from_name(ac,"SetData",2);
        const void* ctor=a.class_get_method_from_name(pc,".ctor",2);
        void* cf=field(a,pc,"_coverSprite",0x10),*af=field(a,pc,"_previewAudioClip",0x18);
        if(!create||!set||!ctor||!cf||!af)return refuse(d,"menu-audio-preview-metadata");
        Roots roots(a);bool threw=false;
        if(d)d->stage="menu-song-sprite";
        void* cover=sprite(a,e,roots,song,tc,ic,sc,bc,&threw);
        if(!cover)return threw?ManagedException:refuse(d,"menu-song-sprite");
        if(d)d->stage="menu-pack-sprite";
        void* pack_image=sprite(a,e,roots,pack,tc,ic,sc,bc,&threw);
        if(!pack_image)return threw?ManagedException:refuse(d,"menu-pack-sprite");
        void* name=a.string_new("BSD custom preview");if(!roots.keep(name))return AllocationFailed;
        int32_t frames=(int32_t)(samples/2),channels=2,frequency=44100;bool stream=false;
        void* args[]={name,&frames,&channels,&frequency,&stream};
        if(d)d->stage="menu-audio-create";
        void* clip=invoke(a,create,NULL,args,&threw);
        if(threw)return ManagedException;
        if(!clip||!media_named(a,a.object_get_class(clip),"UnityEngine","AudioClip")||!retain(a,clip))
            return refuse(d,"menu-audio-create");
        const char* getters[]={"get_samples","get_channels","get_frequency"};
        const int32_t expected[]={frames,channels,frequency};
        for(int i=0;i<3;++i){
            const void* getter=a.class_get_method_from_name(ac,getters[i],0);
            if(!getter)return refuse(d,"menu-audio-getter");
            if(d)d->stage="menu-audio-properties";
            void* value=invoke(a,getter,clip,NULL,&threw);if(threw)return ManagedException;
            if(integer(a,e,roots,value)!=expected[i])return refuse(d,"menu-audio-properties");
        }
        void* floats=array(a,roots,fc,samples,4);if(!floats)return AllocationFailed;
        for(size_t i=0;i<samples;++i){
            uint16_t u=media_u16(pcm+2*i);int32_t v=(u&0x8000)?(int32_t)u-65536:(int32_t)u;
            float value=(float)v/32768.0f;memcpy((char*)floats+32+4*i,&value,4);
        }
        int32_t offset=0;void* set_args[]={floats,&offset};
        if(d)d->stage="menu-audio-setdata";
        void* ok=invoke(a,set,clip,set_args,&threw);if(threw)return ManagedException;
        if(!boolean(a,e,roots,ok))return refuse(d,"menu-audio-setdata");
        void* media=a.object_new(pc);if(!retain(a,media))return AllocationFailed;
        if(d)d->stage="menu-preview-ctor";
        void* ctor_args[]={cover,clip};invoke(a,ctor,media,ctor_args,&threw);if(threw)return ManagedException;
        if(read_ref(a,media,cf)!=cover||read_ref(a,media,af)!=clip)return refuse(d,"menu-preview-readback");
        preview=media;pack_sprite=pack_image;state=1;
        if(d)d->stage="menu-media-ready-cached";
        return Added;
    }
};
} // namespace
