// Exp289/300: OFF-default pack registration; optional NEW-level factory.
// Existing assets/IDs are never replaced.
// Runtime operations use IL2CPP allocation, GC handles, write barriers and captured
// managed exceptions. No malloc-backed managed objects or guessed constructors.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace BsdAdditive {
static const char kPackId[] = "bsd_additive_stock_proof_v1";
static const char kPackName[] = "Custom Songs";
static const size_t kMaxPacks = 512;
static const size_t kMaxLevels = 4096;
static const size_t kMaxGeneratedLevels = 64; // bounded native resource budget; companion shares this bound

// Public IL2CPP C API, resolved by name from the game. Missing API => no hook.
#define BSD_ADDITIVE_APIS(X) \
 X(void*, object_get_class, (void*)) \
 X(const char*, class_get_name, (void*)) \
 X(const char*, class_get_namespace, (void*)) \
 X(void*, class_get_field_from_name, (void*, const char*)) \
 X(size_t, field_get_offset, (void*)) \
 X(void, field_get_value, (void*, void*, void*)) \
 X(void, field_set_value, (void*, void*, void*)) \
 X(const void*, class_get_method_from_name, (void*, const char*, int)) \
 X(void*, object_new, (void*)) \
 X(void*, runtime_invoke, (const void*, void*, void**, void**)) \
 X(void*, array_new, (void*, size_t)) \
 X(uintptr_t, array_length, (void*)) \
 X(int, class_get_rank, (void*)) \
 X(void*, class_get_element_class, (void*)) \
 X(void, gc_wbarrier_set_field, (void*, void**, void*)) \
 X(uint32_t, gchandle_new, (void*, bool)) \
 X(void, gchandle_free, (uint32_t)) \
 X(void*, string_new, (const char*)) \
 X(int32_t, string_length, (void*)) \
 X(const uint16_t*, string_chars, (void*))
struct Api {
#define BSD_DECLARE(ret, name, params) ret (*name) params;
    BSD_ADDITIVE_APIS(BSD_DECLARE)
#undef BSD_DECLARE
};
inline bool resolve_api(Api& api, void* (*resolve)(const char*), const char** missing) {
    memset(&api, 0, sizeof(api));
#define BSD_RESOLVE(ret, name, params) \
    api.name = (ret (*) params)resolve("il2cpp_" #name); \
    if (!api.name) { if (missing) *missing = "il2cpp_" #name; return false; }
    BSD_ADDITIVE_APIS(BSD_RESOLVE)
#undef BSD_RESOLVE
    return true;
}
inline bool complete(const Api& api) {
#define BSD_CHECK(ret, name, params) if (!api.name) return false;
    BSD_ADDITIVE_APIS(BSD_CHECK)
#undef BSD_CHECK
    return true;
}
#undef BSD_ADDITIVE_APIS

enum Result { Added, AlreadyPresent, Incompatible, AllocationFailed,
              ManagedException, VerificationFailed, PublicationRestored, PublicationUnsafe };
inline const char* result_name(Result r) {
    switch (r) {
    case Added: return "registered additive pack (NOT gameplay verification)";
    case AlreadyPresent: return "already present; unchanged";
    case Incompatible: return "incompatible runtime metadata/objects; unchanged";
    case AllocationFailed: return "managed allocation/root failed; unchanged";
    case ManagedException: return "managed invocation threw; unchanged";
    case PublicationRestored: return "publication readback failed; original model restored";
    case PublicationUnsafe: return "publication/rollback verification failed; model unsafe; stop testing";
    default: return "new repository verification failed; unchanged";
    }
}
struct Roots {
    const Api& api;
    uint32_t handles[64+kMaxGeneratedLevels*128];
    size_t count;
    explicit Roots(const Api& a) : api(a), count(0) {}
    ~Roots() { while (count) api.gchandle_free(handles[--count]); }
    bool keep(void* p) {
        if (!p || count == sizeof(handles)/sizeof(handles[0])) return false;
        uint32_t h = api.gchandle_new(p, true);
        if (!h) return false;
        handles[count++] = h;
        return true;
    }
private:
    Roots(const Roots&);
    Roots& operator=(const Roots&);
};
inline bool named(const Api& a, void* klass, const char* name) {
    if (!klass) return false;
    const char* n = a.class_get_name(klass);
    const char* ns = a.class_get_namespace(klass);
    return n && ns && !*ns && strcmp(n, name) == 0;
}
inline void* field(const Api& a, void* klass, const char* name, size_t offset) {
    void* f = a.class_get_field_from_name(klass, name);
    return f && a.field_get_offset(f) == offset ? f : NULL;
}
inline void* read_ref(const Api& a, void* object, void* f) {
    void* value = NULL;
    a.field_get_value(object, f, &value);
    return value;
}
inline bool ascii_equals(const Api& a, void* s, const char* expected) {
    if (!s || a.string_length(s) != (int32_t)strlen(expected)) return false;
    const uint16_t* chars = a.string_chars(s);
    if (!chars) return false;
    for (size_t i = 0; expected[i]; ++i)
        if (chars[i] != (unsigned char)expected[i]) return false;
    return true;
}
// Profile-specific 64-bit IL2CPP SZARRAY header. Confirm rank, element class and
// runtime-reported length before reading vector; constructor code independently
// shows max_length+0x18/vector+0x20. Never used for arbitrary lists or value arrays.
inline void** vector(const Api& a, void* array, const char* element, size_t limit,
                     size_t* count, void** element_class = NULL) {
    if (!array) return NULL;
    void* klass = a.object_get_class(array);
    if (!klass || a.class_get_rank(klass) != 1) return NULL;
    void* elem = a.class_get_element_class(klass);
    if (!named(a, elem, element)) return NULL;
    size_t length = a.array_length(array), header_length = 0;
    void* bounds = NULL;
    memcpy(&bounds, (char*)array + 16, sizeof(bounds));
    memcpy(&header_length, (char*)array + 24, sizeof(header_length));
    if (bounds || length != header_length || length > limit) return NULL;
    *count = length;
    if (element_class) *element_class = elem;
    return (void**)((char*)array + 32);
}
inline void* invoke(const Api& a, const void* method, void* object, void** args,
                    bool* threw) {
    void* exception = NULL;
    void* result = a.runtime_invoke(method, object, args, &exception);
    if (exception) *threw = true;
    return result;
}

// Called ONLY after the game's own LoadAllBeatmapLevelPacks, on its calling
// thread, never from open_hook/the native setup path. Prepare/validate everything
// before publishing; originals, DLC repository and level IDs remain untouched.
struct Diagnostic {
    const char* stage;
    int repository;
    size_t counts[3];
    int32_t pack_count;
    // Bounded palette lookup evidence, never object addresses or song payloads.
    int palette_rank;
    size_t palette_count, palette_stored;
    const char* palette_element;
    const char* palette_element_ns;
    bool palette_bounds;
    Diagnostic() : stage("entry"), repository(-1), counts{0, 0, 0}, pack_count(-1),
        palette_rank(-1), palette_count(0), palette_stored(0),
        palette_element(NULL), palette_element_ns(NULL), palette_bounds(false) {}
};
inline Result refuse(Diagnostic* diagnostic, const char* stage) {
    if (diagnostic) diagnostic->stage = stage;
    return Incompatible;
}
typedef Result (*LevelFactory)(const Api&, void*, Roots&, void**, void*, Diagnostic*);
typedef Result (*BeforePublish)(const Api&, void*, void*, void*, void*, Diagnostic*);
typedef Result (*BeforePublishMany)(const Api&, void*, void*, void* const*, size_t, void*, Diagnostic*);
struct FactoryBatch {
    void* const* contexts;
    const char* const* expected_ids;
    size_t count;
    BeforePublishMany before_publish;
    void* policy_context;
};
inline Result append_stock_pack(const Api& a, void* model, Diagnostic* diagnostic = NULL,
                                LevelFactory factory = NULL, void* factory_context = NULL,
                                BeforePublish before_publish = NULL, void* policy_context = NULL,
                                void* own_pack_sprite = NULL, const FactoryBatch* batch = NULL) {
    if(batch && (!factory || before_publish || !batch->contexts || !batch->expected_ids ||
                 !batch->count || batch->count>kMaxGeneratedLevels))
        return refuse(diagnostic,"batch-spec");
    const size_t generated_count=batch?batch->count:1;
    if(batch)for(size_t i=0;i<generated_count;++i){
        if(!batch->contexts[i]||!batch->expected_ids[i]||
           strncmp(batch->expected_ids[i],"bsd_additive_",13)||strlen(batch->expected_ids[i])<=13||
           strlen(batch->expected_ids[i])>80)return refuse(diagnostic,"batch-ID-spec");
        for(size_t j=0;j<i;++j)if(!strcmp(batch->expected_ids[i],batch->expected_ids[j]))
            return refuse(diagnostic,"batch-duplicate-ID");
    }
    if (diagnostic) *diagnostic = Diagnostic();
    if (!complete(a) || !model) return refuse(diagnostic, "api-or-model-null");
    Roots roots(a);
    if (!roots.keep(model)) return AllocationFailed;
    void* mc = a.object_get_class(model);
    if (!named(a, mc, "BeatmapLevelsModel")) return refuse(diagnostic, "model-class");
    const char* model_names[] = {"ostAndExtrasBeatmapLevelsRepository",
        "_allLoadedBeatmapLevelsRepository", "_allExistingBeatmapLevelsRepository"};
    const size_t model_offsets[] = {0x10, 0x50, 0x58};
    void* mf[3]; void* old[3]; void* arrays[3]; size_t counts[3];
    void* rf = NULL; void* rc = NULL; void* pc = NULL;
    void* pf_id = NULL; void* source = NULL; void* level = NULL;
    void* pf_levels = NULL;
    void* existing_packs[3]={};
    for (int i = 0; i < 3; ++i) {
        if (diagnostic) diagnostic->repository = i;
        mf[i] = field(a, mc, model_names[i], model_offsets[i]);
        if (!mf[i]) return refuse(diagnostic, model_names[i]);
        if (!(old[i] = read_ref(a, model, mf[i]))) return refuse(diagnostic, "repository-null");
        if (!roots.keep(old[i])) return AllocationFailed; // retain originals for rollback
        void* klass = a.object_get_class(old[i]);
        if (!named(a, klass, "BeatmapLevelsRepository") || (rc && rc != klass)) return refuse(diagnostic, "repository-class");
        rc = klass;
        rf = field(a, rc, "_beatmapLevelPacks", 0x10);
        if (!rf) return refuse(diagnostic, "repository-packs-field");
        arrays[i] = read_ref(a, old[i], rf);
        void* elem = NULL;
        void** entries = vector(a, arrays[i], "BeatmapLevelPack", kMaxPacks, &counts[i], &elem);
        if (diagnostic && entries) diagnostic->counts[i] = counts[i];
        if (!entries) return refuse(diagnostic, "repository-pack-array-layout");
        if (!counts[i] || counts[i] == kMaxPacks || (pc && pc != elem)) return refuse(diagnostic, "repository-pack-count-or-element-class");
        pc = elem;
        pf_id = field(a, pc, "packID", 0x10);
        pf_levels = field(a, pc, "_beatmapLevels", 0x40);
        if (!pf_id || !pf_levels) return refuse(diagnostic, "pack-id-or-levels-field");
        for (size_t n = 0; n < counts[i]; ++n) {
            void* p = entries[n];
            if (!p || a.object_get_class(p) != pc) return refuse(diagnostic, "pack-entry-class");
            if (ascii_equals(a, read_ref(a, p, pf_id), kPackId)) {
                if(batch){
                    if(existing_packs[i])return refuse(diagnostic,"batch-duplicate-pack");
                    existing_packs[i]=p;continue;
                }
                if (before_publish) {
                    size_t nlevels=0;
                    void** existing=vector(a,read_ref(a,p,pf_levels),"BeatmapLevel",kMaxLevels,&nlevels);
                    if(!existing||nlevels!=1||!existing[0])return VerificationFailed;
                    void* lid=field(a,a.object_get_class(existing[0]),"levelID",0x18);
                    if(!lid)return Incompatible;
                    Result ready=before_publish(a,model,read_ref(a,p,pf_id),
                        read_ref(a,existing[0],lid),policy_context,diagnostic);
                    if(ready!=Added)return ready;
                }
                return AlreadyPresent;
            }
            if (i == 0 && !source) {
                size_t length = 0;
                void** levels = vector(a, read_ref(a, p, pf_levels), "BeatmapLevel", kMaxLevels, &length);
                if (levels && length && levels[0]) { source = p; level = levels[0]; }
            }
        }
    }
    // Repeated callbacks must verify BOTH IDs in ALL repositories before
    // enabling routes; never call a partial pack already present a success.
    if(batch&&(existing_packs[0]||existing_packs[1]||existing_packs[2])){
        void* pack=existing_packs[0];
        if(!pack||existing_packs[1]!=pack||existing_packs[2]!=pack)return VerificationFailed;
        size_t n=0;void** levels=vector(a,read_ref(a,pack,pf_levels),"BeatmapLevel",kMaxGeneratedLevels,&n);
        if(!levels||n!=generated_count)return VerificationFailed;
        void* ids[kMaxGeneratedLevels]={};
        const void* get=a.class_get_method_from_name(rc,"GetBeatmapLevelById",1);
        const void* get_pack=a.class_get_method_from_name(rc,"GetBeatmapLevelPackByBeatmapLevelId",1);
        if(!get||!get_pack)return Incompatible;
        for(size_t j=0;j<n;++j){
            if(!levels[j]||!named(a,a.object_get_class(levels[j]),"BeatmapLevel"))return VerificationFailed;
            void* f=field(a,a.object_get_class(levels[j]),"levelID",0x18);
            ids[j]=f?read_ref(a,levels[j],f):NULL;
            if(!ascii_equals(a,ids[j],batch->expected_ids[j]))return VerificationFailed;
            if(!roots.keep(levels[j])||!roots.keep(ids[j]))return AllocationFailed;
            for(int i=0;i<3;++i){bool threw=false;void* args[]={ids[j]};
                void* v=invoke(a,get,old[i],args,&threw);if(threw)return ManagedException;
                void* p=invoke(a,get_pack,old[i],args,&threw);if(threw)return ManagedException;
                if(v!=levels[j]||p!=pack)return VerificationFailed;
            }
        }
        if(batch->before_publish){
            Result ready=batch->before_publish(a,model,read_ref(a,pack,pf_id),ids,n,batch->policy_context,diagnostic);
            if(ready!=Added)return ready;
        }
        return AlreadyPresent;
    }
    void* count_field = field(a, mc, "allPacksCount", 0x20);
    int32_t pack_count = 0;
    if (!count_field) return refuse(diagnostic, "model-count-field");
    if (!source || !level) return refuse(diagnostic, "stock-source-level");
    a.field_get_value(model, count_field, &pack_count);
    if (diagnostic) diagnostic->pack_count = pack_count;
    // LoadAll is called inside .ctor BEFORE .ctor initializes allPacksCount.
    // Zero is legitimate here; the caller will compute it from the NEW loaded
    // array after we return. On later reloads set it from validated loaded-pack
    // count, not old count+1 (which would drift after repeated reloads).
    if (pack_count < 0 || pack_count >= (int32_t)kMaxPacks) return refuse(diagnostic, "model-count-range");
    void* lc = a.object_get_class(level);
    if (!named(a, lc, "BeatmapLevel")) return refuse(diagnostic, "stock-level-class");
    void* level_id_field = field(a, lc, "levelID", 0x18);
    void* cover_field = field(a, pc, "coverImage", 0x28);
    void* small_field = field(a, pc, "smallCoverImage", 0x30);
    void* buy_field = field(a, pc, "packBuyOption", 0x38);
    void* rating_field = field(a, pc, "contentRating", 0x3c);
    if (!level_id_field || !cover_field || !small_field || !buy_field || !rating_field) return refuse(diagnostic, "stock-level-or-artwork-fields");
    void* level_id = read_ref(a, level, level_id_field);
    if (!level_id) return refuse(diagnostic, "stock-level-id-null");
    const void* pack_ctor = a.class_get_method_from_name(pc, ".ctor", 8);
    const void* repo_ctor = a.class_get_method_from_name(rc, ".ctor", 1);
    const void* get_pack = a.class_get_method_from_name(rc, "GetBeatmapLevelPackByPackId", 1);
    const void* get_level = a.class_get_method_from_name(rc, "GetBeatmapLevelById", 1);
    const void* get_level_pack = a.class_get_method_from_name(rc, "GetBeatmapLevelPackByBeatmapLevelId", 1);
    if (!pack_ctor || !repo_ctor || !get_pack || !get_level || !get_level_pack) return refuse(diagnostic, "managed-methods");

    void* stock_level = level;
    void* custom_level_id = NULL;
    void* generated[kMaxGeneratedLevels]={};void* custom_ids[kMaxGeneratedLevels]={};
    for(size_t j=0;j<generated_count;++j){
        generated[j]=stock_level;
        if(factory){
            Result made=factory(a,stock_level,roots,&generated[j],batch?batch->contexts[j]:factory_context,diagnostic);
            if(made!=Added)return made;
            void* created=generated[j];
            if(!created||created==stock_level||a.object_get_class(created)!=lc)
                return refuse(diagnostic,"probe-created-level-class");
            custom_ids[j]=read_ref(a,created,level_id_field);
            if(!custom_ids[j]||a.string_length(custom_ids[j])<=13||a.string_length(custom_ids[j])>80)
                return refuse(diagnostic,"probe-created-id");
            int32_t nn=a.string_length(custom_ids[j]),on=a.string_length(level_id);
            if(nn==on&&!memcmp(a.string_chars(custom_ids[j]),a.string_chars(level_id),(size_t)nn*2))
                return refuse(diagnostic,"probe-created-id-is-stock");
            if(batch&&!ascii_equals(a,custom_ids[j],batch->expected_ids[j]))return refuse(diagnostic,"batch-created-ID");
        }
    }
    custom_level_id=custom_ids[0];level=generated[0];
    void* levels=a.array_new(lc,generated_count);
    if(!roots.keep(levels))return AllocationFailed;
    size_t length=0;
    void** lv=vector(a,levels,"BeatmapLevel",kMaxGeneratedLevels,&length);
    if(!lv||length!=generated_count)return refuse(diagnostic,"allocated-level-array-layout");
    for(size_t j=0;j<generated_count;++j)a.gc_wbarrier_set_field(levels,lv+j,generated[j]);
    void* id = a.string_new(kPackId);
    if (!roots.keep(id)) return AllocationFailed;
    void* name = a.string_new(kPackName);
    if (!roots.keep(name)) return AllocationFailed;
    void* short_name = a.string_new("BSD Proof");
    if (!roots.keep(short_name)) return AllocationFailed;
    void* pack = a.object_new(pc);
    if (!roots.keep(pack)) return AllocationFailed;
    // This OWN newly constructed proof pack is not a store product. The exact
    // PS4 enum/UI compares1 (DisableBuyOption); do not copy stock Default=0.
    // Never patch entitlement results or alter source/DLC pack metadata.
    int32_t buy = 1, source_buy = 0, rating = 0;
    a.field_get_value(source, buy_field, &source_buy);
    a.field_get_value(source, rating_field, &rating);
    if (source_buy < 0 || source_buy > 1 || rating < 0 || rating > 3) return refuse(diagnostic, "stock-pack-enums");
    if(own_pack_sprite){
        void* c=a.object_get_class(own_pack_sprite);
        if(!c||strcmp(a.class_get_name(c),"Sprite")||strcmp(a.class_get_namespace(c),"UnityEngine")||
           !roots.keep(own_pack_sprite))return refuse(diagnostic,"own-pack-sprite");
    }
    void* pack_args[] = {id, name, short_name, own_pack_sprite ? own_pack_sprite : read_ref(a, source, cover_field),
        own_pack_sprite ? own_pack_sprite : read_ref(a, source, small_field), &buy, levels, &rating};
    bool threw = false;
    invoke(a, pack_ctor, pack, pack_args, &threw);
    if (threw) return ManagedException;
    int32_t actual_buy = -1;
    a.field_get_value(pack, buy_field, &actual_buy);
    if (actual_buy != buy) {
        refuse(diagnostic, "proof-pack-buy-option-readback");
        return VerificationFailed;
    }
    // Exp309: the exact PS4 menu preserves the OST repository order before
    // concatenating the DLC sequence. Put ONLY our independent-ID pack first;
    // preserve every stock pack's relative order and objects. No UI detour,
    // punctuation name trick or sorting of official packs is needed.
    // The historical duplicate-STOCK proof must still be appended: repository
    // .ctor's first-wins TryInsert(None) must retain stock level->pack lookup.
    const bool custom_first = custom_level_id != NULL;
    const size_t stock_begin = custom_first ? 1 : 0;
    void* prepared[3];
    for (int i = 0; i < 3; ++i) {
        void* new_array = a.array_new(pc, counts[i] + 1);
        if (!roots.keep(new_array)) return AllocationFailed;
        size_t new_count = 0, old_count = 0;
        void** dst = vector(a, new_array, "BeatmapLevelPack", kMaxPacks, &new_count);
        void** src = vector(a, arrays[i], "BeatmapLevelPack", kMaxPacks, &old_count);
        if (diagnostic) diagnostic->repository = i;
        if (!dst || !src || new_count != counts[i] + 1 || old_count != counts[i]) return refuse(diagnostic, "prepared-pack-array-layout");
        for (size_t n = 0; n < old_count; ++n)
            a.gc_wbarrier_set_field(new_array, dst + stock_begin + n, src[n]);
        const size_t custom_index = custom_first ? 0 : old_count;
        a.gc_wbarrier_set_field(new_array, dst + custom_index, pack);
        prepared[i] = a.object_new(rc);
        if (!roots.keep(prepared[i])) return AllocationFailed;
        void* repo_args[] = {new_array};
        invoke(a, repo_ctor, prepared[i], repo_args, &threw);
        if (threw) return ManagedException;
        void* id_args[] = {id}; void* level_args[] = {level_id};
        void* found_pack = invoke(a, get_pack, prepared[i], id_args, &threw);
        if (threw) return ManagedException;
        void* found_level = invoke(a, get_level, prepared[i], level_args, &threw);
        if (threw) return ManagedException;
        void* original_level = invoke(a, get_level, old[i], level_args, &threw);
        if (threw) return ManagedException;
        void* original_pack = invoke(a, get_level_pack, old[i], level_args, &threw);
        if (threw) return ManagedException;
        void* new_level_pack = invoke(a, get_level_pack, prepared[i], level_args, &threw);
        if (threw) return ManagedException;
        if (found_pack != pack || found_level != stock_level || original_level != stock_level ||
            !original_pack || new_level_pack != original_pack) return VerificationFailed;
        if (custom_level_id) for(size_t j=0;j<generated_count;++j){
            void* custom_args[]={custom_ids[j]};
            void* old_custom=invoke(a,get_level,old[i],custom_args,&threw);
            if (threw) return ManagedException;
            void* new_custom=invoke(a,get_level,prepared[i],custom_args,&threw);
            if (threw) return ManagedException;
            void* new_pack=invoke(a,get_level_pack,prepared[i],custom_args,&threw);
            if (threw) return ManagedException;
            if (old_custom || new_custom!=generated[j] || new_pack!=pack) return VerificationFailed;
        }
        size_t verify_count = 0;
        void** verify = vector(a, read_ref(a, prepared[i], rf), "BeatmapLevelPack", kMaxPacks, &verify_count);
        if (!verify || verify_count != new_count) return VerificationFailed;
        for (size_t n = 0; n < old_count; ++n)
            if (verify[stock_begin + n] != src[n]) return VerificationFailed;
        if (verify[custom_index] != pack) return VerificationFailed;
    }
    // Validate constructor retained all distinct generated levels, not just dicts.
    size_t published_count=0;
    void** published_levels=vector(a,read_ref(a,pack,pf_levels),"BeatmapLevel",kMaxGeneratedLevels,&published_count);
    if(!published_levels||published_count!=generated_count)return VerificationFailed;
    for(size_t j=0;j<generated_count;++j)if(published_levels[j]!=generated[j])return VerificationFailed;
    if(batch&&batch->before_publish){
        Result ready=batch->before_publish(a,model,id,custom_ids,generated_count,batch->policy_context,diagnostic);
        if(ready!=Added)return ready;
    }
    if (before_publish) {
        Result ready = before_publish(a, model, id, custom_level_id, policy_context, diagnostic);
        if (ready != Added) return ready;
    }
    // No allocations/managed invocations after this point. One game-thread
    // publication phase, not an atomic transaction for concurrent readers.
    // Exact PS4 field_set_value ABI: managed reference is the third argument
    // ITSELF, not &pointer; scalar I4 still takes &value. Exp294 crashed because
    // the old code published native stack slots instead of managed objects.
    auto restore = [&](const char* stage) -> Result {
        for (int j = 0; j < 3; ++j) a.field_set_value(model, mf[j], old[j]);
        if (pack_count != 0) a.field_set_value(model, count_field, &pack_count);
        bool restored = true;
        for (int j = 0; j < 3; ++j)
            if (read_ref(a, model, mf[j]) != old[j]) restored = false;
        int32_t count_after = -1;
        a.field_get_value(model, count_field, &count_after);
        if (count_after != pack_count) restored = false;
        if (diagnostic) diagnostic->stage = stage;
        return restored ? PublicationRestored : PublicationUnsafe;
    };
    for (int i = 0; i < 3; ++i) {
        a.field_set_value(model, mf[i], prepared[i]);
        // Getter copies to native storage; validate pointer equality before
        // dereferencing or releasing any prepared/original GC roots.
        if (read_ref(a, model, mf[i]) != prepared[i]) {
            if (diagnostic) diagnostic->repository = i;
            return restore("publication-reference-readback");
        }
    }
    if (pack_count != 0) {
        int32_t updated_count = (int32_t)counts[1] + 1;
        a.field_set_value(model, count_field, &updated_count);
        int32_t count_after = -1;
        a.field_get_value(model, count_field, &count_after);
        if (count_after != updated_count) return restore("publication-count-readback");
    }
    if (diagnostic) diagnostic->stage = pack_count == 0 ? "published-constructor-count-deferred" : "published-reload-count-updated";
    return Added;
}
} // namespace BsdAdditive
