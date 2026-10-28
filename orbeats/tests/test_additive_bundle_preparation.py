"""Offline preparation proof: synthetic WAV/map and local tiny bundle fixture only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'development/scripts/prepare_additive_bundle.py'
spec = importlib.util.spec_from_file_location('additive_bundle_prepare', SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
TEMPLATE = ROOT / 'custom_songs/quick_test.bundle'


@pytest.fixture
def song(tmp_path):
    folder = tmp_path / 'song'
    prepare.generate_probe(folder)
    return folder


def change_info(song, change):
    p = song / 'Info.dat'
    info = json.loads(p.read_bytes());change(info);p.write_text(json.dumps(info))


def test_probe_input_is_new_simple_content(song):
    result = prepare.load_song(song)
    assert result['title'] == 'BSD Additive Tone Test'
    assert result['samples'] == 12 * 44100
    assert result['bpm'] == 120
    assert len(result['maps']) == 5
    assert all(len(v['colorNotes']) == 9 for v in result['maps'].values())
    assert result['pcm'] != bytes(len(result['pcm']))
    with pytest.raises(ValueError, match='exists'):
        prepare.generate_probe(song)


def test_input_identity_is_path_independent(song, tmp_path):
    import shutil
    other = tmp_path / 'other';shutil.copytree(song, other)
    assert prepare.load_song(song)['source_sha256'] == prepare.load_song(other)['source_sha256']
    p = other / 'Easy.dat';data = json.loads(p.read_bytes());data['colorNotes'][0]['x'] = 3
    p.write_text(json.dumps(data))
    assert prepare.load_song(song)['source_sha256'] != prepare.load_song(other)['source_sha256']


@pytest.mark.parametrize('name', ['../outside.wav', '/etc/passwd', 'bad\\file.wav', None])
def test_unsafe_song_files_refused(song, name):
    change_info(song, lambda i: i.update(_songFilename=name))
    with pytest.raises(ValueError):prepare.load_song(song)


def test_symlink_escape_refused(song, tmp_path):
    outside = tmp_path / 'outside.dat';outside.write_text('{}')
    (song / 'escaped.dat').symlink_to(outside)
    change_info(song, lambda i: i['_difficultyBeatmapSets'][0]['_difficultyBeatmaps'][0].update(_beatmapFilename='escaped.dat'))
    with pytest.raises(ValueError, match='escapes'):prepare.load_song(song)


@pytest.mark.parametrize('bad', [0, -1, float('nan'), float('inf'), True, '120'])
def test_bad_bpm_refused(song, bad):
    change_info(song, lambda i: i.update(_beatsPerMinute=bad))
    with pytest.raises(ValueError):prepare.load_song(song)


@pytest.mark.parametrize('mutation', ['v4', 'mods', 'out-of-time', 'angle', 'lane', 'arcs', 'empty'])
def test_unsupported_beatmap_refused(song, mutation):
    p = song / 'Easy.dat';d = json.loads(p.read_bytes())
    if mutation == 'v4':d['version'] = '4.0.0'
    if mutation == 'mods':d['customData'] = {'_requirements': ['Noodle Extensions']}
    if mutation == 'out-of-time':d['colorNotes'][0]['b'] = 10000
    if mutation == 'angle':d['colorNotes'][0]['a'] = float('nan')
    if mutation == 'lane':d['colorNotes'][0]['x'] = 4
    if mutation == 'arcs':d['sliders'] = [{'b': 1}]
    if mutation == 'empty':d['colorNotes'] = []
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):prepare.load_song(song)


def test_info_restrictions(song):
    change_info(song, lambda i: i.update(_songTimeOffset=1))
    assert prepare.load_song(song)['presentation']['offset'] == 1
    change_info(song, lambda i: i.update(_songTimeOffset=11))
    with pytest.raises(ValueError):prepare.load_song(song)


def test_roundtrip_bundle_relinks_maps_audio_and_names(song, tmp_path):
    pytest.importorskip('UnityPy')
    before = prepare.digest(TEMPLATE.read_bytes())
    out = tmp_path / 'prepared'
    manifest = prepare.prepare(song, TEMPLATE, out)
    assert manifest['runtime_ready'] is False and manifest['deployment_attempted'] is False
    assert manifest['stock_assets_modified'] is False
    assert manifest['level_id'].startswith('bsd_additive_')
    assert manifest['cab_name'] != 'CAB-6c9e66546e3e23434517417298a18b91'
    assert manifest['note_counts'] == {k: 9 for k in prepare.DIFFICULTIES}
    assert prepare.validate(out, prepare.load_song(song)) == manifest
    assert before == prepare.digest(TEMPLATE.read_bytes())
    import UnityPy
    env = UnityPy.load(str(out / manifest['bundle']['file']))
    bf = next(iter(env.files.values()))
    resource = bf.files[manifest['cab_name'] + '.resource'].bytes
    assert resource[:4] == b'FSB5'
    import struct
    assert (struct.unpack_from('<Q', resource, 60)[0] >> 34) & ((1 << 30) - 1) == 529200
    clip = next(r.read_typetree() for r in env.objects if r.class_id == 83)
    assert clip['m_Length'] == 12
    assert clip['m_Resource']['m_Size'] == len(resource)
    with pytest.raises(ValueError, match='already exists'):prepare.prepare(song, TEMPLATE, out)
    # Independent verify rejects modified/truncated output before Unity parsing.
    p = out / manifest['bundle']['file'];p.write_bytes(p.read_bytes()[:-1])
    with pytest.raises(ValueError, match='hash/length'):prepare.validate(out)


def test_refused_inputs_create_no_output(song, tmp_path):
    change_info(song, lambda i: i.update(_beatsPerMinute=0))
    out = tmp_path / 'must-not-exist'
    with pytest.raises(ValueError):prepare.prepare(song, TEMPLATE, out)
    assert not out.exists()


def test_refuse_output_in_input(song):
    with pytest.raises(ValueError, match='outside'):prepare.prepare(song, TEMPLATE, song / 'out')


def test_cli_requires_explicit_experimental_optin(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), '--generate-probe', str(tmp_path / 'out')], capture_output=True, text=True)
    assert r.returncode != 0 and '--experimental' in r.stderr
    assert not (tmp_path / 'out').exists()


def test_no_console_deploy_or_stock_replacement_interface():
    code = SCRIPT.read_text()
    for forbidden in ['from ftplib', 'import socket', 'storbinary', '--deploy-full', 'catalog_pack_modes', 'RTLD_DEFAULT']:
        assert forbidden not in code
    r = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
    assert r.returncode == 0 and '--verify' in r.stdout
    assert '--deploy' not in r.stdout


def test_bundle_is_deterministic_and_preserves_non_aligned_last_sample(song, tmp_path):
    import wave
    p = song / 'probe.wav'
    with wave.open(str(p), 'rb') as w:
        pcm = w.readframes(w.getnframes())
    # Non-aligned input must retain the last sample with no truncation/padding.
    with wave.open(str(p), 'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(pcm + bytes(4))
    a = prepare.prepare(song, TEMPLATE, tmp_path / 'one')
    b = prepare.prepare(song, TEMPLATE, tmp_path / 'two')
    assert a == b
    assert a['pcm_frames'] == 529201
    assert a['duration_seconds'] == 529201 / 44100
    assert (tmp_path / 'one' / a['bundle']['file']).read_bytes() == (tmp_path / 'two' / b['bundle']['file']).read_bytes()
    prepare.validate(tmp_path / 'one', prepare.load_song(song))


def test_verify_refuses_false_ready_claim(song, tmp_path):
    out = tmp_path / 'prepared'
    prepare.prepare(song, TEMPLATE, out)
    p = out / 'manifest.json';d = json.loads(p.read_bytes());d['runtime_ready'] = True
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match='must not claim'):prepare.validate(out)


@pytest.mark.parametrize('artist',['','   '])
def test_empty_artist_has_explicit_nonempty_wire_fallback(song,artist):
    change_info(song,lambda i:i.update(_songAuthorName=artist))
    assert prepare.load_song(song)['author']=='Unknown artist'


def test_invalid_artist_type_still_rejected(song):
    change_info(song,lambda i:i.update(_songAuthorName={'not':'text'}))
    with pytest.raises(ValueError,match='author'):prepare.load_song(song)
