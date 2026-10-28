#include "worker.h"
#include <assert.h>
#include <chrono>
#include <string.h>
#include <thread>
using namespace OrBeatsExtras;
static std::atomic<int> calls(0),entered(0),cancelled_count(0),mode(0);
static std::atomic<bool> hold(false);
static std::atomic<uint64_t> clock_value(1000000);
static uint64_t now(){return clock_value.load();}
static void sleep(){std::this_thread::sleep_for(std::chrono::milliseconds(1));}
static FetchResult fetch(const char* hash,int difficulty,unsigned limit,bool(*cancelled)(void*),void* context,ScoreBoard* board){
 assert(strlen(hash)==40 && (difficulty==1 || difficulty==3) && limit==100);
 ++calls;++entered;
 for(unsigned i=0;hold.load() && i<4000;++i){if(cancelled(context)){++cancelled_count;return FetchResult::Cancelled;}sleep();}
 assert(!hold.load());
 if(cancelled(context)){++cancelled_count;return FetchResult::Cancelled;}
 if(mode.load()==1)return FetchResult::RateLimited;
 if(mode.load()==2)return FetchResult::Missing;
 board->total=board->count=1;board->rows[0].rank=1;board->rows[0].score=(int)hash[39];return FetchResult::Ok;
}
static ScoreKey key(char last){ScoreKey k={};memset(k.hash,'a',40);k.hash[39]=last;k.difficulty=1;return k;}
static ScoreReply reply;
static void take(ScoreWorker& w,uint64_t generation){
 for(unsigned i=0;i<4000;++i){if(w.take(generation,reply)){assert(reply.generation==generation);return;}sleep();}assert(false);
}
static void wait_for(std::atomic<int>& value,int minimum){for(unsigned i=0;i<4000 && value.load()<minimum;++i)sleep();assert(value.load()>=minimum);}
int main(int argc,char** argv){
 assert(argc==2);ScoreWorker w;assert(!w.start(NULL,now));assert(!w.start(fetch,NULL));assert(w.start(fetch,now));assert(!w.start(fetch,now));
 ScoreKey a=key('1'),b=key('2'),c=key('3');
 if(!strcmp(argv[1],"latest")){
  hold.store(true);uint64_t old=w.select(&a);wait_for(entered,1);
  w.select(&b);uint64_t latest=w.select(&c);assert(!w.take(old,reply));hold.store(false);take(w,latest);
  assert(reply.result==FetchResult::Ok && reply.board.rows[0].score=='3');assert(!w.take(latest,reply));assert(cancelled_count.load()>=1 || calls.load()>=2);
 }else if(!strcmp(argv[1],"cancel")){
  hold.store(true);uint64_t old=w.select(&a);wait_for(entered,1);uint64_t empty=w.select(NULL);wait_for(cancelled_count,1);
  assert(!w.take(old,reply) && !w.take(empty,reply));hold.store(false);take(w,w.select(&b));assert(reply.board.rows[0].score=='2');
 }else if(!strcmp(argv[1],"stop")){
  hold.store(true);w.select(&a);wait_for(entered,1);w.stop();assert(cancelled_count.load()==1);assert(!w.take(1,reply));
  hold.store(false);w.select(&a);std::this_thread::sleep_for(std::chrono::milliseconds(30));assert(calls.load()==1);
  assert(w.start(fetch,now));take(w,w.select(&a));assert(calls.load()==2);
 }else if(!strcmp(argv[1],"ttl") || !strcmp(argv[1],"rate") || !strcmp(argv[1],"missing")){
  int m=!strcmp(argv[1],"rate")?1:!strcmp(argv[1],"missing")?2:0;mode.store(m);
  uint64_t ttl=m==1?60000000:m==2?15000000:120000000;
  take(w,w.select(&a));assert(calls.load()==1);take(w,w.select(&a));assert(calls.load()==1);
  clock_value.fetch_add(ttl-1);take(w,w.select(&a));assert(calls.load()==1);
  clock_value.fetch_add(1);take(w,w.select(&a));assert(calls.load()==2);
  assert(reply.result==(m==1?FetchResult::RateLimited:m==2?FetchResult::Missing:FetchResult::Ok));
  if(m)assert(!reply.board.count);
  a.difficulty=3;take(w,w.select(&a));assert(calls.load()==3); // characteristic difficulty is part of cache key
 }else if(!strcmp(argv[1],"bound")){
  for(unsigned i=0;i<9;++i){ScoreKey k=key((char)('1'+i));take(w,w.select(&k));}
  assert(calls.load()==9);take(w,w.select(&a));assert(calls.load()==10); // eight slots, bounded eviction
 }else assert(false);
 w.stop();w.stop();
}
