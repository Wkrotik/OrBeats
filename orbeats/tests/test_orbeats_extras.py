"""Extras tests use synthetic managed objects/HTTP pages, never a console."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("scoresaber_probe", ROOT / "orbeats_extras/development/scoresaber.py")
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)
HASH = "8AF82A87167070A08EC63DBA0459C829C2954067"


def page(number, total=108):
    return {
        "metadata": {"page": number, "total": total, "itemsPerPage": 12},
        "scores": [
            {
                "rank": i,
                "modifiedScore": 100000 - i,
                "fullCombo": True,
                "leaderboardPlayerInfo": {"name": "<b>Player</b>\u202e\x00"},
            }
            for i in range((number - 1) * 12 + 1, min(number * 12, total) + 1)
        ],
    }


@pytest.mark.parametrize("count,pages", [(50, 5), (100, 9)])
def test_scores_anonymous_pagination_and_plain_names(count, pages):
    urls = []

    def fetch(url, timeout):
        assert 0 < timeout <= 10 and url.startswith(f"https://scoresaber.com/api/leaderboard/by-hash/{HASH}/scores?")
        urls.append(url)
        return page(len(urls))

    result = score.top_scores(HASH, "Normal", count=count, fetch=fetch)
    assert len(urls) == pages and len(result["rows"]) == count
    assert "difficulty=3&gameMode=SoloStandard" in urls[0]
    assert result["rows"][0]["player_name"] == "‹b›Player‹/b›"
    assert result["rows"][-1]["rank"] == count and result["read_only"]
    assert "profilePicture" not in str(result)


@pytest.mark.parametrize("bad", ["bsd_additive_123", "ost_track", "../" + "a" * 40, "a" * 39, "z" * 40])
def test_scores_reject_generated_or_invalid_identity(bad):
    with pytest.raises(ValueError, match="content SHA1"):
        score.top_scores(bad, "Normal", fetch=lambda *args: pytest.fail("no HTTP for invalid identity"))


@pytest.mark.parametrize("fault", ["metadata", "short", "order", "score", "combo", "page", "size", "player"])
def test_scores_fail_closed_without_partial_rows(fault):
    def fetch(url, timeout):
        data = page(1)
        if fault == "metadata":
            data["metadata"] = []
        elif fault == "short":
            data["scores"].pop()
        elif fault == "order":
            data["scores"][0]["rank"] = 2
        elif fault == "score":
            data["scores"][0]["modifiedScore"] = True
        elif fault == "combo":
            data["scores"][0]["fullCombo"] = "yes"
        elif fault == "page":
            data["metadata"]["page"] = True
        elif fault == "size":
            data["metadata"]["itemsPerPage"] = 100
        else:
            data["scores"][0]["leaderboardPlayerInfo"]["name"] = None
        return data

    with pytest.raises(score.Unavailable):
        score.top_scores(HASH, "Normal", fetch=fetch)


def test_scores_empty_short_changed_cancel_and_deadline():
    assert score.top_scores(HASH, "Normal", fetch=lambda *args: page(1, 0))["rows"] == []
    assert len(score.top_scores(HASH, "Normal", fetch=lambda *args: page(1, 7))["rows"]) == 7
    calls = []

    def changed(url, timeout):
        calls.append(url)
        return page(len(calls), 108 if len(calls) == 1 else 107)

    with pytest.raises(score.Unavailable, match="changed"):
        score.top_scores(HASH, "Normal", fetch=changed)
    with pytest.raises(score.Unavailable, match="cancelled"):
        score.top_scores(HASH, "Normal", cancelled=lambda: True, fetch=lambda *args: pytest.fail("cancel before HTTP"))
    clock = iter([0, 31])
    with pytest.raises(score.Unavailable, match="deadline"):
        score.top_scores(
            HASH, "Normal", clock=lambda: next(clock), fetch=lambda *args: pytest.fail("expired before HTTP")
        )
    with pytest.raises(ValueError, match="Standard"):
        score.top_scores(HASH, "Normal", mode="Solo360Degree")


def test_health_guard_native_sanitizers(tmp_path):
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        pytest.skip("C++ compiler required")
    code = r"""
#include "health.h"
#include <assert.h>
using namespace OrBeatsExtras;
struct Object { unsigned char bytes[0x160]; };
static Object flow,health,other;
static int bad_field=0,bad_namespace=0,bad_class=0;
static void* klass(void* o){return o;}
static const char* name(void* o){return bad_class?"Other":o==&flow?"HealthWarningFlowCoordinator":o==&health?"HealthWarningViewController":"EulaViewController";}
static const char* ns(void*){return bad_namespace?"Foreign":"";}
static void* field(void*,const char* n){return (void*)n;}
static size_t offset(void* n){
 if(bad_field)return 0;
 if(!strcmp((char*)n,"_healthWarningViewController"))return 0xd8;
 if(!strcmp((char*)n,"_duration"))return 0x88;
 if(!strcmp((char*)n,"_requiresInteraction"))return 0xb8;
 if(!strcmp((char*)n,"_dismissCoroutine"))return 0xc0;
 return 0;
}
static Api a={klass,name,ns,field,offset};
static void reset(){
 memset(&flow,0,sizeof(flow));memset(&health,0,sizeof(health));
 void* h=&health;memcpy(flow.bytes+0xd8,&h,8);
 float seconds=5;memcpy(health.bytes+0x88,&seconds,4);health.bytes[0xb8]=1;
 bad_field=bad_namespace=bad_class=0;
}
int main(){
 assert(enabled((const unsigned char*)kOptIn,sizeof(kOptIn)-1));
 assert(!enabled((const unsigned char*)kOptIn,sizeof(kOptIn)));
 assert(enabled(NULL,0)); // Missing file hides only the health warning by default.
 assert(!enabled(NULL,1));
 assert(!enabled((const unsigned char*)"",0));
 assert(!enabled((const unsigned char*)kShowHealth,sizeof(kShowHealth)-1));
 assert(!enabled((const unsigned char*)"invalid",7));
 reset();assert(prepare_health(a,true,&flow,&health));
 assert(health.bytes[0xb8]==0);float duration;memcpy(&duration,health.bytes+0x88,4);assert(duration==0.25f);
 reset();Object before=health;assert(!prepare_health(a,false,&flow,&health));assert(!memcmp(&before,&health,sizeof(health)));
 assert(!prepare_health(a,true,&flow,&other));assert(!memcmp(&before,&health,sizeof(health)));
 reset();bad_field=1;assert(!prepare_health(a,true,&flow,&health));
 reset();bad_namespace=1;assert(!prepare_health(a,true,&flow,&health));
 reset();bad_class=1;assert(!prepare_health(a,true,&flow,&health));
 reset();void* p=&other;memcpy(flow.bytes+0xd8,&p,8);assert(!prepare_health(a,true,&flow,&health));
 reset();memcpy(health.bytes+0xc0,&p,8);assert(!prepare_health(a,true,&flow,&health));
 reset();float negative=-1;memcpy(health.bytes+0x88,&negative,4);assert(!prepare_health(a,true,&flow,&health));
 reset();uint32_t nan=0x7fc00000;memcpy(health.bytes+0x88,&nan,4);assert(!prepare_health(a,true,&flow,&health));
 assert(!prepare_health(a,true,NULL,&health));assert(!prepare_health(a,true,&flow,NULL));
 reset();Api empty={};assert(!prepare_health(empty,true,&flow,&health));
}
"""
    source = tmp_path / "health.cpp"
    source.write_text(code)
    exe = tmp_path / "health"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "-I",
            str(ROOT / "orbeats_extras/include"),
            str(source),
            "-o",
            str(exe),
        ],
        check=True,
    )
    subprocess.run([str(exe)], check=True)


def test_health_owned_code_signatures_when_available():
    candidates = list((ROOT / "ps4_dump").glob("*/Media/Modules/Il2cppUserAssemblies.prx"))
    if not candidates:
        pytest.skip("Owned game binary is deliberately not distributed")
    data = candidates[0].read_bytes()
    for offset, size, expected in [
        (0x1D44B20, 0xBD, 0xAB2B66371B634888),
        (0x1D65BD0, 0x2C0, 0xEA16169114A92116),
        (0x1D66030, 0xB4, 0x4733A94E6C3D0E0B),
    ]:
        value = 14695981039346656037
        for c in data[0x4000 + offset : 0x4000 + offset + size]:
            value = ((value ^ c) * 1099511628211) & ((1 << 64) - 1)
        assert value == expected
