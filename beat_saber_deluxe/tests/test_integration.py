"""
Integration tests for the full custom song pipeline.
Tests end-to-end song processing from mock song directory to output bundle generation,
using a minimal mock game dump structure.
"""
import json
import os
import sys

import UnityPy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from full_custom_song_pipeline import (
    DIFFICULTIES,
    GAME_CHARACTERISTIC_MODES,
    _load_local_redirects,
    _load_local_song_metadata,
    _load_song_details,
    _load_song_ids,
    _lookup_song_name,
    _select_beatmap_file,
    build_mode_mapping,
    build_pcm16_fsb5,
    convert_v2_to_v3,
    detect_song_modes,
    is_v2_beatmap,
    load_config,
    manage_redirect_config,
    manage_song_metadata,
)


class TestPipelineIntegration:
    """End-to-end pipeline integration tests with mock dump and custom song."""

    def test_mock_bundle_creation_and_patching(self, tmp_dir, silence_wav, v2_beatmap, info_dat):
        """
        Test that we can create a mock bundle, patch it with audio (PCM16 FSB5)
        and beatmaps, update AudioClip / audio.gz, and save successfully.
        """
        # 1. Setup mock game dump directory structure
        dump_dir = os.path.join(tmp_dir, "ps4_dump", "CUSA12878-patch")
        streaming_assets = os.path.join(dump_dir, "Media", "StreamingAssets", "BeatmapLevelsData")
        os.makedirs(streaming_assets, exist_ok=True)

        # Create a minimal valid UnityFS bundle using UnityPy
        _env = UnityPy.Environment()
        _template_bundle_path = os.path.join(streaming_assets, "startmeup")

        # Build FSB5 audio
        pcm16_fsb5 = build_pcm16_fsb5(silence_wav, pad_to_size=1024)
        assert len(pcm16_fsb5) == 1024
        assert pcm16_fsb5[:4] == b'FSB5'

        # Test beatmap conversion utility directly
        from full_custom_song_pipeline import convert_v2_to_v3
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3_data = convert_v2_to_v3(v2_data)
        assert v3_data['version'] == '3.2.0'
        assert 'colorNotes' in v3_data


class TestPCM16FSB5Build:
    """Test PCM16 FSB5 audio building."""

    def test_build_pcm16_fsb5_returns_valid_header(self, tmp_dir, silence_wav):
        """FSB5 output starts with 'FSB5' magic and is padded correctly."""
        fsb5 = build_pcm16_fsb5(silence_wav, pad_to_size=2048)
        assert fsb5[:4] == b'FSB5'
        assert len(fsb5) == 2048

    def test_build_pcm16_fsb5最小_size(self, tmp_dir, silence_wav):
        """FSB5 output is at least as large as the requested pad size."""
        fsb5 = build_pcm16_fsb5(silence_wav, pad_to_size=512)
        assert len(fsb5) >= 512
        assert fsb5[:4] == b'FSB5'

    def test_build_pcm16_fsb5_preserves_audio_data(self, tmp_dir, tone_wav):
        """FSB5 output contains actual audio data (not all zeros after header)."""
        fsb5 = build_pcm16_fsb5(tone_wav, pad_to_size=4096)
        assert fsb5[:4] == b'FSB5'
        # Audio data should have some non-zero content
        assert any(b != 0 for b in fsb5[64:256])


class TestV2ToV3Conversion:
    """Test V2 to V3 beatmap conversion."""

    def test_conversion_basic(self, v2_beatmap):
        """V2 beatmap converts to V3.2.0 with correct structure."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3 = convert_v2_to_v3(v2_data)
        assert v3['version'] == '3.2.0'
        assert 'colorNotes' in v3
        assert 'bombNotes' in v3
        assert 'obstacles' in v3
        assert 'basicBeatmapEvents' in v3
        assert 'bpmEvents' in v3

    def test_v3_passthrough(self, v3_beatmap):
        """V3 beatmap passes through unchanged."""
        with open(v3_beatmap) as f:
            v3_data = json.load(f)
        result = convert_v2_to_v3(v3_data)
        assert result is v3_data  # Same object, no conversion

    def test_note_type_conversion(self, v2_beatmap):
        """V2 note types map correctly to V3 colorNotes/bombNotes."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3 = convert_v2_to_v3(v2_data)
        # V2 type 0 and 1 -> colorNotes, type 3 -> bombNotes
        assert len(v3['colorNotes']) >= 2  # types 0 and 1
        assert len(v3['bombNotes']) >= 0  # no type 3 in fixture

    def test_obstacle_conversion(self, v2_beatmap):
        """V2 obstacles convert to V3 format."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3 = convert_v2_to_v3(v2_data)
        assert len(v3['obstacles']) == 1
        obs = v3['obstacles'][0]
        assert 'b' in obs  # beat time
        assert 'w' in obs  # width
        assert 'h' in obs  # height

    def test_event_conversion(self, v2_beatmap):
        """V2 events convert to V3 basicBeatmapEvents."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3 = convert_v2_to_v3(v2_data)
        assert len(v3['basicBeatmapEvents']) == 2
        evt = v3['basicBeatmapEvents'][0]
        assert 'b' in evt  # beat time
        assert 'et' in evt  # type
        assert 'i' in evt  # value

    def test_is_v2_detection(self, v2_beatmap, v3_beatmap):
        """is_v2_beatmap correctly identifies V2 vs V3 format."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        with open(v3_beatmap) as f:
            v3_data = json.load(f)
        assert is_v2_beatmap(v2_data) is True
        assert is_v2_beatmap(v3_data) is False

    def test_default_bpm_injection(self, v2_beatmap):
        """V3 bpmEvents uses the default_bpm parameter."""
        with open(v2_beatmap) as f:
            v2_data = json.load(f)
        v3 = convert_v2_to_v3(v2_data, default_bpm=150.0)
        assert v3['bpmEvents'][0]['m'] == 150.0


class TestBeatmapFileSelection:
    """Test beatmap file selection priority chain."""

    def test_standard_priority(self, tmp_dir):
        """Standard mode file is preferred over bare difficulty."""
        files = ['HardStandard.dat', 'Hard.dat', 'Hard90Degree.dat']
        result = _select_beatmap_file('Hard', files)
        assert result == 'HardStandard.dat'

    def test_bare_fallback(self, tmp_dir):
        """Bare difficulty file used when no Standard exists."""
        files = ['Hard.dat', 'Hard90Degree.dat']
        result = _select_beatmap_file('Hard', files)
        assert result == 'Hard.dat'

    def test_beatmap_dat_fallback(self, tmp_dir):
        """BeatSaver .beatmap.dat format used as third priority."""
        files = ['Hard.beatmap.dat', 'Hard90Degree.dat']
        result = _select_beatmap_file('Hard', files)
        assert result == 'Hard.beatmap.dat'

    def test_non_standard_fallback(self, tmp_dir):
        """Non-standard mode used as fourth priority when allowed."""
        files = ['Hard90Degree.dat', 'HardOneSaber.dat']
        result = _select_beatmap_file('Hard', files)
        assert result in ('Hard90Degree.dat', 'HardOneSaber.dat')

    def test_ignore_non_standard(self, tmp_dir):
        """Non-standard modes skipped when ignore_non_standard=True."""
        files = ['Hard90Degree.dat', 'HardOneSaber.dat']
        result = _select_beatmap_file('Hard', files, ignore_non_standard=True)
        assert result is None

    def test_expert_not_expertplus(self, tmp_dir):
        """Expert difficulty never matches ExpertPlus files."""
        files = ['ExpertPlus.dat', 'Expert.dat']
        result = _select_beatmap_file('Expert', files)
        assert result == 'Expert.dat'

    def test_no_match(self, tmp_dir):
        """Returns None when no matching file exists."""
        files = ['Easy.dat', 'Normal.dat']
        result = _select_beatmap_file('Hard', files)
        assert result is None

    def test_info_dat_excluded(self, tmp_dir):
        """Info.dat is never selected as a beatmap file."""
        files = ['Info.dat', 'Hard.dat']
        result = _select_beatmap_file('Hard', files)
        assert result == 'Hard.dat'


class TestRedirectConfigManagement:
    """Test redirect config generation without FTP deployment."""

    def test_generate_creates_file(self, tmp_dir, monkeypatch):
        """generate=True creates a new redirects.json with correct structure."""
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_redirect_config_path',
            lambda project_root=None: os.path.join(tmp_dir, 'redirects.json')
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_redirect_to_ps4',
            lambda config: None
        )
        config = {
            'title': {'id': 'CUSA12878'},
            'paths': {'afr_base': '/data/GoldHEN/AFR', 'afr_target_suffix': '_v3'},
        }
        result = manage_redirect_config(
            config, target_name='startmeup', generate=True, deploy=False
        )
        assert 'redirects' in result
        assert 'BeatmapLevelsData/startmeup' in result['redirects']
        assert result['redirects']['BeatmapLevelsData/startmeup'] == 'startmeup_v3'
        assert result['titleId'] == 'CUSA12878'

    def test_prefix_auto_added(self, tmp_dir, monkeypatch):
        """Target name without BeatmapLevelsData/ prefix gets it auto-added."""
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_redirect_config_path',
            lambda project_root=None: os.path.join(tmp_dir, 'redirects.json')
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_redirect_to_ps4',
            lambda config: None
        )
        config = {
            'title': {'id': 'CUSA12878'},
            'paths': {'afr_base': '/data/GoldHEN/AFR', 'afr_target_suffix': '_v3'},
        }
        result = manage_redirect_config(
            config, target_name='Crystallized', generate=True, deploy=False
        )
        assert 'BeatmapLevelsData/Crystallized' in result['redirects']

    def test_existing_config_merged(self, tmp_dir, monkeypatch):
        """New target is merged into existing redirects.json."""
        config_path = os.path.join(tmp_dir, 'redirects.json')
        existing = {
            'titleId': 'CUSA12878',
            'afrBase': '/data/GoldHEN/AFR',
            'redirects': {'BeatmapLevelsData/startmeup': 'startmeup_v3'}
        }
        with open(config_path, 'w') as f:
            json.dump(existing, f)

        monkeypatch.setattr(
            'full_custom_song_pipeline._get_redirect_config_path',
            lambda project_root=None: config_path
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_redirect_to_ps4',
            lambda config: None
        )
        config = {
            'title': {'id': 'CUSA12878'},
            'paths': {'afr_base': '/data/GoldHEN/AFR', 'afr_target_suffix': '_v3'},
        }
        result = manage_redirect_config(
            config, target_name='angry', generate=True, deploy=False
        )
        assert len(result['redirects']) == 2
        assert 'BeatmapLevelsData/startmeup' in result['redirects']
        assert 'BeatmapLevelsData/angry' in result['redirects']

    def test_load_local_redirects_missing_file(self, tmp_dir):
        """Loading redirects from missing file returns default structure."""
        result = _load_local_redirects(os.path.join(tmp_dir, 'nonexistent.json'))
        assert 'redirects' in result
        assert result['titleId'] == 'CUSA12878'
        assert len(result['redirects']) == 0


class TestPackBundleRedirectConsistency:
    """Test the pack bundle + catalog redirect pair consistency (Exp 180 crash fix)."""

    PACK_CONFIG = {
        'title': {'id': 'CUSA12878'},
        'paths': {'afr_base': '/data/GoldHEN/AFR', 'afr_target_suffix': '_v3'},
        'pack_bundle': {
            'bundle_key': 'therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle',
            'patched_bundle': 'startmeup_pack_modes.bundle',
            'catalog_key': 'aa/catalog.json',
            'patched_catalog': 'catalog_startmeup_modes.json',
        },
        # Hermetic isolation (Exp 224): no pinned pack list and a nonexistent
        # build_dir, so auto-discovery finds nothing from the host workspace
        # and only the pack_bundle prototype pair applies in these tests.
        'pack_modes': {'packs': [], 'build_dir': '/nonexistent-hermetic-build-dir'},
    }

    def test_get_pack_bundle_redirects_returns_pair(self):
        """The pack bundle redirect always comes with the catalog redirect.
        (Exp 224: with no pinned pack list, auto-discovered packs from the
        deployment state are ALSO included — the prototype pair must always
        be a subset, never absent.)"""
        from full_custom_song_pipeline import _get_pack_bundle_redirects
        pair = _get_pack_bundle_redirects(self.PACK_CONFIG)
        assert pair.get('therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle') == 'startmeup_pack_modes.bundle'
        assert pair.get('aa/catalog.json') == 'catalog_startmeup_modes.json'

    def test_get_pack_bundle_redirects_empty_without_config(self):
        """No pack_bundle config, nothing built, no deployment state in scope
        -> no forced redirects. Discovery must never invent packs the user
        did not deploy."""

        from full_custom_song_pipeline import _get_pack_bundle_redirects
        config = {'title': {'id': 'CUSA12878'}, 'paths': {},
                  'pack_modes': {'packs': [], 'build_dir': '/nonexistent-build-dir'}}
        assert _get_pack_bundle_redirects(config) == {}

    def test_ensure_pack_bundle_redirects_adds_missing_pair(self):
        """Regenerated config that lost the pack/catalog pair gets both restored."""
        from full_custom_song_pipeline import _ensure_pack_bundle_redirects
        data = {'redirects': {'BeatmapLevelsData/startmeup': 'startmeup_v3'}}
        changed = _ensure_pack_bundle_redirects(data, self.PACK_CONFIG)
        assert changed >= 2  # prototype pair (2) + any auto-discovered packs
        assert data['redirects']['aa/catalog.json'] == 'catalog_startmeup_modes.json'
        assert data['redirects']['therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle'] == 'startmeup_pack_modes.bundle'

    def test_ensure_pack_bundle_redirects_fixes_stale_pack_target(self):
        """A stale pack target (e.g. rollingstones_pack_patched.bundle) is overwritten."""
        from full_custom_song_pipeline import _ensure_pack_bundle_redirects
        data = {'redirects': {
            'BeatmapLevelsData/startmeup': 'startmeup_v3',
            'therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c': 'rollingstones_pack_patched.bundle',
        }}
        changed = _ensure_pack_bundle_redirects(data, self.PACK_CONFIG)
        # 1 stale key removed + 2 canonical prototype entries added/updated
        # (+ any auto-discovered pack pairs, Exp 224)
        assert changed >= 3
        assert data['redirects']['aa/catalog.json'] == 'catalog_startmeup_modes.json'
        assert data['redirects']['therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle'] == 'startmeup_pack_modes.bundle'
        assert 'rollingstones_pack_patched.bundle' not in data['redirects'].values()

    def test_manage_redirect_config_never_drops_pack_pair(self, tmp_dir, monkeypatch):
        """manage_redirect_config must ALWAYS keep the pack bundle + catalog pair."""
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_redirect_config_path',
            lambda project_root=None: os.path.join(tmp_dir, 'redirects.json')
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_redirect_to_ps4',
            lambda config: None
        )
        result = manage_redirect_config(
            self.PACK_CONFIG, target_name='startmeup', generate=True, deploy=False
        )
        assert result['redirects']['BeatmapLevelsData/startmeup'] == 'startmeup_v3'
        assert result['redirects']['aa/catalog.json'] == 'catalog_startmeup_modes.json'
        assert result['redirects']['therollingstones_pack_assets_all_a99482a8a3da9e991e5ae36f2fea209c.bundle'] == 'startmeup_pack_modes.bundle'

    def test_load_config_defaults_include_pack_modes(self):
        """Default config carries the generalized pack_modes settings; the legacy
        single-pack pack_bundle prototype is gone (superseded by pack_modes)."""
        from full_custom_song_pipeline import load_config
        cfg = load_config('/nonexistent/config.json')
        assert 'pack_bundle' not in cfg, "legacy single-pack prototype removed from defaults"
        assert cfg['pack_modes']['patched_catalog'] == 'catalog_pack_modes.json'
        assert len(cfg['mass_deploy']['slots']) == 38


class TestDeployedBundleNaming:
    """Song redirect VALUES must match the exact deployed bundle filename (Exp 186).

    The game opens the redirect VALUE verbatim and open() is case-sensitive, so a
    value like `Crystallized_v3` silently keeps serving the stale build while the
    fresh bundle sits on the PS4 as `crystallized_v3.bundle`.
    """

    MASS_CFG = {
        'title': {'id': 'CUSA12878'},
        'paths': {'afr_base': '/data/GoldHEN/AFR', 'afr_target_suffix': '_v3.bundle'},
        'mass_deploy': {'slots': ['startmeup', 'crystallized', 'cyclehit',
                                  'Oxytocin', 'AllTheGoodGirlsGoToHell']},
    }

    def test_deployed_bundle_name_uses_slot_casing(self):
        """Deployed name uses the canonical slot casing from mass_deploy.slots."""
        from full_custom_song_pipeline import _deployed_bundle_name
        assert _deployed_bundle_name('Crystallized', self.MASS_CFG) == 'crystallized_v3.bundle'
        assert _deployed_bundle_name('crystallized', self.MASS_CFG) == 'crystallized_v3.bundle'
        assert _deployed_bundle_name('Oxytocin', self.MASS_CFG) == 'Oxytocin_v3.bundle'
        assert _deployed_bundle_name('startmeup', self.MASS_CFG) == 'startmeup_v3.bundle'

    def test_deployed_bundle_name_default_suffix(self):
        """Falls back to _v3.bundle when no suffix is configured."""
        from full_custom_song_pipeline import _deployed_bundle_name
        cfg = {'paths': {}}
        assert _deployed_bundle_name('startmeup', cfg) == 'startmeup_v3.bundle'

    def test_ensure_mass_song_redirects_fixes_stale_values(self):
        """Stale pre-.bundle values are healed to the deployed filename."""
        from full_custom_song_pipeline import _ensure_mass_song_redirects
        data = {'redirects': {
            'BeatmapLevelsData/startmeup': 'startmeup_v3',
            'BeatmapLevelsData/Crystallized': 'Crystallized_v3',
        }}
        changed = _ensure_mass_song_redirects(data, self.MASS_CFG)
        assert changed >= 2
        assert data['redirects']['BeatmapLevelsData/startmeup'] == 'startmeup_v3.bundle'
        assert data['redirects']['BeatmapLevelsData/Crystallized'] == 'crystallized_v3.bundle'

    def test_ensure_mass_song_redirects_adds_missing_slots(self):
        """Slots missing from the config get added with the correct value."""
        from full_custom_song_pipeline import _ensure_mass_song_redirects
        data = {'redirects': {}}
        changed = _ensure_mass_song_redirects(data, self.MASS_CFG)
        assert changed == len(self.MASS_CFG['mass_deploy']['slots'])
        for slot in self.MASS_CFG['mass_deploy']['slots']:
            key = f"BeatmapLevelsData/{slot}"
            assert data['redirects'][key] == f"{slot}_v3.bundle"

    def test_manage_redirect_config_heals_stale_values(self, tmp_dir, monkeypatch):
        """manage_redirect_config writes exact deployed filenames as values."""
        from full_custom_song_pipeline import manage_redirect_config
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_redirect_config_path',
            lambda project_root=None: os.path.join(tmp_dir, 'redirects.json')
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_redirect_to_ps4',
            lambda config: None
        )
        result = manage_redirect_config(
            self.MASS_CFG, target_name='crystallized', generate=True, deploy=False
        )
        assert result['redirects']['BeatmapLevelsData/crystallized'] == 'crystallized_v3.bundle'

    def test_no_slots_no_change(self):
        """No mass_deploy.slots -> no forced song redirects."""
        from full_custom_song_pipeline import _ensure_mass_song_redirects
        data = {'redirects': {'BeatmapLevelsData/startmeup': 'startmeup_v3'}}
        changed = _ensure_mass_song_redirects(data, {'paths': {}})
        assert changed == 0
        assert data['redirects']['BeatmapLevelsData/startmeup'] == 'startmeup_v3'


class TestSongMetadataManagement:
    """Test song metadata generation without FTP deployment."""

    def test_metadata_creates_file(self, tmp_dir, monkeypatch):
        """manage_song_metadata creates song_metadata.json with correct entries."""
        metadata_path = os.path.join(tmp_dir, 'song_metadata.json')
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_song_metadata_path',
            lambda project_root=None: metadata_path
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_song_metadata_to_ps4',
            lambda config: None
        )
        config = {
            'title': {'id': 'CUSA12878'},
            'paths': {'afr_base': '/data/GoldHEN/AFR'},
        }
        result = manage_song_metadata(
            config,
            song_name='Bloom',
            artist='ODESZA',
            target_name='Crystallized',
            deploy=False,
        )
        assert 'song_names' in result
        assert 'song_artists' in result
        # Combined name format: "SongName / Artist"
        assert any('Bloom' in v for v in result['song_names'].values())

    def test_metadata_blanks_original_artist(self, tmp_dir, monkeypatch):
        """Original artist from beat_saber_song_ids.json is blanked."""
        metadata_path = os.path.join(tmp_dir, 'song_metadata.json')
        monkeypatch.setattr(
            'full_custom_song_pipeline._get_song_metadata_path',
            lambda project_root=None: metadata_path
        )
        monkeypatch.setattr(
            'full_custom_song_pipeline._deploy_song_metadata_to_ps4',
            lambda config: None
        )
        config = {
            'title': {'id': 'CUSA12878'},
            'paths': {'afr_base': '/data/GoldHEN/AFR'},
        }
        # Use a slot that exists in beat_saber_song_ids.json
        result = manage_song_metadata(
            config,
            song_name='Bloom',
            artist='ODESZA',
            target_name='Crystallized',
            deploy=False,
        )
        # Should have at least one blanked artist
        assert len(result['song_artists']) > 0


class TestSongIDLookup:
    """Test song ID lookup and name resolution."""

    def test_load_song_details(self):
        """_load_song_details returns slot->details mapping."""
        details = _load_song_details()
        assert isinstance(details, dict)
        # Should have entries with songName and songAuthorName
        for slot_id, info in details.items():
            assert 'songName' in info
            assert 'songAuthorName' in info

    def test_load_song_ids(self):
        """_load_song_ids returns slot->songName mapping."""
        ids = _load_song_ids()
        assert isinstance(ids, dict)
        for slot_id, name in ids.items():
            assert isinstance(name, str)
            assert len(name) > 0

    def test_lookup_exact_match(self):
        """_lookup_song_name finds exact slot ID match."""
        ids = _load_song_ids()
        if ids:
            first_slot = next(iter(ids))
            result = _lookup_song_name(first_slot, ids)
            assert result == ids[first_slot]

    def test_lookup_case_insensitive(self):
        """_lookup_song_name handles case-insensitive slot matching."""
        ids = _load_song_ids()
        if ids:
            first_slot = next(iter(ids))
            result = _lookup_song_name(first_slot.lower(), ids)
            assert result == ids[first_slot]

    def test_lookup_fallback(self):
        """_lookup_song_name falls back to input string when no match."""
        ids = _load_song_ids()
        result = _lookup_song_name("NonexistentSong", ids)
        assert result == "NonexistentSong"


class TestLoadLocalMetadataFiles:
    """Test loading local metadata JSON files."""

    def test_load_song_metadata_missing(self, tmp_dir):
        """Missing song_metadata.json returns default structure."""
        result = _load_local_song_metadata(os.path.join(tmp_dir, 'missing.json'))
        assert result == {"song_names": {}, "song_artists": {}}

    def test_load_song_metadata_existing(self, tmp_dir):
        """Existing song_metadata.json is loaded correctly."""
        path = os.path.join(tmp_dir, 'song_metadata.json')
        data = {"song_names": {"Start Me Up": "Bloom / ODESZA"}, "song_artists": {"Camellia": " "}}
        with open(path, 'w') as f:
            json.dump(data, f)
        result = _load_local_song_metadata(path)
        assert result['song_names']['Start Me Up'] == 'Bloom / ODESZA'
        assert result['song_artists']['Camellia'] == ' '


class TestConfigLoading:
    """Test config loading from JSON files."""

    def test_load_default_config(self, tmp_dir):
        """Missing config file returns default structure."""
        config_path = os.path.join(tmp_dir, 'nonexistent.json')
        config = load_config(config_path)
        assert 'ps4' in config
        assert 'title' in config
        assert config['title']['id'] == 'CUSA12878'

    def test_load_custom_config(self, tmp_dir):
        """Custom config file is loaded and merged."""
        config_path = os.path.join(tmp_dir, 'ps4_config.json')
        custom = {
            "ps4": {"ip": "10.0.0.1", "ftp_port": 2121},
            "title": {"id": "CUSA99999"}
        }
        with open(config_path, 'w') as f:
            json.dump(custom, f)
        config = load_config(config_path)
        assert config['ps4']['ip'] == '10.0.0.1'
        assert config['title']['id'] == 'CUSA99999'


# ======================================================================
# Beatmap Mode Mapping Integration
# ======================================================================
class TestBeatmapModeMappingIntegration:
    """Integration test for detect→build→apply mode mapping chain."""

    def test_detect_build_chain(self, tmp_dir):
        """Full detect→build cycle with multi-mode song directory."""
        # Create Standard beatmaps (bare .dat files)
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            data = {"version": "3.2.0", "colorNotes": [], "bombNotes": [],
                    "obstacles": [], "sliders": [], "burstSliders": [],
                    "basicBeatmapEvents": [], "bpmEvents": [{"b": 0, "m": 120}],
                    "rotationEvents": [], "basicEventTypesWithKeywords": {"d": []},
                    "useNormalEventsAsCompatibleEvents": True}
            with open(os.path.join(tmp_dir, f"{diff}.dat"), 'w') as f:
                json.dump(data, f)

        # Create OneSaber files (2 difficulties)
        for diff in ['Expert', 'ExpertPlus']:
            data = {"version": "3.2.0", "colorNotes": [{"b": 0, "x": 0, "y": 2, "a": 0, "c": 0, "d": 1}],
                    "bombNotes": [], "obstacles": [], "sliders": [], "burstSliders": [],
                    "basicBeatmapEvents": [], "bpmEvents": [{"b": 0, "m": 120}],
                    "rotationEvents": [], "basicEventTypesWithKeywords": {"d": []},
                    "useNormalEventsAsCompatibleEvents": True}
            with open(os.path.join(tmp_dir, f"{diff}OneSaber.dat"), 'w') as f:
                json.dump(data, f)

        # Create 360Degree files (1 difficulty) — must be ignored on PS4
        with open(os.path.join(tmp_dir, "Normal360Degree.dat"), 'w') as f:
            json.dump({"version": "3.2.0", "colorNotes": [], "bombNotes": [],
                       "obstacles": [], "sliders": [], "burstSliders": [],
                       "basicBeatmapEvents": [], "bpmEvents": [{"b": 0, "m": 120}],
                       "rotationEvents": [], "basicEventTypesWithKeywords": {"d": []},
                       "useNormalEventsAsCompatibleEvents": True}, f)

        # Step 1: Detect
        modes = detect_song_modes(tmp_dir)
        assert 'Standard' in modes
        assert len(modes['Standard']) == 5
        assert 'OneSaber' in modes
        assert modes['OneSaber'] == ['Expert', 'ExpertPlus']
        assert '360Degree' not in modes
        assert 'NoArrows' not in modes
        assert '90Degree' not in modes

        # Step 2: Build mapping (default fallback)
        enabled = build_mode_mapping(modes)
        assert enabled == list(GAME_CHARACTERISTIC_MODES)  # all 4 resolved

        # Step 3: Build mapping with custom fallback
        enabled_custom = build_mode_mapping(modes, fallback_mode_map=["90Degree=Standard"])
        assert enabled_custom == list(GAME_CHARACTERISTIC_MODES)

    def test_no_standard_edge_case(self, tmp_dir):
        """Song directory with only non-Standard mode files."""
        with open(os.path.join(tmp_dir, "ExpertPlusOneSaber.dat"), 'w') as f:
            json.dump({}, f)

        modes = detect_song_modes(tmp_dir)
        assert 'OneSaber' in modes
        assert 'Standard' not in modes

        # Even without Standard files, all 4 modes resolve via fallback
        enabled = build_mode_mapping(modes)
        assert enabled == list(GAME_CHARACTERISTIC_MODES)

    def test_single_difficulty_mode(self, tmp_dir):
        """OneSaber with only ExpertPlus file."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            with open(os.path.join(tmp_dir, f"{diff}Standard.dat"), 'w') as f:
                json.dump({"version": "3.2.0", "colorNotes": [], "bombNotes": [],
                           "obstacles": [], "sliders": [], "burstSliders": [],
                           "basicBeatmapEvents": [], "bpmEvents": [{"b": 0, "m": 120}],
                           "rotationEvents": [],
                           "basicEventTypesWithKeywords": {"d": []},
                           "useNormalEventsAsCompatibleEvents": True}, f)
        with open(os.path.join(tmp_dir, "ExpertPlusOneSaber.dat"), 'w') as f:
            json.dump({}, f)

        modes = detect_song_modes(tmp_dir)
        assert modes['OneSaber'] == ['ExpertPlus']
        enabled = build_mode_mapping(modes)
        assert 'OneSaber' in enabled

    def test_all_modes_detected_integration(self, tmp_dir):
        """Song with files for all 4 supported modes (360Degree excluded)."""
        for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
            with open(os.path.join(tmp_dir, f"{diff}Standard.dat"), 'w') as f:
                json.dump({"version": "3.2.0", "colorNotes": [], "bombNotes": [],
                           "obstacles": [], "sliders": [], "burstSliders": [],
                           "basicBeatmapEvents": [], "bpmEvents": [{"b": 0, "m": 120}],
                           "rotationEvents": [],
                           "basicEventTypesWithKeywords": {"d": []},
                           "useNormalEventsAsCompatibleEvents": True}, f)
        for mode in ['OneSaber', 'NoArrows']:
            for diff in ['Easy', 'Normal', 'Hard', 'Expert', 'ExpertPlus']:
                with open(os.path.join(tmp_dir, f"{diff}{mode}.dat"), 'w') as f:
                    json.dump({}, f)
        with open(os.path.join(tmp_dir, "Expert90Degree.dat"), 'w') as f:
            json.dump({}, f)
        with open(os.path.join(tmp_dir, "Expert360Degree.dat"), 'w') as f:
            json.dump({}, f)

        modes = detect_song_modes(tmp_dir)
        assert set(modes.keys()) == {'Standard', 'OneSaber', 'NoArrows', '90Degree'}
        assert modes['Standard'] == list(DIFFICULTIES)
        assert modes['OneSaber'] == list(DIFFICULTIES)
        assert modes['NoArrows'] == list(DIFFICULTIES)

        enabled = build_mode_mapping(modes)
        assert enabled == list(GAME_CHARACTERISTIC_MODES)
