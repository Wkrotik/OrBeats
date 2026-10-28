"""
test_webapp_ps4_adapter.py — banner-free FTP read transport tests.

The transport contract under test (KB: lftp-ftp-pitfalls; plan §9.4 inv 3):
- a banner BEFORE and/or AFTER the JSON never breaks parsing
  (Exp 240: trailing '}156 bytes transferred' broke every read in the field
  while passing on fast dev rigs)
- `get -o` into a mktemp -d dir (never mktemp — pitfall 2: get refuses clobber)
- failed reads return ok=False with an error — NEVER rendered as empty truth
- enable_plugin defaults TRUE when absent (the only flag that does — inv 5)

lftp is fully monkeypatched: NO test contacts a PS4 (hardware-gate pattern).
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import ps4  # noqa: E402

FEATURES_JSON = json.dumps({
    "features": {
        "enable_plugin": True,
        "enable_beatmap_mode_mapping": True,
        "enable_song_metadata_modification": False,
    }
})


class FakeLftp:
    """Configurable stand-in for _run_lftp: writes remote content to -o path.

    The real adapter issues `get <remote> -o <local>` as ONE command string,
    so parse it the way lftp would."""

    def __init__(self, remote_content: str, rc: int = 0, noise: str = ""):
        self.remote_content = remote_content
        self.rc = rc
        self.noise = noise
        self.calls: list[str] = []

    def __call__(self, host, user_part, port, commands, timeout=30):
        self.calls.append(commands[0])
        cmd = commands[0]
        if cmd.startswith("get ") and " -o " in cmd:
            local = cmd.split(" -o ", 1)[1].strip()
            Path(local).write_text(self.remote_content + self.noise, encoding="utf-8")
        return self.rc, self.noise


class TestFetchRemoteJson:
    def test_clean_json(self, monkeypatch):
        fake = FakeLftp(FEATURES_JSON)
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/features.json")
        assert res.ok and res.data["features"]["enable_plugin"] is True

    def test_trailing_banner_survives(self, monkeypatch):
        """Exp 240's exact field failure: '}156 bytes transferred' appended."""
        fake = FakeLftp(FEATURES_JSON, noise="156 bytes transferred\n")
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/features.json")
        assert res.ok, res.error
        assert res.data["features"]["enable_plugin"] is True

    def test_leading_banner_survives(self, monkeypatch):
        fake = FakeLftp(FEATURES_JSON,
                        noise="open: GetPass() failed -- assume anonymous login\n")
        # leading noise must be PREPENDED — FakeLftp appends; emulate by
        # passing the noise as part of content ordering
        fake.remote_content = "login banner chatter\n" + FEATURES_JSON
        fake.noise = ""
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/features.json")
        assert res.ok, res.error
        assert res.data["features"]["enable_plugin"] is True

    def test_both_side_banners_survive(self, monkeypatch):
        fake = FakeLftp("banner before\n" + FEATURES_JSON,
                        noise="}more banner after")
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/features.json")
        assert res.ok, res.error

    def test_read_failure_is_explicit_not_empty(self, monkeypatch):
        """rc!=0 → ok=False with error text. Never an empty-dict 'success'."""
        fake = FakeLftp("", rc=1, noise="get: access failed")
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/features.json")
        assert res.ok is False
        assert res.error
        assert res.data is None

    def test_retries_then_gives_up(self, monkeypatch):
        fake = FakeLftp("", rc=1, noise="get: access failed")
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/x", retries=3)
        assert res.ok is False
        assert len(fake.calls) == 3  # exactly the requested retries

    def test_zero_byte_file_is_failure_not_truth(self, monkeypatch):
        """0-byte remote file (half-written upload) must not parse as {}."""
        fake = FakeLftp("")
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        res = ps4.fetch_remote_json("/x")
        assert res.ok is False

    def test_transport_uses_temp_dir_not_mktemp(self, monkeypatch):
        """Pitfall 2: `get -o` refuses to clobber — the -o target must be a
        path inside a fresh TemporaryDirectory (never a pre-created file)."""
        fake = FakeLftp(FEATURES_JSON)
        monkeypatch.setattr(ps4, "_run_lftp", fake)
        ps4.fetch_remote_json("/x")
        get_cmd = fake.calls[0]
        assert " -o " in get_cmd
        target = Path(get_cmd.split(" -o ", 1)[1].strip())
        assert target.parent.name.startswith("tmp")  # mktemp -d pattern
        assert target.name == "f"


class TestExtractJsonObject:
    def test_plain(self):
        assert ps4._extract_json_object('{"a": 1}') == {"a": 1}

    def test_bannered(self):
        assert ps4._extract_json_object('noise {"a": 1} tail') == {"a": 1}

    def test_no_brace(self):
        assert ps4._extract_json_object("nothing") is None

    def test_broken_json(self):
        assert ps4._extract_json_object("{broken") is None


class TestFeatureDefaults:
    def test_fresh_install_defaults_all_on_when_absent(self, monkeypatch):
        """Exp 281 (user directive): ALL flags default ON when the live file
        omits them — a fresh install works out of the box. The kill switch
        stays the master off; users turn individual features off explicitly."""
        raw = json.dumps({"features": {"enable_beatmap_mode_mapping": True}})
        monkeypatch.setattr(ps4, "_run_lftp", FakeLftp(raw))
        res = ps4.read_features()
        assert res.ok
        for flag in ("enable_plugin", "enable_custom_song_replacements",
                     "enable_song_metadata_modification",
                     "enable_beatmap_mode_mapping", "enable_song_previews",
                     "enable_in_game_plugin_toggle",
                     "enable_game_data_extractor"):
            assert res.data.get(flag) is True, \
                f"{flag} must default ON when absent (fresh install)"

    def test_explicit_false_stays_false(self, monkeypatch):
        raw = json.dumps({"features": {"enable_plugin": False}})
        monkeypatch.setattr(ps4, "_run_lftp", FakeLftp(raw))
        res = ps4.read_features()
        assert res.data["enable_plugin"] is False

    def test_flat_format_supported(self, monkeypatch):
        """Some plugin versions write {flag: bool} without the 'features' key."""
        monkeypatch.setattr(ps4, "_run_lftp", FakeLftp(
            json.dumps({"enable_plugin": True})))
        res = ps4.read_features()
        assert res.ok and res.data["enable_plugin"] is True


class TestRedirectsSummary:
    def test_summary_counts(self, monkeypatch):
        raw = json.dumps({"redirects": {
            "BeatmapLevelsData/BadGuy": "BadGuy_v3.bundle",
            "BeatmapLevelsData/Oxytocin": "Oxytocin_v3.bundle",
            "lizzo_pack_assets_all_deadbeef.bundle": "lizzo_patched.bundle",
            "aa/catalog.json": "catalog_pack_modes.json",
        }})
        monkeypatch.setattr(ps4, "_run_lftp", FakeLftp(raw))
        res = ps4.read_redirects_summary()
        assert res.ok
        assert res.data["song_count"] == 2
        assert res.data["pack_count"] == 1
        assert res.data["catalog_redirect_present"] is True


class TestAbsentFileIsCleanSlate:
    """Exp 280d (user report): after Clear PS4, every state read showed as an
    ERROR ("Access failed: 550 … File unavailable") when the console was in
    the CORRECT clean-slate state. A decisive 550 is a valid answer:
    ok=True + data=None — only genuine failures (connectivity, parse) are
    ok=False. The state payload reports absent sections + clean_slate=True."""

    def test_550_classified_as_absent_not_error(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        def fake_lftp(host, user_part, port, commands, timeout=30):
            return 1, ("get: Access failed: 550 Requested action not taken. "
                       "File unavailable. (/data/GoldHEN/AFR/CUSA12878/redirects.json)")
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/redirects.json")
        assert res.ok is True, "550 (file absent) is the clean-slate state, not an error"
        assert res.data is None
        assert res.error == ""

    def test_connection_refused_still_an_error(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        def fake_lftp(host, user_part, port, commands, timeout=30):
            return 1, "get: Connection refused"
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.fetch_remote_json("/data/GoldHEN/AFR/CUSA12878/redirects.json")
        assert res.ok is False, "a dead host is still an error"
        assert res.error

    def test_list_afr_absent_dir_is_clean_slate(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        def fake_lftp(host, user_part, port, commands, timeout=30):
            return 1, "ls: Access failed: 550 Requested action not taken. " \
                      "File unavailable. (/data/GoldHEN/AFR/CUSA12878)"
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.list_afr_dir()
        assert res.ok is True, "an absent AFR dir is the clean-slate state"
        assert res.data["count"] == 0 and res.data.get("absent") is True


class TestAbsentFlagSurvivesDataTransformation:
    """Exp 280e: the state endpoint's clean_slate never fired for
    redirects/features because the READERS transform data=None into empty
    counts/defaults before the endpoint saw it. The absent flag must ride
    ON the ReadResult (surviving transformation), not be inferred from data."""

    def test_redirects_summary_carries_absent(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        def fake_lftp(host, user_part, port, commands, timeout=30):
            return 1, ("get: Access failed: 550 Requested action not taken. "
                       "File unavailable. (redirects.json)")
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.read_redirects_summary()
        assert res.ok is True
        assert res.absent is True, "the absent flag must survive the data transformation"
        assert res.data["total"] == 0  # the summary shape still renders

    def test_features_read_carries_absent(self, monkeypatch):
        from adapters import ps4 as ps4_mod
        def fake_lftp(host, user_part, port, commands, timeout=30):
            return 1, ("get: 550 File unavailable. (features.json)")
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.read_features()
        assert res.ok is True and res.absent is True

    def test_present_file_absent_false(self, monkeypatch, tmp_path):
        from adapters import ps4 as ps4_mod
        local = tmp_path / "f.json"
        local.write_text('{"redirects": {"BeatmapLevelsData/x": "x_v3.bundle"}}')
        def fake_lftp(host, user_part, port, commands, timeout=30):
            # simulate the get writing our local temp — copy from a fixed file
            import shutil
            for cmd in commands:
                if cmd.startswith("get ") and "-o " in cmd:
                    dst = cmd.split("-o ")[1].strip().strip('"')
                    shutil.copy(local, dst)
            return 0, ""
        monkeypatch.setattr(ps4_mod, "_run_lftp", fake_lftp)
        res = ps4_mod.read_redirects_summary()
        assert res.ok is True and res.absent is False
        assert res.data["song_count"] == 1
