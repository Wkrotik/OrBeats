// Exp305 actual invoke/array/value/reference ABI model; NOT a Unity emulator.
#include "additive_menu_media.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <map>
#include <string>
#include <vector>
using namespace BsdAdditive;
struct C {const char* ns;const char* name;int size,align;C* element=NULL;};
static C texture{"UnityEngine","Texture2D",0,0},image{"UnityEngine","ImageConversion",0,0},
 sprite_c{"UnityEngine","Sprite",0,0},rect_c{"UnityEngine","Rect",16,4},vec_c{"UnityEngine","Vector2",8,4},
 audio{"UnityEngine","AudioClip",0,0},byte_c{"System","Byte",1,1},single_c{"System","Single",4,4},
 preview_c{"","StaticPreviewMediaData",0,0},boolean_c{"System","Boolean",1,1},int_c{"System","Int32",4,4},
 string_c{"System","String",0,0},bytes_c{"System","Byte[]",0,0,&byte_c},floats_c{"System","Single[]",0,0,&single_c},
 duplicate{"UnityEngine","Texture2D",0,0};
static C* classes[]={&texture,&image,&sprite_c,&rect_c,&vec_c,&audio,&byte_c,&single_c,&preview_c};
struct M {C* c;std::string name;int count;};static std::map<std::string,M> methods;
struct S {
 std::vector<void*> allocations;std::map<uint32_t,void*> roots;
 int allocs=0,fail_alloc=0,root_calls=0,fail_root=0,calls=0,throw_at=0;
 bool duplicate_class=false,no_class=false,bad_bool=false,load_false=false,set_false=false,bad_readback=false;
 bool missing_method=false,bad_size=false,null_sprite_texture=false,wrong_sprite_texture=false,missing_texture_getter=false;int width=512;uint32_t next=1;
 int sprite_calls=0,audio_calls=0,set_calls=0,ambiguous_create_calls=0;void* last_clip=NULL;
 S();~S(){for(void* p:allocations)free(p);}
};static S* s;
S::S(){s=this;}
static void* alloc(C* c,size_t n=128){
 if(++s->allocs==s->fail_alloc)return NULL;
 void* o=calloc(1,n);assert(o);memcpy(o,&c,8);s->allocations.push_back(o);return o;
}
static void put(void* o,size_t off,void* p){memcpy((char*)o+off,&p,8);}
static C* klass(void* o){C* c;memcpy(&c,o,8);return c;}
static const char* name(void* c){return ((C*)c)->name;}
static const char* space(void* c){return ((C*)c)->ns;}
static void* field(void*,const char* n){static size_t cover=16,clip=24;if(!strcmp(n,"_coverSprite"))return &cover;if(!strcmp(n,"_previewAudioClip"))return &clip;return NULL;}
static size_t offset(void* f){return *(size_t*)f;}
static void read(void* o,void* f,void* out){memcpy(out,(char*)o+offset(f),8);}
static void write(void* o,void* f,void* value){put(o,offset(f),value);}
static const void* method(void* c,const char* n,int count){
 if(s->missing_method&&!strcmp(n,"Create"))return NULL;
 if(s->missing_texture_getter&&!strcmp(n,"get_texture"))return NULL;
 std::string key=std::string(name(c))+n+std::to_string(count);
 auto i=methods.emplace(key,M{(C*)c,n,count});return &i.first->second;
}
static void* object(void* c){return alloc((C*)c);}
static void* array(void* c,size_t n){
 C* ac=c==&byte_c?&bytes_c:c==&single_c?&floats_c:NULL;assert(ac);
 void* o=alloc(ac,32+n*((C*)c)->size);if(o)memcpy((char*)o+24,&n,8);return o;
}
static uintptr_t length(void* o){size_t n;memcpy(&n,(char*)o+24,8);return n;}
static int rank(void* c){return ((C*)c)->element?1:0;}
static void* element(void* c){return ((C*)c)->element;}
static void barrier(void*,void** slot,void* value){*slot=value;}
static uint32_t root(void* o,bool pin){assert(pin&&o);if(++s->root_calls==s->fail_root)return 0;uint32_t n=s->next++;s->roots[n]=o;return n;}
static void unroot(uint32_t n){assert(s->roots.erase(n)==1);}
static void* string(const char*){return alloc(&string_c);}
static int32_t string_len(void*){return 0;}
static const uint16_t* chars(void*){static uint16_t zero=0;return &zero;}
static void* box_int(int32_t n){void* o=alloc(&int_c);if(o)memcpy((char*)o+16,&n,4);return o;}
static void* box_bool(bool v){void* o=alloc(s->bad_bool?&int_c:&boolean_c);if(o)memcpy((char*)o+16,&v,1);return o;}
static void* invoke_mock(const void* method_,void* self,void** args,void** exception){
 if(++s->calls==s->throw_at){*exception=(void*)1;return NULL;}
 const M& m=*(const M*)method_;
 if(m.c==&texture&&m.name==".ctor"){
  assert(self&&m.count==2&&*(int32_t*)args[0]==2&&*(int32_t*)args[1]==2);return NULL;
 }
 if(m.c==&image){assert(!self&&m.name=="LoadImage"&&m.count==2&&klass(args[0])==&texture&&klass(args[1])==&bytes_c);return box_bool(!s->load_false);}
 if(m.name=="get_width"||m.name=="get_height"){assert(self);return box_int(s->width);}
 if(m.c==&sprite_c&&m.name=="get_texture"){
  assert(self&&m.count==0&&!args);void* t=NULL;memcpy(&t,(char*)self+16,8);return t;
 }
 if(m.c==&sprite_c&&m.name=="Create"&&m.count==3){
  // Real metadata resolves the FIRST arity3: internal(Rect,Vector2,float),
  // not public(Texture2D,Rect,Vector2). It creates a textureless Sprite.
  assert(!self);++s->ambiguous_create_calls;return alloc(&sprite_c);
 }
 if(m.c==&sprite_c){
  assert(!self&&m.name=="Create"&&m.count==5&&klass(args[0])==&texture);
  assert(*(float*)args[3]==100.0f&&*(uint32_t*)args[4]==0);
  float* r=(float*)args[1];float* p=(float*)args[2];assert(r[0]==0&&r[1]==0&&r[2]==512&&r[3]==512&&p[0]==0.5f&&p[1]==0.5f);
  ++s->sprite_calls;void* o=alloc(&sprite_c);
  if(o&&!s->null_sprite_texture)put(o,16,s->wrong_sprite_texture?o:args[0]);
  return o;
 }
 if(m.c==&audio&&m.name=="Create"){
  assert(!self&&m.count==5&&klass(args[0])==&string_c&&*(int32_t*)args[1]==44100&&*(int32_t*)args[2]==2&&*(int32_t*)args[3]==44100&&!*(bool*)args[4]);
  ++s->audio_calls;return s->last_clip=alloc(&audio);
 }
 if(m.c==&audio&&m.name=="SetData"){
  assert(self==s->last_clip&&klass(args[0])==&floats_c&&*(int32_t*)args[1]==0&&length(args[0])==88200);
  float* f=(float*)((char*)args[0]+32);assert(f[0]==-1.0f&&f[1]==32767.0f/32768.0f&&f[2]==0);
  ++s->set_calls;return box_bool(!s->set_false);
 }
 if(m.c==&audio){assert(self==s->last_clip);return box_int(m.name=="get_channels"?2:44100);}
 if(m.c==&preview_c){
  assert(self&&m.name==".ctor"&&m.count==2&&klass(args[0])==&sprite_c&&klass(args[1])==&audio);
  if(!s->bad_readback){put(self,16,args[0]);put(self,24,args[1]);}return NULL;
 }
 assert(false);return NULL;
}
static Api api(){return {[](void* o)->void*{return klass(o);},name,space,field,offset,read,write,method,object,invoke_mock,array,length,rank,element,barrier,root,unroot,string,string_len,chars};}
static int d1,d2;
static void* domain(){return &d1;}
static const void** assemblies(void*,size_t* n){static const void* a[]={&d1,&d2};*n=2;return a;}
static void* image_of(const void* a){return (void*)a;}
static void* find(void* image,const char* ns,const char* n){
 if(s->no_class)return NULL;
 if(image==&d2)return s->duplicate_class&&!strcmp(n,"Texture2D")?&duplicate:NULL;
 for(C* c:classes)if(!strcmp(ns,c->ns)&&!strcmp(n,c->name))return c;
 return NULL;
}
static void* unbox(void* o){return (char*)o+16;}
static int32_t size(void* c,uint32_t* align){*align=((C*)c)->align;return s->bad_size?123:((C*)c)->size;}
static MenuApis extra(){return {domain,assemblies,image_of,find,unbox,size};}
static void u32(std::vector<unsigned char>& b,size_t off,uint32_t n){for(int i=0;i<4;++i)b[off+i]=(unsigned char)(n>>(i*8));}
static std::vector<unsigned char> wave(){
 std::vector<unsigned char> b(44+176400);memcpy(b.data(),"RIFF",4);u32(b,4,(uint32_t)b.size()-8);memcpy(b.data()+8,"WAVEfmt ",8);u32(b,16,16);
 b[20]=1;b[22]=2;u32(b,24,44100);u32(b,28,176400);b[32]=4;b[34]=16;memcpy(b.data()+36,"data",4);u32(b,40,176400);
 b[45]=128;b[46]=255;b[47]=127;return b;
}
static Result build(MenuMedia& m,Diagnostic* d=NULL){
 unsigned char png[24]={};memcpy(png,"\x89PNG\r\n\x1a\n",8);auto w=wave();
 return m.build(api(),extra(),{png,sizeof(png)},{png,sizeof(png)},{w.data(),w.size()},d);
}
int main(){
 {S fixture;MenuMedia a,b;assert(build(a)==Added&&build(b)==Added);
  assert(a.preview!=b.preview&&a.pack_sprite!=b.pack_sprite&&fixture.roots.size()==12);
  void* ac=NULL;void* bc=NULL;memcpy(&ac,(char*)a.preview+24,8);memcpy(&bc,(char*)b.preview+24,8);
  void* as=NULL;void* bs=NULL;memcpy(&as,(char*)a.preview+16,8);memcpy(&bs,(char*)b.preview+16,8);
  assert(ac&&bc&&ac!=bc&&as&&bs&&as!=bs);
  int calls=fixture.calls;assert(a.build(api(),extra(),{},{},{},NULL)==Added);
  assert(b.build(api(),extra(),{},{},{},NULL)==Added&&fixture.calls==calls&&fixture.roots.size()==12);
 }

 {S fixture;MenuMedia m;Diagnostic d;assert(build(m,&d)==Added);assert(m.preview&&m.pack_sprite&&m.handle_count==6&&fixture.roots.size()==6);
  assert(fixture.sprite_calls==2&&fixture.audio_calls==1&&fixture.set_calls==1&&fixture.ambiguous_create_calls==0);int calls=fixture.calls;
  assert(m.build(api(),extra(),{}, {}, {},&d)==Added);assert(fixture.calls==calls&&fixture.roots.size()==6);}
 for(int i=1;i<=20;++i){S fixture;fixture.fail_alloc=i;MenuMedia m;Result r=build(m);assert(r!=Added);int calls=fixture.calls;assert(build(m)!=Added&&fixture.calls==calls&&m.handle_count<=6);}
 for(int i=1;i<=20;++i){S fixture;fixture.fail_root=i;MenuMedia m;assert(build(m)!=Added&&m.handle_count<=6);}
 for(int i=1;i<=18;++i){S fixture;fixture.throw_at=i;MenuMedia m;assert(build(m)==ManagedException);}
 {S fixture;MenuMedia m;const void* ambiguous=method(&sprite_c,"Create",3);void* exception=NULL;void* args[]={NULL,NULL,NULL};
  void* o=invoke_mock(ambiguous,NULL,args,&exception);assert(o&&!exception&&fixture.ambiguous_create_calls==1);
  assert(invoke_mock(method(&sprite_c,"get_texture",0),o,NULL,&exception)==NULL);
  assert(build(m)==Added&&fixture.ambiguous_create_calls==1);}
 {S fixture;fixture.null_sprite_texture=true;MenuMedia m;Diagnostic d;
  assert(build(m,&d)==Incompatible&&!strcmp(d.stage,"menu-song-sprite")&&!m.preview&&!m.pack_sprite&&fixture.audio_calls==0);}
 {S fixture;fixture.wrong_sprite_texture=true;MenuMedia m;assert(build(m)==Incompatible&&!m.preview&&!m.pack_sprite&&fixture.audio_calls==0);}
 {S fixture;fixture.missing_texture_getter=true;MenuMedia m;assert(build(m)==Incompatible&&!m.preview&&!m.pack_sprite&&fixture.sprite_calls==0);}
 {S fixture;fixture.load_false=true;MenuMedia m;Diagnostic d;assert(build(m,&d)==Incompatible&&!strcmp(d.stage,"menu-song-sprite"));}
 {S fixture;fixture.set_false=true;MenuMedia m;Diagnostic d;assert(build(m,&d)==Incompatible&&!strcmp(d.stage,"menu-audio-setdata"));}
 {S fixture;fixture.bad_bool=true;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;fixture.bad_readback=true;MenuMedia m;Diagnostic d;assert(build(m,&d)==Incompatible&&!strcmp(d.stage,"menu-preview-readback"));}
 {S fixture;fixture.width=256;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;fixture.missing_method=true;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;fixture.no_class=true;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;fixture.duplicate_class=true;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;fixture.bad_size=true;MenuMedia m;assert(build(m)==Incompatible);}
 {S fixture;MenuMedia m;MenuApis e=extra();e.object_unbox=NULL;assert(m.build(api(),e,{},{},{},NULL)==Incompatible);}
 {auto w=wave();const unsigned char* pcm=NULL;size_t n=0;assert(preview_pcm({w.data(),w.size()},&pcm,&n)&&n==88200);
  w[20]=3;assert(!preview_pcm({w.data(),w.size()},&pcm,&n));w[20]=1;w.pop_back();assert(!preview_pcm({w.data(),w.size()},&pcm,&n));}
 puts("menu media ABI, bounded cache, allocation/root/exception/format/readback refusal checks passed");
}
