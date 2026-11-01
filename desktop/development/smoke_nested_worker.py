"""Real server -> runner -> real pipeline smoke. No network/FTP or game inputs.

Only a temporary copy's server module and its inventory row are modified. The
pipeline/dispatch/entrypoint/runner bytes and production guards remain intact.
Run on native Windows as part of its frozen smoke; Wine is not native evidence.
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
@app.post('/_test/nested/{case}')
def nested_fixture(case: str):
    if case == 'help':
        argv = ['--help']
    elif case == 'refusal':
        from adapters import paths
        import json
        p = paths.DATA_DIR / 'not-a-console.json'
        p.write_text(json.dumps({'title': {'id': 'SYNTHETIC_NO_NETWORK'}}))
        argv = ['--additive-install', '--config', str(p)]
    else:
        raise ValueError('Invalid smoke case')
    RUNNER.start(argv, label='No-network nested worker ' + case)
    return {'ok': True}
"""


def check(helper, env, root, runtime=None):
    helper, root = Path(helper).resolve(), Path(root).resolve()
    runtime = (
        Path(runtime).resolve() if runtime else helper.parent / "_internal/runtime"
    )
    fixture = root / "nested worker resources"
    shutil.copytree(runtime, fixture)
    server = fixture / "webapp/server.py"
    server.write_text(server.read_text(encoding="utf-8") + ROUTE, encoding="utf-8")
    manifest = json.loads((fixture / "runtime-manifest.json").read_bytes())
    value = server.read_bytes()
    manifest["webapp/server.py"] = {
        "bytes": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }
    (fixture / "runtime-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    state = root / "nested worker état"
    argv = [sys.executable, str(helper)] if helper.suffix == ".py" else [str(helper)]
    stderr = (root / "nested-worker-backend.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [*argv, "--state-dir", str(state), "--resources", str(fixture)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        env=env,
    )
    result = {}
    try:
        lines = queue.Queue()
        threading.Thread(
            target=lambda: lines.put(proc.stdout.readline(4097)), daemon=True
        ).start()
        ready = json.loads(lines.get(timeout=45))
        url = urlsplit(ready["url"])
        origin = f"{url.scheme}://{url.netloc}"
        assert url.hostname == "127.0.0.1"
        client = build_opener(
            ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        client.open(ready["url"], timeout=10).read()
        for case, code, expected in [
            ("help", 0, "usage:"),
            ("refusal", 2, "[additive] Import refused: only CUSA12878 2.04 supported"),
        ]:
            request = Request(
                origin + "/_test/nested/" + case,
                data=b"{}",
                method="POST",
                headers={"Origin": origin, "Content-Type": "application/json"},
            )
            client.open(request, timeout=10).read()
            deadline = time.monotonic() + 60
            while True:
                snap = json.load(client.open(origin + "/api/jobs/lines", timeout=5))
                if not snap["running"]:
                    break
                if time.monotonic() >= deadline:
                    # These test cases cannot enter a publication transaction.
                    client.open(
                        Request(
                            origin + "/api/jobs/cancel",
                            data=b"{}",
                            method="POST",
                            headers={"Origin": origin},
                        ),
                        timeout=5,
                    ).read()
                    raise ValueError(
                        "Nested worker did not finish: "
                        + "\n".join(snap["lines"])[-6000:]
                    )
                time.sleep(0.05)
            output = "\n".join(snap["lines"])
            assert snap["job"]["exit_code"] == code, output[-6000:]
            assert (
                expected in output
                and "[worker] Pipeline imports complete; entering CLI" in output
            ), output[-6000:]
            saved = sorted((state / "logs").glob("installation-*.log"))
            assert saved and expected in saved[-1].read_text(encoding="utf-8")
            result[case] = True
        result["saved_job_logs"] = True
    finally:
        if proc.poll() is None:
            proc.stdin.write("STOP\n")
            proc.stdin.flush()
            proc.stdin.close()
        try:
            proc.wait(timeout=45)
        finally:
            stderr.close()
    assert proc.returncode == 0
    return {**result, "ps4_operations": False, "real_nested_pipeline": True}
