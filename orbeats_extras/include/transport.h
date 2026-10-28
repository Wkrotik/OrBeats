#pragma once
#include "scoresaber.h"
namespace OrBeatsExtras {
enum class FetchResult { Ok, InvalidIdentity, Cancelled, Deadline, Network, Http, Missing, RateLimited, TooLarge, Protocol, Memory };
// Blocking, worker-thread-only. No Unity calls, no auth, no redirects/retries.
// Cancellation/deadline is checked between bounded platform I/O calls.
FetchResult fetch_scores(const char* original_sha1, int difficulty, unsigned limit,
                         bool (*cancelled)(void*), void* context, ScoreBoard* board);
} // namespace OrBeatsExtras
