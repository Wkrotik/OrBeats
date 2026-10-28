"""Native UI/worker and identity exchange, no console or real HTTPS required."""

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXTRAS = ROOT / "orbeats_extras"


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cxx = shutil.which("clang++")
    if not cxx:
        pytest.skip("Native sanitizer tests need clang++")
    out = tmp_path_factory.mktemp("extras-integration")
    imports = out / "imports"
    (imports / "orbis").mkdir(parents=True)
    (imports / "GoldHEN").mkdir()
    (imports / "orbis/libkernel.h").write_text('''#pragma once
#include <stddef.h>
#include <stdint.h>
extern "C" {
int sceKernelOpen(const char*,int,int);
int64_t sceKernelRead(int,void*,size_t);
int sceKernelClose(int);
uint64_t sceKernelGetProcessTime();
}
''')
    (imports / "GoldHEN/Detour.h").write_text('''#pragma once
#include <stdint.h>
struct Detour { void* StubPtr; };
enum DetourMode { DetourMode_x64 };
inline void Detour_Construct(Detour* d,DetourMode){d->StubPtr=nullptr;}
inline void* Detour_DetourFunction(Detour*,uint64_t,void*){return nullptr;}
inline void Detour_RestoreFunction(Detour*){}
#define Detour_Stub(d,type,...) (((type)((d)->StubPtr))(__VA_ARGS__))
''')
    flags = ["-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-pthread", "-I" + str(EXTRAS / "include"), "-I" + str(imports)]
    for name, extra in [("ui", []), ("worker", [EXTRAS / "src/worker.cpp"]), ("lifecycle", [EXTRAS / "src/worker.cpp"])]:
        subprocess.run([cxx, *flags, str(ROOT / f"orbeats/tests/native/extras_{name}_test.cpp"), *map(str, extra), "-o", str(out / name)], check=True)
    return out


@pytest.mark.parametrize("scenario", ["latest", "cancel", "stop", "ttl", "rate", "missing", "bound"])
def test_worker_generation_join_and_bounded_cache(binaries, scenario):
    subprocess.run([str(binaries / "worker"), scenario], check=True, timeout=20, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"})


@pytest.mark.parametrize("target", ["ui", "lifecycle"])
def test_managed_rows_publish_once_and_roots_cleanup(binaries, target):
    subprocess.run([str(binaries / target)], check=True, timeout=20, env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1"})


def source_module():
    spec = importlib.util.spec_from_file_location("score_source", ROOT / "orbeats/tools/score_source.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_identity_wire_matches_actual_native_reader(tmp_path):
    module = source_module()
    song = {"id": "bsd_additive_" + "a" * 24, "sha256": "b" * 64, "mask": 31}
    raw = module.encode(song, "c" * 40)
    assert len(raw) == module.SIZE == 158
    cxx = shutil.which("clang++")
    if not cxx:
        pytest.skip("Native source-identity test needs clang++")
    source = tmp_path / "identity.cpp"
    source.write_text(r'''
#include "source_identity.h"
#include <assert.h>
#include <stdio.h>
using namespace OrBeatsExtras;
int main(int argc,char** argv){
 assert(argc==2);FILE* f=fopen(argv[1],"rb");assert(f);unsigned char bytes[159];size_t n=fread(bytes,1,sizeof(bytes),f);fclose(f);
 char hash[41];const char* id="bsd_additive_aaaaaaaaaaaaaaaaaaaaaaaa";
 const char* bundle="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
 assert(source_identity(bytes,n,id,bundle,31,hash));assert(!strcmp(hash,"cccccccccccccccccccccccccccccccccccccccc"));
 for(size_t i=0;i<158;++i){unsigned char original=bytes[i];bytes[i]^=1;assert(!source_identity(bytes,n,id,bundle,31,hash));assert(hash[0]==0);bytes[i]=original;}
 assert(!source_identity(bytes,n-1,id,bundle,31,hash));assert(!source_identity(bytes,n+1,id,bundle,31,hash));
 assert(!source_identity(bytes,n,"../foreign",bundle,31,hash));assert(!source_identity(bytes,n,id,bundle,1,hash));
}
''')
    (tmp_path / "identity.bin").write_bytes(raw)
    subprocess.run([cxx, "-std=c++11", "-fsanitize=address,undefined", "-I" + str(EXTRAS / "include"), str(source), "-o", str(tmp_path / "identity")], check=True)
    subprocess.run([str(tmp_path / "identity"), str(tmp_path / "identity.bin")], check=True, timeout=10)


@pytest.mark.parametrize("field,value", [("id", "../"), ("sha256", "x" * 64), ("mask", True), ("mask", 32), ("mask", -1)])
def test_source_identity_rejects_invalid_descriptors(field, value):
    song = {"id": "bsd_additive_" + "a" * 24, "sha256": "b" * 64, "mask": 31, field: value}
    with pytest.raises(ValueError):
        source_module().encode(song, "c" * 40)


def test_original_hash_uses_unmodified_info_and_referenced_bytes(tmp_path):
    raw = b'{"_songFilename":"song.ogg","charts":["Expert.dat","Normal.dat"]}'
    (tmp_path / "Info.dat").write_bytes(raw)
    (tmp_path / "Expert.dat").write_bytes(b"original expert")
    (tmp_path / "Normal.dat").write_bytes(b"original normal")
    module = source_module()
    actual = module.original_hash(tmp_path, lambda info: info["charts"], lambda folder, name: folder / name)
    assert actual == hashlib.sha1(raw + b"original expert" + b"original normal").hexdigest()
    assert actual != hashlib.sha1(b"converted").hexdigest()


def test_sidecar_publication_is_immutable_closed_title_and_readback():
    module = source_module()
    song = {"id": "bsd_additive_" + "a" * 24, "sha256": "b" * 64, "mask": 31}

    class API:
        BASE = "/additive"

        def __init__(self):
            self.files = {}
            self.guards = 0
            self.renames = 0
            self.corrupt = False

        def closed(self, ftp):
            self.guards += 1

        def read(self, ftp, path, limit, missing=False):
            return self.files.get(path)

        def stage(self, ftp, path, data, run):
            self.files[path + ".stage"] = data
            return path + ".stage"

        def rename(self, old, new):
            self.renames += 1
            self.files[new] = b"corrupt" if self.corrupt else self.files.pop(old)

    api = API()
    module.publish(api, api, song, "c" * 40, "run")
    assert api.guards == 2 and api.renames == 1
    module.publish(api, api, song, "c" * 40, "run")
    assert api.renames == 1
    with pytest.raises(ValueError, match="conflicting"):
        module.publish(api, api, song, "d" * 40, "run")
    api = API()
    api.corrupt = True
    with pytest.raises(ValueError, match="readback"):
        module.publish(api, api, song, "c" * 40, "run")


def test_owned_leaderboard_fingerprints_and_input_trampoline():
    files = list((ROOT / "ps4_dump").glob("*/Media/Modules/Il2cppUserAssemblies.prx"))
    if not files:
        pytest.skip("Owned game binary is deliberately not distributed")
    code = (EXTRAS / "include/leaderboard_profile.h").read_text()
    with files[0].open("rb") as stream:
        for rva, size, expected in re.findall(r"\{0x([a-f0-9]+),0x([a-f0-9]+),UINT64_C\(0x([a-f0-9]+)\)\}", code):
            stream.seek(int(rva, 16) + 0x4000)
            value = 14695981039346656037
            for byte in stream.read(int(size, 16)):
                value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
            assert value == int(expected, 16)
        # The only executed trampoline spans exactly15 whole nonrelative bytes.
        stream.seek(0x31F5A40 + 0x4000)
        assert stream.read(15) == bytes.fromhex("55 48 89 e5 41 57 41 56 41 54 53 48 83 ec 10")


def test_source_exchange_is_packaged_and_library_is_published_last():
    resources = (ROOT / "desktop/backend/resources.py").read_text()
    assert '"tools/score_source.py"' in resources
    text = (ROOT / "orbeats/tools/additive_companion.py").read_text()
    assert text.index("score_source.publish(ftp", text.index("metadata = source_metadata")) < text.index("commit_library(ftp, candidate")
    assert "source_sha1 = score_source.original_hash(source" in text
