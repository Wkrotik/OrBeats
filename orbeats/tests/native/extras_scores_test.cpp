#include "scoresaber.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
using namespace OrBeatsExtras;
int main(int argc, char** argv) {
    char url[256];
    assert(score_url(url, sizeof(url), "8af82a87167070a08ec63dba0459c829c2954067", 9, 1));
    assert(strstr(url, "/8AF82A87167070A08EC63DBA0459C829C2954067/scores?difficulty=9&gameMode=SoloStandard&page=1"));
    assert(!score_url(url, 10, "8af82a87167070a08ec63dba0459c829c2954067", 9, 1) && !url[0]);
    assert(!score_url(url, sizeof(url), "bsd_additive_123", 9, 1));
    assert(!score_url(url, sizeof(url), "8af82a87167070a08ec63dba0459c829c2954067", 2, 1));
    assert(!score_url(url, sizeof(url), "8af82a87167070a08ec63dba0459c829c2954067", 9, 10));
    static char raw[kMaxScoreResponse + 2];
    size_t bytes = fread(raw, 1, sizeof(raw), stdin);
    ScorePage page;
    memset(&page, 0xaa, sizeof(page));
    unsigned number = (argc == 3 && !strcmp(argv[1], "page")) ? (unsigned)atoi(argv[2]) : 1;
    bool ok = score_page(raw, bytes, number, &page);
    if (argc == 3 && !strcmp(argv[1], "page")) {
        assert(ok);
        printf("{\"page\":%u,\"total\":%u,\"count\":%u}\n", number, page.total, page.count);
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "bad")) {
        assert(!ok && page.count == 0 && page.total == 0 && !page.rows[0].name[0]);
        return 0;
    }
    assert(ok && page.total == 108 && page.count == 12 && page.rows[0].score == 99999);
    assert(page.rows[0].rank == 1 && page.rows[0].full_combo);
    if (argc == 2 && !strcmp(argv[1], "name")) { puts(page.rows[0].name); return 0; }
    assert(!strcmp(page.rows[0].name, "\xe2\x80\xb9" "b" "\xe2\x80\xba" "Player" "\xe2\x80\xb9" "/b" "\xe2\x80\xba"));
    ScoreBoard board = {};
    assert(append_scores(&board, page, 1, 100) && board.count == 12);
    assert(!append_scores(&board, page, 3, 100) && !board.count);
    assert(append_scores(&board, page, 1, 100));
    ++page.total;
    assert(!append_scores(&board, page, 2, 100) && !board.count);
    --page.total;
    for (unsigned limit = 50; limit <= 100; limit += 50) {
        memset(&board, 0, sizeof(board));
        for (unsigned number = 1; board.count < limit; ++number) {
            for (unsigned i = 0; i < 12; ++i) page.rows[i].rank = (int)((number - 1) * 12 + i + 1);
            assert(append_scores(&board, page, number, limit));
        }
        assert(board.count == limit && board.rows[limit - 1].rank == (int)limit);
        ++page.total;
        assert(!append_scores(&board, page, 9, limit) && !board.count);
        --page.total;
    }
    return 0;
}
