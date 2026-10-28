#include "transport.h"
#include "ps4_http.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <atomic>
#include "health.h"

namespace OrBeatsExtras {
namespace {
static std::atomic<void (*)(const char*)> write_log(NULL);
static void diagnostic(const char* operation,int32_t result) {
    auto logger=write_log.load();if(!logger)return;
    char text[160];snprintf(text,sizeof(text),"ScoreSaber transport: %s result=0x%08x",operation,(unsigned)result);logger(text);
}
static bool checked(const char* operation,int32_t result){if(result<0){diagnostic(operation,result);return false;}return true;}
static bool configured(const char* operation,int32_t result){if(result!=0){diagnostic(operation,result);return false;}return true;}
static void request_error(int id) {
    int32_t error=0;uint32_t detail=0;
    int result=sceHttpGetLastErrno(id,&error);diagnostic("sceHttpGetLastErrno",result);
    if(result==0)diagnostic("HTTP errno",error);
    error=0;result=sceHttpsGetSslError(id,&error,&detail);diagnostic("sceHttpsGetSslError",result);
    if(result==0){diagnostic("TLS error",error);diagnostic("TLS verification detail",(int32_t)detail);}
}
// Own contexts only. Never initialize/terminate the game's shared Net subsystem.
struct Session {
    int pool=-1, ssl=-1, http=-1, templ=-1;
    ~Session() {
        if(templ>=0)sceHttpDeleteTemplate(templ);
        if(http>=0)sceHttpTerm(http);
        if(ssl>=0)sceSslTerm(ssl);
        if(pool>=0)sceNetPoolDestroy(pool);
    }
    bool start() {
        // libSceNet, libSceSsl, libSceHttp; a failure is unavailable, not an SSL bypass.
        const uint32_t modules[]={0x8000001c,0x8000000b,0x8000000a};
        for(unsigned i=0;i<3;++i) {
            // Reuse already loaded process modules without acquiring repeatedly.
            // Never unload them: the title/another plugin may depend on them.
            if(sceSysmoduleIsLoadedInternal(modules[i])!=0 &&
               !checked("sceSysmoduleLoadModuleInternal",sceSysmoduleLoadModuleInternal(modules[i])))return false;
        }
        pool=sceNetPoolCreate("OrBeatsExtrasHTTP",1024*1024,0);if(!checked("sceNetPoolCreate",pool))return false;
        ssl=sceSslInit(1024*1024);if(!checked("sceSslInit",ssl))return false;
        http=sceHttpInit(pool,ssl,1024*1024);if(!checked("sceHttpInit",http))return false;
        char agent[64];snprintf(agent,sizeof(agent),"OrBeats-Extras/%s-readonly",kVersion);
        templ=sceHttpCreateTemplate(http,agent,2,0);if(!checked("sceHttpCreateTemplate",templ))return false;
        // Server signature + hostname + both validity dates + known CA + SNI.
        // Never install a certificate callback or disable any verification flags.
        return configured("sceHttpsEnableOption",sceHttpsEnableOption(templ,0xbd)) &&
            configured("sceHttpSetAutoRedirect",sceHttpSetAutoRedirect(templ,0)) &&
            configured("sceHttpSetAuthEnabled",sceHttpSetAuthEnabled(templ,0)) &&
            configured("sceHttpSetCookieEnabled",sceHttpSetCookieEnabled(templ,0)) &&
            configured("sceHttpSetInflateGZIPEnabled",sceHttpSetInflateGZIPEnabled(templ,0)) &&
            configured("sceHttpSetResolveRetry",sceHttpSetResolveRetry(templ,0));
    }
};
struct Request {
    int connection=-1, request=-1;
    ~Request(){if(request>=0)sceHttpDeleteRequest(request);if(connection>=0)sceHttpDeleteConnection(connection);}
};
struct Buffer {
    char* bytes;
    Buffer():bytes((char*)malloc(kMaxScoreResponse+1)){}
    ~Buffer(){free(bytes);}
};
struct Control {
    uint64_t started;
    bool (*cancelled)(void*);
    void* context;
    FetchResult check() const {
        if(cancelled(context))return FetchResult::Cancelled;
        uint64_t now=sceKernelGetProcessTime();
        return now<started || now-started>=30000000 ? FetchResult::Deadline : FetchResult::Ok;
    }
    uint32_t timeout() const {
        uint64_t now=sceKernelGetProcessTime();
        if(now<started || now-started>=30000000)return 0;
        // SendRequest can include resolve/connect/send/receive phases. Budget all
        // four; cancellation is cooperative, not a kill of an in-flight call.
        uint64_t part=(30000000-(now-started))/4;
        return (uint32_t)(part<2000000?part:2000000);
    }
};
static FetchResult get_page(Session& session,const Control& control,const char* url,char* data,size_t& used) {
    used=0;
    uint32_t timeout=control.timeout();if(!timeout)return FetchResult::Deadline;
    int id=session.templ;
    if(!checked("sceHttpSetResolveTimeOut",sceHttpSetResolveTimeOut(id,timeout)) ||
       !checked("sceHttpSetConnectTimeOut",sceHttpSetConnectTimeOut(id,timeout)) ||
       !checked("sceHttpSetSendTimeOut",sceHttpSetSendTimeOut(id,timeout)) ||
       !checked("sceHttpSetRecvTimeOut",sceHttpSetRecvTimeOut(id,timeout)))return FetchResult::Network;
    Request r;
    r.connection=sceHttpCreateConnection(id,"scoresaber.com","https",443,0);
    if(!checked("sceHttpCreateConnection",r.connection))return FetchResult::Network;
    r.request=sceHttpCreateRequestWithURL(r.connection,0,url,0);
    if(!checked("sceHttpCreateRequestWithURL",r.request))return FetchResult::Network;
    if(!checked("sceHttpAddRequestHeader Accept",sceHttpAddRequestHeader(r.request,"Accept","application/json",0)) ||
       !checked("sceHttpAddRequestHeader Accept-Encoding",sceHttpAddRequestHeader(r.request,"Accept-Encoding","identity",0)))return FetchResult::Network;
    FetchResult check=control.check();if(check!=FetchResult::Ok)return check;
    if(!checked("sceHttpSendRequest",sceHttpSendRequest(r.request,NULL,0))){request_error(r.request);return FetchResult::Network;}
    check=control.check();if(check!=FetchResult::Ok)return check;
    int status=0;
    if(!checked("sceHttpGetStatusCode",sceHttpGetStatusCode(r.request,&status)))return FetchResult::Network;
    diagnostic("HTTP status",status);
    if(status==404)return FetchResult::Missing;
    if(status==429)return FetchResult::RateLimited;
    if(status!=200)return FetchResult::Http;
    for(;;) {
        check=control.check();if(check!=FetchResult::Ok)return check;
        timeout=control.timeout();if(!timeout)return FetchResult::Deadline;
        if(!checked("sceHttpSetRecvTimeOut",sceHttpSetRecvTimeOut(r.request,timeout)))return FetchResult::Network;
        size_t capacity=kMaxScoreResponse+1-used;
        uint32_t want=(uint32_t)(capacity<16384?capacity:16384);
        int n=sceHttpReadData(r.request,data+used,want);
        if(!checked("sceHttpReadData",n)){request_error(r.request);return FetchResult::Network;}
        if((unsigned)n>want){diagnostic("sceHttpReadData invalid count",n);return FetchResult::Network;}
        check=control.check();if(check!=FetchResult::Ok)return check;
        used+=(unsigned)n;
        if(used>kMaxScoreResponse)return FetchResult::TooLarge;
        if(n==0)return FetchResult::Ok;
    }
}
}
void set_transport_logger(void (*logger)(const char*)){write_log.store(logger);}
FetchResult fetch_scores(const char* hash,int difficulty,unsigned limit,bool (*cancelled)(void*),void* context,ScoreBoard* board) {
    if(!board)return FetchResult::InvalidIdentity;
    memset(board,0,sizeof(*board));
    char url[256];
    if(!cancelled || limit<1 || limit>100 || !score_url(url,sizeof(url),hash,difficulty,1))return FetchResult::InvalidIdentity;
    Control control={sceKernelGetProcessTime(),cancelled,context};
    FetchResult result=control.check();if(result!=FetchResult::Ok)return result;
    Session session;Buffer buffer;
    if(!buffer.bytes)return FetchResult::Memory;
    if(!session.start())return FetchResult::Network;
    result=control.check();if(result!=FetchResult::Ok)return result;
    for(unsigned number=1;number<=9;++number) {
        if(!score_url(url,sizeof(url),hash,difficulty,number)) {result=FetchResult::InvalidIdentity;break;}
        size_t used=0;
        result=get_page(session,control,url,buffer.bytes,used);
        if(result!=FetchResult::Ok)break;
        ScorePage page;
        if(!score_page(buffer.bytes,used,number,&page) || !append_scores(board,page,number,limit)) {
            result=FetchResult::Protocol;break;
        }
        result=control.check();if(result!=FetchResult::Ok)break;
        if(board->count>=limit || board->count>=board->total)return FetchResult::Ok;
    }
    memset(board,0,sizeof(*board));
    return result==FetchResult::Ok?FetchResult::Protocol:result;
}
} // namespace OrBeatsExtras
