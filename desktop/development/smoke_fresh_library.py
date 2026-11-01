"""No-network regression against real helper/runtime bytes (source or frozen).

Only a temporary copy's pipeline test entry and its inventory digest change.
Production modules, entrypoint and runtime integrity verification are unmodified.
Never install this test wrapper into a shipped bundle.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

WRAPPER = """import json
from pathlib import Path
from ftplib import error_perm
import additive_companion as core
import library_manager as manager
import companion_api as api
from fastapi import HTTPException
assert not (core.ROOT / "development/fixtures").exists()
class FTP:
    def __init__(self):self.connections=[];self.logins=[];self.closed=False
    def connect(self,ip,port,timeout):
        assert ip == "192.0.2.9" and port == 2121
        self.connections.append((ip,port))
    def login(self,user,password):
        assert user == "anonymous" and password == ""
        self.logins.append(user)
    def close(self):self.closed=True
    def retrbinary(self,command,callback):raise error_perm("550 not found")
    def nlst(self,path):
        if path == "/":return ["/data"]
        if path == "/data":return []
        raise error_perm("550 not found")
instances=[]
def fake():
    f=FTP();instances.append(f);return f
manager.FTP=fake
assert manager.catalog({"ps4":{"ip":"192.0.2.9"}}) == []
assert len(instances)==1 and instances[0].closed
# Test must use the submitted IP, not saved config or a library read.
core.load_library=lambda f: (_ for _ in ()).throw(AssertionError("unexpected library read"))
api.settings=lambda: (_ for _ in ()).throw(AssertionError("saved settings used"))
assert api.test_connection({"ip":" 192.0.2.9 "}) == {"ok":True,"ip":"192.0.2.9","port":2121}
try:api.test_connection({"ip":"192.0.2.9:2121"})
except HTTPException as exc:assert exc.status_code == 400
else:raise AssertionError("IP:port accepted")
assert len(instances)==2 and all(f.closed and f.logins==["anonymous"] for f in instances)
# No game input: prove the actual bundled loader never leaves a path reader open
# when parsing fails. This runs natively in the Windows CI helper too.
import tempfile
import UnityPy
prepare=core.helper('prepare_additive_bundle.py')
with tempfile.TemporaryDirectory(prefix='synthetic-template-reader-') as tmp:
    source=Path(tmp)/'source.bundle'
    source.write_bytes(b'synthetic parser sentinel')
    original=UnityPy.load
    def parse(value):
        assert isinstance(value,bytes) and value==b'synthetic parser sentinel'
        source.unlink()  # Would fail on Windows if the input stream stayed open.
        raise ValueError('synthetic parse refusal')
    UnityPy.load=parse
    try:
        try:prepare.build_bundle(source,{},'synthetic')
        except ValueError as exc:assert str(exc)=='synthetic parse refusal'
        else:raise AssertionError('synthetic parser unexpectedly succeeded')
        assert not source.exists()
    finally:UnityPy.load=original
# Exercise the real recovery/archive path in native frozen CI without a console.
class RecoveryFTP(FTP):
    def __init__(self):
        super().__init__();self.locked=True;self.removed=[]
    def nlst(self,path):
        if path=='/mnt/sandbox':return []
        if path==core.BASE:return [core.BASE+'/library.bin']+([core.BASE+'/.install-lock'] if self.locked else [])
        if path==core.BASE+'/.install-lock' and self.locked:return []
        raise AssertionError('unexpected recovery listing')
    def retrbinary(self,command,callback):
        assert command=='RETR '+core.BASE+'/library.bin'
        callback(core.encode([]))
    def rmd(self,path):
        assert path==core.BASE+'/.install-lock' and self.locked
        self.removed.append(path);self.locked=False
recovery=RecoveryFTP()
manager.FTP=lambda:recovery
assert manager.recover_install_lock({'ps4':{'ip':'192.0.2.9'}})['removed']
assert recovery.removed==[core.BASE+'/.install-lock'] and recovery.closed
print(json.dumps({"fresh_catalog_empty":True,"no_development_fixture":True,"submitted_address_tested":True,"invalid_address_rejected":True,"ftp_connections":2,"console_writes":False,"mocked_ftp_only":True,"template_reader_closed":True,"recovery_empty_lock_only":True}))
"""


def check(helper, env, root, runtime=None):
    helper = Path(helper).resolve()
    runtime = (
        Path(runtime).resolve() if runtime else helper.parent / "_internal/runtime"
    )
    fixture = Path(root) / "fresh-library-runtime"
    shutil.copytree(runtime, fixture)
    manifest = json.loads((runtime / "runtime-manifest.json").read_text())
    for name, row in manifest.items():
        value = (fixture / name).read_bytes()
        if len(value) != row["bytes"] or hashlib.sha256(value).hexdigest() != row["sha256"]:
            raise ValueError("Copied runtime differs from shipped inventory: " + name)
    entry = "tools/full_custom_song_pipeline.py"
    (fixture / entry).write_text(WRAPPER, encoding="utf-8")
    value = (fixture / entry).read_bytes()
    manifest[entry] = {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    (fixture / "runtime-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    argv = [sys.executable, str(helper)] if helper.suffix == ".py" else [str(helper)]
    result = subprocess.run(
        [*argv, "--desktop-task", "pipeline", "--"],
        env={
            **env,
            "PYTHONDONTWRITEBYTECODE": "1",
            "ORBEATS_RUNTIME_ROOT": str(fixture),
            "ORBEATS_STATE_DIR": str(Path(root) / "fresh-library-state"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "Fresh-library packaged regression failed: " + result.stderr[-5000:]
        )
    proof = json.loads(result.stdout)
    assert proof == {
        "fresh_catalog_empty": True,
        "no_development_fixture": True,
        "submitted_address_tested": True,
        "invalid_address_rejected": True,
        "ftp_connections": 2,
        "console_writes": False,
        "mocked_ftp_only": True,
        "template_reader_closed": True,
        "recovery_empty_lock_only": True,
    }
    return proof
