"""Companion protocol + scoped FTP transaction, no console/network required."""
import copy
from ftplib import error_perm
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import additive_library as lib
import additive_companion as app


def baseline():return json.loads((ROOT/'development/fixtures/additive-baseline-library.json').read_text())


def synthetic(index):
    s=copy.deepcopy(baseline()[1]);s['id']='bsd_additive_'+f'{index:024x}';s['title']='Synthetic '+str(index)
    blobs=[('bundle'+str(index)).encode(),b'cover',b'preview'*8]
    s['bytes']=len(blobs[0]);s['sha256']=hashlib.sha256(blobs[0]).hexdigest();s['fnv']=lib.fnv(blobs[0])
    for k,b in zip(('cover','preview'),blobs[1:]):s[k]={'bytes':len(b),'fnv':lib.fnv(b)}
    return s,dict(zip(lib.paths(s),blobs))


class FTP:
    def __init__(self,files=None):self.files=dict(files or {});self.active=False;self.writes=[];self.reads=[];self.directories=set();self.fail_publish=False;self.corrupt_stage=False
    def connect(self,*a,**kw):pass
    def login(self,*a):pass
    def close(self):pass
    def nlst(self,p):
        if p=='/mnt/sandbox':return ['/mnt/sandbox/CUSA12878_000'] if self.active else []
        return [x for x in self.files if x.startswith(p+'/')]
    def retrbinary(self,cmd,callback):
        p=cmd[5:];self.reads.append(p)
        if p not in self.files:raise error_perm('550 missing')
        callback(self.files[p])
    def storbinary(self,cmd,file):
        p=cmd[5:];self.writes.append(('write',p));self.files[p]=file.read()
        if self.corrupt_stage:self.files[p]+=b'x'
    def delete(self,path):
        if path not in self.files:raise error_perm("550 missing")
        del self.files[path]
    def rename(self,a,b):
        if self.fail_publish and b.endswith('/library.bin') and '.stage-' in a:
            self.fail_publish=False;raise OSError('publish failed')
        assert b not in self.files
        self.writes.append(('rename',a,b));self.files[b]=self.files.pop(a)
    def mkd(self,p):
        if p in self.directories:raise error_perm('550 already exists')
        self.directories.add(p)
    def rmd(self,path):self.directories.remove(path)


class StrictFTP(FTP):
    """Unlike the old fake, nonexistent directories reject NLST and STOR."""
    def __init__(self, files=None):
        super().__init__(files)
        for path in self.files:
            parent = path.rsplit('/', 1)[0]
            while parent:
                self.directories.add(parent)
                parent = parent.rsplit('/', 1)[0]

    def nlst(self, path):
        if path == '/mnt/sandbox':
            return super().nlst(path)
        if path not in self.directories:
            raise error_perm('550 Requested action not taken. File unavailable.')
        prefix = path + '/'
        return sorted({prefix + entry[len(prefix):].split('/', 1)[0]
                       for entry in self.files.keys() | self.directories
                       if entry.startswith(prefix)})

    def storbinary(self, cmd, file):
        if cmd[5:].rsplit('/', 1)[0] not in self.directories:
            raise error_perm('550 parent unavailable')
        return super().storbinary(cmd, file)

    def mkd(self, path):
        if path.rsplit('/', 1)[0] not in self.directories:
            raise error_perm('550 parent unavailable')
        return super().mkd(path)


def test_codec_roundtrip_preserves_authored_three_difficulties_and_utf8():
    songs=baseline();songs[1]['title']='Cities — café 🎵'
    raw=lib.encode(songs);s=lib.decode(raw)
    assert lib.encode(s)==raw and s[1]['mask']==28
    assert s[1]['stats'][:2]==[[0]*5,[0]*5]
    assert s[1]['id']!=s[0]['id'] and lib.paths(s[1])!=lib.paths(s[0])


@pytest.mark.parametrize('mutation',[
    lambda s:s.append(copy.deepcopy(s[0])),
    lambda s:s[0].update(id='bsd_additive_../../foreign'),
    lambda s:s[0].update(title='nul\x00title'),
    lambda s:s[0].update(duration=float('nan')),
    lambda s:s[1]['stats'][0].__setitem__(0,2),
    lambda s:s[0].update(preview_duration=31),
    lambda s:s[0].update(sha256='X'*64),
    lambda s:s[0].update(mask=32),
])
def test_invalid_host_descriptors_refuse_before_ftp(mutation):
    s=baseline();mutation(s)
    with pytest.raises(ValueError):lib.encode(s)


def test_checksum_truncation_suffix_and_capacity():
    raw=lib.encode(baseline())
    for bad in [raw[:-1],raw+b'x',b'foreign'+raw,raw[:25]+bytes([raw[25]^1])+raw[26:]]:
        with pytest.raises(ValueError):lib.decode(bad)
    assert len(lib.decode(lib.encode([synthetic(i)[0] for i in range(64)])))==64
    assert lib.decode(lib.encode([]))==[]
    with pytest.raises(ValueError):lib.encode([synthetic(i)[0] for i in range(65)])


@pytest.fixture
def decoder(tmp_path):
    cc=shutil.which('clang++')
    if not cc:pytest.skip('clang++ required')
    p=tmp_path/'reader.cpp';out=tmp_path/'reader'
    p.write_text(r'''
#include "additive_runtime_library.h"
#include <assert.h>
#include <stdio.h>
using namespace BsdAdditive;
int main(int argc,char** argv){
 assert(argc==3);FILE* f=fopen(argv[1],"rb");assert(f);
 unsigned char b[kLibraryMaxBytes+1];size_t n=fread(b,1,sizeof(b),f);fclose(f);
 RuntimeLibrary r={};bool ok=decode_library(r,b,n);assert(ok==(argv[2][0]=='1'));
 if(ok){for(size_t i=0;i<r.count;++i){assert(r.approved[i]==r.songs[i].id);
   printf("%s %s %u %s\n",r.songs[i].id,r.songs[i].title,r.songs[i].difficulty_mask,r.songs[i].path);
   if(r.songs[i].environment)printf("environment=%s\n",r.songs[i].environment);}}
}
''')
    subprocess.run([cc,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    '-I'+str(ROOT/'include'),str(p),'-o',str(out)],check=True,capture_output=True)
    def run(raw,valid):
        file=tmp_path/'library.bin';file.write_bytes(raw)
        return subprocess.run([str(out),str(file),'1' if valid else '0'],check=True,capture_output=True,text=True).stdout
    return run


def test_real_cpp_parser_accepts_host_binary_up_to_eight_and_refuses_corruption(decoder):
    songs=[synthetic(i)[0] for i in range(8)];songs[2]['title']='Café 🎵'
    raw=lib.encode(songs);out=decoder(raw,True)
    assert out.count('bsd_additive_')==16 and 'Café 🎵' in out
    for bad in [raw[:-1],raw+b'x',raw[:16]+b'BAD!'+raw[20:],bytes(30),raw[:8]]:decoder(bad,False)
    # Repair checksum deliberately: validation is not just a checksum test.
    payload=bytearray(raw[20:]);payload[:4]=struct.pack('<I',9)
    decoder(lib.MAGIC+struct.pack('<IQ',len(payload),lib.fnv(payload))+payload,False)
    payload=raw[20:].replace(b'Caf\xc3\xa9',b'Caf\xc0\x80')
    decoder(lib.MAGIC+struct.pack('<IQ',len(payload),lib.fnv(payload))+payload,False)


def test_publication_retains_old_library_and_never_touches_stock(tmp_path):
    a,files=synthetic(1);b,new=synthetic(2);old=lib.encode([a]);files[lib.BASE+'/library.bin']=old
    f=FTP(files);result=app.commit_library(f,[a,b],old,'test',tmp_path)
    assert lib.decode(result)[1]['id']==b['id']
    assert not any('.backup-' in p or '.rollback-' in p for p in f.files)
    from console_transaction import LOCAL_BACKUPS
    assert (LOCAL_BACKUPS/'test/0-before.bin').read_bytes()==old
    assert all(lib.BASE in str(w) for w in f.writes)
    for p,v in files.items():
        if not p.endswith('/library.bin'):assert f.files[p]==v


def test_publication_failure_restores_previous_manifest(tmp_path):
    a,files=synthetic(1);b,_=synthetic(2);old=lib.encode([a]);files[lib.BASE+'/library.bin']=old
    f=FTP(files);f.fail_publish=True
    with pytest.raises(OSError,match='publish failed'):app.commit_library(f,[a,b],old,'test',tmp_path)
    assert f.files[lib.BASE+'/library.bin']==old


def test_live_title_bad_stage_or_changed_library_never_publishes(tmp_path):
    a,files=synthetic(1);old=lib.encode([a]);files[lib.BASE+'/library.bin']=old
    for state in ('active','corrupt','changed'):
        f=FTP(files)
        if state=='active':f.active=True
        elif state=='corrupt':f.corrupt_stage=True
        expected=old if state!='changed' else b'wrong previous'
        with pytest.raises(ValueError):app.commit_library(f,[a,synthetic(2)[0]],expected,state,tmp_path)
        assert f.files[lib.BASE+'/library.bin']==old
        assert not any(w[0]=='rename' for w in f.writes)
        if state=='active':assert not f.writes


def test_missing_library_with_retained_backup_refuses_silent_seed_reset():
    f=FTP({lib.BASE+'/library.bin.backup-interrupted':b'old'})
    with pytest.raises(ValueError,match='recover'):app.load_library(f)


def test_installer_rejects_live_title_before_capability_or_any_write(monkeypatch,tmp_path):
    f=FTP();f.active=True;monkeypatch.setattr(app,'FTP',lambda:f)
    with pytest.raises(ValueError,match='Fully close'):
        app.install({'title':{'id':'CUSA12878'},'ps4':{'ip':'fake'}},map_id='4ebb2',report_dir=tmp_path)
    assert not f.writes and not f.directories


def test_existing_companion_builds_additive_command_without_slot():
    from webapp.adapters.deploy import DeployOptions
    from webapp.adapters import paths
    o=DeployOptions(additive=True,map_id='4ebb2')
    assert o.build_argv()==['--additive-install','--download-beat-saver-song','4ebb2','--config',str(paths.CONFIG_PATH)]
    with pytest.raises(ValueError):DeployOptions(additive=True,map_id='4ebb2',pad_fsb5=True).build_argv()


@pytest.mark.parametrize('v4_source', [False, True])
@pytest.mark.parametrize('unrelated_count', [0, 61])
def test_existing_pipeline_installs_second_map_then_idempotent_reimport(monkeypatch,tmp_path,v4_source,unrelated_count):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    pytest.importorskip('UnityPy')
    from PIL import Image
    prepare=app.helper('prepare_additive_bundle.py')
    source=tmp_path/'source';prepare.generate_probe(source)
    info=json.loads((source/'Info.dat').read_text());info.update(_songAuthorName='Fixture artist',
        _coverImageFilename='cover.png',_previewStartTime=1,_previewDuration=1)
    if v4_source:
        import wave
        diffs=[]
        for group in info['_difficultyBeatmapSets']:
            for d in group['_difficultyBeatmaps']:
                path=source/d['_beatmapFilename']; raw=json.loads(path.read_text()); notes=raw['colorNotes']
                path.write_text(json.dumps({'version':'4.1.0',
                    'colorNotes':[{'b':n['b'],'i':i} for i,n in enumerate(notes)],
                    'colorNotesData':[{k:v for k,v in n.items() if k!='b'} for n in notes]}))
                diffs.append({'characteristic':'Standard','difficulty':d['_difficulty'],
                    'beatmapAuthors':{'mappers':['Fixture mapper']},'beatmapDataFilename':d['_beatmapFilename'],
                    'lightshowDataFilename':'Lightshow.dat','noteJumpMovementSpeed':d['_noteJumpMovementSpeed'],
                    'noteJumpStartBeatOffset':d['_noteJumpStartBeatOffset']})
        with wave.open(str(source/info['_songFilename'])) as w: samples,rate=w.getnframes(),w.getframerate()
        (source/'AudioData.dat').write_text(json.dumps({'version':'4.0.0','songSampleCount':samples,
            'songFrequency':rate,'bpmData':[{'si':0,'ei':samples,'sb':0,'eb':samples/rate*info['_beatsPerMinute']/60}]}))
        (source/'Lightshow.dat').write_text(json.dumps({'version':'4.0.0'}))
        info={'version':'4.0.1','song':{'title':info['_songName'],'author':'Fixture artist'},
            'audio':{'songFilename':info['_songFilename'],'audioDataFilename':'AudioData.dat','bpm':info['_beatsPerMinute'],
                     'previewStartTime':1,'previewDuration':1},'coverImageFilename':'cover.png','difficultyBeatmaps':diffs}
    (source/'Info.dat').write_text(json.dumps(info));Image.new('RGB',(64,64),'blue').save(source/'cover.png')
    (source/'beatsaver-metadata.json').write_text('{"id":"synthetic"}')
    a,files=synthetic(1);bundle=(ROOT/'custom_songs/quick_test.bundle').read_bytes()
    a.update(bytes=len(bundle),fnv=lib.fnv(bundle),sha256=hashlib.sha256(bundle).hexdigest())
    files[lib.paths(a)[0]]=bundle
    # Unrelated descriptors may refer to missing/damaged files: appending is not an audit.
    existing=[a]+[synthetic(i)[0] for i in range(2,2+unrelated_count)]
    old=lib.encode(existing);files[lib.BASE+'/library.bin']=old
    plugin=b'ELF fixture';files['/data/GoldHEN/plugins/orbeats.prx']=plugin
    files[lib.BASE+'/companion-protocol.json']=json.dumps({'schema':1,'title':'CUSA12878','max_songs':64,'active_elf_sha256':hashlib.sha256(plugin).hexdigest()}).encode()
    files['/data/GoldHEN/AFR/CUSA12878/features.json']=json.dumps({'enable_plugin':True,'enable_additive_song_packs':True}).encode()
    f=StrictFTP(files);monkeypatch.setattr(app,'FTP',lambda:f)
    cfg={'title':{'id':'CUSA12878'},'ps4':{'ip':'fake'}}
    result=app.install(cfg,song_dir=str(source),report_dir=tmp_path/'reports')
    assert result['ok'] and not result['already_present'] and result['count']==len(existing)+1
    songs=lib.decode(f.files[lib.BASE+'/library.bin'])
    assert lib.encode(songs[:-1])==old and songs[-1]['id']!=a['id']
    assert f.reads.count(lib.paths(a)[0])==1
    assert not any(p in f.reads for s in existing for p in lib.paths(s)[1:])
    assert not any(lib.paths(s)[0] in f.reads for s in existing[1:])
    assert app.checked(f,songs[-1])[0].startswith(b'UnityFS')
    assert json.loads(f.files[lib.BASE+'/'+songs[-1]['id']+'-media/map-info.json']) == {'id':'synthetic'}
    # Full re-import via actual conversion, no extra entry, no plugin/stock changes.
    again=app.install(cfg,song_dir=str(source),report_dir=tmp_path/'reports')
    assert again['already_present'] and again['count']==len(existing)+1
    assert lib.BASE+'/.install-lock' not in f.directories
    for p,v in files.items():
        if p!=lib.BASE+'/library.bin':assert f.files[p]==v
    for w in f.writes:assert w[1].startswith(lib.BASE+'/')


def test_beatsaver_download_hashes_map_contents_not_zip_and_rejects_traversal(monkeypatch,tmp_path):
    import zipfile
    import urllib.request
    info=json.dumps({'_version':'2.1.0','_difficultyBeatmapSets':[
        {'_difficultyBeatmaps':[{'_beatmapFilename':'Hard.dat'}]}]}).encode()
    chart=b'{"version":"3.3.0"}'
    digest=hashlib.sha1(info+chart).hexdigest()
    def archive(unsafe=False):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('Info.dat',info);z.writestr('Hard.dat',chart)
            if unsafe:z.writestr('../escape',b'bad')
        return out.getvalue()
    data=archive();assert hashlib.sha1(data).hexdigest()!=digest
    class Response(io.BytesIO):
        def __init__(self,data,url):super().__init__(data);self.url=url
        def geturl(self):return self.url
    def urlopen(req,timeout):
        if '/maps/id/' in req.full_url:
            return Response(json.dumps({'versions':[{'hash':digest,'downloadURL':'https://r2cdn.beatsaver.com/file.zip','diffs':[]}]}).encode(),req.full_url)
        return Response(data,req.full_url)
    monkeypatch.setattr(urllib.request,'urlopen',urlopen)
    source=app.download('https://beatsaver.com/maps/4ebb2',tmp_path/'download')
    assert (source/'Info.dat').read_bytes()==info
    data=archive(True)
    with pytest.raises(ValueError,match='unsafe'):app.download('4ebb2',tmp_path/'bad')
    assert not (tmp_path/'escape').exists()


def test_conversion_seed_still_requires_matching_length_fnv_and_sha256():
    song, files=synthetic(1);f=FTP(files)
    assert app.checked_bundle(f,song)==b'bundle1'
    assert f.reads==[lib.paths(song)[0]]
    f.files[lib.paths(song)[0]]=b'damaged'
    with pytest.raises(ValueError,match='verification failed'):app.checked_bundle(f,song)
    f.files[lib.paths(song)[0]]=b'bundle1';song['sha256']='0'*64
    with pytest.raises(ValueError,match='SHA256'):app.checked_bundle(f,song)


def test_missing_capability_mismatch_and_legacy_flags_refuse_all_content_writes(monkeypatch,tmp_path):
    plugin=b'current'
    cap={'schema':1,'title':'CUSA12878','active_elf_sha256':hashlib.sha256(plugin).hexdigest()}
    base={lib.BASE+'/companion-protocol.json':json.dumps(cap).encode(),
        '/data/GoldHEN/plugins/orbeats.prx':plugin,
        '/data/GoldHEN/AFR/CUSA12878/features.json':b'{"enable_plugin":true,"enable_additive_song_packs":true,"enable_song_previews":true}'}
    for mismatch in [False,True]:
        f=FTP(base)
        if mismatch:f.files['/data/GoldHEN/plugins/orbeats.prx']=b'wrong'
        monkeypatch.setattr(app,'FTP',lambda:f)
        with pytest.raises(ValueError):app.install({'title':{'id':'CUSA12878'},'ps4':{'ip':'fake'}},map_id='4ebb2',report_dir=tmp_path)
        assert not f.writes and not f.directories


def test_native_defaults_equal_host_seed_exactly(tmp_path):
    cc=shutil.which('clang++')
    if not cc:pytest.skip('clang++ required')
    raw=tmp_path/'seed.bin';raw.write_bytes(lib.encode(baseline()))
    cpp=tmp_path/'compare.cpp';exe=tmp_path/'compare'
    cpp.write_text(r'''
#include "additive_runtime_library.h"
#include <assert.h>
using namespace BsdAdditive;
int main(int argc,char** argv){assert(argc==2);FILE* f=fopen(argv[1],"rb");assert(f);
 unsigned char b[kLibraryMaxBytes];size_t n=fread(b,1,sizeof(b),f);fclose(f);
 RuntimeLibrary r={};assert(decode_library(r,b,n));assert(r.count==kReviewedSongCount);
 for(size_t i=0;i<r.count;++i){auto& a=r.songs[i];auto& d=kReviewedSongs[i];
  assert(!strcmp(a.id,d.id)&&!strcmp(a.title,d.title)&&!strcmp(a.author,d.author));
  assert(!strcmp(a.path,d.path)&&!strcmp(a.asset,d.asset)&&!strcmp(a.sha256,d.sha256));
  assert(a.bytes==d.bytes&&a.fnv==d.fnv&&a.bpm==d.bpm&&a.duration==d.duration&&a.preview_duration==d.preview_duration&&a.difficulty_mask==d.difficulty_mask);
  assert(a.cover.bytes==d.cover.bytes&&a.cover.fnv==d.cover.fnv&&!strcmp(a.cover.path,d.cover.path));
  assert(a.preview.bytes==d.preview.bytes&&a.preview.fnv==d.preview.fnv&&!strcmp(a.preview.path,d.preview.path));
  for(int j=0;j<5;++j){auto& x=a.difficulties[j];auto& y=d.difficulties[j];
   assert(x.notes==y.notes&&x.bombs==y.bombs&&x.obstacles==y.obstacles&&x.njs==y.njs&&x.jump_offset==y.jump_offset);}
 }
}
''')
    subprocess.run([cc,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(ROOT/'include'),str(cpp),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe),str(raw)],check=True,capture_output=True)


def test_actual_native_library_loader_fd_zero_partial_reads_and_no_invalid_fallback(tmp_path):
    from test_additive_probe_runtime import body
    cc=shutil.which('clang++')
    if not cc:pytest.skip('clang++ required')
    raw=tmp_path/'valid.bin';raw.write_bytes(lib.encode([synthetic(i)[0] for i in range(3)]))
    loader=body((ROOT/'src/main.cpp').read_text(),'static int additive_load_library(')
    cpp=tmp_path/'loader.cpp';exe=tmp_path/'loader'
    cpp.write_text(r'''
#include "additive_runtime_library.h"
#include <assert.h>
#include <fcntl.h>
#include <vector>
#include <stdlib.h>
#include <algorithm>
static BsdAdditive::RuntimeLibrary g_library;
static std::vector<unsigned char> file;static size_t offset;static int mode,closes;
static int sceKernelOpen(const char* p,int,int){assert(!strcmp(p,BsdAdditive::kLibraryPath));offset=0;
 return mode==1?(int)0x80020002:mode==2?-5:0;}
static int64_t sceKernelRead(int fd,void* out,size_t n){assert(fd==0);if(mode==3)return -5;
 n=std::min(n,std::min((size_t)37,file.size()-offset));memcpy(out,file.data()+offset,n);offset+=n;return n;}
static int sceKernelClose(int fd){assert(fd==0);++closes;return 0;}
''' + loader + r'''
int main(int argc,char** argv){assert(argc==2);FILE* f=fopen(argv[1],"rb");assert(f);
 unsigned char b[BsdAdditive::kLibraryMaxBytes+1];size_t n=fread(b,1,sizeof(b),f);fclose(f);file.assign(b,b+n);
 mode=0;assert(additive_load_library()==1&&g_library.count==3&&closes==1);
 mode=1;g_library={};assert(additive_load_library()==0&&g_library.count==2&&closes==1);
 mode=2;g_library={};assert(additive_load_library()==-1&&g_library.count==0&&closes==1);
 mode=3;g_library={};assert(additive_load_library()==-1&&g_library.count==0&&closes==2);
 mode=0;g_library={};file[30]^=1;assert(additive_load_library()==-1&&g_library.count==0&&closes==3);
 file.resize(BsdAdditive::kLibraryMaxBytes+1);assert(additive_load_library()==-1&&closes==4);
}
''')
    subprocess.run([cc,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(ROOT/'include'),str(cpp),'-o',str(exe)],check=True,capture_output=True)
    subprocess.run([str(exe),str(raw)],check=True,capture_output=True)


def test_batch_over_resource_budget_refuses_before_any_job(monkeypatch):
    from fastapi.testclient import TestClient
    from webapp import server
    monkeypatch.setattr(server,'_require_config',lambda:None)
    def forbid(*a,**kw):raise AssertionError('must not start an oversized batch')
    monkeypatch.setattr(server.RUNNER,'start',forbid)
    monkeypatch.setattr(server.RUNNER,'start_script',forbid)
    with TestClient(server.app) as client:
        r=client.post('/api/jobs/batch',json={'songs':[{'map_id':'4ebb2','audio':'pcm16'} for _ in range(65)]})
    assert r.status_code==400 and '64-song' in r.json()['detail']


def test_actual_setup_save_button_no_longer_depends_on_game_dump(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('node required')
    from test_additive_probe_runtime import body
    js=(ROOT/'webapp/static/app.js').read_text();fn=body(js,'function updateSaveButton()')
    script=tmp_path/'setup.js';script.write_text('''const assert=require('node:assert/strict');
const state={dumpOk:false};const nodes={'ps4-ip':{value:'192.168.1.67'},'ps4-port':{value:'2121'},'btn-save-config':{}};
function $(id){return nodes[id];}
'''+fn+'''
updateSaveButton();assert.equal(nodes['btn-save-config'].disabled,false);
nodes['ps4-ip'].value='';updateSaveButton();assert.equal(nodes['btn-save-config'].disabled,true);
nodes['ps4-ip'].value='console';nodes['ps4-port'].value='70000';updateSaveButton();assert.equal(nodes['btn-save-config'].disabled,true);
''')
    subprocess.run([node,str(script)],check=True,capture_output=True)


def test_cli_compatibility_refusal_is_actionable_not_traceback(tmp_path,monkeypatch,capsys):
    import full_custom_song_pipeline as pipeline
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps({'ps4':{'ip':'test'}}))
    monkeypatch.setattr(sys,'argv',['pipeline','--additive-install','--song-dir','fixture','--config',str(cfg)])
    def refuse(*a,**kw):raise ValueError('Expert (Expert.dat): unsupported V3 features: burstSliders (chains)')
    monkeypatch.setattr(app,'install',refuse)
    with pytest.raises(SystemExit) as exc:pipeline.main()
    assert exc.value.code==2
    err=capsys.readouterr().err
    assert 'Import refused: Expert (Expert.dat)' in err and 'chains' in err and 'Traceback' not in err


def test_optional_read_still_refuses_missing_parent_or_denied_listing():
    f = StrictFTP({lib.BASE + '/library.bin': b'old'})
    path = lib.BASE + '/new-media/cover.png'
    with pytest.raises(error_perm):
        app.read(f, path, missing=True)
    f.mkd(lib.BASE + '/new-media')
    assert app.read(f, path, missing=True) is None
    real_nlst = f.nlst
    def denied(parent):
        if parent.endswith('/new-media'):
            raise error_perm('550 permission denied')
        return real_nlst(parent)
    f.nlst = denied
    with pytest.raises(error_perm, match='permission denied'):
        app.read(f, path, missing=True)
    assert not f.writes


@pytest.mark.parametrize('flag,label',[('ne','Noodle Extensions'),('me','Mapping Extensions'),('chroma','Chroma')])
def test_extension_refusal_names_requirement_and_difficulty(monkeypatch,tmp_path,flag,label):
    import urllib.request
    class Response(io.BytesIO):
        def geturl(self):return 'https://api.beatsaver.com/maps/id/a'
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**kw:Response(json.dumps({'versions':[{'diffs':[{'difficulty':'Expert',flag:True}]}]}).encode()))
    with pytest.raises(ValueError,match=label+' in Expert'):
        app.download('a',tmp_path/'download')
    assert not (tmp_path/'download').exists()
