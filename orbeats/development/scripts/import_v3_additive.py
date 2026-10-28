#!/usr/bin/env python3
"""Exp310 offline vanilla V3 -> constant-tempo additive input; no FTP.
Bake supported BPM events into absolute note/light/wall times, preserving seconds
and both endpoints of walls/arcs. Reject chains/mod geometry rather than drop it.
Cosmetic colors/labels and editor metadata are not imported. Event boxes use
explicit reviewed Weave routing; other maps keep stock-environment fallback.
"""
import argparse
import bisect
import copy
import importlib.util
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any

spec = importlib.util.spec_from_file_location('additive_prepare', Path(__file__).with_name('prepare_additive_bundle.py'))
assert spec is not None and spec.loader is not None
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
spec_v2 = importlib.util.spec_from_file_location('additive_v2', Path(__file__).with_name('import_v2_additive.py'))
assert spec_v2 is not None and spec_v2.loader is not None
v2 = importlib.util.module_from_spec(spec_v2)
spec_v2.loader.exec_module(v2)


class Tempo:
    def __init__(self, base, events):
        self.base = prepare.finite(base, 'base BPM', 1, 1000)
        self.beats, self.seconds, self.bpms = [0.0], [0.0], [self.base]
        if not isinstance(events, list) or len(events) > 10000:
            raise ValueError('invalid BPM event list')
        last = -1
        for e in events:
            if not isinstance(e, dict) or set(e) - {'b', 'm'} or 'm' not in e:
                raise ValueError('invalid BPM event shape')
            b = prepare.finite(e.get('b', 0), 'BPM event beat', 0, 1000000)
            m = prepare.finite(e['m'], 'BPM event value', 1, 1000)
            if b <= last:
                raise ValueError('BPM events must be strictly increasing')
            last = b
            if b == 0:
                self.bpms[0] = m
            else:
                t = self.time(b)
                self.beats.append(b); self.seconds.append(t); self.bpms.append(m)

    def time(self, beat):
        beat = prepare.finite(beat, 'beat position', 0, 1000000)
        i = bisect.bisect_right(self.beats, beat) - 1
        return self.seconds[i] + (beat - self.beats[i]) * 60 / self.bpms[i]

    def baked(self, beat):
        return self.time(beat) * self.base / 60


def convert_map(data, bpm):
    if not str(data.get('version', '')).startswith('3.'):
        raise ValueError('V3 beatmap required')
    supported = {'version', 'colorNotes', 'bombNotes', 'obstacles', 'basicBeatmapEvents', 'bpmEvents', 'sliders', 'colorBoostBeatmapEvents',
                 'lightColorEventBoxGroups', 'lightRotationEventBoxGroups'}
    empty_only = {'rotationEvents', 'burstSliders', 'waypoints',
                  'lightTranslationEventBoxGroups', 'vfxEventBoxGroups'}
    known = supported | empty_only | {'customData', '_customData', '_fxEventsCollection',
                                      'basicEventTypesWithKeywords', 'useNormalEventsAsCompatibleEvents'}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError('unsupported V3 fields: ' + ', '.join(unknown))
    refused = sorted(k for k in empty_only if data.get(k))
    if refused:
        labels = {'burstSliders': 'burstSliders (chains)',
                  'rotationEvents': 'rotationEvents (rotating maps)'}
        raise ValueError('unsupported V3 features: ' + ', '.join(labels.get(k, k) for k in refused))
    data = copy.deepcopy(data)
    # Native JsonUtility supplies zero for omitted serialized scalar fields.
    defaults = {
        'colorNotes': dict.fromkeys(('b', 'x', 'y', 'c', 'd', 'a'), 0),
        'bombNotes': dict.fromkeys(('b', 'x', 'y'), 0),
        'obstacles': dict.fromkeys(('b', 'x', 'y', 'd', 'w', 'h'), 0),
        'basicBeatmapEvents': dict.fromkeys(('b', 'et', 'i', 'f'), 0),
        'sliders': dict.fromkeys(('b', 'c', 'x', 'y', 'd', 'mu', 'tb', 'tx', 'ty', 'tc', 'tmu', 'm'), 0),
    }
    for key, shape in defaults.items():
        entries = data.get(key, [])
        if not isinstance(entries, list) or len(entries) > 200000:
            raise ValueError('invalid bounded V3 ' + ('sliders (arcs)' if key == 'sliders' else key))
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or set(entry) - set(shape):
                raise ValueError('unsupported V3 ' + ('sliders (arcs)' if key == 'sliders' else key) + ' fields')
            entries[index] = dict(shape, **entry)
    prepare.validate_arcs(data.get('sliders', []), 1000000)
    if data.get('_customData'):
        raise ValueError('unsupported legacy custom data')
    custom = data.get('customData', {})
    if not isinstance(custom, dict) or set(custom) - {'lighter', 'time', 'bookmarks', 'bookmarksUseOfficialBpmEvents'}:
        raise ValueError('unsupported V3 custom/mod data')
    if 'bookmarks' in custom:
        v2.validate_bookmarks(custom['bookmarks'])
    if 'bookmarksUseOfficialBpmEvents' in custom and type(custom['bookmarksUseOfficialBpmEvents']) is not bool:
        raise ValueError('invalid editor bookmark timing flag')
    fx = data.get('_fxEventsCollection', {})
    if not isinstance(fx, dict) or set(fx) - {'_il', '_fl'} or any(fx.values()):
        raise ValueError('unsupported FX events')
    keywords = data.get('basicEventTypesWithKeywords', {})
    if keywords not in ({}, {'d': []}):
        raise ValueError('unsupported light keywords')
    if type(data.get('useNormalEventsAsCompatibleEvents', False)) is not bool:
        raise ValueError('invalid compatibility flag')
    tempo = Tempo(bpm, data.get('bpmEvents', []))
    from additive_lighting import boosts, constant_boxes, has_boxes, validate_boxes
    validate_boxes(data, 1000000)
    if has_boxes(data) and any(not math.isclose(rate, tempo.bpms[0], rel_tol=1e-8, abs_tol=1e-6) for rate in tempo.bpms):
        raise ValueError('event-box lighting with changing BPM is not yet supported; distribution timing must be preserved')
    out: dict[str, Any] = {'version': '3.3.0'}
    if 'useNormalEventsAsCompatibleEvents' in data:
        out['useNormalEventsAsCompatibleEvents'] = data['useNormalEventsAsCompatibleEvents']
    boost_events = boosts(data.get('colorBoostBeatmapEvents', []), 1000000)
    if boost_events:
        out['colorBoostBeatmapEvents'] = boost_events
        for event in out['colorBoostBeatmapEvents']:
            event['b'] = tempo.baked(event['b'])
    if has_boxes(data):
        out.update(constant_boxes(data, tempo.base / tempo.bpms[0]))
    for key in ('colorNotes', 'bombNotes', 'obstacles', 'basicBeatmapEvents', 'sliders'):
        entries = data.get(key, [])
        if not isinstance(entries, list) or len(entries) > 200000:
            raise ValueError('invalid bounded V3 entries')
        out[key] = copy.deepcopy(entries)
        for e in out[key]:
            if not isinstance(e, dict):
                raise ValueError('invalid V3 entry object')
            old = prepare.finite(e['b'], 'beat position', 0, 1000000)
            if key == 'sliders':
                e['tb'] = tempo.baked(e['tb'])
            if key == 'obstacles':
                duration = prepare.finite(e['d'], 'wall duration', 0, 1000000)
                e['d'] = tempo.baked(old + duration) - tempo.baked(old)
            e['b'] = tempo.baked(old)
    return out


def cosmetic_only(custom, allowed):
    empty_lists = {'_requirements', '_suggestions', '_warnings', '_information'}
    empty_strings = {'_customEnvironment', '_customEnvironmentHash'}
    offsets = {'_editorOffset', '_editorOldOffset'}
    if not isinstance(custom, dict):
        raise ValueError('unsupported requirements/custom metadata')
    for key, value in custom.items():
        if key in {'_firstNoteBeat', '_introPadSeconds'} and key in allowed:
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100000:
                raise ValueError('invalid descriptive timing annotation: ' + key)
            continue
        if key in allowed:
            continue
        if key in empty_lists and value == []:
            continue
        if key in empty_strings and value == '':
            continue
        if key in offsets and type(value) in (int, float) and math.isfinite(value):
            continue
        raise ValueError('unsupported requirements/custom metadata: ' + key)


def import_song(source, output, ffmpeg='ffmpeg'):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError('new output outside source required')
    infos = [p for p in source.iterdir() if p.name.lower() == 'info.dat']
    if len(infos) != 1: raise ValueError('one Info.dat required')
    original = json.loads(infos[0].read_text(encoding='utf-8-sig'))
    if not str(original.get('_version', '')).startswith('2.'):
        raise ValueError('InfoV2 required')
    # Descriptive annotations are not playback offsets; retain authored note/audio timing.
    cosmetic_only(original.get('_customData', {}), {'_editors', '_contributors', '_firstNoteBeat', '_introPadSeconds'})
    audio = prepare.local_file(source, original['_songFilename'])
    info = {k: original[k] for k in ('_songName', '_songSubName', '_songAuthorName', '_levelAuthorName', '_beatsPerMinute') if k in original}
    for key in ('_orbeatsLufs', '_colorSchemes'):
        if key in original: info[key] = original[key]
    info.update(_version='2.1.0', _songTimeOffset=prepare.finite(original.get('_songTimeOffset', 0), 'song offset', -10, 10), _songFilename='audio.wav', _difficultyBeatmapSets=[])
    native_audio = None
    decoded_audio = False
    if original.get('_orbeatsAudioData'):
        native_audio = json.loads(prepare.local_file(source, original['_orbeatsAudioData']).read_bytes())
        from additive_v4_native import audio as validate_audio
        validate_audio(native_audio)
        info['_orbeatsAudioData'] = 'native-audio.dat'
    from additive_lighting import has_boxes
    force_native_v3 = False
    preserve_v3 = False
    for group in original.get('_difficultyBeatmapSets', []):
        for diff in group.get('_difficultyBeatmaps', []):
            probe = json.loads(prepare.local_file(source, diff['_beatmapFilename']).read_text(encoding='utf-8-sig'))
            if str(probe.get('_version', '')).startswith('2.') and group.get('_beatmapCharacteristicName') in ('90Degree','360Degree') and any(e.get('_type') in (14,15) for e in probe.get('_events',[])):
                force_native_v3 = preserve_v3 = True
            if str(probe.get('version', '')).startswith('3.'):
                tempo = Tempo(original['_beatsPerMinute'], probe.get('bpmEvents', []))
                preserve_v3 |= bool(probe.get('rotationEvents') or probe.get('vfxEventBoxGroups') or probe.get('_fxEventsCollection'))
                force_native_v3 |= bool(probe.get('rotationEvents')) or any(probe.get(k) for k in ('burstSliders', 'lightTranslationEventBoxGroups', 'vfxEventBoxGroups')) or (has_boxes(probe) and len(set(tempo.bpms)) > 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.additive-v3-', dir=output.parent) as tmp:
        stage = Path(tmp) / 'input'; stage.mkdir()
        seen, tempos, skipped, default_njs = set(), {}, [], {}
        active_environments = {}
        ignored_placeholders = {}
        from additive_modes import key as map_key
        for g in original.get('_difficultyBeatmapSets', []):
            mode = g.get('_beatmapCharacteristicName')
            map_key(mode, 'Easy')
            ds = []
            for d in g.get('_difficultyBeatmaps', []):
                cosmetic_only(d.get('_customData', {}), {'_difficultyLabel', '_colorLeft', '_colorRight', '_envColorLeft', '_envColorRight', '_envColorLeftBoost', '_envColorRightBoost', '_envColorWhite', '_envColorWhiteBoost', '_obstacleColor'})
                label = d['_difficulty']; name = map_key(mode, label)
                if name in seen: raise ValueError('unknown/duplicate difficulty')
                seen.add(name)
                raw = json.loads(prepare.local_file(source, d['_beatmapFilename']).read_text(encoding='utf-8-sig'))
                try:
                    if str(raw.get('_version', '')).startswith('2.'):
                        normalization = {}
                        raw = v2.convert_map(raw, allow_rotations=mode in ('90Degree','360Degree'), normalization=normalization, base_bpm=original['_beatsPerMinute'])
                        if normalization['empty_v2_wall_placeholders']:
                            ignored_placeholders[name] = normalization['empty_v2_wall_placeholders']
                    advanced = False
                    native = str(raw.get('version', '')).startswith('4.')
                    if str(raw.get('version', '')).startswith('3.'):
                        from additive_lighting import has_boxes
                        tempo = Tempo(original['_beatsPerMinute'], raw.get('bpmEvents', []))
                        advanced = force_native_v3
                        if advanced:
                            from additive_v3_native import audio_from_tempo, convert
                            if not decoded_audio:
                                subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(audio), '-vn', '-ac', '2', '-ar', '44100', '-c:a', 'pcm_s16le', str(stage / 'audio.wav')], check=True, timeout=120)
                                decoded_audio = True
                            import wave
                            with wave.open(str(stage / 'audio.wav')) as wave_audio:
                                derived_audio = audio_from_tempo(tempo, wave_audio.getnframes())
                            if native_audio is not None and native_audio != derived_audio:
                                raise ValueError('per-difficulty BPM regions differ; native audio routing requires one shared timeline')
                            native_audio = derived_audio
                            info['_orbeatsAudioData'] = 'native-audio.dat'
                            if preserve_v3:
                                from additive_v3_native import validate_preserved, lightshow_preserved
                                validate_preserved(raw, native_audio, prepare.resolve_note_jump_speed(name, d.get('_noteJumpMovementSpeed', 0)))
                                generated_light = lightshow_preserved(raw)
                            else:
                                raw, generated_light = convert(raw, native_audio, prepare.resolve_note_jump_speed(name, d.get('_noteJumpMovementSpeed', 0)))
                            native = True
                    if native:
                        from additive_v4_native import audio as validate_audio, chart as validate_chart, lighting as validate_lighting
                        if native_audio is None:
                            raise ValueError('native V4 requires reviewed AudioData')
                        if not (advanced and preserve_v3): validate_chart(raw, validate_audio(native_audio), prepare.resolve_note_jump_speed(name, d.get('_noteJumpMovementSpeed', 10)))
                        native_light = generated_light if advanced else json.loads(prepare.local_file(source, d['_orbeatsLightshow']).read_bytes())
                        if not (advanced and preserve_v3): validate_lighting(native_light, validate_audio(native_audio))
                        normalized = raw
                    elif str(raw.get('_version', '')).startswith('2.'):
                        normalized = convert_map(v2.convert_map(raw, base_bpm=original['_beatsPerMinute']), original['_beatsPerMinute'])
                    else:
                        normalized = convert_map(raw, original['_beatsPerMinute'])
                except ValueError as exc:
                    raise ValueError(f"{name} ({d['_beatmapFilename']}): {exc}") from exc
                from additive_lighting import NATIVE_ENVIRONMENTS, has_boxes
                environment = original.get('_environmentName')
                index = d.get('_environmentNameIdx')
                if index is not None:
                    names = original.get('_environmentNames', [])
                    if type(index) is not int or not isinstance(names, list) or index < 0:
                        raise ValueError('invalid lighting environment index')
                    if names:
                        if index >= len(names) or not isinstance(names[index], str):
                            raise ValueError('invalid lighting environment index')
                        environment = names[index]
                    elif index != 0:
                        raise ValueError('invalid lighting environment index')
                    # Empty table + index0 uses the authored root environment.
                if environment in NATIVE_ENVIRONMENTS:
                    info['_environmentName'] = environment
                if ((bool(native_light.get('eventBoxGroups')) or has_boxes(native_light) or bool(native_light.get('vfxEventBoxGroups'))) if native else has_boxes(normalized)):
                    if environment not in NATIVE_ENVIRONMENTS:
                        raise ValueError('event-box lighting requires an available PS4 stock environment; requested ' + str(environment))
                    info['_environmentName'] = environment
                if not any(normalized.get(k) for k in ('colorNotes', 'bombNotes', 'obstacles', 'sliders', 'chains', 'arcs')):
                    skipped.append(name + ' (lighting-only; no playable objects)')
                    continue
                active_environments[name] = environment
                tempos[name] = raw.get('bpmEvents', [])
                filename = name.replace('/', '-') + '.dat'; (stage / filename).write_bytes(prepare.canonical(normalized))
                njs = prepare.resolve_note_jump_speed(name, d.get('_noteJumpMovementSpeed', 0))
                if d.get('_noteJumpMovementSpeed', 0) <= 0:
                    default_njs[name] = njs
                ds.append({'_difficulty': label, '_difficultyRank': d['_difficultyRank'], '_beatmapFilename': filename,
                           '_noteJumpMovementSpeed': njs, '_noteJumpStartBeatOffset': d.get('_noteJumpStartBeatOffset', 0)})
                if d.get('_customData'): ds[-1]['_customData'] = {k:v for k,v in d['_customData'].items() if k in __import__('additive_presentation').LEGACY or k == '_difficultyLabel'}
                if '_beatmapColorSchemeIdx' in d: ds[-1]['_beatmapColorSchemeIdx'] = d['_beatmapColorSchemeIdx']
                if native and advanced and preserve_v3: ds[-1]['_orbeatsNativeV3'] = True
                if native:
                    light_name = name.replace('/', '-') + '.lightshow.dat'
                    (stage / light_name).write_bytes(prepare.canonical(native_light))
                    ds[-1]['_orbeatsLightshow'] = light_name
            if ds:
                info['_difficultyBeatmapSets'].append({'_beatmapCharacteristicName': mode, '_difficultyBeatmaps': ds})
        if not info['_difficultyBeatmapSets']:
            raise ValueError('No playable Standard difficulties; lighting-only charts cannot be installed.')
        if info.get('_environmentName') and any(v != info['_environmentName'] for v in active_environments.values()):
            raise ValueError('mixed per-difficulty environments need independent routing; not supported yet')
        if not decoded_audio:
            subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(audio), '-vn', '-ac', '2', '-ar', '44100', '-c:a', 'pcm_s16le', str(stage / 'audio.wav')], check=True, timeout=120)
        if native_audio is not None:
            (stage / 'native-audio.dat').write_bytes(prepare.canonical(native_audio))
        (stage / 'Info.dat').write_bytes(prepare.canonical(info))
        checked = prepare.load_song(stage)
        report = {'title': checked['title'], 'source_audio_sha256': prepare.digest(audio.read_bytes()),
                  'source_info_sha256': prepare.digest(infos[0].read_bytes()), 'original_bpm_events': tempos,
                  'skipped_difficulties': skipped, 'default_njs': default_njs,
                  'ignored_v2_wall_placeholders': ignored_placeholders,
                  'timing': 'Native sample BPM regions preserved' if native_audio else 'BPM events baked into constant-BPM coordinates; wall and arc start+end seconds preserved',
                  'lighting_environment': info.get('_environmentName', 'stock fallback'),
                  'lighting_counts': {k: {field: len(v.get(field, [])) for field in ('colorBoostBeatmapEvents', 'lightColorEventBoxGroups', 'lightRotationEventBoxGroups')} for k, v in checked['maps'].items()},
                  'arc_counts': {k: len(v.get('sliders', v.get('arcs', []))) for k, v in checked['maps'].items()},
                  'not_imported': 'Editor metadata and difficulty labels; unsupported custom mods are refused',
                  'note_counts': {k: prepare.note_count(v) for k, v in checked['maps'].items()},
                  'duration_seconds': checked['samples'] / 44100, 'stock_modified': False, 'deployed': False}
        (stage / 'import-report.json').write_bytes(prepare.canonical(report)); stage.rename(output)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experimental', required=True, action='store_true')
    p.add_argument('--source', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); print(json.dumps(import_song(a.source, a.output), indent=2))
