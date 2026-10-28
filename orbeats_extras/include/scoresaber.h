// Native, anonymous ScoreSaber page decoding. No Unity or network calls here.
#pragma once
#include <stddef.h>
#include <stdint.h>
namespace OrBeatsExtras {
static const size_t kMaxScoreResponse = 512 * 1024;
static const unsigned kScorePageSize = 12, kMaxScores = 100;
// The stock panel has ten visible rows and no verified scrolling affordance.
static const unsigned kLeaderboardScores = 10;
struct ScoreRow { int score, rank; bool full_combo; char name[257]; };
struct ScorePage { unsigned total, count; ScoreRow rows[kScorePageSize]; };
struct ScoreBoard { unsigned total, count; ScoreRow rows[kMaxScores]; };
// Standard is explicit; never derive an original hash from our generated level ID.
bool score_url(char* out, size_t bytes, const char* hash, int difficulty, unsigned page);
bool score_page(const char* json, size_t bytes, unsigned page, ScorePage* out);
// Failure clears the board; callers must not display a partially validated result.
bool append_scores(ScoreBoard* board, const ScorePage& page, unsigned number, unsigned limit);
} // namespace OrBeatsExtras
