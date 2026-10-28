"""Synthetic native proof + integration/flag checks; never loads a PS4 module."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_managed_registration_and_failure_paths(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("clang++ required for native sanitizer checks")
    output = tmp_path / "additive-native-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                    "-I" + str(ROOT / "include"),
                    str(ROOT / "tests/native/additive_song_packs_test.cpp"),
                    "-o", str(output)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(output)], check=True, capture_output=True, text=True)
    assert "rollback checks passed" in result.stdout


def test_off_default_exception_matches_native_pipeline_and_webapp():
    from tools import full_custom_song_pipeline as pipeline
    from webapp.adapters import ps4
    assert pipeline.DEFAULT_FEATURES["enable_additive_song_packs"] is False
    assert "enable_additive_song_packs" in ps4.KNOWN_FLAGS
    assert "enable_additive_song_packs" not in ps4.DEFAULTS_TRUE
    code = (ROOT / "src/main.cpp").read_text()
    assert "static int g_feature_additive_song_packs = 0;" in code
    assert 'strcmp(key, "enable_additive_song_packs")' in code
    assert "g_feature_plugin_enabled && g_feature_additive_song_packs" in code
    assert "Detour_RestoreFunction(&g_additive_detour)" in code
    assert "[ADDITIVE] refused:" in code


def test_stock_proof_does_not_mutate_level_ids_or_use_native_managed_fallbacks():
    code = (ROOT / "include/additive_song_packs.h").read_text()
    assert 'field(a, lc, "levelID", 0x18)' in code
    assert 'field_set_value(level,' not in code
    assert "malloc(" not in code
    assert "memcpy((char*)model" not in code
    assert "gc_wbarrier_set_field" in code
    assert "gchandle_free" in code
    assert "new_level_pack != original_pack" in code
    assert "found_level != stock_level" in code


def test_ui_exposes_approved_exception_and_version():
    js = (ROOT / "webapp/static/app.js").read_text()
    server = (ROOT / "webapp/server.py").read_text()
    assert js.count('"enable_additive_song_packs"') == 1
    assert 'const TOAST_VERSION = "v0.8077";' in js
    assert '"enable_additive_song_packs": "EXPERIMENTAL, OFF by default' in server
    assert (ROOT / "VERSION").read_text().strip() == "0.5390"


def test_explicit_module_public_symbol_resolution_failure_paths(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("clang++ required for native sanitizer checks")
    output = tmp_path / "module-symbols-test"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                    "-I" + str(ROOT / "include"),
                    str(ROOT / "tests/native/additive_module_symbols_test.cpp"),
                    "-o", str(output)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(output)], check=True, capture_output=True, text=True)
    assert "nonlocal/nonexecutable refusal checks passed" in result.stdout


def test_additive_resolver_is_exact_module_scoped_without_offset_fallback():
    source = (ROOT / "src/main.cpp").read_text()
    block = source.split("static OrbisKernelModule g_additive_module = -1;", 1)[1]
    block = block.split("static int additive_requested", 1)[0]
    assert 'strcmp(info.name, "Il2CppUserAssemblies.prx") != 0' in block
    assert "available > 256" in block
    assert "++matches != 1" in block
    assert "info.segmentCount > 4" in block
    assert "(segment.prot & 5) == 5" in block
    assert "value - begin < segment.size" in block
    assert "sceKernelDlsym" in block
    assert "dlsym(RTLD_DEFAULT" not in block
    assert "base + 0x" not in block
    assert "resolved 20 APIs via sceKernelDlsym" in source


def test_constructor_count_is_deferred_and_reloads_do_not_increment_old_value():
    code = (ROOT / "include/additive_song_packs.h").read_text()
    assert "pack_count < 1" not in code
    assert "pack_count < 0" in code
    assert "if (pack_count != 0)" in code
    assert "int32_t updated_count = (int32_t)counts[1] + 1;" in code
    assert "++pack_count" not in code
    assert "published-constructor-count-deferred" in code
    main = (ROOT / "src/main.cpp").read_text()
    assert "stage=%s repo=%d counts=%lu/%lu/%lu model_count=%d" in main


def test_publication_is_reference_abi_correct_and_verified():
    code = (ROOT / "include/additive_song_packs.h").read_text()
    assert "a.field_set_value(model, mf[i], prepared[i]);" in code
    assert "a.field_set_value(model, mf[i], &prepared[i]);" not in code
    assert "a.field_set_value(model, count_field, &updated_count);" in code
    assert "read_ref(a, model, mf[i]) != prepared[i]" in code
    assert "a.field_set_value(model, mf[j], old[j]);" in code
    assert "roots.keep(old[i])" in code
    assert 'restore("publication-reference-readback")' in code
    assert 'restore("publication-count-readback")' in code
    assert "return restored ? PublicationRestored : PublicationUnsafe;" in code


def test_real_abi_mock_rejects_original_stack_pointer_publication(tmp_path):
    """Mutation test: regress to the actual crash bug; mock MUST reject it."""
    import resource

    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("clang++ required for native ABI regression check")
    header = (ROOT / "include/additive_song_packs.h").read_text()
    good = "a.field_set_value(model, mf[i], prepared[i]);"
    assert header.count(good) == 1
    (tmp_path / "additive_song_packs.h").write_text(
        header.replace(good, "a.field_set_value(model, mf[i], &prepared[i]);"))
    # Keep quoted nested includes on the SAME mutated core header.
    (tmp_path / "additive_probe_level.h").write_bytes(
        (ROOT / "include/additive_probe_level.h").read_bytes())
    (tmp_path / "additive_local_content.h").write_bytes(
        (ROOT / "include/additive_local_content.h").read_bytes())
    (tmp_path / "additive_library_profile.h").write_bytes(
        (ROOT / "include/additive_library_profile.h").read_bytes())
    for dependency in ("additive_menu_profile.h", "additive_menu_media.h"):
        (tmp_path / dependency).write_bytes((ROOT / "include" / dependency).read_bytes())
    output = tmp_path / "original-publication-bug"
    subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(tmp_path), "-I" + str(ROOT / "include"),
                    str(ROOT / "tests/native/additive_song_packs_test.cpp"),
                    "-o", str(output)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(output)], capture_output=True, text=True,
                            cwd=tmp_path,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    assert result.returncode != 0
    assert "reference field requires managed object, not native pointer-to-pointer" in result.stderr


def test_own_pack_disables_store_purchase_without_touching_entitlements():
    code = (ROOT / "include/additive_song_packs.h").read_text()
    assert "int32_t buy = 1, source_buy = 0, rating = 0;" in code
    assert 'a.field_get_value(source, buy_field, &source_buy);' in code
    assert 'a.field_get_value(pack, buy_field, &actual_buy);' in code
    assert 'proof-pack-buy-option-readback' in code
    assert 'field_set_value(source,' not in code
    assert 'GetEntitlementStatus' not in code
