#!/usr/bin/env python3
"""Offline additive bundle preparation. NO FTP/deploy/stock edits.

Normalized InfoV2/native V3/V4 payloads plus bounded stereo44.1/48kHz audio. Original Vorbis
packets are preferred when supported; PCM16 remains the safe fallback. The
companion owns closed-title deployment; this CLI only prepares/verifies files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
DIFFICULTIES = {'Easy': 0, 'Normal': 1, 'Hard': 2, 'Expert': 3, 'ExpertPlus': 4}
MAX_AUDIO_SECONDS = 600


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def complete_v3_keywords(data):
    """Materialize the empty list required by PS4 ConvertBasicEvents.

    Missing/empty containers deserialize with a null inner `d` list. The native
    converter enumerates it without a null check (CUSA12878/2.04 RVA0x9e9b2e).
    This is schema completion, not support for authored keyword routing.
    """
    if data.get('basicEventTypesWithKeywords', {}) not in ({}, {'d': []}):
        raise ValueError('unsupported light keywords')
    data['basicEventTypesWithKeywords'] = {'d': []}


def local_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('invalid relative song filename')
    p = (root / name).resolve()
    if Path(name).is_absolute() or not p.is_relative_to(root) or not p.is_file():
        raise ValueError('song file escapes input directory or is missing: ' + name)
    return p


def finite(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('invalid ' + name)
    return float(value)


def validate_arcs(entries, maxbeat):
    """Vanilla V3 SliderData only; do not reinterpret chains/mod geometry."""
    if not isinstance(entries, list) or len(entries) > 100000:
        raise ValueError('invalid sliders (arcs) list')
    shape = {'b','c','x','y','d','mu','tb','tx','ty','tc','tmu','m'}
    for index, arc in enumerate(entries):
        prefix = f'sliders (arc {index})'
        if not isinstance(arc, dict) or set(arc) != shape:
            raise ValueError(prefix + ': unsupported fields; vanilla V3 SliderData required')
        head = finite(arc['b'], prefix + ' head beat', 0, maxbeat)
        tail = finite(arc['tb'], prefix + ' tail beat', 0, maxbeat)
        if tail <= head:
            raise ValueError(prefix + ': tail beat must be after head beat')
        for key, maximum in [('c',1),('x',3),('tx',3),('y',2),('ty',2),('d',8),('tc',8),('m',2)]:
            if type(arc[key]) is not int or not 0 <= arc[key] <= maximum:
                raise ValueError(prefix + ': invalid ' + key)
        for key in ('mu', 'tmu'):
            finite(arc[key], prefix + ' ' + key, 0, 100)


def resolve_note_jump_speed(difficulty, value=0):
    """Resolve the native game's <=0 default sentinel before strict preparation.

    BeatmapDifficultyMethods.NoteJumpMovementSpeed RVA0x97cf70 and
    DefaultNoteJumpMovementSpeed RVA0x97cfb0 in CUSA12878 patch2.04:
    Easy/Normal/Hard=10, Expert=12, ExpertPlus=16; positive values preserved.
    Invalid types/nonfinite values never become defaults.
    """
    difficulty = difficulty.rsplit('/', 1)[-1]
    if difficulty not in DIFFICULTIES:
        raise ValueError('unknown difficulty for NJS')
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('invalid NJS')
    if value <= 0:
        return {'Expert': 12, 'ExpertPlus': 16}.get(difficulty, 10)
    return finite(value, 'NJS', .1, 100)


def note_count(data):
    if str(data.get('version', '')).startswith('4.'):
        return len(data.get('colorNotes', [])) + sum(data['chainsData'][e.get('ci', 0)].get('c', 0) - 1 for e in data.get('chains', []))
    return len(data.get('colorNotes', [])) + sum(e['sc'] - 1 for e in data.get('burstSliders', []))


def stored_audio_data(song, rate, samples):
    if song.get('audio_data') is not None:
        from additive_v4_native import resample_audio
        return resample_audio(song['audio_data'], rate, samples, song['source_sha256'])
    return {'version': '4.0.0', 'songChecksum': song['source_sha256'],
            'songSampleCount': samples, 'songFrequency': rate,
            'bpmData': [{'si': 0, 'ei': samples, 'sb': 0.0, 'eb': samples / rate * song['bpm'] / 60}]}


def load_song(folder):
    folder = Path(folder).resolve()
    raw_info = local_file(folder, 'Info.dat').read_bytes()
    info = json.loads(raw_info)
    if not str(info.get('_version', '')).startswith('2.'):
        raise ValueError('prototype requires Info.dat v2')
    title = info.get('_songName')
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError('invalid song title')
    author = info.get('_songAuthorName', '')
    if not isinstance(author, str):
        raise ValueError('invalid song author')
    author = author.strip() or 'Unknown artist'
    bpm = finite(info.get('_beatsPerMinute'), 'BPM', 1, 1000)
    if info.get('_customData'):
        raise ValueError('offset/mod-dependent Info.dat is not supported')
    from additive_lighting import REVIEWED_ENVIRONMENT, NATIVE_ENVIRONMENTS
    environment = info.get('_environmentName')
    if environment not in NATIVE_ENVIRONMENTS | {None}:
        raise ValueError('unreviewed lighting environment')
    audio = local_file(folder, info.get('_songFilename')).read_bytes()
    import io
    with wave.open(io.BytesIO(audio), 'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) != (2, 2, 44100, 'NONE'):
            raise ValueError('prototype requires PCM16 WAV 44.1kHz stereo')
        samples = w.getnframes()
        if not 44100 <= samples <= MAX_AUDIO_SECONDS * 44100:
            raise ValueError('audio duration outside prototype bounds')
        pcm = w.readframes(samples)
    if len(pcm) != samples * 4:
        raise ValueError('truncated WAV')
    from additive_presentation import from_info
    presentation = from_info(info)
    maps, native_lights = {}, {}
    audio_data = None
    if info.get('_orbeatsAudioData'):
        from additive_v4_native import audio as validate_audio, audio_duration_matches
        audio_data = json.loads(local_file(folder, info['_orbeatsAudioData']).read_bytes())
        validate_audio(audio_data)
        if not audio_duration_matches(audio_data, 44100, samples):
            raise ValueError('native AudioData duration disagrees with audio')
    for entry in info.get('_difficultyBeatmapSets', []):
        from additive_modes import key as map_key
        mode = entry.get('_beatmapCharacteristicName')
        map_key(mode, 'Easy')
        for diff in entry.get('_difficultyBeatmaps', []):
            finite(diff.get('_noteJumpMovementSpeed',10),'NJS',.1,100)
            finite(diff.get('_noteJumpStartBeatOffset',0),'jump offset',-10,10)
            name = map_key(mode, diff.get('_difficulty'))
            if name in maps:
                raise ValueError('unknown/duplicate difficulty')
            # Palette/editor metadata was validated by from_info; no mod metadata passes.
            data = json.loads(local_file(folder, diff.get('_beatmapFilename')).read_bytes())
            if str(data.get('version', '')).startswith('4.') or diff.get('_orbeatsNativeV3'):
                from additive_v4_native import chart as validate_chart, lighting as validate_lighting
                if audio_data is None:
                    raise ValueError('native V4 AudioData missing')
                maxbeat = validate_audio(audio_data)
                if not diff.get('_orbeatsNativeV3'): validate_chart(data, maxbeat, diff.get('_noteJumpMovementSpeed', 10))
                native_light = json.loads(local_file(folder, diff.get('_orbeatsLightshow')).read_bytes())
                if diff.get('_orbeatsNativeV3'):
                    from additive_v3_native import validate_preserved, lightshow_preserved
                    _, boxes = validate_preserved(data, audio_data, diff.get('_noteJumpMovementSpeed',10))
                    if native_light != lightshow_preserved(data): raise ValueError('native V3 lightshow mismatch')
                    complete_v3_keywords(data)
                    native_light = lightshow_preserved(data)
                else: boxes = validate_lighting(native_light, maxbeat)
                if boxes and environment not in NATIVE_ENVIRONMENTS:
                    raise ValueError('native event boxes require reviewed environment')
                maps[name], native_lights[name] = data, native_light
                continue
            if not str(data.get('version', '')).startswith('3.') or data.get('customData') or data.get('_customData'):
                raise ValueError('only unmodded V3 beatmaps are supported')
            # Initial subset intentionally refuses unsupported geometry rather
            # than silently discarding chains/walls/events or mod effects.
            allowed = {'version', 'colorNotes', 'bombNotes', 'obstacles', 'sliders', 'burstSliders',
                       'basicBeatmapEvents', 'colorBoostBeatmapEvents', 'bpmEvents', 'rotationEvents',
                       'waypoints', 'basicEventTypesWithKeywords', 'useNormalEventsAsCompatibleEvents',
                       'lightColorEventBoxGroups', 'lightRotationEventBoxGroups', 'lightTranslationEventBoxGroups'}
            if set(data) - allowed:
                raise ValueError('unknown V3 fields')
            supported = {'version','colorNotes','bombNotes','obstacles','basicBeatmapEvents','sliders','useNormalEventsAsCompatibleEvents','basicEventTypesWithKeywords',
                         'colorBoostBeatmapEvents','lightColorEventBoxGroups','lightRotationEventBoxGroups'}
            for key, value in data.items():
                if key not in supported and value:
                    raise ValueError('unsupported proof geometry/events: ' + key)
            if type(data.get('useNormalEventsAsCompatibleEvents', False)) is not bool:
                raise ValueError('invalid lighting compatibility flag')
            notes = data.get('colorNotes', [])
            if not isinstance(notes, list) or not 1 <= len(notes) <= 100000:
                raise ValueError('proof needs a nonempty bounded colorNotes list')
            for note in notes:
                if set(note) != {'b', 'x', 'y', 'c', 'd', 'a'}:
                    raise ValueError('invalid V3 color-note shape')
                finite(note['b'], 'note beat', 0, samples / 44100 * bpm / 60)
                finite(note['a'], 'note angle', -180, 180)
                for key, maximum in [('x', 3), ('y', 2), ('c', 1), ('d', 8)]:
                    if type(note[key]) is not int or not 0 <= note[key] <= maximum:
                        raise ValueError('invalid color-note ' + key)
            maxbeat = samples / 44100 * bpm / 60
            validate_arcs(data.get('sliders', []), maxbeat)
            from additive_lighting import boosts, has_boxes, is_basic_light_event_type, validate_boxes
            boosts(data.get('colorBoostBeatmapEvents', []), maxbeat)
            validate_boxes(data, maxbeat)
            if has_boxes(data) and environment not in NATIVE_ENVIRONMENTS:
                raise ValueError('event-box lighting requires explicit reviewed environment')
            for key, shape in [('bombNotes', {'b','x','y'}),
                               ('obstacles', {'b','x','y','d','w','h'}),
                               ('basicBeatmapEvents', {'b','et','i','f'})]:
                entries=data.get(key, [])
                if not isinstance(entries,list) or len(entries)>200000:raise ValueError('invalid '+key)
                for e in entries:
                    if set(e)!=shape:raise ValueError('invalid '+key+' shape')
                    finite(e['b'],key+' beat',0,maxbeat)
                    if key=='bombNotes':
                        for k,hi in [('x',3),('y',2)]:
                            if type(e[k]) is not int or not 0<=e[k]<=hi:raise ValueError('invalid bomb coordinate')
                    elif key=='obstacles':
                        finite(e['d'],'wall duration',0,maxbeat-e['b'])
                        for k,lo,hi in [('x',-4,7),('y',0,2),('w',1,4),('h',1,5)]:
                            if type(e[k]) is not int or not lo<=e[k]<=hi:raise ValueError('invalid wall geometry')
                        # Vanilla integer decorative walls may sit beside the four note lanes.
                        # Keep a bounded extent; do NOT widen note coordinates or accept mod geometry.
                        if e['x']+e['w']>8:raise ValueError('wall exceeds bounded vanilla extent')
                    else:
                        if not is_basic_light_event_type(e['et']) or type(e['i']) is not int:raise ValueError('invalid basic event')
                        finite(e['f'],'basic event float',-100000,100000)
            # Complete the minimal V3 schema; never fill it with stock notes.
            for key in ('bombNotes', 'obstacles', 'sliders', 'burstSliders', 'bpmEvents',
                        'rotationEvents', 'waypoints', 'basicBeatmapEvents',
                        'colorBoostBeatmapEvents', 'lightColorEventBoxGroups',
                        'lightRotationEventBoxGroups', 'lightTranslationEventBoxGroups'):
                data.setdefault(key, [])
            complete_v3_keywords(data)
            data.setdefault('useNormalEventsAsCompatibleEvents', False)
            maps[name] = data
    if not maps:
        raise ValueError('no supported beatmaps')
    # Hash tagged content/lengths, not directory paths or user-selected stock IDs.
    identity = {'info': info, 'maps': maps, 'audio_sha256': digest(audio)}
    if native_lights:
        identity.update(native_lights=native_lights, audio_data=audio_data)
    source = canonical(identity)
    return {'title': title, 'author': author[:200], 'environment': environment,
            'bpm': bpm, 'samples': samples, 'pcm': pcm, 'wav': audio, 'maps': maps,
            'native_lights': native_lights, 'audio_data': audio_data, 'presentation': presentation,
            'source_sha256': digest(source), 'source_audio_sha256': digest(audio)}


def build_bundle(template: Path, song, level_id, compressed_fsb=None):
    import io

    import UnityPy
    from hevag_encoder import build_pcm16_fsb5
    from UnityPy.files import BundleFile
    from UnityPy.streams import EndianBinaryReader
    env = UnityPy.load(str(template))
    if len(env.files) != 1:
        raise ValueError('requires one UnityFS bundle')
    bundle = next(iter(env.files.values()))
    if not isinstance(bundle, BundleFile):
        raise ValueError('requires a UnityFS bundle')
    serialized = [(k, v) for k, v in bundle.files.items() if hasattr(v, 'objects')]
    resources = [k for k in bundle.files if k.endswith('.resource')]
    if len(serialized) != 1 or len(resources) != 1:
        raise ValueError('requires one serialized file and one audio resource')
    old_cab, cab = serialized[0]
    if cab.externals:
        raise ValueError('template external serialized references not supported')
    objects = list(cab.objects.values())
    def only(class_id):
        entries = [r for r in objects if r.class_id == class_id]
        if len(entries) != 1:
            raise ValueError('unexpected template object count for class ' + str(class_id))
        return entries[0]
    level = only(114)
    clip = only(83)
    container = only(142)
    tree = level.read_typetree()
    if '_difficultyBeatmapSets' not in tree or '_audioDataAsset' not in tree:
        raise ValueError('not a BeatmapLevelDataSO template')
    new_cab = 'CAB-' + digest((level_id + song['source_sha256']).encode())[:32]
    rate, samples = audio_coordinates(compressed_fsb, song)
    # Never inherit codec/seek/padding metadata from the template. Reuse only
    # the serialized Unity schema, even if the template is already compressed.
    fsb = compressed_fsb if compressed_fsb is not None else build_pcm16_fsb5(io.BytesIO(song['wav']), pad_to_size=0)
    res: Any = EndianBinaryReader(fsb)  # UnityPy attaches bundle-entry metadata dynamically.
    res.flags = 0
    res.BaseOffset = 0
    bundle.files.pop(old_cab);bundle.files.pop(resources[0])
    bundle.files[new_cab] = cab
    bundle.files[new_cab + '.resource'] = res
    ct = clip.read_typetree()
    ct.update({'m_Name': level_id, 'm_Channels': 2, 'm_Frequency': rate,
               'm_Length': samples / rate, 'm_CompressionFormat': 1 if compressed_fsb is not None else 0, 'm_BitsPerSample': 16,
               'm_LoadType': 0, 'm_PreloadAudioData': True, 'm_LoadInBackground': False})
    ct['m_Resource'] = {'m_Source': f'archive:/{new_cab}/{new_cab}.resource',
                        'm_Offset': 0, 'm_Size': len(fsb)}
    clip.save_typetree(ct)
    def text(pid, data, name):
        r = cab.objects[pid];t = r.read_typetree()
        t['m_Name'] = name
        t['m_Script'] = gzip.compress(canonical(data), mtime=0).decode('utf-8', 'surrogateescape')
        r.save_typetree(t)
    audio_pid = tree['_audioDataAsset']['m_PathID']
    text(audio_pid, stored_audio_data(song, rate, samples), level_id + '.audio.gz')
    sets = tree['_difficultyBeatmapSets']
    standard = [s for s in sets if s['_beatmapCharacteristicSerializedName'] == 'Standard']
    if len(standard) != 1:
        raise ValueError('template Standard set is ambiguous')
    by_diff = {d['_difficulty']: d for d in standard[0]['_difficultyBeatmaps']}
    extra_pids = []
    import copy
    from additive_modes import parts, order
    output_sets = {}
    if not by_diff: raise ValueError('template has no Standard schema')
    for name in sorted(song['maps'], key=order):
        mode, label = parts(name)
        entry = copy.deepcopy(by_diff.get(DIFFICULTIES[label], next(iter(by_diff.values()))))
        entry['_difficulty'] = DIFFICULTIES[label]
        for field in ('_beatmapAsset', '_lightshowAsset'):
            pid = max(cab.objects) + 1
            cloned = copy.copy(cab.objects[entry[field]['m_PathID']])
            cloned.path_id = pid; cab.objects[pid] = cloned; extra_pids.append(pid)
            entry[field] = {'m_FileID': 0, 'm_PathID': pid}
        text(entry['_beatmapAsset']['m_PathID'], song['maps'][name], level_id + name.replace('/', '-') + '.beatmap.gz')
        from additive_lighting import lightshow
        text(entry['_lightshowAsset']['m_PathID'], song.get('native_lights', {}).get(name, lightshow(song['maps'][name])), level_id + name.replace('/', '-') + '.lightshow.gz')
        output_sets.setdefault(mode, []).append(entry)
    tree['m_Name'] = level_id + 'BeatmapLevelData'
    tree['_difficultyBeatmapSets'] = [dict(_beatmapCharacteristicSerializedName=k, _difficultyBeatmaps=v) for k,v in output_sets.items()]
    # Remove unused beatmap payloads instead of shipping unrelated template maps.
    for name, number in DIFFICULTIES.items():
        if number in by_diff:
            text(by_diff[number]['_beatmapAsset']['m_PathID'],
                 {'version': '3.3.0', 'colorNotes': []}, level_id + name + '.unused.gz')
    level.save_typetree(tree)
    asset_name = level_id + 'BeatmapLevelData.asset'
    bt = container.read_typetree()
    if bt.get('m_Dependencies') or len(bt.get('m_Container', [])) != 1:
        raise ValueError('template container/dependencies unsupported')
    entry = bt['m_Container'][0][1]
    if entry['asset']['m_PathID'] != level.path_id:
        raise ValueError('container does not point to level data')
    if entry['preloadIndex']!=0 or entry['preloadSize']!=len(bt['m_PreloadTable']):
        raise ValueError('unsupported template preload span')
    bt['m_PreloadTable'].extend({'m_FileID':0,'m_PathID':pid} for pid in extra_pids)
    entry['preloadSize']=len(bt['m_PreloadTable'])
    bt.update({'m_Name': level_id, 'm_AssetBundleName': level_id,
               'm_Container': [('assets/bsd_additive/' + asset_name.lower(), entry)]})
    container.save_typetree(bt)
    return bundle.save(packer='none'), asset_name, new_cab


def audio_coordinates(fsb, song):
    """Sample coordinates of the stored audio, not the normalized baseline WAV."""
    if fsb is None:
        return 44100, song['samples']
    descriptor = struct.unpack_from('<Q', fsb, 60)[0]
    rate = {8: 44100, 9: 48000}.get((descriptor >> 1) & 15)
    if rate is None:
        raise ValueError('unsupported selected audio rate')
    return rate, (descriptor >> 34) & ((1 << 30) - 1)


def select_audio(original_audio, song):
    """Choose the proven profile, otherwise retain the normal PCM16 output."""
    if original_audio is None:
        return None, 'no original compressed source supplied'
    from vorbis_audio import MAX_BYTES, build_fsb
    original_audio = Path(original_audio)
    if original_audio.stat().st_size > MAX_BYTES:
        return None, 'original source exceeds compressed audio bound'
    data = original_audio.read_bytes()
    if data[:5] != b'OggS\x00':
        return None, 'source is not Ogg Vorbis'
    try:
        import io

        import soundfile as sf
        try:
            rate = sf.info(io.BytesIO(data)).samplerate
        except sf.LibsndfileError as exc:
            return None, 'unsupported original audio: ' + str(exc)
        fsb, frames, _ = build_fsb(data, sample_rate=rate)
    except (ImportError, OSError):
        return None, 'open-source Vorbis codec libraries unavailable'
    except ValueError as exc:
        return None, str(exc)
    if ((rate == 44100 and frames != song['samples']) or
            (rate == 48000 and abs(frames * 44100 - song['samples'] * rate) > rate)):
        return None, 'original Vorbis and normalized PCM sample counts disagree'
    return fsb, None


def prepare(folder, template, output, original_audio=None):
    output = Path(output).resolve();template = Path(template).resolve()
    if output.exists():
        raise ValueError('output already exists; refusing overwrite')
    if output.is_relative_to(Path(folder).resolve()):
        raise ValueError('output must be outside the song input directory')
    song = load_song(folder)
    pcm_level_id = 'bsd_additive_' + song['source_sha256'][:24]
    compressed_fsb, fallback_reason = select_audio(original_audio, song)
    rate, frames = audio_coordinates(compressed_fsb, song)
    level_id = pcm_level_id
    if compressed_fsb is not None:
        from vorbis_audio import PROFILE, PROFILE_48000
        profile = PROFILE if rate == 44100 else PROFILE_48000
        identity = digest((profile + song['source_sha256'] + digest(compressed_fsb)).encode())
        level_id = 'bsd_additive_' + identity[:24]
    template_bytes = template.read_bytes()
    blob, asset, cab = build_bundle(template, song, level_id, compressed_fsb)
    manifest = {'schema': 1, 'kind': 'bsd_additive_bundle_candidate',
                'runtime_ready': False, 'deployment_attempted': False,
                'reason': 'offline candidate; an exact reviewed runtime profile is required before deployment',
                'level_id': level_id, 'asset_name': asset, 'cab_name': cab,
                'song_name': song['title'], 'song_author': song['author'], 'bpm': song['bpm'],
                'duration_seconds': frames / rate, 'pcm_frames': frames,
                'audio_sample_rate': rate,
                'audio_codec': 'vorbis' if compressed_fsb is not None else 'pcm16',
                'audio_format': (f'FSB5 Vorbis stereo {rate}, original packets, fresh seek table'
                    if compressed_fsb is not None else 'FSB5 PCM16 stereo 44100, unpadded'),
                'difficulties': sorted(song['maps'], key=__import__('additive_modes').order),
                'note_counts': {k: note_count(v) for k, v in song['maps'].items()},
                'difficulty_stats': {__import__('additive_modes').key(g['_beatmapCharacteristicName'], d['_difficulty']): {'notes':note_count(song['maps'][__import__('additive_modes').key(g['_beatmapCharacteristicName'], d['_difficulty'])]),
                    'bombs':len(song['maps'][__import__('additive_modes').key(g['_beatmapCharacteristicName'], d['_difficulty'])].get('bombNotes', [])), 'obstacles':len(song['maps'][__import__('additive_modes').key(g['_beatmapCharacteristicName'], d['_difficulty'])].get('obstacles', [])),
                    'njs':d.get('_noteJumpMovementSpeed',10), 'jump_offset':d.get('_noteJumpStartBeatOffset',0)}
                    for g in json.loads(local_file(Path(folder).resolve(),'Info.dat').read_bytes())['_difficultyBeatmapSets'] for d in g['_difficultyBeatmaps']},
                'audio_load_settings':'decompress on load, preload TRUE, background FALSE',
                'source_sha256': song['source_sha256'], 'source_audio_sha256': song['source_audio_sha256'],
                'template_sha256': digest(template_bytes),
                'bundle': {'file': level_id + '.bundle', 'bytes': len(blob), 'sha256': digest(blob)},
                'proposed_remote_directory': '/data/GoldHEN/AFR/CUSA12878/additive/' + level_id,
                'stock_assets_modified': False}
    if any('/' in k for k in song['maps']): manifest['characteristics'] = sorted({__import__('additive_modes').parts(k)[0] for k in song['maps']})
    if song.get('presentation'): manifest['presentation'] = song['presentation']
    if song.get('native_lights'):
        manifest['native_v4'] = True
        manifest['native_v3'] = [k for k,v in song['maps'].items() if str(v.get('version','')).startswith('3.')]
    if song.get('environment'):
        manifest['environment'] = song['environment']
    if compressed_fsb is not None:
        manifest['audio_profile'] = profile
        manifest['pcm_level_id'] = pcm_level_id  # Preserve existing PCM installations on reimport.
    else:
        manifest['audio_fallback_reason'] = fallback_reason
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bsd-additive-', dir=output.parent) as tmp:
        staging = Path(tmp) / 'candidate';staging.mkdir()
        (staging / manifest['bundle']['file']).write_bytes(blob)
        (staging / 'manifest.json').write_bytes(canonical(manifest) + b'\n')
        validate(staging, song)
        staging.rename(output)
    return manifest


def validate(folder, expected_song=None):
    from additive_lighting import NATIVE_ENVIRONMENTS
    import UnityPy
    from UnityPy.files import BundleFile
    folder = Path(folder).resolve()
    manifest = json.loads((folder / 'manifest.json').read_bytes())
    import re
    level_id = manifest['level_id']
    if not re.fullmatch(r'bsd_additive_[0-9a-f]{24}', level_id):
        raise ValueError('invalid additive level ID')
    blob = local_file(folder, manifest['bundle']['file']).read_bytes()
    if len(blob) != manifest['bundle']['bytes'] or digest(blob) != manifest['bundle']['sha256']:
        raise ValueError('bundle hash/length mismatch')
    env = UnityPy.load(blob)
    if len(env.files) != 1:
        raise ValueError('requires one UnityFS bundle')
    bundle = next(iter(env.files.values()))
    if not isinstance(bundle, BundleFile):
        raise ValueError('requires a UnityFS bundle')
    objs = list(env.objects)
    lev = [r.read_typetree() for r in objs if r.class_id == 114]
    clips = [r.read_typetree() for r in objs if r.class_id == 83]
    containers = [r.read_typetree() for r in objs if r.class_id == 142]
    if len(lev) != 1 or len(clips) != 1 or len(containers) != 1:
        raise ValueError('invalid prepared object counts')
    level, clip, container = lev[0], clips[0], containers[0]
    if manifest.get('schema') != 1 or manifest.get('kind') != 'bsd_additive_bundle_candidate':
        raise ValueError('unsupported candidate schema')
    if manifest.get('runtime_ready') is not False or manifest.get('deployment_attempted') is not False:
        raise ValueError('offline candidate must not claim deployment/readiness')
    if manifest['asset_name'] != level_id + 'BeatmapLevelData.asset':
        raise ValueError('asset name does not match level ID')
    if level['m_Name'] != level_id + 'BeatmapLevelData' or clip['m_Name'] != level_id:
        raise ValueError('prepared names disagree')
    if container['m_Dependencies'] or container['m_Container'][0][0] != 'assets/bsd_additive/' + manifest['asset_name'].lower():
        raise ValueError('prepared container/dependencies disagree')
    cab = next(v for v in bundle.files.values() if hasattr(v, 'objects'))
    if len(cab.externals) or not clip['m_Resource']['m_Source'].startswith('archive:/' + manifest['cab_name'] + '/'):
        raise ValueError('resource alias/external dependency')
    resource = bundle.files.get(manifest['cab_name'] + '.resource')
    if resource is None:
        raise ValueError('missing audio resource')
    fsb = resource.bytes
    codec = manifest.get('audio_codec', 'pcm16')  # Retain old PCM candidate compatibility.
    if codec not in ('pcm16', 'vorbis'):
        raise ValueError('unsupported audio codec')
    rate = manifest.get('audio_sample_rate', 44100)
    if type(rate) is not int or rate not in ((44100, 48000) if codec == 'vorbis' else (44100,)):
        raise ValueError('unsupported audio sample rate')
    frames = manifest['pcm_frames']
    if type(frames) is not int or not rate <= frames <= MAX_AUDIO_SECONDS * rate:
        raise ValueError('invalid audio frame count')
    if abs(manifest['duration_seconds'] - frames / rate) > 1e-8:
        raise ValueError('audio duration/frame metadata mismatch')
    if expected_song and abs(frames / rate - expected_song['samples'] / 44100) > 1 / 44100:
        raise ValueError('source and prepared audio durations disagree')
    if (len(fsb) < 125 or fsb[:4] != b'FSB5' or
            clip['m_Resource']['m_Offset'] != 0 or clip['m_Resource']['m_Size'] != len(fsb) or
            clip['m_Channels'] != 2 or clip['m_Frequency'] != rate or
            clip['m_CompressionFormat'] != (1 if codec == 'vorbis' else 0) or clip['m_BitsPerSample'] != 16 or
            clip['m_LoadType'] != 0 or not clip['m_PreloadAudioData'] or clip['m_LoadInBackground'] or
            abs(clip['m_Length'] - manifest['duration_seconds']) > .0001):
        raise ValueError('audio resource/header metadata mismatch')
    if codec == 'vorbis':
        from vorbis_audio import PROFILE, PROFILE_48000, verify_fsb
        if manifest.get('audio_profile') != (PROFILE if rate == 44100 else PROFILE_48000):
            raise ValueError('unsupported Vorbis audio profile')
        verify_fsb(fsb, manifest['pcm_frames'], expected_song['pcm'] if expected_song else None, sample_rate=rate)
    else:
        if (struct.unpack_from('<III', fsb, 4) != (1, 1, 65) or struct.unpack_from('<I', fsb, 24)[0] != 2 or
                struct.unpack_from('<I', fsb, 20)[0] != len(fsb) - 125 or
                len(fsb) - 125 != manifest['pcm_frames'] * 4):
            raise ValueError('audio PCM16 payload length mismatch')
        if expected_song:
            # Existing PCM builder's float->int16 one-LSB rounding/peak limiter.
            import numpy as np
            source_pcm = np.frombuffer(expected_song['pcm'], dtype='<i2').astype(np.int32)
            output_pcm = np.frombuffer(fsb[125:], dtype='<i2').astype(np.int32)
            peak = float(np.max(np.abs(source_pcm)))
            scale = min(1., .99 * 32768 / peak) if peak else 1.
            if np.max(np.abs(output_pcm - source_pcm * scale)) > 2:
                raise ValueError('independent PCM audio roundtrip mismatch')
    if (struct.unpack_from('<Q', fsb, 60)[0] >> 34) & ((1 << 30) - 1) != manifest['pcm_frames']:
        raise ValueError('audio sample descriptor mismatch')
    # Independently reopen and compare every routed map and sample metadata.
    sets = level['_difficultyBeatmapSets']
    if not sets or any(v['_beatmapCharacteristicSerializedName'] not in __import__('additive_modes').MODES for v in sets):
        raise ValueError('invalid prepared characteristic')
    def data(pid):
        t = cab.objects[pid].read_typetree()
        return json.loads(gzip.decompress(t['m_Script'].encode('utf-8', 'surrogateescape')))
    audio = data(level['_audioDataAsset']['m_PathID'])
    if audio['songSampleCount'] != manifest['pcm_frames'] or audio['songFrequency'] != rate:
        raise ValueError('audio sample metadata mismatch')
    expected_bpm = stored_audio_data(expected_song, rate, frames)['bpmData'] if expected_song else audio.get('bpmData')
    from additive_v4_native import audio as validate_audio
    maxbeat = validate_audio(audio)
    if expected_song and audio != stored_audio_data(expected_song, rate, frames):
        raise ValueError('native audio metadata roundtrip mismatch')
    if audio.get('bpmData') != expected_bpm:
        raise ValueError('audio BPM sample coordinates mismatch')
    from additive_modes import key as map_key, DIFFS
    routed = [(map_key(group['_beatmapCharacteristicSerializedName'], DIFFS[e['_difficulty']]), e) for group in sets for e in group['_difficultyBeatmaps']]
    if [k for k, _ in routed] != manifest['difficulties']:
        raise ValueError('difficulty routing mismatch')
    for name, entry in routed:
        lighting = data(entry['_lightshowAsset']['m_PathID'])
        bm = data(entry['_beatmapAsset']['m_PathID'])
        if name in manifest.get('native_v3', []):
            from additive_v3_native import validate_preserved, lightshow_preserved
            count, boxes = validate_preserved(bm, audio, manifest['difficulty_stats'][name]['njs'])
            if count != manifest['note_counts'][name] or lighting != lightshow_preserved(bm): raise ValueError('native V3 roundtrip mismatch')
            if boxes and manifest.get('environment') not in NATIVE_ENVIRONMENTS: raise ValueError('native V3 environment missing')
            if expected_song and bm != expected_song['maps'][name]: raise ValueError('native V3 source changed')
            continue
        if str(bm.get('version', '')).startswith('4.'):
            from additive_v4_native import chart as validate_chart, lighting as validate_lighting
            stat = manifest['difficulty_stats'][name]
            count = validate_chart(bm, maxbeat, stat['njs'])
            if validate_lighting(lighting, maxbeat) and manifest.get('environment') not in NATIVE_ENVIRONMENTS:
                raise ValueError('native lighting environment missing')
            if count != manifest['note_counts'][name] or not manifest.get('native_v4'):
                raise ValueError('native map statistics/profile mismatch')
            if expected_song and (bm != expected_song['maps'][name] or lighting != expected_song['native_lights'][name]):
                raise ValueError('native chart/lightshow roundtrip mismatch')
            continue
        from additive_lighting import REVIEWED_ENVIRONMENT, NATIVE_ENVIRONMENTS, boosts, has_boxes, lightshow, validate_boxes
        if type(bm.get('useNormalEventsAsCompatibleEvents', False)) is not bool:
            raise ValueError('invalid prepared lighting compatibility flag')
        boosts(bm.get('colorBoostBeatmapEvents', []), frames / rate * manifest['bpm'] / 60)
        validate_boxes(bm, frames / rate * manifest['bpm'] / 60)
        if has_boxes(bm) and manifest.get('environment') != REVIEWED_ENVIRONMENT:
            raise ValueError('prepared lighting environment missing')
        if manifest.get('environment') not in NATIVE_ENVIRONMENTS | {None} or (expected_song and manifest.get('environment') != expected_song.get('environment')):
            raise ValueError('lighting environment mismatch')
        if lighting != lightshow(expected_song['maps'][name] if expected_song else bm):
            raise ValueError('lightshow roundtrip mismatch')
        if note_count(bm) != manifest['note_counts'][name] or (expected_song and bm != expected_song['maps'][name]):
            raise ValueError('beatmap roundtrip mismatch')
    return manifest


def generate_probe(folder):
    folder = Path(folder).resolve()
    if folder.exists():
        raise ValueError('probe output already exists')
    # Synthesized sparse low-volume tones, not third-party music. All five
    # difficulties deliberately share a simple, comfortable color-note pattern.
    samples = 44100 * 12
    pcm = bytearray(samples * 4)
    for beat in range(2, 22):
        start = int(beat * .5 * 44100)
        for i in range(441):
            value = int(1800 * math.sin(2 * math.pi * (440 if beat % 2 else 660) * i / 44100))
            struct.pack_into('<hh', pcm, (start + i) * 4, value, value)
    info = {'_version': '2.1.0', '_songName': 'BSD Additive Tone Test',
            '_songSubName': '', '_songAuthorName': 'BSD generated test', '_levelAuthorName': 'BSD',
            '_beatsPerMinute': 120, '_songTimeOffset': 0, '_songFilename': 'probe.wav',
            '_difficultyBeatmapSets': [{'_beatmapCharacteristicName': 'Standard',
                                       '_difficultyBeatmaps': []}]}
    folder.mkdir(parents=True)
    with wave.open(str(folder / 'probe.wav'), 'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(pcm)
    for name, number in DIFFICULTIES.items():
        info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps'].append(
            {'_difficulty': name, '_difficultyRank': (number + 1) * 2 - 1,
             '_beatmapFilename': name + '.dat', '_noteJumpMovementSpeed': 10,
             '_noteJumpStartBeatOffset': 0})
        (folder / (name + '.dat')).write_bytes(canonical({'version': '3.3.0',
            'colorNotes': [{'b': b, 'x': 1 if (b // 2) % 2 else 2, 'y': 0,
                            'c': (b // 2) % 2, 'd': 1, 'a': 0} for b in range(4, 21, 2)]}))
    (folder / 'Info.dat').write_bytes(canonical(info) + b'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experimental', action='store_true', required=True,
                        help='acknowledge offline development-only, NOT deployable output')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--song-dir', type=Path)
    group.add_argument('--generate-probe', type=Path)
    group.add_argument('--verify', type=Path)
    parser.add_argument('--template', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.generate_probe:
            if args.template or args.output:parser.error('probe generation accepts no template/output')
            generate_probe(args.generate_probe);print('Generated private synthetic test input only. No console access.')
        elif args.verify:
            if args.template or args.output:parser.error('verification accepts no template/output')
            print(json.dumps(validate(args.verify), indent=2))
        else:
            if not args.template or not args.output:parser.error('--song-dir requires --template and --output')
            print(json.dumps(prepare(args.song_dir, args.template, args.output), indent=2))
    except (ValueError, OSError, KeyError, EOFError, wave.Error) as e:
        parser.exit(1, 'Refused additive preparation: ' + str(e) + '\n')


if __name__ == '__main__':
    main()
