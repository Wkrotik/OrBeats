#pragma once
#include "scoresaber.h"
namespace OrBeatsExtras {
enum class FetchResult { Ok, InvalidIdentity, Cancelled, Deadline, Network, Http, Missing, RateLimited, TooLarge, Protocol, Memory };
// Set once before starting the worker. Messages contain operation/status only,
// never URLs, identities, player names or response bodies.
void set_transport_logger(void (*logger)(const char*));
// Blocking, worker-thread-only. No Unity calls, auth, redirects or application
// retries. SDK resolver defaults remain; do not require its optional retry setter.
// Cancellation/deadline is checked between bounded platform I/O calls.
FetchResult fetch_scores(const char* original_sha1, int difficulty, unsigned limit,
                         bool (*cancelled)(void*), void* context, ScoreBoard* board);
} // namespace OrBeatsExtras
