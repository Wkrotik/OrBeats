"""Exp305 real managed invocation ABI model + integration guards, not console proof."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_native_menu_media_abi_cache_and_failure_paths(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("clang++ required for native sanitizer checks")
    output = tmp_path / "menu-native-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                    "-I" + str(ROOT / "include"),
                    str(ROOT / "tests/native/additive_menu_media_test.cpp"),
                    "-o", str(output)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(output)], check=True, capture_output=True, text=True)
    assert "format/readback refusal checks passed" in result.stdout


def test_menu_is_reviewed_bounded_and_only_created_on_game_callback():
    code = (ROOT / "src/main.cpp").read_text()
    callback = code.split("static void additive_load_all_hook(", 1)[1].split(
        "static int additive_code_matches", 1)[0]
    assert "g_menu_media[i].build(" in callback
    assert callback.index("g_menu_media[i].build(") < callback.index("BsdAdditive::append_stock_pack(")
    assert "no repository change" in callback
    assert "g_probe_registered=0;additive_free_menu_files();" in callback
    assert "additive_resolve(\"il2cpp_domain_get\")" in code
    assert "additive_resolve(\"il2cpp_class_from_name\")" in code
    files = (ROOT / "include/additive_menu_files.h").read_text()
    assert "spec.bytes>6000000" in files
    assert "d->hash!=spec.fnv" in files
    assert "g_menu_song[BsdAdditive::kMaxGeneratedLevels]" not in code
    assert "additive_read_menu(g_library.songs[i].preview,NULL)" in code
    assert "additive_free_menu_pair(); // Unity has copied bytes" in callback
    assert "incomplete/invalid library media files; no registration" in code
    assert "additive_free_menu_files();" in code
    header = (ROOT / "include/additive_menu_media.h").read_text()
    assert "if(state==1)return Added;" in header
    assert "if(state<0)return refuse" in header
    assert "uint32_t handles[8]" in header
    assert "preview_pcm(wav,&pcm,&samples)" in header
    assert "read_ref(a,media,cf)!=cover||read_ref(a,media,af)!=clip" in header
    assert "il2cpp_method_get_pointer" not in header


def test_user_icon_is_native_square_input_not_game_asset():
    path = ROOT / "development/assets/custom-songs-icon.png"
    with Image.open(path) as image:
        assert image.format == "PNG" and image.size == (512, 512)
    profile = (ROOT / "include/additive_menu_profile.h").read_text()
    assert "-media/pack-cover.png" in profile
    assert len(re.findall(r"UINT64_C\(0x[0-9a-f]+\)", profile)) == 3
    assert "menu_preview_duration=g_library.songs[i].preview_duration" in (ROOT / "src/main.cpp").read_text()


def test_wkrotik_credit_preserves_upstream_and_matches_notifications():
    code = (ROOT / "src/main.cpp").read_text()
    assert 'log_write("OrBeats — Wkrotik")' in code
    assert code.count('\\nBy Wkrotik"') == 1
    assert 'Chris Primeish' not in code
    assert 'Chris Primeish' in (ROOT.parent / "README.md").read_text()
    assert 'PLUGIN_VERSION "v0.8079"' in code
    assert (ROOT / "webapp/VERSION").read_text().strip() == "0.7.32"


def test_reference_media_override_is_local_to_generated_level():
    core = (ROOT / "include/additive_song_packs.h").read_text()
    factory = (ROOT / "include/additive_probe_level.h").read_text()
    assert 'own_pack_sprite ? own_pack_sprite : read_ref(a, source, cover_field)' in core
    assert 'own_pack_sprite ? own_pack_sprite : read_ref(a, source, small_field)' in core
    assert 'p->menu_media ? p->menu_media : read_ref(a,source,preview_field)' in factory
    assert "preview_start=0;preview_duration=p->menu_preview_duration;" in factory
    assert 'field_set_value(source,' not in factory
    assert 'field_set_value(source,' not in core
    makefile = (ROOT / "Makefile").read_text()
    assert "include/additive_menu_media.h" in makefile
    assert "include/additive_menu_profile.h" in makefile


def test_sprite_lookup_avoids_real_ps4_same_arity_collision():
    header = (ROOT / "include/additive_menu_media.h").read_text()
    assert 'class_get_method_from_name(sprite_c,"Create",3)' not in header
    assert 'class_get_method_from_name(sprite_c,"Create",5)' in header
    assert 'void* create_args[]={texture,rect,pivot,&pixels_per_unit,&extrude};' in header
    assert 'float pixels_per_unit=100.0f;uint32_t extrude=0;' in header


def test_attached_texture_is_verified_before_success_or_pack_publication():
    header = (ROOT / "include/additive_menu_media.h").read_text()
    sprite = header.split('    void* sprite(', 1)[1].split('    Result build(', 1)[0]
    assert 'class_get_method_from_name(sprite_c,"get_texture",0)' in sprite
    assert 'if(!ctor||!load||!create||!get_texture||!width||!height)return NULL;' in sprite
    assert 'void* attached=invoke(a,get_texture,result,NULL,threw);' in sprite
    assert 'if(*threw||attached!=texture)return NULL;' in sprite
    assert sprite.index('attached!=texture') < sprite.index('return result;')


def test_native_mock_models_real_textureless_overload_and_refusal():
    mock = (ROOT / "tests/native/additive_menu_media_test.cpp").read_text()
    assert 'm.name=="Create"&&m.count==3' in mock
    assert '++s->ambiguous_create_calls;return alloc(&sprite_c);' in mock
    assert 'fixture.null_sprite_texture=true' in mock
    assert 'fixture.wrong_sprite_texture=true' in mock
    assert 'fixture.missing_texture_getter=true' in mock
    assert 'fixture.ambiguous_create_calls==0' in mock


def test_bounded_native_menu_file_reads(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("clang++ required for native sanitizer checks")
    binary = tmp_path / "menu-files"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                    "-I" + str(ROOT / "include"),
                    str(ROOT / "tests/native/additive_menu_files_test.cpp"),
                    "-o", str(binary)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    assert "64-song bounded media IO" in result.stdout
