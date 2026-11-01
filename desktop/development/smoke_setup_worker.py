"""Native/source HTTP responsiveness while the real setup worker is running.

Test-only route and a deterministic gate in a copied worker; inventory is rehashed.
Real dispatch/child/native imports/schema refusal run, no FTP or game assets.
"""

import hashlib
import http.cookiejar
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

ROUTE = """
@app.post('/_test/isolated-setup')
def isolated_setup_fixture():
    import first_setup
    with first_setup.operation('Testing isolated local worker'):
        try:
            first_setup._validate_seed(b'Not a Unity bundle; synthetic refusal before any console work')
        except ValueError as exc:
            if 'Template validation worker failed' not in str(exc):raise
            return {'refused_invalid_template':True,'console_writes':False}
        raise AssertionError('Invalid template accepted')
"""


def check(helper, env, root, runtime=None):
    helper, root = Path(helper).resolve(), Path(root).resolve()
    runtime = (
        Path(runtime).resolve() if runtime else helper.parent / "_internal/runtime"
    )
    fixture = root / "setup worker resources"
    shutil.copytree(runtime, fixture)
    server = fixture / "webapp/server.py"
    server.write_text(server.read_text(encoding="utf-8") + ROUTE, encoding="utf-8")
    worker = fixture / "development/scripts/validate_setup_template.py"
    gate = root / "release-worker"
    marker = '    phase("Loading conversion helpers in isolated worker")'
    content = worker.read_text(encoding="utf-8")
    assert content.count(marker) == 1
    worker.write_text(
        content.replace(
            marker,
            marker
            + '\n    phase("Test gate: isolated worker waiting")\n    import time\n    while not Path('
            + repr(str(gate))
            + ").exists(): time.sleep(0.02)",
        ),
        encoding="utf-8",
    )
    manifest = json.loads((fixture / "runtime-manifest.json").read_bytes())
    for file in (server, worker):
        value = file.read_bytes()
        manifest[file.relative_to(fixture).as_posix()] = {
            "bytes": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    (fixture / "runtime-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    argv = [sys.executable, str(helper)] if helper.suffix == ".py" else [str(helper)]
    state = root / "setup worker état"
    with (root / "setup-worker-backend.log").open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            [*argv, "--state-dir", str(state), "--resources", str(fixture)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            env=env,
        )
        result = queue.Queue()
        try:
            ready_queue = queue.Queue()
            threading.Thread(
                target=lambda: ready_queue.put(proc.stdout.readline(4097)), daemon=True
            ).start()
            ready = json.loads(ready_queue.get(timeout=45))
            url = urlsplit(ready["url"])
            origin = f"{url.scheme}://{url.netloc}"
            assert url.hostname == "127.0.0.1"
            jar = http.cookiejar.CookieJar()
            client = build_opener(ProxyHandler({}), HTTPCookieProcessor(jar))
            client.open(ready["url"], timeout=10).read()
            # Use independent openers/immutable cookie headers across threads.
            request = Request(
                origin + "/_test/isolated-setup",
                data=b"{}",
                method="POST",
                headers={"Origin": origin, "Content-Type": "application/json"},
            )
            jar.add_cookie_header(request)
            worker_client = build_opener(ProxyHandler({}))

            def invoke():
                try:
                    result.put(json.load(worker_client.open(request, timeout=120)))
                except (OSError, ValueError) as exc:
                    result.put(exc)

            thread = threading.Thread(target=invoke, daemon=True)
            thread.start()
            deadline = time.monotonic() + 45
            while True:
                status = json.load(client.open(origin + "/api/orbis/setup", timeout=3))
                if status["activity"]["phase"] == "Test gate: isolated worker waiting":
                    break
                if not result.empty():
                    raise ValueError(
                        "Setup worker ended before gate: " + str(result.get())
                    )
                if time.monotonic() > deadline:
                    raise ValueError("Isolated setup did not reach test gate")
                time.sleep(0.05)
            for _ in range(3):
                started = time.monotonic()
                snap = json.load(client.open(origin + "/api/orbis/setup", timeout=3))
                assert snap["activity"]["busy"] and time.monotonic() - started < 3
            gate.write_text("release", encoding="ascii")
            deadline = time.monotonic() + 120
            # Continue polling through the real NumPy/audio native imports too,
            # not just the deterministic pre-conversion gate.
            while result.empty():
                started = time.monotonic()
                snap = json.load(client.open(origin + "/api/orbis/setup", timeout=3))
                assert time.monotonic() - started < 3 and not snap["ready"]
                if time.monotonic() > deadline:
                    raise ValueError("Isolated worker did not finish its safe schema refusal")
                time.sleep(0.05)
            outcome = result.get_nowait()
            if isinstance(outcome, Exception):
                raise outcome
            assert outcome == {
                "refused_invalid_template": True,
                "console_writes": False,
            }
            thread.join(timeout=5)
            saved = list((state / "logs").glob("setup-*.log"))
            assert saved and "Test gate: isolated worker waiting" in saved[0].read_text(
                encoding="utf-8"
            )
            assert "Traceback (most recent call last)" in saved[0].read_text(
                encoding="utf-8"
            )
        finally:
            gate.touch()
            if proc.poll() is None:
                proc.stdin.write("STOP\n")
                proc.stdin.flush()
                proc.stdin.close()
            try:
                proc.wait(timeout=120)
            finally:
                proc.stdout.close()
        assert proc.returncode == 0
    return {
        "responsive_during_worker": True,
        "invalid_template_refused": True,
        "real_child_dispatch": True,
        "console_writes": False,
    }
