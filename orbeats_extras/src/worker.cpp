#include "worker.h"
#include <string.h>
#ifdef ORBEATS_PS4
#include <orbis/libkernel.h>
#else
#include <pthread.h>
#include <unistd.h>
#endif
namespace OrBeatsExtras {
ScoreWorker::ScoreWorker():generation_(0),stopping_(false),thread_(NULL),started_(false),pending_(false),completed_(false),requested_(0),next_(0),fetch_(NULL),clock_(NULL) {memset(cache_,0,sizeof(cache_));}
void ScoreWorker::lock(){while(lock_.test_and_set(std::memory_order_acquire)){} }
void ScoreWorker::unlock(){lock_.clear(std::memory_order_release);}
bool ScoreWorker::start(Fetch fetch,Clock clock) {
    if(started_ || !fetch || !clock)return false;
    fetch_=fetch;clock_=clock;stopping_.store(false);
#ifdef ORBEATS_PS4
    int result=scePthreadCreate((OrbisPthread*)&thread_,NULL,run,this,"OrBeatsScores");
#else
    pthread_t id;int result=pthread_create(&id,NULL,run,this);if(!result)thread_=(void*)id;
#endif
    started_=result==0;return started_;
}
void ScoreWorker::stop() {
    if(!started_)return;
    stopping_.store(true);generation_.fetch_add(1);
#ifdef ORBEATS_PS4
    scePthreadJoin((OrbisPthread)thread_,NULL);
#else
    pthread_join((pthread_t)thread_,NULL);
#endif
    lock();pending_=completed_=false;memset(cache_,0,sizeof(cache_));unlock();started_=false;
}
uint64_t ScoreWorker::select(const ScoreKey* key) {
    lock();uint64_t generation=generation_.fetch_add(1)+1;
    completed_=false;pending_=key && started_ && !stopping_.load();
    if(pending_){key_=*key;requested_=generation;}
    unlock();return generation;
}
bool ScoreWorker::take(uint64_t generation,ScoreReply& out) {
    lock();bool available=completed_ && generation==generation_.load() && reply_.generation==generation;
    if(available){out=reply_;completed_=false;}unlock();return available;
}
bool ScoreWorker::cancelled(void* context) {
    Cancellation* c=(Cancellation*)context;
    return c->worker->stopping_.load() || c->worker->generation_.load()!=c->generation;
}
void* ScoreWorker::run(void* context) {
    ScoreWorker* w=(ScoreWorker*)context;
    while(!w->stopping_.load()) {
        ScoreKey key;uint64_t generation=0;
        w->lock();if(w->pending_){key=w->key_;generation=w->requested_;w->pending_=false;}w->unlock();
        if(!generation){
#ifdef ORBEATS_PS4
            sceKernelUsleep(10000);
#else
            usleep(10000);
#endif
            continue;
        }
        ScoreReply reply={};reply.generation=generation;bool cached=false;
        uint64_t now=w->clock_();
        for(unsigned i=0;i<8;++i){Cache& c=w->cache_[i];
            if(c.valid && now<c.until && c.key.difficulty==key.difficulty && !strcmp(c.key.hash,key.hash)){
                reply.result=c.result;reply.board=c.board;cached=true;break;
            }
        }
        Cancellation cancel={w,generation};
        if(!cached)reply.result=w->fetch_(key.hash,key.difficulty,100,cancelled,&cancel,&reply.board);
        if(cancelled(&cancel))continue;
        if(!cached && reply.result!=FetchResult::Cancelled) {
            Cache& c=w->cache_[w->next_++%8];c.valid=true;c.key=key;c.result=reply.result;c.board=reply.board;
            uint64_t ttl=reply.result==FetchResult::RateLimited?60000000:reply.result==FetchResult::Ok?120000000:15000000;
            now=w->clock_();c.until=now>UINT64_MAX-ttl?UINT64_MAX:now+ttl;
        }
        w->lock();if(!cancelled(&cancel)){w->reply_=reply;w->completed_=true;}w->unlock();
    }
    return NULL;
}
} // namespace
