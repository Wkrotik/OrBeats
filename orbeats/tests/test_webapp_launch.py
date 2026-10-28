"""Resilient launcher tests (Exp 278h) — hermetic, no PS4.

The web app's launch flow must (user directives):
- identify what occupies the preferred port and PRESENT OPTIONS instead of
  dying with uvicorn's raw "[Errno 98] address already in use";
- take a smart default in non-interactive contexts (pytest's stdin is
  already non-tty, exercising that path);
- NEVER kill anything it cannot identify as its own web app;
- carry a suggested course of action ("To fix:") in EVERY error message.
"""
import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "webapp"))

import server  # noqa: E402


def _free_port() -> int:
    """A port number that is currently free (bound+closed to reserve it)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _PingHandler(BaseHTTPRequestHandler):
    """Mimics our /api/ping with a deliberately OLD webapp version (stale)."""

    def do_GET(self):
        if self.path == "/api/ping":
            body = json.dumps({
                "mode": "local-backend",
                "webapp_version": "0.0.1-test-stale",
                "pipeline_version": "9.9.9",
                "plugin_version": "vX-test",
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


class TestPortInUse:
    def test_free_port_reports_free(self):
        port = _free_port()
        assert server._port_in_use("127.0.0.1", port) is False

    def test_bound_port_reports_busy(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        port = s.getsockname()[1]
        try:
            assert server._port_in_use("127.0.0.1", port) is True
        finally:
            s.close()


class TestWhoIsOn:
    def test_identifies_our_webapp_with_versions(self):
        srv = HTTPServer(("127.0.0.1", 0), _PingHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            desc, ping = server._who_is_on("127.0.0.1", port)
            assert desc and "OrBeats web app 0.0.1-test-stale" in desc
            assert ping["webapp_version"] == "0.0.1-test-stale"
        finally:
            srv.shutdown()

    def test_non_webapp_listener_returns_none(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        port = s.getsockname()[1]
        try:
            desc, ping = server._who_is_on("127.0.0.1", port)
            assert desc is None and ping is None
        finally:
            s.close()


class TestNextFreePort:
    def test_finds_the_next_free_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        occupied = s.getsockname()[1]
        try:
            nxt = server._next_free_port("127.0.0.1", occupied)
            assert nxt > occupied
            assert not server._port_in_use("127.0.0.1", nxt)
        finally:
            s.close()

    def test_all_busy_error_carries_a_fix(self, monkeypatch):
        monkeypatch.setattr(server, "_port_in_use", lambda host, port: True)
        with pytest.raises(SystemExit) as ei:
            server._next_free_port("127.0.0.1", 8765, max_tries=2)
        msg = str(ei.value)
        assert "To fix:" in msg            # EVERY error carries a suggested action
        assert "--port" in msg             # ...and a concrete one


class TestResolveLaunchPort:
    """Non-interactive resolution (pytest's stdin is not a tty → the smart
    defaults run; _our_server_pids is pinned so the devcontainer's real
    processes never influence the tests)."""

    def test_free_port_uses_it_directly(self):
        port = _free_port()
        assert server._resolve_launch_port("127.0.0.1", port) == port

    def test_unknown_occupant_takes_next_port_and_never_kills(self, monkeypatch, capsys):
        monkeypatch.setattr(server, "_our_server_pids", lambda: [])
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        occupied = s.getsockname()[1]
        try:
            got = server._resolve_launch_port("127.0.0.1", occupied, open_browser=False)
            out = capsys.readouterr().out
            assert got != occupied                       # fresh instance on another port
            assert "unknown process" in out              # the occupant was identified as not ours
            assert "NOT be touched" in out               # and explicitly never killed
        finally:
            s.close()

    def test_stale_webapp_occupant_falls_back_when_port_never_frees(self, monkeypatch, capsys):
        # A stale instance of ours that "refuses" to die: the port stays bound by
        # our test socket after the (bogus-PID) kill attempt — the resolver must
        # warn with a fix suggestion and fall back to the next free port.
        monkeypatch.setattr(server, "_our_server_pids", lambda: [999999])
        monkeypatch.setattr(server, "_who_is_on",
                            lambda h, p: ("OrBeats web app 0.0.1 (stale)",
                                         {"mode": "local-backend",
                                          "webapp_version": "0.0.1"}))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        occupied = s.getsockname()[1]
        try:
            got = server._resolve_launch_port("127.0.0.1", occupied, open_browser=False)
            out = capsys.readouterr().out
            assert got != occupied
            assert "STALE" in out                       # staleness called out
            assert "To fix:" in out                     # error path carries the fix
            assert "falling back" in out                # and the automatic fallback
        finally:
            s.close()

    def test_current_webapp_occupant_defaults_to_reuse(self, monkeypatch, capsys):
        # A CURRENT instance of ours on the port → the smart default is to USE it
        # (SystemExit 0, nothing started); pytest's non-tty stdin takes the default.
        monkeypatch.setattr(server, "_our_server_pids", lambda: [])
        current = server._webapp_version()
        monkeypatch.setattr(server, "_who_is_on",
                            lambda h, p: (f"OrBeats web app {current}",
                                         {"mode": "local-backend",
                                          "webapp_version": current}))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(128)
        occupied = s.getsockname()[1]
        try:
            with pytest.raises(SystemExit) as ei:
                server._resolve_launch_port("127.0.0.1", occupied, open_browser=False)
            assert ei.value.code == 0
            out = capsys.readouterr().out
            assert "nothing new started" in out
            assert "— current." in out          # the state line says current (not STALE)
        finally:
            s.close()
