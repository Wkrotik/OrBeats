"""Owned branding and host-executed native file publication; no console access."""
import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_current_log_banner_is_orbeats_and_previous_sessions_are_preserved():
    main = (ROOT / 'src/main.cpp').read_text()
    assert 'log_write("=== OrBeats " PLUGIN_VERSION PLUGIN_VARIANT " started ===");' in main
    assert 'sceKernelOpen(LOG_PATH, O_WRONLY|O_CREAT|O_APPEND, 0644)' in main
    assert '"OrBeats %s\\nBy Wkrotik"' in main
    assert '"OrBeats %s — disabled\\nBy Wkrotik\\n(official songs only)"' in main


def test_active_http_clients_identify_as_orbeats(tmp_path, monkeypatch):
    """Exercise actual Request headers; no HTTP or PS4 connections are made."""
    monkeypatch.syspath_prepend(str(ROOT / 'webapp'))
    import full_custom_song_pipeline as pipeline
    from adapters import beatsage, beatsaver

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('Info.dat', '{}')
    captured = []

    class Response(io.BytesIO):
        headers = {}

        def getcode(self):
            return 200

    def fake_open(request, **kwargs):
        captured.append(request.get_header('User-agent'))
        if request.full_url.endswith('.zip'):
            return Response(archive.getvalue())
        metadata = {'name': 'Synthetic', 'versions': [{
            'downloadURL': 'https://fixture.invalid/map.zip',
            'diffs': [{'characteristic': 'Standard'}],
        }]}
        return Response(json.dumps(metadata).encode())

    monkeypatch.setattr(beatsaver.urllib.request, 'urlopen', fake_open)
    beatsaver._get_json('https://fixture.invalid/map')
    beatsage._request('fixture')
    extracted = pipeline.download_beat_saver_song(
        'synthetic', str(tmp_path), api_base='https://fixture.invalid')
    assert (Path(extracted) / 'Info.dat').read_text() == '{}'
    assert captured == [
        'OrBeats-WebApp',
        'OrBeats-WebApp (one job at a time; thanks Beat Sage!)',
        'OrBeats-Pipeline', 'OrBeats-Pipeline',
    ]


@pytest.mark.parametrize('name', ['OrBeats', 'BS Deluxe', 'Beat Saber Deluxe'])
def test_old_binary_banners_remain_recognizable(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'webapp'))
    import library_manager

    blob = b'\x7fELF' + f'=== {name} v0.8079 started ===\x00'.encode()
    assert library_manager.binary_version(blob) == '0.8079'


def test_current_help_and_warning_branding_keeps_legacy_plugin_identifiers():
    example = json.loads((ROOT / 'ps4_config.example.json').read_text())
    assert example['comment'] == 'OrBeats — PS4 Configuration'
    backup = (ROOT.parent / 'backup-orbeats-files.py').read_text()
    assert 'Beat Saber Deluxe' not in backup and 'BS Deluxe' not in backup
    # These are compatibility inputs, not user-facing product branding.
    assert '"beat_saber_deluxe.prx"' in backup
    assert 'beat_saber_deluxe.prx' in (ROOT / 'tools/goldhen_config.py').read_text()
    script = (ROOT / 'webapp/static/app.js').read_text()
    warning = script.split('async function backupNow()', 1)[1].split('const btn', 1)[0]
    assert 'OrBeats' in warning and 'Deluxe' not in warning
    page = (ROOT / 'webapp/static/index.html').read_text()
    assert 'beat-saber-deluxe-' not in page and 'bs-deluxe' not in page
    assert 'https://github.com/Wkrotik/OrBeats/releases/latest' in page
    assert 'Source code (zip)' in page and 'AppImage' in page


def test_new_theme_downloads_use_orbeats_metadata_without_rewriting_history():
    script = (ROOT / 'webapp/static/app.js').read_text()
    form = script.split('async function useTestSong()', 1)[1].split('const btn', 1)[1]
    form = form.split('async function ', 1)[0]
    assert '"orbeats_theme_48s.wav"' in form
    assert 'if (!$("bsage-title").value) $("bsage-title").value = "OrBeats Theme (An Original)"' in form
    assert 'if (!$("bsage-artist").value)' in form
    assert 'BSD Deluxe Theme' not in form
    assert "already-deployed 'BSD Deluxe Theme (An Original)'" in script


def test_embedded_brand_is_the_desktop_logo_not_a_song_asset():
    header = (ROOT/'include/orbeats_branding.h').read_text()
    value = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-f]{2})', header))
    assert hashlib.sha256(value).hexdigest() in header
    actual = Image.open(io.BytesIO(value)).convert('RGBA')
    source = Image.open(ROOT.parent/'desktop/src-tauri/icons/icon.png').convert('RGBA')
    assert actual.size == (512, 512)
    assert actual.tobytes() == source.resize((512, 512), Image.Resampling.LANCZOS).tobytes()
    packs = (ROOT/'include/additive_song_packs.h').read_text()
    assert 'kPackName[] = "OrBeats"' in packs
    assert 'kPackId[] = "bsd_additive_stock_proof_v1"' in packs
    main = (ROOT/'src/main.cpp').read_text()
    assert 'notif.useIconImageUri=1' in main
    assert 'file:///data/GoldHEN/plugins/orbeats-logo.png' in main


def test_actual_native_brand_copy_and_atomic_notification_icon(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('clang++ required for native branding checks')
    main = (ROOT/'src/main.cpp').read_text()
    functions = main.split('static int additive_read_menu(', 1)[1].split('static void additive_free_menu_pair', 1)[0]
    functions = 'static int additive_read_menu(' + functions
    functions = functions.replace('/data/GoldHEN/plugins/orbeats-logo.png', str(tmp_path/'logo.png'))
    program = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <fcntl.h>
#include <unistd.h>
#include "additive_menu_files.h"
#include "orbeats_branding.h"
static bool fail_write=false,fail_rename=false;
static int open_read(const char*p){return open(p,O_RDONLY);}
static int64_t read_bytes(int fd,void*p,size_t n){return read(fd,p,n);}
static void close_read(int fd){close(fd);}
static BsdAdditive::MenuFileIo kMenuIo={open_read,read_bytes,close_read,malloc,free};
static int log_write(const char*){return 0;}
static int sceKernelOpen(const char*p,int flags,int mode){return open(p,flags,mode);}
static int64_t sceKernelWrite(int fd,const void*p,size_t n){return fail_write?-1:write(fd,p,n>4096?4096:n);}
static int sceKernelClose(int fd){return close(fd);}
static int sceKernelRename(const char*a,const char*b){return fail_rename?-1:rename(a,b);}
static int sceKernelUnlink(const char*p){return unlink(p);}
''' + functions + r'''
static void put(const char*p,const char*s){FILE*f=fopen(p,"wb");assert(f);assert(fwrite(s,1,strlen(s),f)==strlen(s));fclose(f);}
static std::string get(const char*p){FILE*f=fopen(p,"rb");assert(f);std::string s;char b[4096];size_t n;while((n=fread(b,1,sizeof(b),f)))s.append(b,n);fclose(f);return s;}
int main(int argc,char**argv){
 assert(argc==3);const char*path=argv[1];const char*stage=argv[2];
 assert(additive_read_menu(BsdAdditive::kMenuPack,NULL)==1);
 BsdAdditive::MediaBytes bytes={};assert(additive_read_menu(BsdAdditive::kMenuPack,&bytes)==1);
 assert(bytes.size==OrBeatsBrand::kLogoBytes&&!memcmp(bytes.data,OrBeatsBrand::kLogoPng,bytes.size));
 assert(additive_read_menu(BsdAdditive::kMenuPack,&bytes)==-1);free((void*)bytes.data);
 assert(prepare_notification_icon());assert(get(path)==std::string((const char*)OrBeatsBrand::kLogoPng,OrBeatsBrand::kLogoBytes));
 put(stage,"do not delete");assert(prepare_notification_icon());assert(get(stage)=="do not delete");
 put(path,"old icon");assert(!prepare_notification_icon());assert(get(path)=="old icon"&&get(stage)=="do not delete");
 unlink(stage);fail_write=true;assert(!prepare_notification_icon());assert(get(path)=="old icon"&&access(stage,F_OK)!=0);
 fail_write=false;fail_rename=true;assert(!prepare_notification_icon());assert(get(path)=="old icon"&&access(stage,F_OK)!=0);
 fail_rename=false;assert(prepare_notification_icon());assert(get(path)==std::string((const char*)OrBeatsBrand::kLogoPng,OrBeatsBrand::kLogoBytes));
 puts("branding copy/partial-write/readback/rename/fallback checks passed");
}
'''
    source = tmp_path/'branding.cpp'
    source.write_text(program)
    exe = tmp_path/'branding'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I'+str(ROOT/'include'), str(source), '-o', str(exe)],
                   check=True, capture_output=True, text=True)
    result = subprocess.run([str(exe), str(tmp_path/'logo.png'), str(tmp_path/'logo.png.stage-08078')],
                            check=True, capture_output=True, text=True)
    assert 'fallback checks passed' in result.stdout


def test_owned_svg_is_the_canonical_product_artwork():
    root = ROOT.parent
    canonical = (root / 'icon.svg').read_bytes()
    assert (ROOT / 'webapp/static/orbeats.svg').read_bytes() == canonical
    assert (root / 'desktop/ui/icon.svg').read_bytes() == canonical
    assert b'#ABE28F' in canonical and b'<svg' in canonical
    html = (ROOT / 'webapp/static/companion.html').read_text()
    assert html.count('/static/orbeats.svg') >= 3
    assert 'src="icon.svg"' in (root / 'desktop/ui/index.html').read_text()


def test_required_raster_derivatives_keep_transparency_and_smooth_edges():
    root = ROOT.parent
    for name in ('icon.png', 'icon.ico'):
        image = Image.open(root / 'desktop/src-tauri/icons' / name).convert('RGBA')
        w, h = image.size
        assert image.getextrema()[-1] == (0, 255)
        assert all(image.getpixel(xy)[3] == 0 for xy in ((0, 0), (w-1, 0), (0, h-1), (w-1, h-1)))
        assert any(0 < a < 255 for a in image.getchannel('A').tobytes())


def test_readme_is_a_stable_introduction_with_real_local_assets():
    root = ROOT.parent
    text = (root / 'README.md').read_text()
    assert len(text.splitlines()) < 100
    assert '<img src="icon.svg"' in text
    assert 'experimental' not in text.lower()
    assert 'SHA256' not in text and 'tests passed' not in text
    for link in re.findall(r'(?:src="|\]\()([^"\s)]+)', text):
        if link.startswith(('https://', 'http://', '#')):
            continue
        assert (root / link.split('#')[0]).is_file(), link
    for image in ('companion-dark.png', 'companion-light.png'):
        with Image.open(root / 'docs/images' / image) as picture:
            assert picture.size == (1440, 1040)
    assert 'illustrative sample maps' in text
