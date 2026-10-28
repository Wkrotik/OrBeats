"""
test_webapp_boot_wiring.py — EXECUTE the page's DOMContentLoaded wiring
under a quickjs DOM shim and assert every binding attaches.

Exp 283e motivation (the user's field report: "clicking this does nothing
that I can notice"): a SINGLE null-element or throw anywhere in the
DOMContentLoaded callback kills EVERY listener registered after it — the
page renders, but every later button is dead. The existing quickjs gate
only PARSES app.js; parsing cannot see this class. This test RUNS the
wiring with a minimal DOM and fails if any bound id is missing from
index.html or any statement throws.

No browser, no network: document/window/$/fetch are shimmed.
"""

from pathlib import Path

import pytest

quickjs = pytest.importorskip("quickjs", reason="quickjs not installed")

WEBAPP = Path(__file__).resolve().parents[1] / "webapp"
APP_JS = (WEBAPP / "static" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (WEBAPP / "static" / "index.html").read_text(encoding="utf-8")

SHIM = r"""
// ── minimal DOM shim: enough for app.js's wiring to RUN ──────────────
var __bound = [];        // every (id/event) actually bound
var __elements = {};     // id → fake element
function __el(id) {
  if (!__elements[id]) {
    __elements[id] = {
      id: id, value: "", checked: false, textContent: "", innerHTML: "",
      files: null, disabled: false, dataset: {}, className: "",
      addEventListener: function(ev, fn) { __bound.push(id + ":" + ev); },
      classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
      appendChild(){}, querySelector(sel){ return __el(id + "::qs::" + sel); },
      querySelectorAll(){ return []; }, iterdir(){ return []; },
      scrollIntoView(){}, click(){}, focus(){},
      on(){},
    };
  }
  return __elements[id];
}
var document = {
  getElementById: function(id) { return __el(id); },
  querySelectorAll: function(sel) { return []; },
  querySelector: function(sel) { return __el("__qs_" + sel); },
  createElement: function(tag) { return __el("__el_" + tag); },
  addEventListener: function(ev, fn) {
    if (ev === "DOMContentLoaded") { document.__domready = fn; }
  },
  body: { appendChild(){}, removeChild(){} },
};
var window = { location: { href: "" }, addEventListener(){}, open(){} };
var navigator = {};
var AbortSignal = { timeout: function(ms) { return {}; } };
var fetch = function(url, opts) {
  return Promise.reject(new Error("no network in the test shim"));
};
// boot()'s awaits reject harmlessly; the wiring proceeds synchronously.
"""


def _run_wiring():
    ctx = quickjs.Context()
    ctx.eval(SHIM)
    # EXECUTE app.js (NOT eval(repr(...)) — a repr'd program is just a string
    # literal whose value is discarded; the first version of this test did
    # exactly that and proved nothing. app.js's 'use strict' keeps its
    # declarations eval-scoped; the DOMContentLoaded callback is captured via
    # the shim's document object and its closure carries its scope.)
    ctx.eval(APP_JS)
    # Execute the page's wiring exactly as a browser would
    ctx.eval("document.__domready();")
    return ctx


class TestBootWiring:
    def test_domcontentloaded_wiring_completes_without_error(self):
        # Any throw in the callback kills every LATER binding — assert it
        # ran to completion by checking the LAST registered listener too.
        ctx = _run_wiring()
        bound = ctx.eval("JSON.stringify(__bound)")
        assert bound and "btn-deploy:click" in bound, \
            f"wiring incomplete — a statement before the Deploy binding threw. Bound: {bound[:400]}"
        assert "btn-bsage-testsong:click" in bound, \
            "the test-song button never bound — its click does nothing (the Exp 283e report)"

    def test_every_wired_id_exists_in_index_html(self):
        """Each id the wiring touches must exist in the real index.html —
        a null element anywhere in the chain kills the rest."""
        import re
        ctx = _run_wiring()
        bound = eval(ctx.eval("JSON.stringify(__bound)"))  # noqa: S307 (our own json)
        wired_ids = {b.split(":")[0] for b in bound}
        # dynamic element handles from createElement carry the __el_ prefix
        wired_ids = {i for i in wired_ids if not i.startswith("__el_")}
        html_ids = set(re.findall(r'id="([^"]+)"', INDEX_HTML))
        missing = sorted(wired_ids - html_ids)
        assert not missing, \
            f"app.js wires buttons whose ids are missing from index.html: {missing}"

    def test_bsage_testsong_button_present_with_handler(self):
        assert 'id="btn-bsage-testsong"' in INDEX_HTML
        assert "function useTestSong" in APP_JS
        # the label must NOT claim console state (Exp 283e: "already on the
        # console" was wrong for fresh users — a new install has nothing)
        button_html = INDEX_HTML[INDEX_HTML.index('id="btn-bsage-testsong"'):]
        button_html = button_html[:button_html.index("</button>")]
        assert "console" not in button_html.lower(), \
            f"the button must not reference console state: {button_html[:120]}"
