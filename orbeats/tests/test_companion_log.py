"""Log location and follow policy. Real DOM/scroll checks live in browser regression."""
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "webapp/static"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.items[values["id"]] = (tag, values, self.getpos())


def test_log_is_collapsed_accessible_and_before_every_queue_list():
    html = Elements()
    html.feed((STATIC / "companion.html").read_text())
    elements = html.items
    assert elements["job"][2] < elements["installation-log"][2] < elements["queue-list"][2] < elements["queue-history"][2]
    assert elements["toggle-log"][1]["aria-controls"] == "diagnostics"
    assert elements["toggle-log"][1]["aria-expanded"] == "false"
    assert "hidden" in elements["diagnostics"][1]
    assert elements["log"][1]["tabindex"] == "0"
    assert elements["log"][1]["aria-label"] == "Installation log"
    assert "hidden" in elements["log-latest"][1]


@pytest.mark.skipif(not shutil.which("node"), reason="Node needed for JS policy unit checks")
def test_log_follow_policy_and_raw_diagnostics_remain_independent():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8');
const elements=Object.fromEntries(['diagnostics','toggle-log','log-title','log-follow','log-latest','downloads','log','job-stage'].map(id=>[id,{textContent:'',hidden:false,open:true,scrollHeight:1000,scrollTop:0,attributes:{},setAttribute(k,v){this.attributes[k]=v}}]));
const frames=[];
const ctx={$:id=>elements[id],state:{logFollowing:true,logRunning:true,rawLog:''},requestAnimationFrame:f=>frames.push(f)};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function cleanLogLine('),source.indexOf('function updateQueueButtons(')),ctx);
ctx.updateLogControls();assert.equal(elements['log-title'].textContent,'Installation log');
ctx.logLines(['   Project: private-path','[additive] useful output <img onerror=bad>']);
assert.equal(ctx.state.rawLog,'   Project: private-path\n[additive] useful output <img onerror=bad>\n');
assert.equal(elements.log.textContent,'useful output <img onerror=bad>\n');
assert.equal(frames.length,1);frames.shift()();assert.equal(elements.log.scrollTop,1000);
ctx.state.logFollowing=false;elements.log.scrollTop=123;
ctx.logLines(['next output']);assert.equal(frames.length,0);assert.equal(elements.log.scrollTop,123);
ctx.setLogOpen(false);assert.equal(elements.diagnostics.hidden,true);assert.equal(ctx.state.logFollowing,false);
ctx.setLogOpen(true);assert.equal(frames.length,0);assert.equal(elements.log.scrollTop,123);
assert.equal(elements['log-latest'].hidden,false);assert.equal(elements['toggle-log'].attributes['aria-expanded'],'true');
ctx.state.logFollowing=true;ctx.followLogTail();ctx.state.logFollowing=false;
frames.shift()();assert.equal(elements.log.scrollTop,123,'scheduled frame stole scroll after reader paused');
ctx.state.logFollowing=true;elements.downloads.open=false;ctx.followLogTail();assert.equal(frames.length,0);
ctx.state.logRunning=false;ctx.updateLogControls();assert.equal(elements['log-title'].textContent,'Last installation log');
"""
    subprocess.run([shutil.which("node"), "-e", script, str(STATIC / "companion.js")], check=True, capture_output=True, text=True)
