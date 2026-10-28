"""Executable pure UI metadata regressions; no console or external API access."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_discovery_metadata_helpers():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for executable UI checks")
    source = (ROOT / "webapp/static/companion.js").read_text()
    helpers = source[:source.index("const state =")] + source[source.index("const number ="):source.index("function mediaURL")] + source[source.index("function relativeDate"):source.index("function positionNotice")] + source[source.index("function compatibility(map)"):source.index("function card(map")]
    program = r'''
const vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({});vm.runInContext(JSON.parse(process.argv[1]),ctx);
vm.runInContext(`
const chart={characteristic:'Standard',difficulty:'Expert',ne:false,me:false,chroma:false,cinema:false};
const map=(diffs)=>({versions:[{diffs}]});
if(compatibility(map([chart])).status!=='likely')throw Error('Expected vanilla metadata hint');
for(const flag of ['ne','me','chroma','cinema']){
 if(compatibility(map([{...chart,[flag]:true}])).status!=='unsupported')throw Error(flag);
}
if(compatibility(map([chart,{...chart,ne:true}])).status!=='unsupported')throw Error('Mixed pack must fail');
if(compatibility(map([{...chart,characteristic:'OneSaber'}])).status!=='likely')throw Error('OneSaber');
if(compatibility(map([{...chart,characteristic:'360Degree'}])).status!=='likely')throw Error('Rotation');
if(compatibility(map([{...chart,requirements:['Unknown mod']}])).status!=='unsupported')throw Error('Requirements');
for(const data of [{},map([]),map([{}]),map([null]),map([{...chart,ne:undefined}])]){
 if(compatibility(data).status!=='unknown')throw Error('Missing metadata must not be a green guarantee');
}
if(!compatibility(map([chart])).reason.includes('not a compatibility guarantee'))throw Error('Overclaim');
const malicious=compatibilityBadge(map([{...chart,characteristic:'<img src=x>'}]));
if(malicious.includes('title="<img'))throw Error('Unescaped reason');
if(!rating({score:.96,upvotes:999,downvotes:1}).includes('1,000 votes'))throw Error('Vote count');
if(!rating({score:.96,upvotes:1,downvotes:0}).includes('1 vote'))throw Error('Low sample');
if(!rating({score:.5,upvotes:0,downvotes:0}).includes('♡ — · 0 votes'))throw Error('No votes');
if(!rating({score:.96}).includes('— votes'))throw Error('Missing votes');
if(rating({score:.96,upvotes:1,downvotes:0}).includes('Few')||rating({score:.96,upvotes:1,downvotes:0}).includes('<small>'))throw Error('No extra rating labels');
if(votes({upvotes:-1,downvotes:0})!==null||votes({upvotes:'1',downvotes:0})!==null)throw Error('Invalid votes');
if(number(null)!=='—'||number(undefined)!=='—'||number(0)!=='0')throw Error('Do not invent zeros');
const now=Date.parse('2026-10-26T12:00:00Z'), ago=(days)=>new Date(now-days*86400000).toISOString();
for(const [days,expected] of [[0,'Today'],[1,'Yesterday'],[3,'3 days ago'],[7,'1 week ago'],[22,'3 weeks ago'],[30,'1 month ago'],[250,'8 months ago'],[366,'1 year ago'],[800,'2 years ago']]){
 if(relativeDate(ago(days),now)!==expected)throw Error('Relative date '+days+': '+relativeDate(ago(days),now));
}
if(relativeDate('invalid',now)!=='Unknown upload date')throw Error('Missing time');
`,ctx);
console.log('metadata presentation verified');
'''
    result = subprocess.run([node, "-e", program, json.dumps(helpers)], text=True, capture_output=True, check=True)
    assert "metadata presentation verified" in result.stdout


def test_no_placeholder_play_download_metrics_or_default_checkboxes():
    source = (ROOT / "webapp/static/companion.js").read_text()
    assert "stats.downloads" not in source
    assert "stats.plays" not in source
    assert "data-select-song" not in source
    assert 'editingSelection: false' in source
    assert 'data-song-tile=' in source
    assert '" ", "Enter"' in source
    assert 'aria-checked' in source
