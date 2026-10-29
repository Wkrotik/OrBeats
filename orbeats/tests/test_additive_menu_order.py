"""Exp309 UI cleanup; no console/network and no claims about hardware proof."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_first_position_is_only_for_independent_ids_with_stock_proof_last():
    header = (ROOT / "include/additive_song_packs.h").read_text()
    assert "const bool custom_first = custom_level_id != NULL;" in header
    assert "const size_t stock_begin = custom_first ? 1 : 0;" in header
    assert "const size_t custom_index = custom_first ? 0 : old_count;" in header
    assert "dst + stock_begin + n, src[n]" in header
    assert "if (verify[stock_begin + n] != src[n])" in header
    assert "if (verify[custom_index] != pack)" in header
    # Pack identity/display name is not a punctuation-based sorting workaround.
    assert 'kPackName[] = "OrBeats"' in header
    assert 'kPackId[] = "bsd_additive_stock_proof_v1"' in header


def test_no_extra_ui_hook_or_stock_field_changes_for_pack_position():
    source = (ROOT / "src/main.cpp").read_text()
    assert '"SetupBeatmapLevelPacks"' not in source
    assert '"ShowPacksInSecondChildController"' not in source
    header = (ROOT / "include/additive_song_packs.h").read_text()
    assert "field_set_value(source," not in header
    assert "field_set_value(level," not in header
    assert "read_ref(a, model, mf[i]) != prepared[i]" in header


@pytest.mark.parametrize("on", [True, False])
def test_notification_simulator_executes_without_feature_scoreboard(on):
    node = shutil.which("node")
    if not node:
        pytest.skip("node required for executable notification simulator checks")
    script = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const source = fs.readFileSync(process.argv[1], "utf8");
const code = source.slice(source.indexOf("const TOAST_VERSION ="),
                          source.indexOf("async function flagsRefresh()"));
const on = process.argv[2] === "true";
const checks = ["enable_plugin", "enable_additive_song_packs",
                "enable_game_data_extractor", "enable_song_previews"].map((flag, i) =>
  ({dataset: {flag}, checked: i === 0 ? on : i === 1}));
const elements = {
  "flags-list": {querySelectorAll: () => checks},
  "toast-title": {}, "toast-status": {}, "toast-note": {}
};
const context = { $: id => { assert(id in elements, "stale DOM id: " + id); return elements[id]; } };
vm.createContext(context); vm.runInContext(code, context); context.updateToastSim();
assert.strictEqual(elements["toast-title"].textContent, `OrBeats v0.8079${on ? "" : " — disabled"}`);
assert.strictEqual(elements["toast-status"].textContent, on ? "" : "(official songs only)");
assert.strictEqual(elements["toast-status"].hidden, on);
assert(!JSON.stringify(elements).includes("features ON"));
// Flipping irrelevant flags must not alter notification content.
checks[2].checked = !checks[2].checked; checks[3].checked = !checks[3].checked;
const before = elements["toast-title"].textContent;
context.updateToastSim(); assert.strictEqual(elements["toast-title"].textContent, before);
// No flags loaded yet: must not overwrite the placeholder or touch missing state.
checks.length = 0; context.updateToastSim();
assert.strictEqual(elements["toast-title"].textContent, before);
console.log("count-free ON/OFF notification matches DOM");
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "webapp/static/app.js"),
                             str(on).lower()], capture_output=True, text=True, check=True)
    assert "count-free ON/OFF notification matches DOM" in result.stdout


def test_boot_toast_and_web_placeholder_have_credits_but_no_counter():
    source = (ROOT / "src/main.cpp").read_text()
    js = (ROOT / "webapp/static/app.js").read_text()
    html = (ROOT / "webapp/static/index.html").read_text()
    for text in [source, js, html]:
        assert " features ON)" not in text
        assert 'Wkrotik' in text
    assert "enabled_count" not in source
    assert "FEATURE_FLAG_KEYS" not in js
    assert "toast-count" not in html + js
    assert 'id="toast-status" hidden' in html
    assert 'OrBeats v0.8079' in html
    assert (ROOT / "webapp/VERSION").read_text().strip() == "0.7.29"
