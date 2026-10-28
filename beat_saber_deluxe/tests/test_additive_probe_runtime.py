"""Generated-content bridge: synthetic managed ABI and actual wrapper bodies."""
from pathlib import Path
import json
import re
import shutil
import subprocess

import pytest
ROOT = Path(__file__).resolve().parents[1]


def body(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1; end = opening + 1
    while depth:
        if source[end] == '{': depth += 1
        elif source[end] == '}': depth -= 1
        end += 1
    return source[start:end]


def test_actual_route_wrappers_forward_stock_and_cancel_and_real_results(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:pytest.skip('clang++ required')
    source = (ROOT / 'src/main.cpp').read_text()
    wrappers = body(source, 'static void* additive_probe_load(') + '\n' + body(source, 'static void* additive_probe_check(')
    cpp = r'''
#include "additive_probe_profile.h"
#include "additive_song_packs.h"
#include "additive_runtime_library.h"
#include <assert.h>
#include <map>
#include <string>
#include <vector>
#include <stdio.h>
using namespace BsdAdditive;
struct Detour { void* original; };
#define Detour_Stub(d,type,...) (reinterpret_cast<type>((d)->original))(__VA_ARGS__)
static Api g_additive_api = {};
static RuntimeLibrary g_library;
static Detour g_probe_load_detour, g_probe_check_detour;
static bool active=false;
static int additive_probe_active(){return active;}
static int log_write(const char*){return 1;}
static std::map<void*,std::u16string> strings;
static std::vector<char*> allocated;
static std::map<uint32_t,void*> handles;
static uint32_t serial=0;
static int news=0,fail_new=0,root_calls=0,fail_root=0;
static void* make(const char* s){
 if(++news==fail_new)return NULL;
 char* p=new char[8];allocated.push_back(p);std::u16string v;
 for(;*s;++s)v.push_back(*s);strings[p]=v;return p;
}
static int32_t length(void* s){return strings.at(s).size();}
static const uint16_t* chars(void* s){return (const uint16_t*)strings.at(s).data();}
static uint32_t root(void* p,bool pin){assert(pin);if(++root_calls==fail_root)return 0;handles[++serial]=p;return serial;}
static void release(uint32_t h){assert(handles.erase(h)==1);}
static bool equals(void* p,const char* s){return ascii_equals(g_additive_api,p,s);}
static void *seen_self,*seen_id,*seen_path,*seen_asset;
static uintptr_t seen_cancel;static const void* seen_method;
static void* result=(void*)0x123abc;
static int calls=0;
static void* original_load(void* self,void* id,void* path,void* asset,uintptr_t cancel,const void* method){
 ++calls;seen_self=self;seen_id=id;seen_path=path;seen_asset=asset;seen_cancel=cancel;seen_method=method;return result;
}
static void* original_check(void* self,void* id,void* path,uintptr_t cancel,const void* method){
 ++calls;seen_self=self;seen_id=id;seen_path=path;seen_cancel=cancel;seen_method=method;return result;
}
''' + wrappers + r'''
int main(){
 g_library.defaults();g_additive_api.string_new=make;g_additive_api.string_length=length;g_additive_api.string_chars=chars;
 g_additive_api.gchandle_new=root;g_additive_api.gchandle_free=release;
 g_probe_load_detour.original=(void*)original_load;g_probe_check_detour.original=(void*)original_check;
 void* own=make(kProbeLevelId),*stock=make("100bills"),*path=make("original path"),*asset=make("original asset");
 void* self=(void*)0x987;const void* method=(void*)0xdead;uintptr_t token=0xf123abcd;
 // OFF and other IDs are passed through bit-for-bit; no allocation.
 for(int on=0;on<2;++on){active=on;int n=news;
  assert(additive_probe_load(self,on?stock:own,path,asset,token,method)==result);
  assert(seen_path==path&&seen_asset==asset&&seen_cancel==token&&seen_method==method);
  assert(seen_self==self&&seen_id==(on?stock:own)&&news==n&&handles.empty());
  assert(additive_probe_check(self,on?stock:own,path,token,method)==result);
  assert(seen_path==path&&seen_cancel==token&&seen_method==method&&news==n&&handles.empty());}
 active=true;
 assert(additive_probe_load(self,own,path,asset,token,method)==result);
 assert(equals(seen_path,kProbePath)&&equals(seen_asset,kProbeAsset));
 assert(seen_id==own&&seen_self==self&&seen_cancel==token&&seen_method==method&&handles.empty());
 assert(additive_probe_check(self,own,path,token,method)==result);
 assert(equals(seen_path,kProbePath)&&seen_cancel==token&&handles.empty());
 // Every allocation/root failure forwards ORIGINAL args, real result; no leaks.
 for(int n=1;n<=2;++n){fail_new=news+n;
  assert(additive_probe_load(self,own,path,asset,token,method)==result);
  assert(seen_path==path&&seen_asset==asset&&seen_cancel==token&&handles.empty());fail_new=0;}
 for(int n=1;n<=2;++n){fail_root=root_calls+n;
  assert(additive_probe_load(self,own,path,asset,token,method)==result);
  assert(seen_path==path&&seen_asset==asset&&seen_cancel==token&&handles.empty());fail_root=0;}
 fail_new=news+1;assert(additive_probe_check(self,own,path,token,method)==result);
 assert(seen_path==path&&handles.empty());fail_new=0;
 fail_root=root_calls+1;assert(additive_probe_check(self,own,path,token,method)==result);
 assert(seen_path==path&&handles.empty());fail_root=0;
 result=NULL;assert(additive_probe_load(self,own,path,asset,token,method)==NULL);assert(handles.empty());
 // Different own ID gets a DIFFERENT route; never match prefix-only/lookalikes.
 result=(void*)0x123abc;void* second=make(kReviewedSongs[1].id);
 for(void* id: {own,second,own}){
  const ReviewedSong* p=reviewed_song(g_additive_api,id);assert(p);
  assert(additive_probe_load(self,id,path,asset,token,method)==result);
  assert(equals(seen_path,p->path)&&equals(seen_asset,p->asset)&&seen_id==id&&seen_cancel==token&&seen_method==method);
  assert(additive_probe_check(self,id,path,token,method)==result&&equals(seen_path,p->path)&&handles.empty());
 }
 for(const char* name: {"bsd_additive_376607927402e50fcf6ab89f_extra","bsd_additive_unreviewed",""}){
  void* id=make(name);int n=news;assert(additive_probe_load(self,id,path,asset,token,method)==result);
  assert(seen_path==path&&seen_asset==asset&&news==n&&seen_id==id&&handles.empty());
 }
 active=false;assert(additive_probe_check(self,second,path,token,method)==result&&seen_path==path);
 assert(calls==23);
 for(char* p:allocated)delete[] p;
 puts("real wrapper passthrough, cancellation, async result and allocation/root checks passed");
}
'''
    file = tmp_path / 'wrappers.cpp';file.write_text(cpp)
    exe = tmp_path / 'wrappers'
    subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I'+str(ROOT/'include'), str(file), '-o', str(exe)],
                   check=True, capture_output=True, text=True)
    run = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert 'real wrapper passthrough' in run.stdout


def test_profile_is_unique_content_and_not_stock_redirect():
    profile = (ROOT/'include/additive_probe_profile.h').read_text()
    level_id = re.search(r'kProbeLevelId\[\] = "([^"]+)"', profile)[1]
    assert re.fullmatch('bsd_additive_[0-9a-f]{24}', level_id)
    assert 'kProbePath[] = "/data/GoldHEN/AFR/CUSA12878/additive/'+level_id+'.bundle"' in profile
    assert level_id+'BeatmapLevelData.asset' in profile
    assert 'NOT cryptographic authenticity' in profile
    code = (ROOT/'src/main.cpp').read_text()
    assert 'g_probe_enabled && g_probe_registered' in code
    assert 'g_probe_enabled?BsdAdditive::make_probe_level:NULL' in code
    assert 'additive_restore_probe_routes();' in code
    assert 'probe_file<0' in code and 'no registration' in code
    assert 'base+0x977a10' not in code  # unsafe RIP-relative entry is NOT detoured


def test_probe_only_constructs_new_managed_data():
    code = (ROOT/'include/additive_probe_level.h').read_text()
    assert 'a.object_new(lc)' in code and 'a.object_new(bc)' in code
    assert 'a.object_new(dc)' in code
    assert 'field_set_value' not in code
    assert 'a.field_get_offset(key_diff) != start+8' in code
    assert 'p->class_value_size(kc,&alignment) != 24' in code
    assert 'for(int32_t difficulty=0;difficulty<5;++difficulty)' in code
    assert 'notes=p->spec.notes' in code
    assert '"Standard"' in code
    assert 'temp/additive-exp303-full-map/prepared/manifest.json' in (ROOT/'include/additive_probe_profile.h').read_text()


def test_actual_file_gate_closes_fd_and_rejects_bad_content(tmp_path):
    compiler = shutil.which('clang++')
    if not compiler:pytest.skip('clang++ required')
    source=(ROOT/'src/main.cpp').read_text()
    gate=body(source,'static int additive_one_file_state(')+'\n'+body(source,'static int additive_probe_file_state(')
    fnv=body((ROOT/'include/additive_probe_profile.h').read_text(),'inline uint64_t probe_fnv_update(')
    cpp=r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <string.h>
#include <vector>
#include <fcntl.h>
#include <stdio.h>
namespace BsdAdditive {
struct ReviewedSong {const char* path;size_t bytes;uint64_t fnv;};

static const ReviewedSong kReviewedSongs[]={
 {"expected proof path0",5,UINT64_C(0xa430d84680aabd0b)},
 {"expected proof path1",5,UINT64_C(0x4f59ff5e730c8af3)}};
''' + fnv + r'''
}
static std::vector<unsigned char> bytes[2];
static size_t offset=0;static int opens[2]={0,0},current=-1,read_error=-1,closes=0;static bool live=false;
static int sceKernelOpen(const char* p,int flags,int mode){
 assert(!live&&flags==O_RDONLY&&mode==0);
 current=!strcmp(p,BsdAdditive::kReviewedSongs[0].path)?0:1;
 assert(!strcmp(p,BsdAdditive::kReviewedSongs[current].path));offset=0;
 if(opens[current]>=0)live=true;return opens[current];
}
static int64_t sceKernelRead(int fd,void* dest,size_t n){
 assert(live&&fd==0&&n==8192);if(read_error==current)return -5;
 if(offset==bytes[current].size())return 0;
 size_t take=bytes[current].size()-offset;if(take>2)take=2;
 memcpy(dest,bytes[current].data()+offset,take);offset+=take;return take;
}
static int sceKernelClose(int fd){assert(live&&fd==0);live=false;++closes;return 0;}
static struct {size_t count=2;BsdAdditive::ReviewedSong songs[2]={BsdAdditive::kReviewedSongs[0],BsdAdditive::kReviewedSongs[1]};} g_library;
''' + gate + r'''
int main(){
 opens[0]=opens[1]=(int)0x80020002;assert(additive_probe_file_state()==0&&closes==0);
 opens[0]=-9;assert(additive_probe_file_state()==-1&&closes==0);
 opens[0]=opens[1]=0;bytes[0]={'h','e','l','l','o'};bytes[1]={'w','o','r','l','d'};
 assert(additive_probe_file_state()==1&&closes==2&&!live);
 for(int i=0;i<2;++i){
  closes=0;opens[i]=(int)0x80020002;assert(additive_probe_file_state()==-1&&closes==1&&!live);opens[i]=0;
  closes=0;auto good=bytes[i];bytes[i][0]='x';assert(additive_probe_file_state()==-1&&closes==i+1&&!live);bytes[i]=good;
  closes=0;bytes[i].pop_back();assert(additive_probe_file_state()==-1&&closes==i+1&&!live);bytes[i]=good;
  closes=0;bytes[i].push_back('!');assert(additive_probe_file_state()==-1&&closes==i+1&&!live);bytes[i]=good;
  closes=0;read_error=i;assert(additive_probe_file_state()==-1&&closes==i+1&&!live);read_error=-1;
 }
 puts("file gate fd0/short reads/full digest/truncation/corruption/oversize/errors pass");
}
'''
    p=tmp_path/'gate.cpp';p.write_text(cpp);exe=tmp_path/'gate'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True,capture_output=True,text=True)
    assert 'file gate' in subprocess.run([str(exe)],check=True,capture_output=True,text=True).stdout


def test_compiled_profile_matches_reviewed_full_map_manifest():
    # Text-only metadata fixture. Full third-party audio/map is deliberately NOT
    # a test dependency or repository asset; deployment verifies exact private
    # bytes independently. Synthetic preparation roundtrip tests remain separate.
    m=json.loads((ROOT/'development/fixtures/additive-full-map-manifest.json').read_text())
    profile=(ROOT/'include/additive_probe_profile.h').read_text()
    assert m['level_id'] in profile and m['bundle']['sha256'] in profile
    assert 'kProbeBytes = '+str(m['bundle']['bytes'])+';' in profile
    assert m['song_name']=='Wake Me Up' and 249<m['duration_seconds']<250
    ds=['Easy','Normal','Hard','Expert','ExpertPlus']
    for name,key in [('Notes','notes'),('Bombs','bombs'),('Obstacles','obstacles'),('Njs','njs'),('JumpOffset','jump_offset')]:
        values=','.join(str(m['difficulty_stats'][d][key]) for d in ds)
        assert 'kProbe'+name+'[5] = {'+values+'};' in profile
    native=(ROOT/'src/main.cpp').read_text()
    assert 'song.difficulties,song.author,song.difficulty_mask' in native
    assert 'g_probe_context.spec={BsdAdditive::kProbeLevelId,BsdAdditive::kProbeTitle,120,12,9}' not in native


def test_local_free_classification_is_bound_transactional_and_not_platform_patch():
    code = (ROOT/'include/additive_local_content.h').read_text()
    assert 'ascii_equals(api,pack_id,kPackId)' in code
    assert 'ascii_equals(api,level_ids[i],expected)' in code
    assert 'const char* expected=approved_ids?approved_ids[i]:kProbeLevelId;' in code
    assert '"_alwaysOwnedBeatmapLevelIds","_alwaysOwnedPacksIds"' in code
    assert '"Contains",1' in code and '"Add",1' in code and '"Remove",1' in code
    assert '"Clear"' not in code and 'field_set_value' not in code
    assert 'GetLevelEntitlementStatusAsync' not in code
    assert 'GetPackEntitlementStatusAsync' not in code
    assert 'unbox(result)' in code and 'value_size(c,&alignment)!=1' in code
    assert 'attempted[i]=true' in code and 'if(!attempted[i]||existed[i])continue;' in code
    assert 'local-free-rollback-verification' in code
    core = (ROOT/'include/additive_song_packs.h').read_text()
    assert core.index('if (before_publish) {\n        Result ready') < core.index('// No allocations/managed invocations after this point.')
    native = (ROOT/'src/main.cpp').read_text()
    assert 'additive_resolve("il2cpp_object_unbox")' in native
    assert '!g_probe_contexts[0].class_value_size || !g_probe_unbox' in native
    assert 'BsdAdditive::prepare_local_content_many,&local' in native
    assert 'result=local.finish(result,&diagnostic)' in native
    assert 'if(g_probe_enabled && local.ready &&' in native
