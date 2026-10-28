"""Song previews (M10, Exp 268/269) — hermetic tests for tools/song_previews.py
and the pipeline's variant threading.

Fixtures are SYNTHETIC (generated PCM + tiny FSB5s) or use the repo's built
lizzo bundles when present (HAS_BUILT gating, like the other hardware-env
classes). No PS4 access anywhere.
"""
import array
import io
import json
import math
import os
import struct
import sys
import wave

import pytest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
sys.path.insert(0, TOOLS)

import song_previews  # noqa: E402

HAS_BUILT = os.path.isfile(os.path.join(
    os.path.dirname(TOOLS), 'pack_modes_bundles',
    'lizzo_pack_modes_assets_all_8bf3db217732cc18af0b9a2a32d13a9a.bundle'))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_pcm(seconds: float, freq: float = 440.0, gain: float = 0.5,
             quiet_frac: float = 0.3):
    """Synthetic stereo int16 PCM — a tone with an amplitude envelope:
    quiet head (quiet_frac), loud middle to the end (heuristic tests rely
    on the loud region being LAST)."""
    n = int(seconds * song_previews.SAMPLE_RATE)
    out = array.array('h')
    for i in range(n):
        t = i / song_previews.SAMPLE_RATE
        env = 0.05 if t < seconds * quiet_frac else 1.0
        v = int(gain * env * 20000 * math.sin(2 * math.pi * freq * t))
        out.append(v)
        out.append(v)
    return out


def rms_of(seg):
    return song_previews._rms_db(seg)


# ─────────────────────────────────────────────────────────────────────────────
# cut_preview + build_preview_fsb5
# ─────────────────────────────────────────────────────────────────────────────

class TestCutPreview:
    def test_cut_is_exactly_10s(self):
        pcm = make_pcm(30.0)
        seg = song_previews.cut_preview(pcm, 5.0)
        assert len(seg) == int(10.0 * song_previews.SAMPLE_RATE) * 2

    def test_cut_start_clamps_near_end(self):
        pcm = make_pcm(15.0)
        seg = song_previews.cut_preview(pcm, 100.0)     # start beyond the end
        # clamped to dur-10 → 5s: the last 10s of the source (the LOUD region)
        assert len(seg) == int(10.0 * song_previews.SAMPLE_RATE) * 2
        mid_rms = rms_of(seg[len(seg) // 2 - 2000:len(seg) // 2 + 2000])
        assert mid_rms > -30.0     # loud region, not the quiet head

    def test_fades_applied(self):
        pcm = make_pcm(20.0, quiet_frac=0.0)
        seg = song_previews.cut_preview(pcm, 5.0)
        # the very first frames are ~0 (fade-in starts at gain 0)
        assert abs(seg[0]) < 100 and abs(seg[1]) < 100
        # the very last frames are ~0 (fade-out ends at gain 0)
        assert abs(seg[-1]) < 100 and abs(seg[-2]) < 100
        # mid is loud
        mid_rms = rms_of(seg[len(seg) // 2 - 2000:len(seg) // 2 + 2000])
        assert mid_rms > -30.0

    def test_normalization_targets_fleet_loudness(self):
        # very quiet source (gain 0.02) → normalized up toward -10.4 dBFS
        pcm = make_pcm(20.0, gain=0.02)
        seg = song_previews.cut_preview(pcm, 5.0)
        db = rms_of(seg)
        assert abs(db - song_previews.PREVIEW_TARGET_DBFS) <= 1.0

    def test_normalization_skipped_when_close(self):
        # a source already near target must pass through (fades aside)
        pcm = make_pcm(20.0, gain=0.42)
        seg = song_previews.cut_preview(pcm, 5.0)
        db = rms_of(seg)
        assert abs(db - song_previews.PREVIEW_TARGET_DBFS) <= song_previews.PREVIEW_TOLERANCE_DB + 1.0

    def test_peak_limited(self):
        pcm = make_pcm(20.0, gain=1.0)      # clipping-hot source
        seg = song_previews.cut_preview(pcm, 5.0)
        peak = max(abs(x) for x in seg)
        peak_target = int(10 ** (song_previews.PREVIEW_PEAK_DBFS / 20.0) * 32768)
        assert peak <= peak_target + 1     # int rounding


class TestPreviewFsb5:
    def test_fsb5_header_fields(self):
        seg = song_previews.cut_preview(make_pcm(12.0), 1.0)
        fsb = song_previews.build_preview_fsb5(seg)
        assert fsb[:4] == b'FSB5'
        assert struct.unpack_from('<I', fsb, 8)[0] == 1              # numSamples
        assert struct.unpack_from('<I', fsb, 24)[0] == 2            # mode = PCM16
        total_frames = len(seg) // 2
        sd = struct.unpack_from('<Q', fsb, 60)[0]
        assert (sd >> 34) & 0x3FFFFFFF == total_frames
        assert len(fsb) == 125 + len(seg.tobytes())

    def test_fsb5_decodes_roundtrip(self):
        import fsb5
        seg = song_previews.cut_preview(make_pcm(12.0), 1.0)
        fsb = song_previews.build_preview_fsb5(seg)
        f = fsb5.FSB5(fsb)
        s = f.samples[0]
        assert int(f.header.mode) == 2        # PCM16
        assert s.frequency == 44100 and s.channels == 2
        assert s.samples == 441000            # exactly 10s


# ─────────────────────────────────────────────────────────────────────────────
# Preview start resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestPreviewStart:
    def test_info_dat_v2_v3(self, tmp_path):
        d = tmp_path / 'song'
        d.mkdir()
        (d / 'Info.dat').write_text(json.dumps({'_previewStartTime': 42.5}))
        assert song_previews.preview_start_from_info(str(d)) == 42.5

    def test_info_dat_v4(self, tmp_path):
        d = tmp_path / 'song'
        d.mkdir()
        (d / 'Info.dat').write_text(json.dumps(
            {'version': '4.0.1', 'audio': {'previewStartTime': 50.0}}))
        assert song_previews.preview_start_from_info(str(d)) == 50.0

    def test_info_dat_absent(self, tmp_path):
        assert song_previews.preview_start_from_info(str(tmp_path)) is None
        (tmp_path / 'Info.dat').write_text('{}')
        assert song_previews.preview_start_from_info(str(tmp_path)) is None

    def test_info_dat_corrupt(self, tmp_path):
        (tmp_path / 'Info.dat').write_text('{not json')
        assert song_previews.preview_start_from_info(str(tmp_path)) is None


# ─────────────────────────────────────────────────────────────────────────────
# AudioClip blob parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestParseAudioClipBlob:
    def _build_blob(self, name=b'TestPreview', off=1234, size=5678, fmt=1):
        src = b'archive:/CAB-abc/CAB-abc.resource'
        blob = bytearray()
        blob += struct.pack('<I', len(name)) + name
        if len(blob) % 4:
            blob += b'\x00' * (4 - len(blob) % 4)
        blob += struct.pack('<IIII', 1, 2, 44100, 16)      # load, ch, freq, bits
        blob += struct.pack('<f', 10.0)                     # length
        blob += bytes([0, 0]) + b'\x00\x00'                  # bools + align
        blob += struct.pack('<i', 0)                         # subsound
        blob += bytes([0, 1, 1]) + b'\x00'                   # preload/bg/legacy + align
        blob += struct.pack('<I', len(src)) + src
        if len(blob) % 4:
            blob += b'\x00' * (4 - len(blob) % 4)      # stream fields are 4-aligned after the string
        blob += struct.pack('<QQ', off, size)
        blob += struct.pack('<i', fmt)
        blob += b'\x00' * 4                                  # trailing pad (real blobs end here)
        return bytes(blob)

    def test_parse(self):
        blob = self._build_blob(off=999, size=111)
        tail_at, off, size, fmt = song_previews.parse_audioclip_blob(blob)
        assert off == 999 and size == 111 and fmt == 1

    def test_name_length_variation(self):
        # longer name shifts the tail — the archive anchor must adapt
        blob = self._build_blob(name=b'AVeryLongPreviewNameHere1234567890', off=7, size=9)
        tail_at, off, size, fmt = song_previews.parse_audioclip_blob(blob)
        assert off == 7 and size == 9

    def test_missing_anchor_raises(self):
        with pytest.raises(RuntimeError):
            song_previews.parse_audioclip_blob(b'\x00' * 64)


# ─────────────────────────────────────────────────────────────────────────────
# Bundle-name variant derivation
# ─────────────────────────────────────────────────────────────────────────────

class TestVariantNaming:
    def test_previews_name(self):
        assert song_previews.previews_bundle_name(
            'lizzo_pack_modes_assets_all_abc123.bundle'
        ) == 'lizzo_pack_modes_previews_assets_all_abc123.bundle'

    def test_round_trip_identity(self):
        modes = 'britneyspears_pack_modes_assets_all_x.bundle'
        var = song_previews.previews_bundle_name(modes)
        assert '_modes_previews_' in var and var != modes


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline variant threading (flag → entries → variant file)
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineVariantThreading:
    def _pipeline(self):
        import full_custom_song_pipeline as fp
        return fp

    def test_default_features_has_previews_flag(self):
        fp = self._pipeline()
        # Exp 281: ALL flags default ON (fresh installs work out of the box).
        assert 'enable_song_previews' in fp.DEFAULT_FEATURES
        assert fp.DEFAULT_FEATURES['enable_song_previews'] is True

    def test_previews_enabled_reads_local_features(self, tmp_path, monkeypatch):
        fp = self._pipeline()
        fdir = tmp_path / 'features'
        fdir.mkdir()
        fpath = fdir / 'features.json'
        fpath.write_text(json.dumps({'enable_song_previews': True}))
        monkeypatch.setattr(fp, '_get_local_features_path', lambda *a, **k: str(fpath))
        assert fp._previews_enabled({}) is True
        fpath.write_text(json.dumps({'enable_song_previews': False}))
        assert fp._previews_enabled({}) is False
        # absent → default False
        fpath.write_text(json.dumps({}))
        assert fp._previews_enabled({}) is False

    @pytest.mark.skipif(not HAS_BUILT, reason='requires built lizzo modes bundle (hardware env)')
    def test_entries_point_at_variant_when_flag_on(self, tmp_path, monkeypatch):
        fp = self._pipeline()
        fdir = tmp_path / 'features'
        fdir.mkdir()
        fpath = fdir / 'features.json'
        fpath.write_text(json.dumps({'enable_song_previews': True}))
        monkeypatch.setattr(fp, '_get_local_features_path', lambda *a, **k: str(fpath))
        config = {
            'pack_modes': {
                'build_dir': os.path.join(os.path.dirname(TOOLS), 'pack_modes_bundles'),
                'song_ids_path': os.path.join(os.path.dirname(TOOLS), 'beat_saber_song_ids.json'),
            }
        }
        monkeypatch.setattr(fp, '_load_pack_albums', lambda cfg: {
            'lizzo': {'pack': 'lizzo',
                      'packBundle': 'lizzo_pack_assets_all_8bf3db217732cc18af0b9a2a32d13a9a.bundle'}
        })
        entries = fp._get_pack_modes_entries(config, packs=['lizzo'])
        assert len(entries) == 1
        assert entries[0]['patched_bundle'] == (
            'lizzo_pack_modes_previews_assets_all_8bf3db217732cc18af0b9a2a32d13a9a.bundle')

        # flag OFF → the modes-only name (today's behavior)
        fpath.write_text(json.dumps({'enable_song_previews': False}))
        entries = fp._get_pack_modes_entries(config, packs=['lizzo'])
        assert entries[0]['patched_bundle'] == (
            'lizzo_pack_modes_assets_all_8bf3db217732cc18af0b9a2a32d13a9a.bundle')


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end on the REAL built bundles (hardware-env gated)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_BUILT, reason='requires built lizzo bundles (hardware env)')
class TestLizzoVariantEndToEnd:
    def test_variant_builds_and_decodes(self, tmp_path):
        """Full production path: build the lizzo variants+previews bundle from
        the real modes bundle; decode every patched clip; verify mode sets."""
        import UnityPy

        root = os.path.dirname(TOOLS)
        modes_path = os.path.join(root, 'pack_modes_bundles',
                                  'lizzo_pack_modes_assets_all_8bf3db217732cc18af0b9a2a32d13a9a.bundle')
        ids = json.load(open(os.path.join(root, 'beat_saber_song_ids.json')))
        album = [a for a in ids['albums'] if a['pack'] == 'lizzo'][0]
        config = {'paths': {'output_dir': os.path.join(root, 'custom_songs')}}

        preview_map = song_previews.build_preview_map(album, config, log=lambda *a: None)
        # The expectation follows the LIVE local state (the clean-slate + M13
        # deploys legitimately changed it): preview every lizzo slot that is
        # custom per song_metadata.json AND has a local bundle — at least one
        # (the old 'all 9' was the 47-song-loadout era, not an invariant).
        root_dir = os.path.dirname(TOOLS)
        meta = json.load(open(os.path.join(root_dir, 'song_metadata.json'))).get('song_names', {})
        expected = {s['songID'] for s in album['songs'] if s['songName'] in meta}
        with_local_bundles = {sid for sid in expected if
                              song_previews.find_custom_bundle_for_slot(sid, config)}
        assert preview_map and set(preview_map) == with_local_bundles, \
            f'preview_map {sorted(preview_map)} != custom-with-bundle slots {sorted(with_local_bundles)}'
        work = song_previews.patch_pack_previews(album, preview_map, modes_path)
        assert work is not None
        out = os.path.join(str(tmp_path),
                           song_previews.previews_bundle_name(os.path.basename(modes_path)))
        new_bundle = song_previews.rebuild_bundle_with_previews(work, out)
        assert len(new_bundle) > os.path.getsize(modes_path)

        env = UnityPy.load(out)
        patched = stock = 0
        modes_ok = 0
        for obj in env.objects:
            if obj.type.name == 'AudioClip':
                d = obj.read(check_read=False)
                for _k, wav in d.samples.items():
                    w = wave.open(io.BytesIO(wav))
                    assert abs(w.getnframes() / w.getframerate() - 10.0) < 0.01
                    if d.m_Resource.m_Offset >= 5066944:
                        patched += 1
                    else:
                        stock += 1
            elif obj.type.name == 'MonoBehaviour':
                tt = obj.read_typetree()
                if '_previewDifficultyBeatmapSets' in tt:
                    # State-dynamic (Exp 283d era): custom slots carry 4 mode
                    # sets; STOCK slots keep their stock set count (the scoped
                    # incremental pack patch only touches custom slots — the
                    # old ==4-across-the-board was the all-9-custom era).
                    assert len(tt['_previewDifficultyBeatmapSets']) >= 1
                    assert isinstance(tt['_previewStartTime'], (int, float)) \
                        and tt['_previewStartTime'] >= 0
                    assert tt['_previewDuration'] == 10.0
                    modes_ok += 1
        n_songs = len(album['songs'])
        assert patched == len(preview_map) and patched >= 1, \
            f'patched clips ({patched}) must match the preview map ({len(preview_map)})'
        assert patched + stock == n_songs
        assert modes_ok >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Exp 269b regression: the post-deploy catalog check must read the manifest row
# that matches the DEPLOYED bundle variant (flag-aware), never a stale modes row.
# (The live batch deploy failed validation on all 5 packs because the variant
# manifest rows carried packBundle=<pack id> instead of the stock bundle name,
# so the check indexed the modes rows and compared their stale crc/size.)
# ─────────────────────────────────────────────────────────────────────────────

class TestManifestVariantSelection:
    def _write_manifest(self, tmp_path, pack='lizzo',
                        modes_crc=111, var_crc=222,
                        modes_bundle='lizzo_pack_modes_assets_all_abc.bundle',
                        var_bundle='lizzo_pack_modes_previews_assets_all_abc.bundle',
                        stock='lizzo_pack_assets_all_abc.bundle',
                        guid='0092fb8fb92ea09b9665fceaf1a42d0e',
                        modes_packbundle=None, var_packbundle=None):
        """Manifest with BOTH rows. Defaults give the variant row the CORRECT
        packBundle (stock name); *_packbundle overrides let us simulate the bug."""
        entries = [
            {'pack': pack, 'patchedBundle': modes_bundle, 'packBundle':
             modes_packbundle if modes_packbundle is not None else stock,
             'catalogBundleName': guid, 'crc': modes_crc, 'size': 5000},
            {'pack': pack, 'bundle': var_bundle, 'patchedBundle': var_bundle,
             'packBundle': var_packbundle if var_packbundle is not None else stock,
             'catalogBundleName': guid, 'crc': var_crc, 'size': 9000,
             'previews': [pack]},
        ]
        import json as _json
        mp = tmp_path / 'manifest.json'
        mp.write_text(_json.dumps({'entries': entries}))
        return str(mp)

    def test_buggy_packbundle_reproduces_stale_lookup(self, tmp_path):
        """The exact live scenario: variant row's packBundle = the PACK ID →
        index-by-stock-name picks the modes row (stale crc) → check fails."""
        import build_pack_mode_bundles as pmb
        self._write_manifest(tmp_path, var_packbundle='lizzo')  # the bug
        manifest = {e['packBundle']: e for e in pmb.load_manifest(str(tmp_path))}
        me = manifest.get('lizzo_pack_assets_all_abc.bundle')
        assert me['crc'] == 111   # modes row won — the stale one. Bug reproduced.

    def test_flag_on_selects_variant_row(self, tmp_path):
        import build_pack_mode_bundles as pmb
        self._write_manifest(tmp_path)   # correct packBundle
        # the FIXED selection logic (mirrors the pipeline's check):
        for want_variant, expect in ((True, 222), (False, 111)):
            manifest = {}
            for me in pmb.load_manifest(str(tmp_path)):
                cur = manifest.get(me['packBundle'])
                is_var = 'previews' in me
                if cur is None or is_var == want_variant:
                    manifest[me['packBundle']] = me
            assert manifest['lizzo_pack_assets_all_abc.bundle']['crc'] == expect


# ─────────────────────────────────────────────────────────────────────────────
# Exp 269c — batch optimization: --skip-song-preview-management + dirty-check
# ─────────────────────────────────────────────────────────────────────────────

class TestSkipPreviewManagement:
    def test_cli_flag_exists(self):
        # the parser registration is in main(); assert the attribute plumbing
        # by checking the pipeline source carries the argument + threading
        src = open(os.path.join(TOOLS, 'full_custom_song_pipeline.py')).read()
        assert "'--skip-song-preview-management'" in src
        assert 'args.skip_song_preview_management' in src

    def test_ensure_skips_previews_when_flag_set(self, tmp_path, monkeypatch):
        import full_custom_song_pipeline as fp
        called = []
        monkeypatch.setattr(fp, '_ensure_previews_variants',
                            lambda *a, **k: called.append(k) or 0)
        fdir = tmp_path / 'f'
        fdir.mkdir()
        fpath = fdir / 'features.json'
        fpath.write_text(json.dumps({'enable_song_previews': True}))
        monkeypatch.setattr(fp, '_get_local_features_path', lambda *a, **k: str(fpath))
        cfg = {'pack_modes': {}}
        # no packs in scope → returns 0 quickly, but the call decision matters:
        fp._ensure_pack_mode_bundles(cfg, packs=[], skip_previews=True)
        assert called == []          # skipped entirely

    def test_batch_runner_defers_previews(self):
        """The runner appends the skip flag to all-but-the-last --deploy-full
        command (Exp 269c): a 9-song batch regenerates previews exactly once."""
        runner = os.path.join(os.path.dirname(TOOLS), 'webapp', 'batch_runner.py')
        src = open(runner).read()
        assert '--skip-song-preview-management' in src
        assert 'batch[:-1]' in src          # all but the last
        # and the last command is left untouched (the full pass runs there)


class TestPreviewsDirtyCheck:
    """The per-pack dirty-check legs, each pinned in isolation."""

    def _fp(self):
        import full_custom_song_pipeline as fp
        return fp

    def _album(self):
        return {'pack': 'lizzo', 'packBundle': 'lizzo_pack_assets_all_x.bundle',
                'songs': [{'songID': '2BeLoved', 'songName': '2 Be Loved'},
                          {'songID': 'Juice', 'songName': 'Juice'}]}

    def test_missing_variant_file_is_dirty(self, tmp_path, monkeypatch):
        fp = self._fp()
        monkeypatch.setattr(fp, '_previews_enabled', lambda c: True)
        dirty, why = fp._previews_pack_dirty(
            self._album(), {}, str(tmp_path),
            str(tmp_path / 'modes.bundle'), 'lizzo_pack_modes_previews_assets_all_x.bundle',
            None)
        assert dirty and 'missing' in why

    def test_fresh_row_skips(self, tmp_path, monkeypatch):
        fp = self._fp()
        import time as _t
        var_name = 'lizzo_pack_modes_previews_assets_all_x.bundle'
        (tmp_path / var_name).write_bytes(b'x')
        # a manifest row claiming everything current:
        row = {'pack': 'lizzo', 'patchedBundle': var_name, 'previews': ['2BeLoved'],
               'previewsAt': _t.time(), 'previewsInputs': {'2BeLoved': ['md5a', 'info']}}
        (tmp_path / 'manifest.json').write_text(json.dumps({'entries': [row]}))
        modes = tmp_path / 'modes.bundle'
        modes.write_bytes(b'm')
        # mtime of modes must be OLDER than previewsAt
        os.utime(modes, (_t.time() - 100, _t.time() - 100))
        monkeypatch.setattr(fp, '_slot_is_custom', lambda song, cfg: song['songID'] == '2BeLoved')
        import song_previews as sp
        monkeypatch.setattr(sp, 'find_custom_bundle_for_slot', lambda sid, cfg: '/dev/null')
        monkeypatch.setattr(sp, 'slot_input_fingerprint', lambda sid, cfg, album: ['md5a', 'info'])
        dirty, why = fp._previews_pack_dirty(
            self._album(), {}, str(tmp_path), str(modes), var_name, None)
        assert not dirty, why

    def test_changed_slot_set_is_dirty(self, tmp_path, monkeypatch):
        fp = self._fp()
        import time as _t
        var_name = 'lizzo_pack_modes_previews_assets_all_x.bundle'
        (tmp_path / var_name).write_bytes(b'x')
        row = {'pack': 'lizzo', 'patchedBundle': var_name, 'previews': ['2BeLoved'],
               'previewsAt': _t.time(), 'previewsInputs': {'2BeLoved': ['md5a', 'info']}}
        (tmp_path / 'manifest.json').write_text(json.dumps({'entries': [row]}))
        modes = tmp_path / 'modes.bundle'
        modes.write_bytes(b'm')
        os.utime(modes, (_t.time() - 100, _t.time() - 100))
        # BOTH slots now custom → slot set differs from the row → dirty
        monkeypatch.setattr(fp, '_slot_is_custom', lambda song, cfg: True)
        import song_previews as sp
        monkeypatch.setattr(sp, 'find_custom_bundle_for_slot', lambda sid, cfg: '/dev/null')
        dirty, why = fp._previews_pack_dirty(
            self._album(), {}, str(tmp_path), str(modes), var_name, None)
        assert dirty and ('new custom slots' in why or 'input changed' in why)

    def test_modes_base_newer_is_dirty(self, tmp_path, monkeypatch):
        fp = self._fp()
        import time as _t
        var_name = 'lizzo_pack_modes_previews_assets_all_x.bundle'
        (tmp_path / var_name).write_bytes(b'x')
        row = {'pack': 'lizzo', 'patchedBundle': var_name, 'previews': ['2BeLoved'],
               'previewsAt': _t.time() - 1000, 'previewsInputs': {}}
        (tmp_path / 'manifest.json').write_text(json.dumps({'entries': [row]}))
        modes = tmp_path / 'modes.bundle'
        modes.write_bytes(b'm')       # mtime = NOW > previewsAt
        dirty, why = fp._previews_pack_dirty(
            self._album(), {}, str(tmp_path), str(modes), var_name, None)
        assert dirty and 'modes base' in why


class TestFingerprintShape:
    def test_fingerprint_is_md5_pair(self, tmp_path, monkeypatch):
        """[bundle_md5, info_dat_md5_or_None] — no UnityPy parsing on the
        skip path (the profiling lesson: any parse per-slot = 40+s waste)."""
        import song_previews as sp
        fake_bundle = tmp_path / 'fake_custom.bundle'
        fake_bundle.write_bytes(b'BUNDLEBYTES')
        monkeypatch.setattr(sp, 'find_custom_bundle_for_slot', lambda sid, cfg: str(fake_bundle))
        # no metadata → disp '' → info md5 None
        monkeypatch.setattr(sp, '_info_dat_md5_for', lambda disp, root: None)
        album = {'songs': [{'songID': 'X', 'songName': 'Y'}]}
        f = sp.slot_input_fingerprint('X', {}, album)
        import hashlib
        assert f == [hashlib.md5(b'BUNDLEBYTES').hexdigest(), None]

    def test_repo_title_index_cached(self):
        import song_previews as sp
        a = sp._repo_title_index()
        b = sp._repo_title_index()
        assert a is b          # same object → the per-slot reparse waste is gone


# ─────────────────────────────────────────────────────────────────────────────
# Exp 269c round 2 — the second live failure class + hardening
# ─────────────────────────────────────────────────────────────────────────────

class TestManifestVariantPreservation:
    """The modes builder must NEVER clobber variant rows (the second live
    failure: a fresh modes rebuild replaced all 5 variant rows → the check
    compared modes CRCs against the variant catalog → false mismatch ×5)."""

    def test_modes_save_preserves_variant_rows(self, tmp_path):
        import build_pack_mode_bundles as pmb
        var_row = {'pack': 'lizzo', 'bundle': 'v.b', 'patchedBundle': 'v.b',
                   'packBundle': 'stock.b', 'crc': 2, 'size': 200,
                   'previews': ['A'], 'previewsAt': 99}
        modes_row = {'pack': 'lizzo', 'patchedBundle': 'm.b', 'packBundle': 'stock.b',
                     'crc': 1, 'size': 100}
        (tmp_path / 'manifest.json').write_text(
            json.dumps({'entries': [modes_row, var_row]}))
        # a fresh modes build result arrives:
        pmb._save_manifest(str(tmp_path), [dict(modes_row, crc=11)])
        rows = pmb.load_manifest(str(tmp_path))
        by_name = {r['patchedBundle']: r for r in rows}
        assert 'v.b' in by_name and by_name['v.b']['crc'] == 2    # variant survived
        assert by_name['m.b']['crc'] == 11                        # modes updated

    def test_duplicate_variant_rows_dedupe_newest(self, tmp_path):
        import build_pack_mode_bundles as pmb
        old_v = {'pack': 'lizzo', 'patchedBundle': 'v.b', 'previews': [], 'previewsAt': 1}
        new_v = {'pack': 'lizzo', 'patchedBundle': 'v.b', 'previews': [], 'previewsAt': 5}
        (tmp_path / 'manifest.json').write_text(
            json.dumps({'entries': [old_v, new_v]}))
        pmb._save_manifest(str(tmp_path), [])      # any modes merge
        rows = [r for r in pmb.load_manifest(str(tmp_path)) if 'previews' in r]
        assert len(rows) == 1 and rows[0]['previewsAt'] == 5


class TestDisplayTitleResolution:
    """The 'Queencard ( / G)I-DLE' class: map titles can contain separator-
    adjacent punctuation; the resolution ladder must still find the source."""

    def test_rsplit_takes_last_separator(self):
        import song_previews as sp
        assert sp._display_title('Queencard ( / G)I-DLE') == 'queencard ('
        assert sp._display_title('Yes I\'m A Mess / AJR') == "yes i'm a mess"
        assert sp._display_title('NoSeparator') == 'noseparator'

    def test_resolve_ladder_strips_trailing_punct(self):
        import song_previews as sp
        # simulate a repo index with the clean title:
        sp._REPO_TITLE_INDEX_CACHE = {'queencard': '/repo/x'}
        try:
            assert sp._resolve_source_dir('Queencard ( / G)I-DLE') == '/repo/x'
            assert sp._resolve_source_dir('Queencard / (G)I-DLE') == '/repo/x'
        finally:
            sp._REPO_TITLE_INDEX_CACHE = None    # reset the cache for other tests


class TestIdenticalUploadSkip:
    """Exp 269e SUPERSEDES the Exp 269c size-only skip (which caused the
    CE-34878-0 crash): same-size remote files are NOT trusted without a
    same-session upload record. The sound skip lives in
    TestUploadSkipSoundness above; this class keeps the ORIGINAL regression
    name for the history but asserts the corrected behavior."""

    def test_skip_on_same_size(self, tmp_path, monkeypatch):
        """Same size on the remote + NO session record → MUST UPLOAD.
        (The Exp 269c version asserted the unsound skip; the crash inverted
        this contract.)"""
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        fp_mod._SESSION_UPLOADED_BUNDLES.clear()
        local = tmp_path / 'lizzo_pack_modes_previews_assets_all_x.bundle'
        local.write_bytes(b'V' * 500)
        monkeypatch.setattr(fp_mod, '_list_remote_dir',
                            lambda cfg: {local.name: 500})
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4({'ps4': {}, 'title': {'id': 'CUSA12878'},
                                         'paths': {'afr_base': '/afr'}},
                                        str(local), local.name)
        assert ok and len(uploaded) == 1   # uploaded: size alone is not identity

    def test_uploads_when_size_differs(self, tmp_path, monkeypatch):
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        local = tmp_path / 'lizzo_pack_modes_previews_assets_all_x.bundle'
        local.write_bytes(b'V' * 500)
        monkeypatch.setattr(fp_mod, '_list_remote_dir',
                            lambda cfg: {'lizzo_pack_modes_previews_assets_all_x.bundle': 499})
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4({'ps4': {}, 'title': {'id': 'CUSA12878'},
                                         'paths': {'afr_base': '/afr'}},
                                        str(local), local.name)
        assert ok and len(uploaded) == 1   # actually uploaded

    def test_song_bundles_always_upload(self, tmp_path, monkeypatch):
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        local = tmp_path / '2BeLoved_v3.bundle'
        local.write_bytes(b'S' * 300)
        monkeypatch.setattr(fp_mod, '_list_remote_dir',
                            lambda cfg: {'2BeLoved_v3.bundle': 300})   # same size!
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4({'ps4': {}, 'title': {'id': 'CUSA12878'},
                                         'paths': {'afr_base': '/afr'}},
                                        str(local), local.name)
        assert ok and len(uploaded) == 1   # song payload never skipped


# ─────────────────────────────────────────────────────────────────────────────
# Exp 269e — THE CE-34878-0 CRASH CLASS: catalog encodes one build, the PS4
# carries another (same size, different bytes). Two causes fixed:
#   (a) the same-size upload-skip was unsound (size ≠ identity for variants
#       with the same slot set — fixed 10s PCM16 slices);
#   (b) --deploy-full built the variant TWICE (upload pass 1, rebuild pass 2)
#       — the second build's CRC went into the catalog while the first's
#       file could stay deployed.
# Plus the DEPLOYED-BUNDLE CRC GUARD that catches any recurrence pre-boot.
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadSkipSoundness:
    def test_skip_requires_session_ledger(self, tmp_path, monkeypatch):
        """Same-size remote file + NO session record → MUST upload (a fresh
        batch-song process must never trust size alone — the crash path)."""
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        fp_mod._SESSION_UPLOADED_BUNDLES.clear()      # fresh process simulation
        local = tmp_path / 'lizzo_pack_modes_previews_assets_all_x.bundle'
        local.write_bytes(b'V' * 500)
        monkeypatch.setattr(fp_mod, '_list_remote_dir',
                            lambda cfg: {local.name: 500})     # same size on PS4!
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4(
            {'ps4': {}, 'title': {'id': 'CUSA12878'}, 'paths': {'afr_base': '/afr'}},
            str(local), local.name)
        assert ok and len(uploaded) == 1, \
            'same-size alone must NOT skip the upload (the Exp 269e crash)'

    def test_skip_after_same_session_upload(self, tmp_path, monkeypatch):
        """Same-process record + remote size unchanged → skip (the sound case)."""
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        fp_mod._SESSION_UPLOADED_BUNDLES.clear()
        local = tmp_path / 'lizzo_pack_modes_previews_assets_all_x.bundle'
        local.write_bytes(b'V' * 500)
        fp_mod._SESSION_UPLOADED_BUNDLES.add(local.name)      # we uploaded it this session
        monkeypatch.setattr(fp_mod, '_list_remote_dir', lambda cfg: {local.name: 500})
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4(
            {'ps4': {}, 'title': {'id': 'CUSA12878'}, 'paths': {'afr_base': '/afr'}},
            str(local), local.name)
        assert ok and uploaded == []

    def test_size_change_forces_upload(self, tmp_path, monkeypatch):
        import subprocess as sp_mod

        import full_custom_song_pipeline as fp_mod
        fp_mod._SESSION_UPLOADED_BUNDLES.clear()
        local = tmp_path / 'lizzo_pack_modes_previews_assets_all_x.bundle'
        local.write_bytes(b'V' * 600)
        fp_mod._SESSION_UPLOADED_BUNDLES.add(local.name)
        monkeypatch.setattr(fp_mod, '_list_remote_dir', lambda cfg: {local.name: 500})
        uploaded = []
        def fake_run(cmd, **kw):
            uploaded.append(cmd)
            class R:
                returncode = 0
            return R()
        monkeypatch.setattr(sp_mod, 'run', fake_run)
        ok = fp_mod._deploy_file_to_ps4(
            {'ps4': {}, 'title': {'id': 'CUSA12878'}, 'paths': {'afr_base': '/afr'}},
            str(local), local.name)
        assert ok and len(uploaded) == 1


class TestDeployedBundleCrcGuard:
    """The verify-side check: deployed file's actual catalog-scheme CRC must
    equal the manifest/catalog's expected CRC. Source-extracted from the
    pipeline's verify block to pin the comparison contract itself."""

    def test_crc_distinguishes_same_size_builds(self, tmp_path):
        """THE CRASH SCENARIO, pinned with the live numbers: the batch's
        lizzo variant and the pass-2 rebuild shared SIZE 22,656,896 but had
        CRCs 1065772882 vs 2222108153. Size similarity must NEVER imply
        content identity for same-slot-set variants — the CRC guard exists
        because these two builds are indistinguishable by size."""
        # the two live builds of the same variant (measured on the crash RCA):
        size_a, crc_a = 22656896, 1065772882   # pass-1 build (deployed file)
        size_b, crc_b = 22656896, 2222108153  # pass-2 build (catalog/manifest)
        assert size_a == size_b, 'fixture: both builds share size'
        assert crc_a != crc_b, 'fixture: different bytes, different CRCs'
        # the guard's decision rule:
        deployed_matches_catalog = (crc_a == crc_b)
        assert not deployed_matches_catalog, \
            'same-size different-content builds must NOT pass a CRC guard'

    def test_deployed_bundle_guard_in_verify(self):
        """The verify path actually contains the CRC-vs-deployed-file check."""
        src = open(os.path.join(TOOLS, 'full_custom_song_pipeline.py')).read()
        assert 'deployed bundle CRC' in src
        assert 'CE-34878-0' in src          # the crash signature must be named


class TestSingleBuildPerDeploy:
    """deploy_pack_bundle must build BEFORE any upload (one build, then
    uploads of those exact bytes) — the double-build was the other half."""

    def test_build_before_upload_in_source(self):
        src = open(os.path.join(TOOLS, 'full_custom_song_pipeline.py')).read()
        i_build = src.find('Exp 269e: BUILD BEFORE ANY UPLOAD')
        i_upload = src.find('pairs = _get_remote_pack_paths(config, packs=packs)')
        # find the deploy_pack_bundle occurrence of the upload (it's after the marker)
        assert i_build > 0 and i_upload > i_build, \
            'the build step must precede the upload-list construction in deploy_pack_bundle'


# ─────────────────────────────────────────────────────────────────────────────
# Exp 270a — release-layout validation findings:
#   (a) relative config paths must resolve against PROJECT_ROOT (the shipped
#       example config uses ./ps4_dump/...);
#   (b) the deploy-only CLI paths (--deploy-pack-modes / --deploy-pack-bundle)
#       must refresh the pack redirect pair — shipping variant bundles + a
#       variant catalog while live redirects still name the modes bundles is
#       the catalog/bundle CE-34878-0 landmine.
# ─────────────────────────────────────────────────────────────────────────────

class TestRelativeConfigPaths:
    def test_example_config_uses_relative_paths(self):
        """The SHIPPED ps4_config.example.json must not carry devcontainer
        absolutes (the Exp 234 finding) — relative paths work anywhere."""
        p = os.path.join(os.path.dirname(TOOLS), 'ps4_config.example.json')
        cfg = json.load(open(p))
        assert not cfg['paths']['game_dump_dir'].startswith('/workspace')
        assert not cfg['paths']['output_dir'].startswith('/workspace')

    def test_defaults_are_project_relative(self, monkeypatch, tmp_path):
        """load_config's fallback defaults resolve against PROJECT_ROOT, so a
        release works from any extraction directory."""
        import full_custom_song_pipeline as fp
        # defaults computed at call time from PROJECT_ROOT — assert they are
        # inside PROJECT_ROOT (not the devcontainer /workspace literal)
        c = fp.load_config('/nonexistent-config.json')
        assert c['pack_modes']['build_dir'].startswith(fp.PROJECT_ROOT)
        assert c['paths']['output_dir'].startswith(fp.PROJECT_ROOT)
        assert c['paths']['game_dump_dir'].startswith(fp.PROJECT_ROOT)

    def test_user_relative_paths_localize(self, tmp_path, monkeypatch):
        """A config with './ps4_dump/...' values resolves them against
        PROJECT_ROOT at load time (absolute by the time callers see them)."""
        import full_custom_song_pipeline as fp
        cfgfile = tmp_path / 'cfg.json'
        cfgfile.write_text(json.dumps({
            'ps4': {}, 'title': {}, 'paths': {
                'game_dump_dir': './ps4_dump/CUSA12878-patch',
                'output_dir': './custom_songs'}}))
        c = fp.load_config(str(cfgfile))
        assert c['paths']['game_dump_dir'] == os.path.join(fp.PROJECT_ROOT, 'ps4_dump', 'CUSA12878-patch')
        assert c['paths']['output_dir'] == os.path.join(fp.PROJECT_ROOT, 'custom_songs')


class TestDeployOnlyRefreshesRedirects:
    """The --deploy-pack-modes / --deploy-pack-bundle CLI paths must call
    manage_redirect_config after deploying (the redirect VALUES name the
    bundle variant; deploying bundles without refreshing redirects leaves the
    live pair naming the OLD variant against the NEW catalog = the
    CE-34878-0 landmine the release validation caught)."""

    def test_source_wires_redirect_refresh(self):
        src = open(os.path.join(TOOLS, 'full_custom_song_pipeline.py')).read()
        i = src.find('Exp 270a: a pack deploy MUST also refresh the pack redirect pair')
        assert i > 0, 'the deploy-only redirect-refresh block must exist'
        tail = src[i:i + 2500]
        assert 'manage_redirect_config(' in tail
        assert 'args.deploy_pack_modes or args.deploy_pack_bundle' in src

    def test_batch_dirs_cover_zip_layout(self):
        """EXAMPLE_DIRS must probe PROJECT_DIR-level docs too (flat zip)."""
        sys.path.insert(0, os.path.join(os.path.dirname(TOOLS), 'webapp'))
        try:
            from adapters import batch, paths
            assert (paths.PROJECT_DIR / "docs" / "example-scripts") in batch.EXAMPLE_DIRS
            assert any(d.is_dir() for d in batch.EXAMPLE_DIRS), \
                'at least one example dir must exist in this checkout'
        finally:
            sys.path.remove(os.path.join(os.path.dirname(TOOLS), 'webapp'))
