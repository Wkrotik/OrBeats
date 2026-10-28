// Exp300: independent generated-content level. No hardcoded managed function calls.
#pragma once
#include "additive_environments.h"
#include "additive_song_packs.h"
#include <math.h>
namespace BsdAdditive {
struct ProbeDifficulty { int32_t notes,bombs,obstacles; float njs,jump_offset; };
struct ProbePalette { uint32_t mask; float colors[9][4]; };
struct ProbePresentation { float lufs, offset; ProbePalette palettes[5]; };
struct ProbeModes { uint32_t flags, masks[4]; ProbeDifficulty stats[4][5]; };
struct ProbeSpec {
    const char* level_id;
    const char* title;
    float bpm, duration;
    int32_t notes; // legacy generated proof fallback
    const ProbeDifficulty* difficulties = NULL; // exactly5 Standard entries
    const char* author = NULL;
    uint32_t difficulty_mask = 31; // exact available Standard slots, no fabricated Easy/Normal
    const char* environment = NULL;
    const ProbePresentation* presentation = NULL;
    const ProbeModes* modes = NULL;
};
struct PaletteApis;
struct ProbeContext {
    ProbeSpec spec;
    int32_t (*class_value_size)(void*, uint32_t*);
    void* menu_media = NULL;
    float menu_preview_duration = 0;
    void* characteristic_model = NULL;
    const PaletteApis* palette_apis = NULL;
};
inline bool scalar_float(const Api& a, void* object, void* c, const char* n,
                         size_t off, float* value) {
    void* f = field(a,c,n,off);
    if (!f) return false;
    a.field_get_value(object,f,value);
    return isfinite(*value);
}
} // namespace
#include "additive_palette.h"
#include "additive_characteristics.h"
namespace BsdAdditive {
// Called within registration roots, while the old repositories still own source.
// Only new managed objects are changed; never assign a field of the stock level.
inline Result make_probe_level(const Api& a, void* source, Roots& roots,
                              void** output, void* context, Diagnostic* d) {
    ProbeContext* p = (ProbeContext*)context;
    if (!p || !p->class_value_size || !p->spec.level_id || !p->spec.title ||
        strncmp(p->spec.level_id,"bsd_additive_",13) ||
        !isfinite(p->spec.bpm) || p->spec.bpm <= 0 ||
        !isfinite(p->spec.duration) || p->spec.duration <= 0 || p->spec.notes <= 0 ||
        (!p->spec.difficulty_mask && (!p->spec.modes||!p->spec.modes->flags)) || (p->spec.difficulty_mask & ~31u))
        return refuse(d,"probe-spec");
    if(p->spec.difficulties)for(int i=0;i<5;++i){
        if(!(p->spec.difficulty_mask & (1u<<i)))continue;
        const ProbeDifficulty& v=p->spec.difficulties[i];
        if(v.notes<=0||v.notes>100000||v.bombs<0||v.bombs>100000||v.obstacles<0||v.obstacles>100000||
           !isfinite(v.njs)||v.njs<=0||v.njs>100||!isfinite(v.jump_offset)||v.jump_offset < -10||v.jump_offset>10)
            return refuse(d,"probe-difficulty-spec");
    }
    if(p->spec.environment && !reviewed_environment(p->spec.environment))
        return refuse(d,"probe-unreviewed-environment");
    void* explicit_environment=NULL;
    if(p->spec.environment){
        explicit_environment=a.string_new(p->spec.environment);
        if(!roots.keep(explicit_environment))return AllocationFailed;
    }
    void* lc = a.object_get_class(source);
    if (!named(a,lc,"BeatmapLevel")) return refuse(d,"probe-source-class");
    const void* keys_method = a.class_get_method_from_name(lc,"GetBeatmapKeys",0);
    const void* ctor = a.class_get_method_from_name(lc,".ctor",17);
    const void* add = a.class_get_method_from_name(lc,"AddBeatmapBasicData",3);
    const void* get = a.class_get_method_from_name(lc,"GetDifficultyBeatmapData",2);
    void* data_field = field(a,lc,"_beatmapBasicDatas",0x70);
    void* preview_field = field(a,lc,"previewMediaData",0x68);
    void* mapper_field = field(a,lc,"allMappers",0x38);
    void* lighter_field = field(a,lc,"allLighters",0x40);
    if (!keys_method || !ctor || !add || !get || !data_field || !preview_field ||
        !mapper_field || !lighter_field) return refuse(d,"probe-level-metadata");
    bool threw = false;
    void* keys = invoke(a,keys_method,source,NULL,&threw);
    if (threw) return ManagedException;
    if (!keys) return refuse(d,"probe-source-keys-null");
    if (!roots.keep(keys)) return AllocationFailed;
    void* ac = a.object_get_class(keys);
    void* kc = a.class_get_element_class(ac);
    uint32_t alignment = 0;
    if (a.class_get_rank(ac) != 1 || !named(a,kc,"BeatmapKey") ||
        p->class_value_size(kc,&alignment) != 24 || alignment != 8)
        return refuse(d,"probe-key-array-class-size");
    // Runtime field offsets for boxed values include a16byte object header.
    // Some runtimes report unboxed offsets; accept only a CONSISTENT profile.
    void* key_char = a.class_get_field_from_name(kc,"beatmapCharacteristic");
    void* key_diff = a.class_get_field_from_name(kc,"difficulty");
    void* key_id = a.class_get_field_from_name(kc,"levelId");
    if (!key_char || !key_diff || !key_id) return refuse(d,"probe-key-fields");
    size_t start = a.field_get_offset(key_char);
    if ((start != 0 && start != 16) || a.field_get_offset(key_diff) != start+8 ||
        a.field_get_offset(key_id) != start+16) return refuse(d,"probe-key-offsets");
    size_t count = a.array_length(keys), header = 0;
    void* bounds = NULL;
    memcpy(&header,(char*)keys+24,8);memcpy(&bounds,(char*)keys+16,8);
    if (bounds || header != count || !count || count > 32)
        return refuse(d,"probe-key-array-header");
    void* characteristic = NULL;
    bool difficulties[5] = {false,false,false,false,false};
    void* idf = field(a,lc,"levelID",0x18);
    if (!idf) return refuse(d,"probe-source-id-field");
    void* source_id = read_ref(a,source,idf);
    for (size_t n=0;n<count;++n) {
        char* entry = (char*)keys+32+n*24;
        void* ch = NULL;void* id = NULL;int32_t diff=-1;
        memcpy(&ch,entry,8);memcpy(&diff,entry+8,4);memcpy(&id,entry+16,8);
        if (!ch || id != source_id || diff < 0 || diff > 4)
            return refuse(d,"probe-source-key-values");
        void* cc = a.object_get_class(ch);
        if (!named(a,cc,"BeatmapCharacteristicSO")) return refuse(d,"probe-characteristic-class");
        void* serialized = field(a,cc,"_serializedName",0x30);
        if (!serialized) return refuse(d,"probe-characteristic-name-field");
        if (!ascii_equals(a,read_ref(a,ch,serialized),"Standard")) continue;
        if ((characteristic && characteristic != ch) || difficulties[diff])
            return refuse(d,"probe-standard-keys-duplicate");
        characteristic=ch;difficulties[diff]=true;
    }
    for (int i=0;i<5;++i) if (!difficulties[i]) return refuse(d,"probe-standard-difficulties");
    void* source_data = read_ref(a,source,data_field);
    if (!source_data) return refuse(d,"probe-source-dictionary-null");
    void* dc = a.object_get_class(source_data);
    const void* dict_ctor = a.class_get_method_from_name(dc,".ctor",0);
    if (!dict_ctor) return refuse(d,"probe-dictionary-constructor");
    void* dictionary = a.object_new(dc);
    if (!roots.keep(dictionary)) return AllocationFailed;
    invoke(a,dict_ctor,dictionary,NULL,&threw);
    if (threw) return ManagedException;
    void* level = a.object_new(lc);
    if (!roots.keep(level)) return AllocationFailed;
    void* strings[4];
    const char* text[] = {p->spec.level_id,p->spec.title,"",p->spec.author ? p->spec.author : "BSD Generated"};
    for(int i=0;i<4;++i) {strings[i]=a.string_new(text[i]);if(!roots.keep(strings[i])) return AllocationFailed;}
    int32_t version = 0, rating = 0;bool precalculated = true;
    float bpm=p->spec.bpm,lufs=-14,offset=0,preview_start=0,preview_duration=p->spec.duration,duration=p->spec.duration;
    if(p->spec.presentation){
        lufs=p->spec.presentation->lufs;offset=p->spec.presentation->offset;
        if(!isfinite(lufs)||lufs < -100||lufs > 100||!isfinite(offset)||offset < -10||offset > 10)
            return refuse(d,"probe-presentation-bounds");
    }
    // Reviewed own media overrides only this generated level. Absent menu files
    // retain the earlier stock-preview fallback; never a gameplay-audio proof.
    void* preview = p->menu_media ? p->menu_media : read_ref(a,source,preview_field);
    if(p->menu_media){
        if(!named(a,a.object_get_class(preview),"StaticPreviewMediaData")||
           !isfinite(p->menu_preview_duration)||p->menu_preview_duration<1||p->menu_preview_duration>30||
           !roots.keep(preview))return refuse(d,"probe-menu-media");
        preview_start=0;preview_duration=p->menu_preview_duration;
    }
    void* mappers = read_ref(a,source,mapper_field);
    void* lighters = read_ref(a,source,lighter_field);
    if (!preview || !mappers || !lighters) return refuse(d,"probe-preview-or-author-arrays");
    void* args[] = {&version,&precalculated,strings[0],strings[1],strings[2],strings[3],mappers,lighters,
        &bpm,&lufs,&offset,&preview_start,&preview_duration,&duration,&rating,preview,dictionary};
    invoke(a,ctor,level,args,&threw);
    if (threw) return ManagedException;
    if(p->spec.modes&&p->spec.modes->flags>15)return refuse(d,"probe-mode-flags");
    const char* mode_names[]={"OneSaber","NoArrows","90Degree","360Degree"};
    for(int mode=-1;mode<4;++mode){
      if(mode>=0&&(!p->spec.modes||!(p->spec.modes->flags&(1u<<mode))))continue;
      uint32_t mask=mode<0?p->spec.difficulty_mask:p->spec.modes->masks[mode];
      if(!mask)continue;if(mask>31)return refuse(d,"probe-mode-mask");
      void* target=mode<0?characteristic:stock_characteristic(a,roots,p->characteristic_model,kc,mode_names[mode],&threw);
      if(threw)return ManagedException;if(!target)return refuse(d,"probe-native-characteristic-unavailable");
      const ProbeDifficulty* stats=mode<0?p->spec.difficulties:p->spec.modes->stats[mode];
      for(int32_t difficulty=0;difficulty<5;++difficulty) {
        if(!(mask & (1u<<difficulty)))continue;
        void* lookup[] = {characteristic,&difficulty};
        void* old_basic = invoke(a,get,source,lookup,&threw);
        if (threw) return ManagedException;
        if (!old_basic) return refuse(d,"probe-source-basic-null");
        void* bc = a.object_get_class(old_basic);
        if (!named(a,bc,"BeatmapBasicData")) return refuse(d,"probe-basic-class");
        const char* ref_names[] = {"environmentName","beatmapColorScheme","mappers","lighters"};
        const size_t offsets[] = {0x18,0x20,0x38,0x40};void* refs[4];
        for(int j=0;j<4;++j) {void* f=field(a,bc,ref_names[j],offsets[j]);if(!f) return refuse(d,"probe-basic-field-layout");refs[j]=read_ref(a,old_basic,f);}
        if(explicit_environment)refs[0]=explicit_environment;
        if(p->spec.presentation && p->spec.presentation->palettes[difficulty].mask){
            void* base=refs[1];
            if(!base){Result result=environment_palette(a,roots,p->palette_apis,refs[0],&base,d);if(result!=Added)return result;}
            void* palette=NULL;Result result=copy_authored_palette(a,roots,base,p->spec.presentation->palettes[difficulty],&palette,d);
            if(result!=Added)return result;refs[1]=palette;
        }
        // EnvironmentName is a VALUE struct containing one string reference.
        // Its invoke argument is &refs[0]; ColorScheme/arrays are direct refs.
        float njs=10,jump_offset=0;
        int32_t notes=p->spec.notes,cuttable=notes,obstacles=0,bombs=0;
        if(stats){
            const ProbeDifficulty& v=stats[difficulty];
            cuttable=v.notes;bombs=v.bombs;notes=cuttable+bombs;obstacles=v.obstacles;
            njs=v.njs;jump_offset=v.jump_offset;
        }
        const void* basic_ctor = a.class_get_method_from_name(bc,".ctor",10);
        if(!basic_ctor) return refuse(d,"probe-basic-constructor");
        void* basic = a.object_new(bc);
        if(!roots.keep(basic)) return AllocationFailed;
        void* basic_args[]={&njs,&jump_offset,&refs[0],refs[1],&notes,&cuttable,&obstacles,&bombs,refs[2],refs[3]};
        invoke(a,basic_ctor,basic,basic_args,&threw);
        if(threw) return ManagedException;
        void* add_args[]={target,&difficulty,basic};
        invoke(a,add,level,add_args,&threw);
        if(threw) return ManagedException;
        void* output_lookup[]={target,&difficulty};
        void* got=invoke(a,get,level,output_lookup,&threw);
        if(threw) return ManagedException;
        if(got != basic) return VerificationFailed;
        void* notes_field=field(a,bc,"notesCount",0x28);int32_t got_notes=-1;
        if(!notes_field) return refuse(d,"probe-basic-notes-field");
        a.field_get_value(basic,notes_field,&got_notes);
        if(got_notes!=notes) return VerificationFailed;
        void* env_field=field(a,bc,"environmentName",0x18);
        if(!env_field || read_ref(a,basic,env_field)!=refs[0])return VerificationFailed;
    }
    } // characteristic
    // Readback of constructor references/scalars before handing new level to
    // repository construction. Do not publish a partially initialized object.
    float got_duration=0,got_bpm=0;
    if(read_ref(a,level,idf)!=strings[0] || read_ref(a,level,data_field)!=dictionary ||
        read_ref(a,source,idf)!=source_id ||
        !scalar_float(a,level,lc,"beatsPerMinute",0x48,&got_bpm) ||
        !scalar_float(a,level,lc,"songDuration",0x5c,&got_duration) ||
        got_bpm!=bpm || got_duration!=duration) return VerificationFailed;
    *output=level;
    return Added; // means NEW OBJECT PREPARED, not repository/console success
}
} // namespace
