"""Offline queue lifecycle and job-cursor regressions; never use console/network."""

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))
import server
from adapters.install_queue import InstallQueue
from adapters.runner import Job, SingleJobRunner


class FakeRunner:
    def __init__(self):
        self.jobs = []
        self.fail_start = False

    def is_busy(self):
        return self.fail_start

    def start(self, argv, label=""):
        if self.fail_start:
            raise RuntimeError("another job is running")
        assert not self.jobs or self.jobs[-1].exit_code is not None
        job = Job(id=len(self.jobs) + 1, argv=argv, cwd=".", started_at=time.time(), label=label)
        self.jobs.append(job)
        return job


def wait_for(predicate):
    end = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < end, "queue worker did not reach expected state"
        time.sleep(0.01)


def test_explicit_start_and_serial_dispatch():
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add("AB12", "<img title>")
    queue.add("123")
    assert not runner.jobs and queue.status()["paused"]
    with pytest.raises(ValueError, match="already queued"):
        queue.add("ab12")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    assert queue.status()["active"]["map_id"] == "ab12"
    assert runner.jobs[0].argv[:3] == ["--additive-install", "--download-beat-saver-song", "ab12"]
    assert len(queue.status()["pending"]) == 1
    runner.jobs[0].exit_code = 0
    wait_for(lambda: len(runner.jobs) == 2)
    runner.jobs[1].exit_code = 0
    wait_for(lambda: len(queue.status()["history"]) == 2)
    wait_for(lambda: queue.status()["paused"])
    assert not queue.has_work()
    assert all(e["status"] == "complete" for e in queue.status()["history"])


def test_cancel_pauses_and_retains_remaining_maps():
    cancelled = True
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add("a")
    queue.add("b")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    runner.jobs[0].cancelled = cancelled
    runner.jobs[0].exit_code = -15 if cancelled else 2
    wait_for(lambda: queue.status()["paused"])
    assert len(runner.jobs) == 1 and queue.status()["pending"][0]["map_id"] == "b"
    assert queue.status()["history"][0]["status"] == ("cancelled" if cancelled else "failed")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 2)
    runner.jobs[1].exit_code = 0
    wait_for(lambda: not queue.has_work())


def test_pause_clear_and_remove_do_not_interrupt_active_install():
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add("a")
    second = queue.add("b")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    queue.pause()
    queue.remove(second["id"])
    queue.add("c")
    queue.clear()
    assert queue.status()["active"]["map_id"] == "a" and not queue.status()["pending"]
    assert runner.jobs[0].exit_code is None
    runner.jobs[0].exit_code = 0
    wait_for(lambda: not queue.has_work())
    assert len(runner.jobs) == 1


def test_busy_runner_keeps_entry_and_pauses():
    runner = FakeRunner()
    runner.fail_start = True
    queue = InstallQueue(runner)
    queue.add("abc")
    queue.start()
    wait_for(lambda: queue.status()["paused"])
    assert queue.status()["pending"][0]["map_id"] == "abc"
    assert "another job" in queue.status()["message"].lower()
    assert queue.status()["error"]
    queue.clear()
    assert not queue.status()["error"]
    assert not queue.status()["active"]


def test_bounds_and_status_do_not_mutate_internal_entries():
    queue = InstallQueue(FakeRunner())
    for i in range(queue.MAX_PENDING):
        queue.add(f"{i:x}")
    with pytest.raises(ValueError, match="full"):
        queue.add("ffff")
    queue.status()["pending"][0]["map_id"] = "bad"
    assert queue.status()["pending"][0]["map_id"] == "0"
    for bad in ["../a", "https://beatsaver.com/maps/a", "", "z", "a" * 13]:
        with pytest.raises(ValueError):
            queue.add(bad)
    with pytest.raises(ValueError):
        queue.remove("missing")


def test_atomic_snapshot_resets_cursor_and_preserves_large_job_ids():
    runner = SingleJobRunner()
    runner._job = Job(id=1793030351128670239, argv=[], cwd=".", started_at=0, lines=["old"])
    first = runner.snapshot(99, "")
    assert first["job"]["id"] == "1793030351128670239" and first["lines"] == ["old"]
    assert runner.snapshot(1, first["job"]["id"])["lines"] == []
    runner._job = Job(id=1793030351128670240, argv=[], cwd=".", started_at=0, lines=["new"])
    assert runner.snapshot(1, first["job"]["id"])["lines"] == ["new"]


def test_queue_routes_and_configuration_write_guard(monkeypatch):
    runner = SingleJobRunner()
    queue = InstallQueue(runner)
    monkeypatch.setattr(server, "INSTALL_QUEUE", queue)
    monkeypatch.setattr(server, "RUNNER", runner)
    monkeypatch.setattr(server, "_require_config", lambda: None)
    client = TestClient(server.app)
    assert client.post("/api/install-queue", json={"map_id": "12a", "title": "Fixture"}).status_code == 200
    assert client.get("/api/install-queue").json()["pending"][0]["title"] == "Fixture"
    assert client.post("/api/install-queue", json={"map_id": "12a"}).status_code == 400
    for path, method in [
        ("/api/orbis/settings", "post"),
        ("/api/orbis/plugin", "post"),
        ("/api/orbis/library/owned", "delete"),
        ("/api/config/save", "post"),
        ("/api/jobs/deploy", "post"),
    ]:
        assert client.request(method.upper(), path, json={} if method == "post" else None).status_code == 409
    assert client.post("/api/install-queue/pause").json()["paused"]
    assert client.post("/api/install-queue/clear").json()["pending"] == []
    assert client.post("/api/install-queue/start").status_code == 400
    assert client.post("/api/install-queue/start", headers={"Origin": "https://evil.example"}).status_code == 403


def test_cancel_route_pauses_queue_before_cancelling_runner(monkeypatch):
    queue = InstallQueue(FakeRunner())
    queue.add("abc")
    queue._paused = False
    monkeypatch.setattr(server, "INSTALL_QUEUE", queue)

    class Runner:
        def cancel(self):
            assert queue.status()["paused"]
            return True

    monkeypatch.setattr(server, "RUNNER", Runner())
    assert server.jobs_cancel() == {"ok": True}


def test_paused_pending_queue_blocks_test_map_removal_until_explicitly_cleared(monkeypatch):
    from companion_api import library

    fake = FakeRunner()
    queue = InstallQueue(fake)
    queue.add("55528", "Brainrot Giga Choir")
    monkeypatch.setattr(server, "INSTALL_QUEUE", queue)
    monkeypatch.setattr(server, "RUNNER", SingleJobRunner())
    calls = []
    test_id = "bsd_additive_e12f6738fd8db99e0add5c25"

    def remove(config, id):
        calls.append(id)
        return {"ok": True, "count": 0, "cleanup_pending": []}

    monkeypatch.setattr(library, "remove", remove)
    client = TestClient(server.app)
    response = client.delete("/api/orbis/library/" + test_id)
    assert response.status_code == 409
    assert "Finish or clear" in response.json()["detail"]
    assert queue.status()["paused"] and len(queue.status()["pending"]) == 1
    assert not calls and not fake.jobs
    assert client.post("/api/install-queue/clear").status_code == 200
    assert client.delete("/api/orbis/library/" + test_id).status_code == 200
    assert calls == [test_id] and not fake.jobs


def test_failed_install_is_retained_with_reason_and_next_map_runs():
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add("a", "Bad map")
    queue.add("b", "Good map")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    runner.jobs[0].lines = ["[additive] Import refused: invalid NJS"]
    runner.jobs[0].exit_code = 2
    wait_for(lambda: len(runner.jobs) == 2)
    assert not queue.status()["paused"]
    assert queue.status()["history"][0]["error"] == "Import refused: invalid NJS"
    runner.jobs[1].exit_code = 0
    wait_for(lambda: not queue.has_work())
    wait_for(lambda: queue.status()["paused"])
    assert [e["status"] for e in queue.status()["history"]] == ["complete", "failed"]
    assert queue.status()["error"] and "Retry" in queue.status()["message"]
    failed = queue.status()["history"][1]
    retry = queue.add(failed["map_id"], failed["title"])
    assert retry["id"] != failed["id"] and len(runner.jobs) == 2
    with pytest.raises(ValueError, match="already queued"):
        queue.add(failed["map_id"])
    queue.start()
    wait_for(lambda: len(runner.jobs) == 3)
    runner.jobs[2].exit_code = 0
    wait_for(lambda: not queue.has_work())


def test_launch_error_skips_only_affected_entry():
    class Runner(FakeRunner):
        def start(self, argv, label=""):
            if argv[argv.index("--download-beat-saver-song") + 1] == "a":
                raise OSError("cannot launch fixture")
            return super().start(argv, label)

    runner = Runner()
    queue = InstallQueue(runner)
    queue.add("a")
    queue.add("b")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    assert queue.status()["active"]["map_id"] == "b"
    assert queue.status()["history"][0]["map_id"] == "a"
    assert queue.status()["history"][0]["error"] == "cannot launch fixture"
    runner.jobs[0].exit_code = 0
    wait_for(lambda: not queue.has_work())


def test_manual_pause_still_wins_when_current_map_fails():
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add("a")
    queue.add("b")
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    queue.pause()
    runner.jobs[0].exit_code = 2
    wait_for(lambda: queue.status()["active"] is None)
    assert len(runner.jobs) == 1 and queue.status()["pending"][0]["map_id"] == "b"


def test_explicit_queue_handoff_preserves_order_history_and_never_autostarts():
    import copy

    runner = FakeRunner()
    old = InstallQueue(runner)
    old.add("b", "Second")
    old.add("a", "Third")
    old._history.append({"id": "123", "map_id": "f", "title": "Failed", "status": "failed", "error": "Refused"})
    snapshot = old.status()
    restored = InstallQueue(runner)
    restored.restore(snapshot)
    assert restored.status()["pending"] == snapshot["pending"]
    assert restored.status()["history"] == snapshot["history"]
    assert restored.status()["paused"] and not runner.jobs
    snapshot["pending"][0]["title"] = "changed"
    assert restored.status()["pending"][0]["title"] == "Second"
    with pytest.raises(ValueError, match="existing"):
        restored.restore(old.status())
    for field, value in [
        ("active", {"id": "x"}),
        ("paused", False),
        ("pending", [{}]),
        ("pending", old.status()["pending"] * 2),
        ("history", [{}]),
    ]:
        bad = copy.deepcopy(old.status())
        bad[field] = value
        target = InstallQueue(runner)
        with pytest.raises(ValueError):
            target.restore(bad)
        assert not target.has_work() and not runner.jobs
    assert restored._history.maxlen == 128


def test_full_64_map_batch_skips_failures_and_retains_all_results():
    class Runner(FakeRunner):
        def start(self, argv, label=""):
            job = super().start(argv, label)
            job.exit_code = 2 if len(self.jobs) % 4 == 0 else 0
            job.lines = ["[additive] Import refused: " + "x" * 2000]
            return job

    runner = Runner()
    queue = InstallQueue(runner)
    for i in range(64):
        queue.add(f"{i:x}", f"Fixture {i}")
    queue.start()
    wait_for(lambda: len(queue.status()["history"]) == 64 and queue.status()["paused"])
    results = queue.status()["history"]
    assert len(runner.jobs) == 64 and not queue.has_work()
    assert sum(e["status"] == "failed" for e in results) == 16
    assert sum(e["status"] == "complete" for e in results) == 48
    assert all(len(e.get("error", "")) <= 512 for e in results)
    assert queue.status()["error"]


def test_pyinstaller_wrapper_never_hides_real_failure_before_next_job():
    runner = FakeRunner()
    queue = InstallQueue(runner)
    queue.add('a', 'fixture')
    queue.start()
    wait_for(lambda: len(runner.jobs) == 1)
    runner.jobs[0].lines.extend(['Traceback (most recent call last):',
        'ValueError: actual map or connection reason',
        '[PYI-12345:ERROR] Failed to execute script entrypoint due to unhandled exception!'])
    runner.jobs[0].exit_code = 1
    wait_for(lambda: bool(queue.status()['history']))
    assert queue.status()['history'][0]['error'] == 'ValueError: actual map or connection reason'
