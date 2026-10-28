"""Private-loopback session/lifecycle adapter for the future frozen backend.

Does not launch a server, read user settings or connect to the PS4 on import.
A parent must bind its own 127.0.0.1:0 socket and pass the resulting exact origin.
"""

from __future__ import annotations

import secrets
import threading
from contextlib import contextmanager
from urllib.parse import urlsplit

from starlette.responses import JSONResponse, RedirectResponse

COOKIE = "orbeats_desktop_session"


class Session:
    def __init__(self, origin: str):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.port
            or parsed.path
            or parsed.query
            or parsed.fragment
            or origin != f"http://127.0.0.1:{parsed.port}"
        ):
            raise ValueError(
                "Desktop backend requires an exact private-loopback origin"
            )
        self.origin = origin
        self.host = parsed.netloc
        self._token = secrets.token_hex(32)
        self._bootstrap = secrets.token_hex(32)
        self._lock = threading.Lock()
        self._closing = False
        self._mutations = 0

    def readiness(self) -> dict:
        """Send ONLY through the owned parent's private stdout pipe, never a log."""
        return {
            "protocol": 1,
            "url": f"{self.origin}/_desktop/bootstrap/{self._bootstrap}",
        }

    def begin_shutdown(self) -> None:
        """Irreversible: block new mutations before pausing/waiting for active work."""
        with self._lock:
            self._closing = True

    def drained(self, *, runner_busy: bool, queue_active: bool) -> bool:
        with self._lock:
            return (
                self._closing
                and not self._mutations
                and not runner_busy
                and not queue_active
            )

    @contextmanager
    def mutation(self):
        with self._lock:
            accepted = not self._closing
            if accepted:
                self._mutations += 1
        try:
            yield accepted
        finally:
            if accepted:
                with self._lock:
                    self._mutations -= 1

    async def guard(self, request, call_next):
        if request.headers.get("host") != self.host:
            return JSONResponse({"detail": "Invalid desktop host"}, status_code=403)
        # A single-use bootstrap exchanges the pipe secret for an HttpOnly cookie.
        if request.url.path.startswith("/_desktop/bootstrap/"):
            supplied = request.url.path.removeprefix("/_desktop/bootstrap/")
            with self._lock:
                accepted = (
                    request.method == "GET"
                    and bool(self._bootstrap)
                    and secrets.compare_digest(supplied, self._bootstrap)
                    and not self._closing
                    and not request.url.query
                )
                if accepted:
                    self._bootstrap = ""
            if not accepted:
                return JSONResponse(
                    {"detail": "Invalid desktop bootstrap"}, status_code=403
                )
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(
                COOKIE, self._token, httponly=True, samesite="strict", path="/"
            )
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            return response
        if not secrets.compare_digest(request.cookies.get(COOKIE, ""), self._token):
            return JSONResponse({"detail": "Desktop session required"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin") != self.origin:
                return JSONResponse(
                    {"detail": "Invalid desktop origin"}, status_code=403
                )
            with self.mutation() as accepted:
                if not accepted:
                    return JSONResponse(
                        {"detail": "Finishing work before closing"}, status_code=423
                    )
                return await call_next(request)
        return await call_next(request)
