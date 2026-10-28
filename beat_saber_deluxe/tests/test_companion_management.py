"""Offline regression tests for new UI services and scoped console transactions."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from test_additive_companion import FTP, synthetic

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'webapp'))
import library_manager as manager
import companion_api
import server
from additive_library import BASE, encode, decode, paths

CONFIG={'ps4':{'ip':'192.168.1.67'},'title':{'id':'CUSA12878'}}
PLUGIN='/data/GoldHEN/plugins/orbeats.prx'
INI='/data/GoldHEN/plugins.ini'

class Console(FTP):
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.deletes=[];self.fail_target=None
    def nlst(self, path):
        if path == '/mnt/sandbox':
            return super().nlst(path)
        return sorted(set(super().nlst(path)) | {
            p for p in self.directories if p.rsplit('/', 1)[0] == path
        })
    def retrbinary(self,cmd,callback):
        # GoldHEN reconstructs canonical ELF only when RETR ends with .prx.
        path=cmd[5:];value=self.files.get(path,b'')
        if path.endswith('.prx') and value[:4]==bytes.fromhex('4f153d1d'):
            callback(manager.elf_from_fself(value));return
        return super().retrbinary(cmd,callback)
    def rmd(self,path):
        if path not in self.directories:raise manager.error_perm('550 missing')
        self.directories.remove(path)
    def delete(self,path):
        if path not in self.files:raise manager.error_perm('550 missing')
        self.deletes.append(path);del self.files[path]
    def rename(self,a,b):
        if self.fail_target==b and '.stage-' in a:
            self.fail_target=None;raise OSError('injected publication failure')
        return super().rename(a,b)


def seed(monkeypatch,count=2):
    songs=[];files={}
    for i in range(count):
        s,b=synthetic(i);songs.append(s);files.update(b)
    files[BASE+'/library.bin']=encode(songs)
    f=Console(files);monkeypatch.setattr(manager,'FTP',lambda:f)
    return f,songs


def test_catalog_never_advertises_absent_migration_defaults(monkeypatch):
    f=Console();monkeypatch.setattr(manager,'FTP',lambda:f)
    assert manager.catalog(CONFIG)==[]
    assert not f.writes and not f.deletes
    defaults=manager.core.load_library(f)[0]
    f.files[paths(defaults[0])[0]]=b'partial legacy bundle'
    with pytest.raises(ValueError,match='Incomplete legacy library'):
        manager.catalog(CONFIG)
    assert not f.writes and not f.deletes


def test_ini_preserves_every_original_byte_comments_and_other_sections():
    raw=b'\xef\xbb\xbf; Keep this comment\r\n[default]\r\n/other.prx\r\n[CUSA55555]\r\n/keep.prx'
    merged=manager.merge_ini(raw)
    assert merged.startswith(raw) and merged.count(b'/keep.prx')==1
    assert merged.endswith(b'[CUSA12878]\r\n'+PLUGIN.encode()+b'\r\n')
    assert manager.merge_ini(merged)==merged
    with pytest.raises(ValueError):manager.merge_ini(b'[default]\n'+PLUGIN.encode()+b'\n')
    with pytest.raises(ValueError):manager.merge_ini(b'invalid\x00ini')


def test_catalog_metadata_cover_and_removal_leave_other_maps_untouched(monkeypatch):
    f,songs=seed(monkeypatch);meta={'metadata':{'levelAuthorName':'Mapper <script>'}}
    f.files[BASE+'/'+songs[0]['id']+'-media/map-info.json']=json.dumps(meta).encode()
    assert manager.catalog(CONFIG)[0]['info']==meta
    assert manager.media(CONFIG,songs[0]['id'],'cover')==b'cover'
    other={p:f.files[p] for p in paths(songs[1])}
    f.files['/data/other-game/keep.dat']=b'untouched'
    r=manager.remove(CONFIG,songs[0]['id'])
    assert r['count']==1 and not r['cleanup_pending']
    assert f.files[BASE+'/library.bin']==encode([songs[1]])
    assert all(f.files[p]==b for p,b in other.items())
    assert f.files['/data/other-game/keep.dat']==b'untouched'
    assert all(p.startswith(BASE+'/'+songs[0]['id']) or '.rollback-' in p for p in f.deletes)
    assert BASE+'/.install-lock' not in f.directories


@pytest.mark.parametrize('existing_template', [False, True])
def test_deleting_last_map_preserves_remote_conversion_seed_not_host_song(monkeypatch,existing_template):
    f,songs=seed(monkeypatch,1)
    if existing_template:f.files[BASE+'/template.bundle']=b'existing seed'
    r=manager.remove(CONFIG,songs[0]['id'])
    assert r['count']==0 and decode(f.files[BASE+'/library.bin'])==[]
    assert f.files[BASE+'/template.bundle']==(b'existing seed' if existing_template else b'bundle0')
    assert all(p not in f.files for p in paths(songs[0]))
    assert f.reads.count(paths(songs[0])[0])==(0 if existing_template else 1)
    assert not any(p in f.reads for p in paths(songs[0])[1:])
    assert BASE+'/template.bundle' not in f.reads


def test_live_title_and_corrupt_cover_refuse(monkeypatch):
    f,songs=seed(monkeypatch);f.active=True
    with pytest.raises(ValueError,match='Fully close'):manager.remove(CONFIG,songs[0]['id'])
    assert not f.writes and not f.deletes
    f.active=False;f.files[paths(songs[0])[1]]=b'bad'
    with pytest.raises(ValueError,match='checksum'):manager.media(CONFIG,songs[0]['id'],'cover')
    with pytest.raises(ValueError,match='Unknown'):manager.remove(CONFIG,'../../other')
    assert not f.deletes


def test_library_publish_failure_retains_active_map_and_all_bytes(monkeypatch):
    f,songs=seed(monkeypatch);before=copy.deepcopy(f.files);f.fail_publish=True
    with pytest.raises(OSError,match='publish failed'):manager.remove(CONFIG,songs[0]['id'])
    assert all(f.files[p]==b for p,b in before.items())
    assert all('.stage-' in p or '.rollback-' in p for p in f.deletes)


def artifact():
    path=ROOT/'orbeats.prx'
    if not path.exists():pytest.skip('local native artifact required for real FSELF verification')
    return path


def test_plugin_setup_preserves_ini_flags_and_populated_library(monkeypatch):
    f,songs=seed(monkeypatch);raw=b'; original comment\n[default]\n/keep.prx\n'
    f.files[INI]=raw;f.files[PLUGIN]=b'old-elf';f.files[BASE+'/companion-protocol.json']=b'old-capability'
    flags='/data/GoldHEN/AFR/CUSA12878/features.json';f.files[flags]=b'{"enable_plugin":false}'
    old_library=f.files[BASE+'/library.bin']
    r=manager.deploy_plugin(CONFIG,artifact())
    assert r['ok'] and f.files[INI].startswith(raw)
    assert f.files[flags]==b'{"enable_plugin":false}' and f.files[BASE+'/library.bin']==old_library
    expected=manager.elf_from_fself(artifact().read_bytes())
    cap=json.loads(f.files[BASE+'/companion-protocol.json'])
    assert manager.core.read(f,PLUGIN)==expected and cap['active_elf_sha256']==hashlib.sha256(expected).hexdigest()
    assert cap['max_songs']==64 and BASE+'/.install-lock' not in f.directories
    assert not any('.backup-' in p or '.rollback-' in p for p in f.files)


@pytest.mark.parametrize('target',[INI,BASE+'/companion-protocol.json'])
def test_plugin_setup_failure_rolls_back_plugin_ini_capability(monkeypatch,target):
    f,songs=seed(monkeypatch);f.files.update({PLUGIN:b'old-elf',INI:b'; original\n',BASE+'/companion-protocol.json':b'old-cap'})
    before=copy.deepcopy(f.files);f.fail_target=target
    with pytest.raises(OSError,match='publication failure'):manager.deploy_plugin(CONFIG,artifact())
    assert all(f.files[p]==b for p,b in before.items())
    flags='/data/GoldHEN/AFR/CUSA12878/features.json'
    assert flags not in f.files and BASE+'/.install-lock' not in f.directories


def test_fresh_plugin_setup_creates_empty_library_not_fictitious_seed_maps(monkeypatch):
    f=Console();monkeypatch.setattr(manager,'FTP',lambda:f)
    assert manager.deploy_plugin(CONFIG,artifact())['ok']
    assert decode(f.files[BASE+'/library.bin'])==[]
    assert json.loads(f.files['/data/GoldHEN/AFR/CUSA12878/features.json'])['enable_additive_song_packs'] is True


def test_incomplete_legacy_setup_refuses_before_active_files_changed(monkeypatch):
    f=Console({paths(manager.core.load_library(Console())[0][0])[0]:b'only-one-file'})
    monkeypatch.setattr(manager,'FTP',lambda:f)
    with pytest.raises(ValueError,match='Incomplete legacy'):manager.deploy_plugin(CONFIG,artifact())
    assert not f.writes and PLUGIN not in f.files


def test_settings_hide_password_validate_ip_and_expose_honest_update_state(monkeypatch):
    cfg=copy.deepcopy(CONFIG);cfg['ps4']['ftp_password']='secret'
    monkeypatch.setattr(companion_api.config,'load_config',lambda:copy.deepcopy(cfg))
    saved=[];monkeypatch.setattr(companion_api.config,'save_config',saved.append)
    c=TestClient(server.app);value=c.get('/api/orbis/settings').json()
    assert 'secret' not in json.dumps(value) and value['password_set']
    assert value['updates']['state']=='unconfigured'
    assert c.post('/api/orbis/settings',json={'ip':'not-an-ip'}).status_code==400
    assert c.post('/api/orbis/settings',json={'ip':'192.168.1.22','port':2121,'user':'anonymous'}).status_code==200
    assert saved[0]['ps4']['ftp_password']=='secret'


def test_origin_guard_rebinding_and_new_home_shell():
    c=TestClient(server.app)
    assert c.post('/api/orbis/plugin',headers={'Origin':'https://attacker.invalid'}).status_code==403
    assert c.get('/api/ping',headers={'Host':'attacker.invalid'}).status_code==400
    html=c.get('/').text
    assert 'OrBeats' in html and 'Dump Guide' not in html and 'companion.js' in html
    assert '8 song' not in html and '8-song' not in html


def test_discovery_filters_are_server_validated(monkeypatch):
    calls=[];monkeypatch.setattr(companion_api.beatsaver,'_get_json',lambda url:(calls.append(url) or {'docs':[]}))
    c=TestClient(server.app)
    assert c.get('/api/orbis/search?q=throttle&sort=Rating&period=month').status_code==200
    assert 'sortOrder=Rating' in calls[0] and 'from=' in calls[0]
    assert c.get('/api/orbis/search?sort=evil').status_code==400
    assert c.get('/api/orbis/map/../../etc').status_code==404


def test_preview_route_verifies_console_bytes_and_never_writes(monkeypatch):
    f,songs=seed(monkeypatch)
    monkeypatch.setattr(companion_api,'settings',lambda:CONFIG)
    client=TestClient(server.app)
    path='/api/orbis/library/'+songs[0]['id']+'/preview'
    response=client.get(path)
    assert response.status_code==200 and response.content==f.files[paths(songs[0])[2]]
    assert response.headers['content-type']=='audio/wav'
    assert response.headers['cache-control']=='private, max-age=3600'
    f.files[paths(songs[0])[2]]=b'bad'
    assert client.get(path).status_code==400
    with pytest.raises(ValueError,match='Unknown'):manager.media(CONFIG,songs[0]['id'],'../bundle')
    assert not f.writes and not f.deletes


def test_concurrent_browser_media_requests_share_one_ftp_connection(monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    f,songs=seed(monkeypatch)
    active=0;peak=0;counter=threading.Lock()
    class LimitedConsole(Console):
        def connect(self,*args,**kwargs):
            nonlocal active,peak
            with counter: active+=1;peak=max(peak,active)
            time.sleep(.02)
        def close(self):
            nonlocal active
            with counter:active-=1
    monkeypatch.setattr(manager,'FTP',lambda:LimitedConsole(f.files))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda kind:manager.media(CONFIG,songs[0]['id'],kind),['cover','preview','cover','preview']))
    assert results==[f.files[paths(songs[0])[i]] for i in (1,2,1,2)] and peak==1 and active==0


@pytest.mark.parametrize("operation", ["plugin", "remove"])
def test_existing_install_lock_is_explained_and_never_cleared(monkeypatch, operation):
    f, songs = seed(monkeypatch)
    lock = BASE + '/.install-lock'
    f.directories.add(lock)
    before = copy.deepcopy(f.files)
    with pytest.raises(ValueError, match='active or interrupted installation holds .install-lock'):
        if operation == 'plugin':
            manager.deploy_plugin(CONFIG, artifact())
        else:
            manager.remove(CONFIG, songs[0]['id'])
    assert f.files == before and not f.writes and not f.deletes
    assert lock in f.directories


@pytest.mark.parametrize('inspection_denied', [False, True])
def test_lock_write_denial_is_not_reported_as_existing_lock(monkeypatch, inspection_denied):
    f = Console()
    def denied(_):
        raise manager.error_perm('550 Permission denied')
    monkeypatch.setattr(f, 'mkd', denied)
    if inspection_denied:
        monkeypatch.setattr(f, 'nlst', denied)
    message = 'Cannot inspect' if inspection_denied else 'Cannot create'
    with pytest.raises(ValueError, match=message):
        manager.acquire_install_lock(f)
    assert not f.writes and not f.directories and not f.deletes


def test_plugin_api_returns_actionable_lock_error_without_mutation(monkeypatch):
    f, _ = seed(monkeypatch)
    f.directories.add(BASE + '/.install-lock')
    monkeypatch.setattr(companion_api.config, 'load_config', lambda: CONFIG)
    response = TestClient(server.app).post('/api/orbis/plugin')
    assert response.status_code == 400
    assert 'interrupted installation holds .install-lock' in response.json()['detail']
    assert not f.writes and BASE + '/.install-lock' in f.directories


def banner_blob(version='0.8071', debug=False):
    return b'\x7fELF' + b'\0' * 60 + ('=== OrBeats v' + version + (' DEBUG' if debug else '') + ' started ===').encode() + b'\0'


@pytest.mark.parametrize('debug', [False, True])
def test_version_is_read_from_unique_embedded_banner_not_loose_string(debug):
    blob=banner_blob(debug=debug)
    assert manager.binary_version(blob)=='0.8071'
    assert manager.binary_version(b'\x7fELF\0v0.9999\0') is None
    assert manager.binary_version(blob+banner_blob('0.8068')) is None
    assert manager.binary_version(blob.replace(b'OrBeats',b'BS Deluxe'))=='0.8071'
    assert manager.binary_version(blob[:-1]) is None


@pytest.mark.parametrize('problem', ['none','stale_hash','wrong_version','invalid_json','missing_binary','duplicate_ini'])
def test_readonly_plugin_version_never_trusts_stale_sidecar(monkeypatch,tmp_path,problem):
    blob=banner_blob('0.8068');cap={'schema':1,'title':'CUSA12878','plugin':'0.8068','active_elf_sha256':hashlib.sha256(blob).hexdigest()}
    if problem=='stale_hash':cap['active_elf_sha256']='0'*64
    if problem=='wrong_version':cap['plugin']='0.9999'
    files={PLUGIN:blob,BASE+'/companion-protocol.json':json.dumps(cap).encode(),INI:b'[CUSA12878]\n'+PLUGIN.encode()+b'\n'}
    if problem=='invalid_json':files[BASE+'/companion-protocol.json']=b'[]'
    if problem=='missing_binary':del files[PLUGIN]
    if problem=='duplicate_ini':files[INI]+=PLUGIN.encode()+b'\n'
    f=Console(files);monkeypatch.setattr(manager,'FTP',lambda:f)
    r=manager.plugin_status(CONFIG,tmp_path/'missing-candidate.prx')
    assert not f.writes and not f.deletes
    assert r['runtime_verified'] is False and r['available_version'] is None
    assert r['installed_version']==(None if problem=='missing_binary' else '0.8068')
    assert r['max_songs']==(8 if problem in ('none','duplicate_ini') else None)
    assert r['registration']==('needs_review' if problem=='duplicate_ini' else 'registered_once')


def test_ini_update_idempotent_and_duplicate_refusal():
    raw=b'\xef\xbb\xbf; original\r\n[default]\r\n/unrelated.prx\r\n'
    merged=manager.merge_ini(raw)
    for _ in range(5):assert manager.merge_ini(merged)==merged
    assert merged.startswith(raw) and merged.endswith(PLUGIN.encode()+b'\r\n')
    with pytest.raises(ValueError,match='Duplicate'):
        manager.merge_ini(merged+PLUGIN.encode()+b'\r\n')


def test_repeated_plugin_updates_do_not_rewrite_ini(monkeypatch):
    f,_=seed(monkeypatch);f.files[INI]=b'; original\n[default]\n/keep.prx\n'
    manager.deploy_plugin(CONFIG,artifact());registered=f.files[INI];f.writes.clear()
    manager.deploy_plugin(CONFIG,artifact())
    assert f.files[INI]==registered
    assert registered.count(PLUGIN.encode())==1
    assert not any(INI in value for event in f.writes for value in event[1:])
    cap=json.loads(f.files[BASE+'/companion-protocol.json'])
    assert cap['plugin']==manager.binary_version(manager.elf_from_fself(artifact().read_bytes()))


def test_current_binary_and_matching_capability_report_64_without_writes(monkeypatch,tmp_path):
    blob=banner_blob();files={PLUGIN:blob,BASE+'/companion-protocol.json':json.dumps({'schema':1,'title':'CUSA12878','plugin':'0.8071','active_elf_sha256':hashlib.sha256(blob).hexdigest(),'max_songs':64}).encode(),INI:b'[CUSA12878]\n'+PLUGIN.encode()+b'\n'}
    f=Console(files);monkeypatch.setattr(manager,'FTP',lambda:f)
    result=manager.plugin_status(CONFIG,tmp_path/'not-built.prx')
    assert result['installed_version']=='0.8071' and result['max_songs']==64
    assert result['capability_matches'] and result['declared_version_matches']
    assert not f.writes and not f.deletes


def test_plugin_version_check_rejects_mid_read_replacement(monkeypatch,tmp_path):
    blob=banner_blob();f=Console({PLUGIN:blob,BASE+'/companion-protocol.json':b'{}',INI:b''})
    original=f.retrbinary;reads=0
    def replaced(cmd,callback):
        nonlocal reads
        if cmd=='RETR '+PLUGIN:
            reads+=1
            if reads==2:f.files[PLUGIN]=banner_blob('0.8068')
        return original(cmd,callback)
    monkeypatch.setattr(f,'retrbinary',replaced);monkeypatch.setattr(manager,'FTP',lambda:f)
    with pytest.raises(ValueError,match='changed during version check'):
        manager.plugin_status(CONFIG,tmp_path/'missing.prx')
    assert not f.writes and not f.deletes
