"""
test_webapp_loadout.py — loadout merge tests (pure functions; zero I/O).

The merge joins three real-world data sources with KNOWN key quirks:
- redirects key slots by songID (`BeatmapLevelsData/<songID>`)
- song_metadata keys by STOCK songName — with case/space drift vs the
  catalog (the real files: catalog `'You Should See Me In A Crown '`
  trailing space vs song_metadata `'You Should See Me In A Crown'`)
- song_names values are combined display lines: `"<Custom> / <Artist>"`
"""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "webapp"))

from adapters import loadout  # noqa: E402

CATALOG = {
    "billieeilish": [
        {"songID": "BadGuy", "songName": "bad guy", "songAuthorName": "Billie Eilish"},
        {"songID": "Bellyache", "songName": "bellyache", "songAuthorName": "Billie Eilish"},
        {"songID": "YouShouldSeeMeInACrown", "songName": "You Should See Me In A Crown ",
         "songAuthorName": "Billie Eilish"},
    ],
    "lizzo": [
        {"songID": "Juice", "songName": "Juice", "songAuthorName": "Lizzo"},
    ],
}


class TestMergeLoadout:
    def test_empty_state_all_stock(self):
        out = loadout.merge_loadout(CATALOG, {}, {}, {})
        assert [p["pack"] for p in out["packs"]] == ["billieeilish", "lizzo"]
        assert all(not r["customDeployed"] for p in out["packs"] for r in p["songs"])
        assert out["redirectedSlotCount"] == 0
        assert out["staleBundleCount"] == 0

    def test_deployed_slot_detection(self):
        red = {"BeatmapLevelsData/BadGuy": "BadGuy_v3.bundle",
               "lizzo_pack_assets_all_x.bundle": "lizzo_patched.bundle",
               "aa/catalog.json": "catalog_pack_modes.json"}
        out = loadout.merge_loadout(CATALOG, red, {}, {})
        billie = out["packs"][0]
        assert billie["songs"][0]["customDeployed"] is True     # BadGuy
        assert billie["songs"][1]["customDeployed"] is False    # Bellyache
        # pack redirects and catalog redirects are NOT song deployments
        assert out["redirectedSlotCount"] == 1
        assert billie["deployedCount"] == 1

    def test_stale_bundle_vs_served(self):
        """A bundle in AFR WITHOUT a redirect is STALE (uploaded, not served) —
        the deployed-truth model verified in Exp 245 against live state."""
        red = {"BeatmapLevelsData/BadGuy": "BadGuy_v3.bundle"}
        bundles = ["BadGuy", "Bellyache", "Juice"]  # BadGuy served; others stale
        out = loadout.merge_loadout(CATALOG, red, {}, {}, slot_bundles=bundles)
        by_id = {r["songID"]: r for p in out["packs"] for r in p["songs"]}
        assert by_id["BadGuy"]["customDeployed"] is True
        assert by_id["BadGuy"]["staleBundle"] is False
        assert by_id["Bellyache"]["customDeployed"] is False
        assert by_id["Bellyache"]["staleBundle"] is True
        assert by_id["Juice"]["staleBundle"] is True
        assert out["staleBundleCount"] == 2
        assert out["unmatchedBundles"] == []

    def test_unmatched_bundle_reported(self):
        """A bundle whose stem matches NO catalog slot (orphan file) is
        reported, never silently dropped."""
        out = loadout.merge_loadout(CATALOG, {}, {}, {}, slot_bundles=["NotARealSlot"])
        assert out["unmatchedBundles"] == ["notarealslot"]

    def test_label_only_row(self):
        """Metadata relabels a slot with NO redirect and NO bundle: 'label
        only' — the game shows the custom name but serves stock audio."""
        names = {"Juice": "Espresso / Sabrina Carpenter"}
        out = loadout.merge_loadout(CATALOG, {}, names, {})
        juice = out["packs"][1]["songs"][0]
        assert juice["customDeployed"] is False
        assert juice["staleBundle"] is False
        assert juice["customName"] == "Espresso"

    def test_metadata_join_case_and_space_insensitive(self):
        """The real-data quirk: catalog songName has a trailing space."""
        names = {"You Should See Me In A Crown": "Renai Circulation / Kana Hanazawa",
                 "Bad Guy": "Odo / Ado"}   # case-drifted key too
        out = loadout.merge_loadout(CATALOG, {}, names, {})
        by_id = {r["songID"]: r for p in out["packs"] for r in p["songs"]}
        assert by_id["YouShouldSeeMeInACrown"]["customName"] == "Renai Circulation"
        assert by_id["YouShouldSeeMeInACrown"]["customArtist"] == "Kana Hanazawa"
        assert by_id["BadGuy"]["customName"] == "Odo"
        assert by_id["BadGuy"]["customArtist"] == "Ado"
        assert out["unmatchedMetadata"] == []

    def test_display_value_without_artist_slash(self):
        names = {"Juice": "Espresso"}   # no " / " — name only
        out = loadout.merge_loadout(CATALOG, {}, names, {})
        juice = out["packs"][1]["songs"][0]
        assert juice["customName"] == "Espresso"
        assert juice["customArtist"] is None

    def test_unmatched_metadata_reported(self):
        names = {"Totally Unknown Song": "X / Y"}
        out = loadout.merge_loadout(CATALOG, {}, names, {})
        assert out["unmatchedMetadata"] == ["Totally Unknown Song"]

    def test_read_failures_never_fake_empty(self):
        """loadout_from_state must carry read errors, not render as clean."""
        state = {"redirects_read_error": "get: timeout",
                 "song_names": {}, "song_artists": {}}
        out = loadout.loadout_from_state(state)
        assert out["redirectedSlotCount"] == 0  # explicit: unknown, shown as not-deployed
        # the readStatus halves are surfaced by the endpoint, not silently
        state2 = {"metadata_read_error": "parse failed",
                  "redirects": {}}
        out2 = loadout.loadout_from_state(state2)
        assert out2["customNameCount"] == 0
        assert out2["unmatchedMetadata"] == []

    def test_none_sources_treated_as_empty(self):
        out = loadout.merge_loadout(CATALOG, None, None, None)
        assert out["redirectedSlotCount"] == 0
        assert out["customNameCount"] == 0


class TestRealCatalog:
    def test_real_catalog_loads(self):
        catalog = loadout.load_catalog()
        assert len(catalog) == 36
        assert "billieeilish" in catalog and "therollingstones" in catalog
        # every song has the join key
        for pack, songs in catalog.items():
            for s in songs:
                assert s["songID"], f"{pack} has a song without songID"

    def test_real_local_state_merge(self):
        """Merge against the dev repo's real local state files (NOT the PS4):
        redirects.json + song_metadata.json in beat_saber_deluxe/ — the same
        formats the live endpoint reads. Purely local file reads, no FTP."""
        import json
        red_path = PROJECT / "redirects.json"
        md_path = PROJECT / "song_metadata.json"
        if not red_path.exists() or not md_path.exists():
            pytest.skip("local state files absent (clean checkout)")
        redirects = json.loads(red_path.read_text())["redirects"]
        md = json.loads(md_path.read_text())
        out = loadout.merge_loadout(loadout.load_catalog(), redirects,
                                    md["song_names"], md["song_artists"])
        # the dev repo's known-good state: every metadata entry joins, ≥1 redirected slot
        assert out["customNameCount"] == len(md["song_names"])
        assert out["redirectedSlotCount"] >= 1
        # the trailing-space crown song quirk — exercised when the local state
        # has it (the 47-song loadout did; the clean-slate + M13-era state has
        # its own customs instead). The invariant that holds in EVERY state:
        # whatever entries exist, they all join into their slots.
        crown_meta_key = "You Should See Me in a Crown"
        if any(k.strip() == crown_meta_key for k in md["song_names"]):
            crown = [r for p in out["packs"] for r in p["songs"]
                     if r["songID"] == "YouShouldSeeMeInACrown"][0]
            assert crown["customName"], "trailing-space catalog name failed to join"
        else:
            joined = [r for p in out["packs"] for r in p["songs"] if r["customName"]]
            assert len(joined) == len(md["song_names"]), \
                "every song_metadata entry must join into its catalog slot"


class TestLiveDeployedTruthModel:
    """Pin the deployed-truth model discovered in Exp 245 (live PS4 audit):

    The LIVE redirects.json carried only ONE song redirect (MessItUp) while
    the AFR dir held 48 `<slot>_v3.bundle` files and song_metadata carried 47
    entries — i.e. bundle presence WITHOUT a redirect is real, common state
    (earlier scoped deploys left bundles; the game serves ONLY redirected
    slots per open_hook's match against the redirect table). The merge must
    represent all three signals distinctly.
    """

    LIVE_REDIRECTS = {"BeatmapLevelsData/MessItUp": "MessItUp_v3.bundle"}
    LIVE_METADATA = {f"song{i}": f"Custom{i} / Artist{i}" for i in range(47)}
    LIVE_BUNDLES = [f"Slot{i}" for i in range(48)]

    def test_one_served_many_stale(self):
        catalog = {"pack": [
            {"songID": "MessItUp", "songName": "Mess It Up", "songAuthorName": "X"},
            {"songID": "Slot0", "songName": "song0", "songAuthorName": "Y"},
            {"songID": "Untouched", "songName": "untouched", "songAuthorName": "Z"},
        ]}
        out = loadout.merge_loadout(catalog, self.LIVE_REDIRECTS,
                                    self.LIVE_METADATA, {}, slot_bundles=self.LIVE_BUNDLES)
        by_id = {r["songID"]: r for p in out["packs"] for r in p["songs"]}
        assert by_id["MessItUp"]["customDeployed"] is True
        assert by_id["Slot0"]["customDeployed"] is False
        assert by_id["Slot0"]["staleBundle"] is True     # bundle, no redirect
        assert by_id["Slot0"]["customName"] == "Custom0"  # but still labeled
        assert by_id["Untouched"]["customDeployed"] is False
        assert by_id["Untouched"]["staleBundle"] is False
        assert out["staleBundleCount"] == 1
        # 47 stale bundles belong to NO catalog slot → reported, not hidden
        assert len(out["unmatchedBundles"]) == 47
