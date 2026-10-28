"""Desktop prototype: no real listener, subprocess, credentials or console calls."""
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

path = Path(__file__).resolve().parents[2] / "desktop/backend/session.py"
spec = importlib.util.spec_from_file_location("desktop_session", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Session = module.Session
ORIGIN = "http://127.0.0.1:18765"


@pytest.fixture
def fixture():
    session = Session(ORIGIN)
    app = FastAPI()
    app.middleware("http")(session.guard)
    calls = []

    @app.get("/")
    def home():
        return {"ok": True}

    @app.post("/mutate")
    def mutate():
        calls.append(True)
        return {"ok": True}

    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield session, client, calls


def bootstrap(session, client):
    ready = session.readiness()
    assert ready["protocol"] == 1
    response = client.get(ready["url"])
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    return response


@pytest.mark.parametrize("origin", [
    "http://localhost:8765", "http://0.0.0.0:8765", "https://127.0.0.1:8765",
    "http://127.0.0.1", "http://127.0.0.1:8765/", "http://127.0.0.1:8765/?x=1",
    "http://user@127.0.0.1:8765", "http://127.0.0.1:8765#token", "http://[::1]:8765",
])
def test_exact_loopback_only(origin):
    with pytest.raises(ValueError):
        Session(origin)


def test_unknown_clients_cannot_read_or_mutate(fixture):
    _, client, calls = fixture
    assert client.get("/").status_code == 403
    assert client.post("/mutate", headers={"Origin": ORIGIN}).status_code == 403
    assert not calls


def test_one_time_bootstrap_cookie_is_private(fixture):
    session, client, _ = fixture
    ready = session.readiness()
    response = bootstrap(session, client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/").json() == {"ok": True}
    assert client.get(ready["url"]).status_code == 403


def test_foreign_host_or_origin_never_reaches_handler(fixture):
    session, client, calls = fixture
    bootstrap(session, client)
    for headers in ({}, {"Origin": "https://attacker.example"}, {"Origin": "null"},
                    {"Origin": ORIGIN, "Host": "attacker.example"},
                    {"Origin": ORIGIN, "Host": "127.0.0.1:8765"}):
        assert client.post("/mutate", headers=headers).status_code == 403
    assert not calls
    assert client.post("/mutate", headers={"Origin": ORIGIN}).status_code == 200
    assert calls == [True]


def test_sessions_cannot_authenticate_each_other(fixture):
    session, client, _ = fixture
    bootstrap(session, client)
    second = Session(ORIGIN)
    app = FastAPI()
    app.middleware("http")(second.guard)
    with TestClient(app, base_url=ORIGIN) as other:
        other.cookies.update(client.cookies)
        assert other.get("/").status_code == 403


def test_bootstrap_wrong_method_query_or_secret(fixture):
    session, client, calls = fixture
    url = session.readiness()["url"]
    assert client.post(url).status_code == 403
    assert client.get(url + "?x=1").status_code == 403
    assert client.get(url[:-2] + "xx").status_code == 403
    bootstrap(session, client)
    assert not calls


def test_closing_prevents_new_writes_but_keeps_status_readable(fixture):
    session, client, calls = fixture
    bootstrap(session, client)
    session.begin_shutdown()
    assert client.post("/mutate", headers={"Origin": ORIGIN}).status_code == 423
    assert client.get("/").status_code == 200
    assert not calls
    assert session.drained(runner_busy=False, queue_active=False)
    assert not session.drained(runner_busy=True, queue_active=False)
    assert not session.drained(runner_busy=False, queue_active=True)


def test_close_waits_for_in_flight_mutation_and_releases_on_exception():
    session = Session(ORIGIN)
    assert not session.drained(runner_busy=False, queue_active=False)
    with pytest.raises(RuntimeError), session.mutation() as accepted:
        assert accepted
        session.begin_shutdown()
        assert not session.drained(runner_busy=False, queue_active=False)
        with session.mutation() as newer:
            assert not newer
        raise RuntimeError("handler failed")
    assert session.drained(runner_busy=False, queue_active=False)


def test_closing_before_bootstrap_never_opens_a_session(fixture):
    session, client, _ = fixture
    ready = session.readiness()
    session.begin_shutdown()
    assert client.get(ready["url"]).status_code == 403
