// Exp301: classify ONLY our verified, self-generated local IDs as free content.
// No platform entitlement hooks, DLC IDs, set replacement/clear or generic unlock.
#pragma once
#include "additive_song_packs.h"
#include "additive_probe_profile.h"
namespace BsdAdditive {
struct LocalContent {
    const Api& api;
    Roots roots;
    void* (*unbox)(void*);
    int32_t (*value_size)(void*,uint32_t*);
    static const size_t capacity=kMaxGeneratedLevels+1;
    const char* const* approved_ids;
    size_t approved_count, entry_count;
    void* sets[capacity]; void* ids[capacity];
    const void *contains[capacity], *add[capacity], *remove[capacity];
    bool existed[capacity], attempted[capacity], ready;
    LocalContent(const Api& a,void*(*u)(void*),int32_t(*v)(void*,uint32_t*),
                 const char* const* approved=NULL,size_t count=1)
        : api(a),roots(a),unbox(u),value_size(v),approved_ids(approved),approved_count(count),entry_count(0),
          sets{},ids{},contains{},add{},remove{},
          existed{},attempted{},ready(false) {}
    bool boolean(const void* method,void* set,void* id,bool* value,bool* threw) {
        void* args[]={id};void* result=invoke(api,method,set,args,threw);
        if(*threw||!result)return false;
        void* c=api.object_get_class(result);
        const char *n=c?api.class_get_name(c):NULL,*ns=c?api.class_get_namespace(c):NULL;
        uint32_t alignment=0;
        if(!n||!ns||strcmp(n,"Boolean")||strcmp(ns,"System")||
           value_size(c,&alignment)!=1||alignment!=1)return false;
        void* data=unbox(result);if(!data)return false;
        unsigned char b=0;memcpy(&b,data,1);if(b>1)return false;
        *value=b!=0;return true;
    }
    Result prepare(void* model,void* pack_id,void* level_id,Diagnostic* d) {
        void* levels[]={level_id};return prepare_many(model,pack_id,levels,1,d);
    }
    Result prepare_many(void* model,void* pack_id,void* const* level_ids,size_t count,Diagnostic* d){
        if(!unbox||!value_size||!ascii_equals(api,pack_id,kPackId)||!level_ids||
           !count||count>kMaxGeneratedLevels||count!=approved_count||entry_count)
            return refuse(d,"local-free-bound-IDs");
        for(size_t i=0;i<count;++i){
            const char* expected=approved_ids?approved_ids[i]:kProbeLevelId;
            if(!expected||strncmp(expected,"bsd_additive_",13)||strlen(expected)<=13||
               strlen(expected)>80||!ascii_equals(api,level_ids[i],expected))return refuse(d,"local-free-bound-IDs");
            for(size_t j=0;j<i;++j){
                const char* other=approved_ids?approved_ids[j]:kProbeLevelId;
                if(!strcmp(expected,other))return refuse(d,"local-free-duplicate-ID");
            }
        }
        entry_count=count+1;
        void* mc=api.object_get_class(model);
        void* ef=field(api,mc,"_entitlements",0x48);
        void* entitlement=ef?read_ref(api,model,ef):NULL;
        if(!entitlement||!named(api,api.object_get_class(entitlement),"BeatmapLevelsEntitlementModel"))
            return refuse(d,"local-free-entitlement-model");
        if(!roots.keep(model)||!roots.keep(entitlement)||!roots.keep(pack_id))
            return AllocationFailed;
        const char* fields[]={"_alwaysOwnedBeatmapLevelIds","_alwaysOwnedPacksIds"};
        for(size_t i=0;i<count;++i){ids[i]=level_ids[i];if(!roots.keep(ids[i]))return AllocationFailed;}
        ids[count]=pack_id;
        for(size_t i=0;i<entry_count;++i){
            const int which=i<count?0:1;
            void* f=field(api,api.object_get_class(entitlement),fields[which],0x18+8*which);
            sets[i]=f?read_ref(api,entitlement,f):NULL;
            if(!sets[i])return refuse(d,"local-free-set-field");
            void* c=api.object_get_class(sets[i]);
            const char *n=api.class_get_name(c),*ns=api.class_get_namespace(c);
            if(!n||!ns||strcmp(n,"HashSet`1")||strcmp(ns,"System.Collections.Generic"))
                return refuse(d,"local-free-set-class");
            if(!roots.keep(sets[i]))return AllocationFailed;
            contains[i]=api.class_get_method_from_name(c,"Contains",1);
            add[i]=api.class_get_method_from_name(c,"Add",1);
            remove[i]=api.class_get_method_from_name(c,"Remove",1);
            if(!contains[i]||!add[i]||!remove[i])return refuse(d,"local-free-set-methods");
        }
        // Observe ALL original memberships before changing either. Only these
        // exact, reviewed bound IDs may ever be added or removed by this object.
        for(size_t i=0;i<entry_count;++i){bool threw=false;
            if(!boolean(contains[i],sets[i],ids[i],&existed[i],&threw)){
                if(d)d->stage="local-free-original-membership";
                return threw?ManagedException:VerificationFailed;
            }
        }
        for(size_t i=0;i<entry_count;++i){
            bool threw=false,ignored=false,present=false;
            if(!existed[i]){
                attempted[i]=true; // invocation may mutate THEN throw
                if(!boolean(add[i],sets[i],ids[i],&ignored,&threw)){
                    if(d)d->stage="local-free-add";
                    return threw?ManagedException:VerificationFailed;
                }
            }
            if(!boolean(contains[i],sets[i],ids[i],&present,&threw)||!present){
                if(d)d->stage="local-free-add-readback";
                return threw?ManagedException:VerificationFailed;
            }
        }
        ready=true;return Added;
    }
    // Called after core registration result, BEFORE this context/GC roots die.
    // Success does no managed calls after model publication. Failure restores
    // only memberships this context attempted to add; existing free/DLC/user
    // memberships are never removed. A failed restore is reported explicitly.
    Result finish(Result result,Diagnostic* d){
        if((result==Added||result==AlreadyPresent)&&ready)return result;
        bool restored=true;
        for(int i=(int)entry_count-1;i>=0;--i){
            if(!attempted[i]||existed[i])continue;
            bool threw=false,ignored=false,present=true;
            boolean(remove[i],sets[i],ids[i],&ignored,&threw);
            // Even if Remove threw after mutation, a successful absent readback
            // verifies state. Never replace/clear either original HashSet.
            threw=false;
            if(!boolean(contains[i],sets[i],ids[i],&present,&threw)||present)restored=false;
        }
        if(!restored){if(d)d->stage="local-free-rollback-verification";return PublicationUnsafe;}
        return result;
    }
private:
    LocalContent(const LocalContent&);
    LocalContent& operator=(const LocalContent&);
};
inline Result prepare_local_content(const Api&,void* model,void* pack_id,void* level_id,
                                    void* context,Diagnostic* d){
    if(!context)return refuse(d,"local-free-context");
    return ((LocalContent*)context)->prepare(model,pack_id,level_id,d);
}
inline Result prepare_local_content_many(const Api&,void* model,void* pack_id,void* const* level_ids,
                                         size_t count,void* context,Diagnostic* d){
    if(!context)return refuse(d,"local-free-context");
    return ((LocalContent*)context)->prepare_many(model,pack_id,level_ids,count,d);
}
} // namespace
