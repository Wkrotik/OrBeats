// Genuine managed allocation/invocation only; called on the game's UI thread.
#pragma once
#include "scoresaber.h"
#include <stdio.h>
#include "../../orbeats/include/additive_song_packs.h"
namespace OrBeatsExtras {
struct UiApi {
    BsdAdditive::Api managed;
    void* (*declaring_type)(void*);
    void* (*parent)(void*);
};
struct ViewParts { void *table,*loading,*scope,*list,*key_field; };
inline bool view_parts(const UiApi& u,void* self,ViewParts& p) {
    const auto& a=u.managed;
    if(!self || !BsdAdditive::named(a,a.object_get_class(self),"PlatformLeaderboardViewController"))return false;
    void* klass=a.object_get_class(self);
    const char* names[]={"_leaderboardTableView","_loadingControl","_scopeSegmentedControl","_scores","_beatmapKey","_getScoresAsyncRequest","_getOnlineServicesAvailabilityCancelationTokenSource"};
    const size_t offsets[]={0x78,0x88,0x80,0xe0,0xf0,0xd0,0xd8};void* f[7];
    for(unsigned i=0;i<7;++i)if(!(f[i]=BsdAdditive::field(a,klass,names[i],offsets[i])))return false;
    if(BsdAdditive::read_ref(a,self,f[5]) || BsdAdditive::read_ref(a,self,f[6]))return false; // never take over an in-flight Sony request
    p={BsdAdditive::read_ref(a,self,f[0]),BsdAdditive::read_ref(a,self,f[1]),BsdAdditive::read_ref(a,self,f[2]),BsdAdditive::read_ref(a,self,f[3]),f[4]};
    return p.table && p.loading && p.scope && p.list &&
        BsdAdditive::named(a,a.object_get_class(p.table),"LeaderboardTableView") &&
        BsdAdditive::named(a,a.object_get_class(p.loading),"LoadingControl");
}
inline bool invoke_ui(const UiApi& u,void* object,const char* name,int count,void** args,void** result=NULL) {
    const auto& a=u.managed;if(!object)return false;
    const void* method=a.class_get_method_from_name(a.object_get_class(object),name,count);
    if(!method)return false;bool threw=false;void* value=BsdAdditive::invoke(a,method,object,args,&threw);
    if(result)*result=value;return !threw;
}
inline bool status_text(const UiApi& u,void* self,const char* message) {
    ViewParts p;if(!view_parts(u,self,p))return false;
    const auto& a=u.managed;BsdAdditive::Roots roots(a);void* text=a.string_new(message);
    if(!roots.keep(text))return false;bool refresh=false;void* args[]={text,&refresh};
    return invoke_ui(u,p.loading,"ShowText",2,args);
}
inline bool hide_scopes(const UiApi& u,void* self) {
    ViewParts p;if(!view_parts(u,self,p))return false;
    void* game_object=NULL;if(!invoke_ui(u,p.scope,"get_gameObject",0,NULL,&game_object) || !game_object)return false;
    bool active=false;void* args[]={&active};return invoke_ui(u,game_object,"SetActive",1,args);
}
inline bool table_visible(const UiApi& u,void* self,bool active) {
    ViewParts p;if(!view_parts(u,self,p))return false;
    void* object=NULL;if(!invoke_ui(u,p.table,"get_gameObject",0,NULL,&object) || !object)return false;
    void* args[]={&active};return invoke_ui(u,object,"SetActive",1,args);
}
inline bool show_scores(const UiApi& u,void* self,const ScoreBoard& board) {
    if(board.count>kMaxScores || board.count>board.total)return false;
    ViewParts p;if(!view_parts(u,self,p))return false;
    const auto& a=u.managed;void* list_class=a.object_get_class(p.list);
    const char* ns=a.class_get_namespace(list_class);const char* name=a.class_get_name(list_class);
    if(!ns || !name || strcmp(ns,"System.Collections.Generic") || strcmp(name,"List`1"))return false;
    void* items_field=BsdAdditive::field(a,list_class,"_items",0x10);
    if(!items_field)return false;void* items=BsdAdditive::read_ref(a,p.list,items_field);
    if(!items)return false;void* array_class=a.object_get_class(items);
    if(a.class_get_rank(array_class)!=1)return false;void* row_class=a.class_get_element_class(array_class);
    if(!BsdAdditive::named(a,row_class,"ScoreData") || !u.declaring_type ||
       !BsdAdditive::named(a,u.declaring_type(row_class),"LeaderboardTableView"))return false;
    const void* ctor=a.class_get_method_from_name(list_class,".ctor",0);
    const void* add=a.class_get_method_from_name(list_class,"Add",1);
    const void* row_ctor=a.class_get_method_from_name(row_class,".ctor",4);
    const void* set=a.class_get_method_from_name(a.object_get_class(p.table),"SetScores",2);
    if(!ctor || !add || !row_ctor || !set)return false;
    BsdAdditive::Roots roots(a);void* list=a.object_new(list_class);bool threw=false;
    if(!roots.keep(list))return false;BsdAdditive::invoke(a,ctor,list,NULL,&threw);if(threw)return false;
    for(unsigned i=0;i<board.count;++i) {
        const ScoreRow& input=board.rows[i];if(input.rank!=(int)i+1 || input.score<0 || !memchr(input.name,0,sizeof(input.name)))return false;
        char labelled[sizeof(input.name)+16];snprintf(labelled,sizeof(labelled),"[SS/PC] %s",input.name);
        void* text=a.string_new(labelled);if(!roots.keep(text))return false;
        void* row=a.object_new(row_class);if(!roots.keep(row))return false;
        int score=input.score,rank=input.rank;bool fc=input.full_combo;void* args[]={&score,text,&rank,&fc};
        BsdAdditive::invoke(a,row_ctor,row,args,&threw);if(threw)return false;
        void* add_args[]={row};BsdAdditive::invoke(a,add,list,add_args,&threw);if(threw)return false;
    }
    // Publish once, only after all rows were constructed. SetScores owns the
    // ordinary managed reference/barrier and native TableView.ReloadData path.
    int special=-1;void* args[]={list,&special};BsdAdditive::invoke(a,set,p.table,args,&threw);
    return !threw && invoke_ui(u,p.loading,"Hide",0,NULL);
}
} // namespace
