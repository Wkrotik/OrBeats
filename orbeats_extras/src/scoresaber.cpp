#include "scoresaber.h"
#include "../third_party/cjson/cJSON.h"
#include <stdio.h>
#include <string.h>

namespace OrBeatsExtras {
namespace {
static const cJSON* member(const cJSON* parent, const char* key) {
    if (!cJSON_IsObject(parent)) return NULL;
    const cJSON* found = NULL;
    for (const cJSON* p = parent->child; p; p = p->next) {
        if (p->string && !strcmp(p->string, key)) {
            if (found) return NULL; // Ambiguous schema fields fail closed.
            found = p;
        }
    }
    return found;
}
static bool integer(const cJSON* p, unsigned low, unsigned high, unsigned* out) {
    if (!cJSON_IsNumber(p) || !(p->valuedouble >= low && p->valuedouble <= high)) return false;
    unsigned n = (unsigned)p->valuedouble;
    if (p->valuedouble != (double)n) return false;
    *out = n;
    return true;
}
static bool codepoint(const unsigned char*& text, uint32_t& cp) {
    unsigned char lead = *text++;
    if (lead < 0x80) { cp = lead; return true; }
    unsigned count;
    uint32_t minimum;
    if (lead >= 0xc2 && lead <= 0xdf) { count = 1; cp = lead & 31; minimum = 0x80; }
    else if (lead >= 0xe0 && lead <= 0xef) { count = 2; cp = lead & 15; minimum = 0x800; }
    else if (lead >= 0xf0 && lead <= 0xf4) { count = 3; cp = lead & 7; minimum = 0x10000; }
    else return false;
    for (unsigned i = 0; i < count; ++i) {
        unsigned char c = *text;
        if (c < 0x80 || c > 0xbf) return false;
        ++text;
        cp = (cp << 6) | (c & 63);
    }
    return cp >= minimum && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff);
}
static unsigned encode(uint32_t cp, char* out) {
    if (cp < 0x80) { out[0] = (char)cp; return 1; }
    if (cp < 0x800) { out[0] = (char)(0xc0 | (cp >> 6)); out[1] = (char)(0x80 | (cp & 63)); return 2; }
    if (cp < 0x10000) {
        out[0] = (char)(0xe0 | (cp >> 12)); out[1] = (char)(0x80 | ((cp >> 6) & 63)); out[2] = (char)(0x80 | (cp & 63)); return 3;
    }
    out[0] = (char)(0xf0 | (cp >> 18)); out[1] = (char)(0x80 | ((cp >> 12) & 63));
    out[2] = (char)(0x80 | ((cp >> 6) & 63)); out[3] = (char)(0x80 | (cp & 63)); return 4;
}
static bool name(const cJSON* value, char* out) {
    if (!cJSON_IsString(value) || !value->valuestring || strlen(value->valuestring) > 4096) return false;
    const unsigned char* p = (const unsigned char*)value->valuestring;
    unsigned kept = 0, size = 0, length = 0;
    while (*p) {
        uint32_t cp;
        if (!codepoint(p, cp) || ++length > 1024) return false;
        // Strip control, direction-override and invisible-format characters.
        if (cp < 32 || (cp >= 0x7f && cp <= 0x9f) || cp == 0xad || cp == 0x61c ||
            (cp >= 0x200b && cp <= 0x200f) || (cp >= 0x202a && cp <= 0x202e) ||
            (cp >= 0x2060 && cp <= 0x206f) || cp == 0xfeff || (cp >= 0xe0000 && cp <= 0xe007f)) continue;
        if (kept == 64) continue; // Still validate the remainder of the name.
        if (cp == '<') cp = 0x2039;
        if (cp == '>') cp = 0x203a;
        size += encode(cp, out + size);
        ++kept;
    }
    out[size] = 0;
    if (!kept) strcpy(out, "Unknown player");
    return true;
}
static bool decode(const cJSON* root, unsigned number, ScorePage& out) {
    const cJSON* meta = member(root, "metadata");
    const cJSON* scores = member(root, "scores");
    unsigned page, size;
    if (!integer(member(meta, "total"), 0, 100000000, &out.total) ||
        !integer(member(meta, "page"), number, number, &page) ||
        !integer(member(meta, "itemsPerPage"), 12, 12, &size) || !cJSON_IsArray(scores)) return false;
    unsigned offset = (number - 1) * 12;
    unsigned expected = out.total > offset ? out.total - offset : 0;
    if (expected > 12) expected = 12;
    if (cJSON_GetArraySize(scores) != (int)expected) return false;
    for (const cJSON* item = scores->child; item; item = item->next) {
        if (out.count >= expected) return false;
        ScoreRow& row = out.rows[out.count];
        unsigned rank, score;
        const cJSON* combo = member(item, "fullCombo");
        if (!integer(member(item, "rank"), offset + out.count + 1, offset + out.count + 1, &rank) ||
            !integer(member(item, "modifiedScore"), 0, 2147483647, &score) || !cJSON_IsBool(combo) ||
            !name(member(member(item, "leaderboardPlayerInfo"), "name"), row.name)) return false;
        row.rank = (int)rank; row.score = (int)score; row.full_combo = cJSON_IsTrue(combo);
        ++out.count;
    }
    return out.count == expected;
}
}

bool score_url(char* out, size_t bytes, const char* hash, int difficulty, unsigned page) {
    if (out && bytes) out[0] = 0;
    if (!out || !bytes || !hash || strlen(hash) != 40 || page < 1 || page > 9 ||
        (difficulty != 1 && difficulty != 3 && difficulty != 5 && difficulty != 7 && difficulty != 9)) return false;
    char upper[41];
    for (unsigned i = 0; i < 40; ++i) {
        char c = hash[i];
        if (c >= 'a' && c <= 'f') c -= 32;
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))) return false;
        upper[i] = c;
    }
    upper[40] = 0;
    int n = snprintf(out, bytes, "https://scoresaber.com/api/leaderboard/by-hash/%s/scores?difficulty=%d&gameMode=SoloStandard&page=%u", upper, difficulty, page);
    if (n < 0 || (size_t)n >= bytes) { out[0] = 0; return false; }
    return true;
}
bool score_page(const char* json, size_t bytes, unsigned page, ScorePage* out) {
    if (!out) return false;
    memset(out, 0, sizeof(*out));
    if (!json || !bytes || bytes > kMaxScoreResponse || page < 1 || page > 9 || memchr(json, 0, bytes)) return false;
    // cJSON exposes C strings: disallow escaped NUL rather than aliasing keys/names.
    for (size_t i = 0; i + 1 < bytes; ++i) {
        if (json[i] != '\\') continue;
        if (i + 5 < bytes && !memcmp(json + i + 1, "u0000", 5)) return false;
        ++i;
    }
    const char* end = NULL;
    cJSON* root = cJSON_ParseWithLengthOpts(json, bytes, &end, 0);
    if (!root) return false;
    while (end < json + bytes && (*end == ' ' || *end == '\n' || *end == '\t' || *end == '\r')) ++end;
    bool ok = end == json + bytes && decode(root, page, *out);
    cJSON_Delete(root);
    if (!ok) memset(out, 0, sizeof(*out));
    return ok;
}
bool append_scores(ScoreBoard* board, const ScorePage& page, unsigned number, unsigned limit) {
    if (!board) return false;
    bool ok = limit >= 1 && limit <= kMaxScores && number >= 1 && number <= 9 &&
        board->count == (number - 1) * 12 && page.count <= 12 &&
        (number == 1 || page.total == board->total);
    unsigned offset = (number >= 1 && number <= 9) ? (number - 1) * 12 : 0;
    unsigned expected = page.total > offset ? page.total - offset : 0;
    if (expected > 12) expected = 12;
    ok = ok && page.count == expected;
    if (!ok) { memset(board, 0, sizeof(*board)); return false; }
    board->total = page.total;
    for (unsigned i = 0; i < page.count && board->count < limit; ++i) board->rows[board->count++] = page.rows[i];
    return true;
}
} // namespace OrBeatsExtras
