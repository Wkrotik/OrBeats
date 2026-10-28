"""Exp 263 — redirect healing must never rewrite a value that names a real
PS4 file (the case-collision dangle found by validating
v0.8047-pipeline-0.5354-webapp-0.6.0-alpha01 against the live console).

Exact live scenario, reproduced from the pre-validation backup: a single-song
--deploy-full against a PS4 carrying mixed-case bundle filenames
(MessItUp_v3.bundle) with the DEFAULT config (whose mass_deploy.slots spells
the Rolling Stones slots lowercase) "healed" 11 healthy values to lowercase
without re-uploading those slots — dangling redirects the post-deploy check
correctly failed. The fix: _ensure_mass_song_redirects takes the live AFR
listing; existing values that resolve on-disk are kept verbatim; dangling
values heal toward the case variant that exists.
"""

import importlib.util
import json
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parent.parent / "tools" / "full_custom_song_pipeline.py"


def _load_pipeline():
    spec = importlib.util.spec_from_file_location("fcsp_exp263", PIPELINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def f():
    return _load_pipeline()


DEFAULT_CFG = None  # loaded lazily per test (pipeline loads pure defaults)


@pytest.fixture()
def default_cfg(f):
    # No config file → the pipeline's built-in defaults: mass_deploy.slots
    # includes the Rolling Stones slots spelled lowercase ('messitup').
    return f.load_config(str(Path(__file__).parent / "no-such-config.json"))


# The live AFR state at validation time (the case variants that existed):
LIVE_AFR = {
    "MessItUp_v3.bundle": 34_665_613,
    "Angry_v3.bundle": 39_474_212,
    "angry_v3.bundle": 39_473_985,          # both variants on disk (dual-era upload)
    "StartMeUp_v3.bundle": 43_468_403,
    "startmeup_v3.bundle": 43_468_407,
    "Oxytocin_v3.bundle": 36_706_086,
    "Crystallized_v3.bundle": 30_000_000,
    # ... other slots mixed-case only
}

# The live redirects at validation time (pre-validation backup, mixed-case values)
LIVE_REDIRECTS = {
    "titleId": "CUSA12878",
    "afrBase": "/data/GoldHEN/AFR",
    "redirects": {
        "BeatmapLevelsData/MessItUp": "MessItUp_v3.bundle",
        "BeatmapLevelsData/Angry": "Angry_v3.bundle",
        "BeatmapLevelsData/StartMeUp": "StartMeUp_v3.bundle",
        "BeatmapLevelsData/Oxytocin": "Oxytocin_v3.bundle",
        "BeatmapLevelsData/Crystallized": "Crystallized_v3.bundle",
        "aa/catalog.json": "catalog_pack_modes.json",
    },
}


def _data():
    return json.loads(json.dumps(LIVE_REDIRECTS))  # deep copy per test


class TestCaseCollisionGuard:
    """The Exp 263 fix: healthy values are never rewritten by config-casing."""

    def test_live_bug_reproduced_without_fix(self, f, default_cfg, monkeypatch):
        """RED check (pre-fix behavior): remote_files=None rewrites values to
        the config's lowercase spellings — the exact live wipe. This test
        documents WHY remote_files must be passed; the next ones pin the fix."""
        data = _data()
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized"],
            remote_files=None)
        redirects = data["redirects"]
        assert redirects["BeatmapLevelsData/MessItUp"] == "messitup_v3.bundle"
        assert changed > 0

    def test_healthy_values_kept_verbatim(self, f, default_cfg):
        """With the live listing, every value that names an existing file is
        untouched — zero healthy entries rewritten, exactly what failed live."""
        data = _data()
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized"],
            remote_files=dict(LIVE_AFR))
        redirects = data["redirects"]
        assert redirects["BeatmapLevelsData/MessItUp"] == "MessItUp_v3.bundle"
        assert redirects["BeatmapLevelsData/Angry"] == "Angry_v3.bundle"
        assert redirects["BeatmapLevelsData/StartMeUp"] == "StartMeUp_v3.bundle"
        assert redirects["BeatmapLevelsData/Oxytocin"] == "Oxytocin_v3.bundle"
        assert changed == 0

    def test_dangling_value_heals_toward_on_disk_variant(self, f, default_cfg):
        """A value that dangles at its exact case heals toward the case
        variant that EXISTS on disk — never deeper into config casing."""
        data = _data()
        data["redirects"]["BeatmapLevelsData/MessItUp"] = "MESSITUP_v3.bundle"  # not on disk
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized"],
            remote_files=dict(LIVE_AFR))
        assert data["redirects"]["BeatmapLevelsData/MessItUp"] == "MessItUp_v3.bundle"
        assert changed == 1

    def test_dangling_with_no_disk_variant_falls_back_to_config(self, f, default_cfg):
        """Slot deployed nowhere (no case variant on disk at all): the config
        spelling wins — the value this session is about to upload under."""
        data = _data()
        data["redirects"]["BeatmapLevelsData/MessItUp"] = "messitup_v3.bundle"  # not on disk
        remote = {k: v for k, v in LIVE_AFR.items() if "essItUp" not in k and "essitup" not in k}
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized"],
            remote_files=remote)
        assert data["redirects"]["BeatmapLevelsData/MessItUp"] == "messitup_v3.bundle"
        assert changed == 0  # already the config value

    def test_pre_bundle_stale_value_still_healed(self, f, default_cfg):
        """The original healing purpose is intact: stale pre-.bundle values
        (value `Crystallized_v3` while the file is `Crystallized_v3.bundle`)
        still get fixed even with remote_files present."""
        data = _data()
        data["redirects"]["BeatmapLevelsData/Crystallized"] = "Crystallized_v3"  # pre-.bundle stale
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized"],
            remote_files=dict(LIVE_AFR))
        assert data["redirects"]["BeatmapLevelsData/Crystallized"] == "crystallized_v3.bundle"
        assert changed == 1

    def test_manage_redirect_config_passes_listing_on_deploy(self, f, default_cfg, monkeypatch, tmp_path):
        """manage_redirect_config(deploy=True) must fetch the live listing and
        hand it to the healing (the wiring, not just the math).

        HERMETIC (Exp 263 lesson): the deploy branch RESYNCS the local
        redirects.json from the live state — point _get_redirect_config_path
        at a tmp file so the fixture never leaks into the working copy (this
        exact test overwrote the real file with its 6-entry fixture on the
        first run; the env-dependent pack-mode tests caught it by failing).
        """
        seen_remote = {}
        local_file = tmp_path / "redirects.json"
        local_file.write_text(json.dumps(_data()))

        def fake_ensure(redirect_data, config, slots=None, remote_files=None):
            seen_remote["value"] = remote_files
            return 0

        def fake_listing(cfg):
            return {"MessItUp_v3.bundle": 1}

        monkeypatch.setattr(f, "_ensure_mass_song_redirects", fake_ensure)
        monkeypatch.setattr(f, "_list_remote_dir", fake_listing)
        # deploy path: stub the actual upload so no real PS4 write happens
        monkeypatch.setattr(f, "_deploy_redirect_to_ps4", lambda cfg: None)
        # local path → tmp (the resync must not touch the working copy)
        monkeypatch.setattr(f, "_get_redirect_config_path", lambda: str(local_file))
        # live download succeeds with the live-like state (so the deploy
        # branch's stale-local resync path runs instead of the Exp 246 abort)
        monkeypatch.setattr(f, "_download_redirect_from_ps4",
                            lambda cfg: _data())
        f.manage_redirect_config(default_cfg, target_name=None, generate=True,
                                 deploy=True, slots=["MessItUp"])
        assert seen_remote.get("value") == {"MessItUp_v3.bundle": 1}

    def test_new_target_still_gets_config_name(self, f, default_cfg):
        """A brand-new song redirect for a slot deployed NOW uses the config
        spelling for BOTH key and value (the name this session uploads under)
        — the guard only protects pre-existing values."""
        data = _data()
        changed = f._ensure_mass_song_redirects(
            data, default_cfg, slots=["MessItUp", "Angry", "StartMeUp",
                                      "Oxytocin", "Crystallized", "GimmeShelter"],
            remote_files=dict(LIVE_AFR))
        # GimmeShelter not previously redirected → added with config spelling
        # for key AND value (this session's upload will use exactly this name)
        assert data["redirects"]["BeatmapLevelsData/gimmeshelter"] == "gimmeshelter_v3.bundle"
        assert changed == 1
