"""
test_webapp_js_syntax.py — app.js must PARSE (quickjs full-syntax check).

Exp 283 finding: the web app's JS had NO syntax gate — a template-literal
typo (missing `)`) and a lexical redefinition both slipped through every
existing test (Python tests can't parse JS). quickjs parses with FULL
modern syntax (??, ?., optional catch binding — esprima-era parsers choke
on the pre-existing, valid code and hide real bugs behind false ones).

This catches the class of breakage where the page loads but every click is
dead: the browser refuses to run the whole script on ANY syntax error.
"""

from pathlib import Path

import pytest

quickjs = pytest.importorskip("quickjs", reason="quickjs not installed")

WEBAPP = Path(__file__).resolve().parents[1] / "webapp"


def test_app_js_parses():
    ctx = quickjs.Context()
    src = (WEBAPP / "static" / "app.js").read_text(encoding="utf-8")
    try:
        # new Function(body) parses WITHOUT executing (no DOM needed)
        ctx.eval(f"new Function({src!r})")
    except quickjs.JSException as e:
        pytest.fail(f"app.js has a syntax error (the browser would run NOTHING):\n{e}")


def test_index_html_ids_exist_for_js():
    """Every $(\"id\") lookup in app.js must exist in index.html — a missing
    element kills that flow at runtime (the M13 wiring relies on ~20 new
    ids; this pins the contract between the two files)."""
    import re
    js = (WEBAPP / "static" / "app.js").read_text(encoding="utf-8")
    html = (WEBAPP / "static" / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', js))
    # dynamically-built ids are looked up via template strings — skip those
    # (they are covered by their static call sites)
    dynamic_skips = {"deploy-log", "bs-results", "bs-mapid-result", "opt-audio",
                    "opt-v3", "opt-skip-plugin", "opt-pad", "opt-songname",
                    "opt-artist", "deploy-pack", "deploy-slot"}
    defined = set(re.findall(r'id="([A-Za-z0-9_-]+)"', html))
    missing = sorted(used - defined - dynamic_skips)
    assert not missing, f"app.js references ids missing from index.html: {missing}"
