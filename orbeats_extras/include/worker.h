#pragma once
#include "transport.h"
#include <atomic>
namespace OrBeatsExtras {
struct ScoreKey { char hash[41]; int difficulty; };
struct ScoreReply { uint64_t generation; FetchResult result; ScoreBoard board; };
// One network thread, latest-selection mailbox, eight bounded TTL cache slots.
// Only native values cross threads. The worker never receives managed pointers.
class ScoreWorker {
public:
    using Fetch = FetchResult (*)(const char*,int,unsigned,bool(*)(void*),void*,ScoreBoard*);
    using Clock = uint64_t (*)();
    ScoreWorker();
    bool start(Fetch fetch,Clock clock);
    void stop(); // cancel, join, then destroy; no detached thread
    uint64_t select(const ScoreKey* key); // NULL cancels selection
    bool take(uint64_t generation,ScoreReply& out);
private:
    struct Cache { bool valid; ScoreKey key; FetchResult result; ScoreBoard board; uint64_t until; };
    struct Cancellation { ScoreWorker* worker; uint64_t generation; };
    std::atomic_flag lock_=ATOMIC_FLAG_INIT;
    std::atomic<uint64_t> generation_;
    std::atomic<bool> stopping_;
    void* thread_;
    bool started_,pending_,completed_;
    ScoreKey key_;
    uint64_t requested_;
    ScoreReply reply_;
    Cache cache_[8]; unsigned next_;
    Fetch fetch_; Clock clock_;
    void lock(); void unlock();
    static bool cancelled(void*);
    static void* run(void*);
};
} // namespace
