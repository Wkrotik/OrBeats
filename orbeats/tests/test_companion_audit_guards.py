"""Audit regressions: denied FTP reads, byte-preserving INI merge and job races."""
import io
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import time
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'webapp')]
import additive_companion as core
import goldhen_config
from adapters.runner import SingleJobRunner
from test_companion_management import Console,CONFIG,INI,PLUGIN


def test_denied_existing_read_is_not_treated_as_absent():
    class Denied(Console):
        def retrbinary(self,cmd,callback):raise core.error_perm('550 permission denied')
    f=Denied({INI:b'precious existing entries'})
    with pytest.raises(ValueError,match='Cannot read existing'):core.read(f,INI,missing=True)
    assert core.read(f,INI+'.missing',missing=True) is None


def test_ini_extends_existing_section_without_duplicate_header_or_reformatting():
    before=b'; header\r\n[CUSA12878]\r\n/other.prx\r\n; keep\r\n[OTHER]\r\n/keep.prx\r\n'
    after=goldhen_config.merge_ini(before)
    assert after.count(b'[CUSA12878]')==1
    assert after.replace(PLUGIN.encode()+b'\r\n',b'',1)==before
    assert after.index(PLUGIN.encode())<after.index(b'[OTHER]')
    with pytest.raises(ValueError,match='Another variant'):
        goldhen_config.merge_ini(b'[CUSA12878]\n/data/GoldHEN/plugins/orbeats_debug.prx\n')


def test_legacy_cli_ini_registration_uses_same_safe_merge(monkeypatch):
    f=Console({INI:b'; retain me\n[CUSA12878]\n/keep.prx\n'})
    old=f.files[INI];monkeypatch.setattr(core,'FTP',lambda:f)
    goldhen_config.ensure_remote_ini(CONFIG,PLUGIN)
    assert f.files[INI].startswith(old)
    assert f.files[INI].count(b'[CUSA12878]')==1
    import console_transaction
    assert not any('.backup-' in p or '.rollback-' in p for p in f.files)
    assert old in [p.read_bytes() for p in console_transaction.LOCAL_BACKUPS.rglob('*-before.bin')]


def test_two_simultaneous_jobs_only_spawn_one_and_cancel_remains_busy(monkeypatch):
    from adapters import runner as module
    done=threading.Event();spawned=[]
    class Process:
        pid=1234567
        returncode=0
        stdout=io.StringIO('')
        def wait(self):done.wait(5);return 0
    def popen(*args,**kwargs):spawned.append(args);return Process()
    monkeypatch.setattr(module.subprocess,'Popen',popen)
    monkeypatch.setattr(module.os,'getpgid',lambda pid:pid)
    monkeypatch.setattr(module.os,'killpg',lambda *args:None)
    runner=SingleJobRunner();barrier=threading.Barrier(2)
    def start():
        barrier.wait()
        try:return runner.start_script('fixture.py',[],label='test')
        except RuntimeError:return None
    try:
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:start(),range(2)))
        assert len(spawned)==1 and sum(r is not None for r in results)==1
        assert runner.cancel() and runner.is_busy()
        with pytest.raises(RuntimeError):runner.start_script('other.py',[])
    finally:done.set()
    for _ in range(100):
        if not runner.is_busy():break
        time.sleep(.01)
    assert not runner.is_busy()


def test_failed_subprocess_start_does_not_leave_phantom_busy_job(monkeypatch):
    from adapters import runner as module
    def fail(*args,**kw):raise FileNotFoundError('missing interpreter')
    monkeypatch.setattr(module.subprocess,'Popen',fail)
    r=SingleJobRunner()
    with pytest.raises(FileNotFoundError):r.start_script('fixture.py',[])
    assert r.current is None and not r.is_busy()
