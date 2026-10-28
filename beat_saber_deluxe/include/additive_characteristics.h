// Reuse genuine characteristic SO instances reachable from stock repositories.
// No fabricated SOs, Resources reflection, guessed symbol offsets or mode aliases.
#pragma once
namespace BsdAdditive {
inline void* stock_characteristic(const Api& a,Roots& roots,void* model,void* key_class,
                                  const char* requested,bool* threw){
    if(!model||!named(a,a.object_get_class(model),"BeatmapLevelsModel"))return NULL;
    void* f=field(a,a.object_get_class(model),"_allLoadedBeatmapLevelsRepository",0x50);
    void* repo=f?read_ref(a,model,f):NULL;if(!repo||!named(a,a.object_get_class(repo),"BeatmapLevelsRepository"))return NULL;
    f=field(a,a.object_get_class(repo),"_beatmapLevelPacks",0x10);
    size_t packs=0;void** ps=f?vector(a,read_ref(a,repo,f),"BeatmapLevelPack",kMaxPacks,&packs):NULL;
    if(!ps)return NULL;size_t examined=0;
    for(size_t p=0;p<packs;++p){
        if(!ps[p]||!named(a,a.object_get_class(ps[p]),"BeatmapLevelPack"))return NULL;
        void* pc=a.object_get_class(ps[p]);void* id=field(a,pc,"packID",0x10);void* levels=field(a,pc,"_beatmapLevels",0x40);
        if(!id||!levels)return NULL;if(ascii_equals(a,read_ref(a,ps[p],id),kPackId))continue;
        size_t n=0;void** ls=vector(a,read_ref(a,ps[p],levels),"BeatmapLevel",kMaxLevels,&n);if(!ls)return NULL;
        for(size_t i=0;i<n;++i){
            if(++examined>kMaxLevels||!ls[i]||!named(a,a.object_get_class(ls[i]),"BeatmapLevel"))return NULL;
            const void* get=a.class_get_method_from_name(a.object_get_class(ls[i]),"GetBeatmapKeys",0);if(!get)return NULL;
            Roots temporary(a);
            void* keys=invoke(a,get,ls[i],NULL,threw);if(*threw||!keys||!temporary.keep(keys))return NULL;
            void* c=a.object_get_class(keys);size_t count=a.array_length(keys),stored=0;void* bounds=NULL;
            memcpy(&bounds,(char*)keys+16,8);memcpy(&stored,(char*)keys+24,8);
            if(a.class_get_rank(c)!=1||a.class_get_element_class(c)!=key_class||bounds||stored!=count||count>128)return NULL;
            for(size_t k=0;k<count;++k){void* ch=NULL;memcpy(&ch,(char*)keys+32+k*24,8);
                if(!ch||!named(a,a.object_get_class(ch),"BeatmapCharacteristicSO"))return NULL;
                void* name=field(a,a.object_get_class(ch),"_serializedName",0x30);if(!name)return NULL;
                if(ascii_equals(a,read_ref(a,ch,name),requested)){if(!roots.keep(ch))return NULL;return ch;}
            }
        }
    }
    return NULL;
}
} // namespace
