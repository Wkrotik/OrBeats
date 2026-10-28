// Link production transport to fake PS4 imports. No actual network/console.
#include "transport.h"
#include "ps4_http.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
using namespace OrBeatsExtras;
static int calls=0,fail_at=0,live=0,pages=0,reads=0,closed=0;
static uint64_t now=1000000;
static std::string scenario,body,diagnostics;
static void diagnostic(const char* message){diagnostics+=message;diagnostics+="\n";}
static size_t position;
static int attempt(){++calls;return calls==fail_at?-1:0;}
static int acquire(){if(attempt()<0)return -1;++live;return 20+live;}
static int release(int id){assert(id>=20 && live>0);--live;++closed;return 0;}
extern "C" {
uint64_t sceKernelGetProcessTime(){return now;}
int32_t sceSysmoduleIsLoadedInternal(uint32_t){return scenario=="modules-present"?0:-1;}
int32_t sceSysmoduleLoadModuleInternal(uint32_t id){assert(id==0x8000001c || id==0x8000000b || id==0x8000000a);return attempt();}
int32_t sceNetPoolCreate(const char* name,int32_t bytes,int32_t flags){assert(!strcmp(name,"OrBeatsExtrasHTTP") && bytes==1024*1024 && !flags);return acquire();}
void sceNetPoolDestroy(int32_t id){release(id);}
int32_t sceSslInit(size_t bytes){assert(bytes==1024*1024);return acquire();}
int32_t sceSslTerm(int32_t id){return release(id);}
int32_t sceHttpInit(int32_t pool,int32_t ssl,size_t bytes){assert(pool>=20 && ssl>=20 && bytes==1024*1024);return acquire();}
int32_t sceHttpTerm(int32_t id){return release(id);}
int32_t sceHttpCreateTemplate(int32_t id,const char* ua,int32_t version,int32_t proxy){assert(id>=20 && strstr(ua,"readonly") && version==2 && proxy==0);return acquire();}
int32_t sceHttpDeleteTemplate(int32_t id){return release(id);}
int32_t sceHttpsEnableOption(int32_t id,uint32_t flags){assert(id>=20 && flags==0xbd);return attempt();}
#define DISABLE(name) int32_t name(int32_t id,int32_t value){assert(id>=20 && value==0);return attempt();}
DISABLE(sceHttpSetAutoRedirect)
DISABLE(sceHttpSetAuthEnabled)
DISABLE(sceHttpSetCookieEnabled)
DISABLE(sceHttpSetInflateGZIPEnabled)
DISABLE(sceHttpSetResolveRetry)
#define TIMEOUT(name) int32_t name(int32_t id,uint32_t value){assert(id>=20 && value>0 && value<=2000000);return attempt();}
TIMEOUT(sceHttpSetResolveTimeOut)
TIMEOUT(sceHttpSetConnectTimeOut)
TIMEOUT(sceHttpSetSendTimeOut)
TIMEOUT(sceHttpSetRecvTimeOut)
int32_t sceHttpCreateConnection(int32_t id,const char* host,const char* scheme,uint16_t port,int32_t keep){assert(id>=20 && !strcmp(host,"scoresaber.com") && !strcmp(scheme,"https") && port==443 && !keep);return acquire();}
int32_t sceHttpDeleteConnection(int32_t id){return release(id);}
int32_t sceHttpCreateRequestWithURL(int32_t id,int32_t method,const char* url,uint64_t bytes){
 assert(id>=20 && method==0 && !bytes && !strncmp(url,"https://scoresaber.com/",22));
 assert(strstr(url,"difficulty=9&gameMode=SoloStandard&page="));
 const char* number=strstr(url,"&page=");assert(number);unsigned page=(unsigned)atoi(number+6);assert(page==(unsigned)pages+1);++pages;
 body="{\"metadata\":{\"total\":"+std::to_string(scenario=="empty"?0:scenario=="changed" && page==2?107:108)+",\"page\":"+std::to_string(page)+",\"itemsPerPage\":12},\"scores\":[";
 for(unsigned n=0;scenario!="empty" && n<12;++n){
  if(n)body+=",";
  body+="{\"rank\":"+std::to_string((page-1)*12+n+1)+",\"modifiedScore\":99999,\"fullCombo\":false,\"leaderboardPlayerInfo\":{\"name\":\"Player\"}}";
 }
 body+="]}";position=0;
 if(scenario=="oversize")body=std::string(kMaxScoreResponse+1,'x');
 if(scenario=="json")body="{bad";
 return acquire();
}
int32_t sceHttpDeleteRequest(int32_t id){return release(id);}
int32_t sceHttpAddRequestHeader(int32_t id,const char* name,const char* value,int32_t mode){assert(id>=20 && mode==0);assert((!strcmp(name,"Accept") && !strcmp(value,"application/json")) || (!strcmp(name,"Accept-Encoding") && !strcmp(value,"identity")));return attempt();}
int32_t sceHttpSendRequest(int32_t id,const void* body,size_t bytes){assert(id>=20 && !body && !bytes);if(scenario=="send-deadline")now+=30000000;if(scenario=="send-error" || scenario=="ssl-error" || scenario=="diagnostic-error")return (int32_t)0x80431075;return attempt();}
int32_t sceHttpGetStatusCode(int32_t id,int32_t* status){assert(id>=20);*status=scenario=="404"?404:scenario=="429"?429:scenario=="redirect"?302:scenario=="500"?500:200;return attempt();}
int32_t sceHttpGetLastErrno(int32_t id,int32_t* error){assert(id>=20);*error=42;return scenario=="diagnostic-error"?-1:0;}
int32_t sceHttpsGetSslError(int32_t id,int32_t* error,uint32_t* detail){assert(id>=20);*error=(int32_t)0x81800006;*detail=0x20;return scenario=="diagnostic-error"?-1:0;}
int32_t sceHttpReadData(int32_t id,void* bytes,uint32_t capacity){
 assert(id>=20 && capacity>0 && capacity<=16384);++reads;
 if(attempt()<0)return -1;
 if(scenario=="read-deadline")now+=30000000;
 if(scenario=="time-backwards")now=0;
 if(scenario=="invalid-count")return (int)capacity+1;
 size_t count=body.size()-position;if(count>capacity)count=capacity;
 if(scenario=="chunks" && count>7)count=7;
 memcpy(bytes,body.data()+position,count);position+=count;return (int)count;
}
}
static bool cancelled(void*){return scenario=="cancel-before" || (scenario=="cancel-read" && reads>0) || (scenario=="cancel-second" && pages==2);}
static void reset(){diagnostics.clear();calls=live=pages=reads=closed=0;now=1000000;position=0;}
int main(int argc,char** argv){
 assert(argc==2);scenario=argv[1];set_transport_logger(scenario=="no-logger"?NULL:diagnostic);
 if(scenario=="faults") {
  scenario="normal";ScoreBoard board;assert(fetch_scores("8AF82A87167070A08EC63DBA0459C829C2954067",9,100,cancelled,NULL,&board)==FetchResult::Ok && live==0);
  int maximum=calls;
  for(fail_at=1;fail_at<=maximum;++fail_at){reset();memset(&board,0xaa,sizeof(board));FetchResult r=fetch_scores("8AF82A87167070A08EC63DBA0459C829C2954067",9,100,cancelled,NULL,&board);assert(r!=FetchResult::Ok && !live && board.count==0 && board.total==0 && !board.rows[0].name[0]);assert(diagnostics.find("result=0xffffffff")!=std::string::npos);}
  return 0;
 }
 ScoreBoard board;memset(&board,0xaa,sizeof(board));
 unsigned limit=scenario=="fifty"?50:100;
 FetchResult r=fetch_scores(scenario=="identity"?"generated_level_id":"8AF82A87167070A08EC63DBA0459C829C2954067",9,limit,cancelled,NULL,&board);
 assert(live==0);
 if(scenario=="normal" || scenario=="fifty" || scenario=="chunks" || scenario=="modules-present" || scenario=="no-logger")assert(r==FetchResult::Ok && board.count==limit && pages==(limit==50?5:9));
 else if(scenario=="empty")assert(r==FetchResult::Ok && board.count==0 && pages==1);
 else {
  FetchResult expected=scenario=="identity"?FetchResult::InvalidIdentity:scenario.find("cancel")==0?FetchResult::Cancelled:scenario.find("deadline")!=std::string::npos || scenario=="time-backwards"?FetchResult::Deadline:scenario=="404"?FetchResult::Missing:scenario=="429"?FetchResult::RateLimited:scenario=="redirect" || scenario=="500"?FetchResult::Http:scenario=="oversize"?FetchResult::TooLarge:(scenario=="invalid-count" || scenario=="send-error" || scenario=="ssl-error" || scenario=="diagnostic-error")?FetchResult::Network:FetchResult::Protocol;
  assert(r==expected && board.count==0 && board.total==0 && !board.rows[0].name[0]);
  if(scenario=="identity" || scenario=="cancel-before")assert(calls==0);
 }
 if(scenario=="send-error" || scenario=="ssl-error" || scenario=="diagnostic-error"){
  assert(diagnostics.find("sceHttpSendRequest result=0x80431075")!=std::string::npos);
  if(scenario=="diagnostic-error")assert(diagnostics.find("TLS verification detail")==std::string::npos && diagnostics.find("HTTP errno")==std::string::npos);
  else assert(diagnostics.find("TLS verification detail result=0x00000020")!=std::string::npos && diagnostics.find("HTTP errno result=0x0000002a")!=std::string::npos);
 }
 assert(diagnostics.find("8AF82A87167070A08EC63DBA0459C829C2954067")==std::string::npos && diagnostics.find("https://")==std::string::npos && diagnostics.find("Player")==std::string::npos);
 if(scenario=="no-logger")assert(diagnostics.empty());
 return 0;
}
