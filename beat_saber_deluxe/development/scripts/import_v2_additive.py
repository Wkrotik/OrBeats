#!/usr/bin/env python3
"""Exp303 offline vanilla V2 -> additive-preparer input. No FTP/stock replacement.
Requires explicit --experimental. Decode full audio with ffmpeg (no clipping or
normalization); preserve playable notes/bombs/walls/basic lights. Refuse BPM
changes, mod requirements, custom geometry and rotation, not silently downgrade.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('additive_prepare',HERE/'prepare_additive_bundle.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


def validate_bookmarks(value, legacy=False):
    """Editor-only labels, separate from objects/BPM events in ChroMapper."""
    if not isinstance(value, list) or len(value) > 10000:
        raise ValueError('invalid editor bookmark list')
    beat, name, color = ('_time', '_name', '_color') if legacy else ('b', 'n', 'c')
    for marker in value:
        if not isinstance(marker, dict) or set(marker) - {beat, name, color} or not {beat, name} <= set(marker):
            raise ValueError('unsupported editor bookmark fields')
        if type(marker[beat]) not in (int, float) or not math.isfinite(marker[beat]) or not -1000000 <= marker[beat] <= 1000000:
            raise ValueError('invalid editor bookmark beat')
        if not isinstance(marker[name], str) or len(marker[name]) > 1000:
            raise ValueError('invalid editor bookmark name')
        if color in marker:
            c = marker[color]
            if not isinstance(c, list) or len(c) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in c):
                raise ValueError('invalid editor bookmark color')


def validate_editor_metadata(custom):
    if not isinstance(custom, dict):
        raise ValueError('V2 chart custom metadata must be an object')
    for key, value in custom.items():
        if key == '_bookmarks':
            validate_bookmarks(value, legacy=True)
            continue
        if key == '_bookmarksUseOfficialBpmEvents' and type(value) is bool:
            continue
        if key == '_time' and type(value) in (int, float) and math.isfinite(value):
            continue  # last editor cursor position
        if key in ('_BPMChanges', '_bpmChanges'):
            # ChroMapper distinguishes these editor-grid markers (BpmChanges)
            # from runtime BpmEvents. Applying them to V2 object times would
            # retime the song incorrectly; retain authored constant-BPM times.
            # See Caeden117/ChroMapper BaseDifficulty.JsonTimeToSongBpmTime and
            # V2Difficulty.LoadCustom at 0d67a67d9b6ee750c412660a43ce34aa889378ae.
            if not isinstance(value, list):
                raise ValueError('invalid V2 editor BPM marker list')
            for marker in value:
                if (not isinstance(marker, dict)
                        or set(marker) - {'_time', '_BPM', '_beatsPerBar', '_metronomeOffset'}
                        or not {'_time', '_BPM'} <= set(marker)):
                    raise ValueError('unsupported V2 editor BPM marker fields')
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in marker.values()):
                    raise ValueError('invalid V2 editor BPM marker values')
                if marker['_BPM'] <= 0 or marker.get('_beatsPerBar', 4) <= 0:
                    raise ValueError('invalid V2 editor BPM marker values')
            continue
        if key in ('_requirements', '_suggestions') and isinstance(value, list) and not value:
            continue
        raise ValueError('unsupported V2 chart custom metadata: ' + key)


def is_empty_wall_placeholder(wall):
    """Only the exact legacy all-zero editor sentinel, never general geometry.

    Numeric timestamps/durations may be JSON0 or0.0. Integer schema fields
    remain actual ints (not bool/float); extra/custom fields are never ignored.
    """
    return (isinstance(wall, dict)
            and set(wall) == {'_time', '_lineIndex', '_type', '_duration', '_width'}
            and all(type(wall[k]) is int and wall[k] == 0
                    for k in ('_lineIndex', '_type', '_width'))
            and all(type(wall[k]) in (int, float) and wall[k] == 0
                    for k in ('_time', '_duration')))


def convert_map(data, allow_rotations=False, *, normalization=None):
    if not str(data.get('_version','')).startswith('2.'):
        raise ValueError('requires V2 beatmap version 2.x')
    if data.get('_BPMChanges'):
        raise ValueError('unsupported top-level V2 BPM changes; runtime timing cannot be dropped')
    validate_editor_metadata(data.get('_customData', {}))
    if '_waypoints' in data and data['_waypoints'] != []:
        raise ValueError('nonempty V2 waypoints are unsupported')
    if set(data)-{'_version','_notes','_obstacles','_events','_BPMChanges','_bookmarks','_customData','_waypoints'}:
        raise ValueError('unsupported V2 fields: ' + ', '.join(sorted(set(data)-{'_version','_notes','_obstacles','_events','_BPMChanges','_bookmarks','_customData','_waypoints'})))
    out={'version':'3.3.0','colorNotes':[],'bombNotes':[],'obstacles':[],'basicBeatmapEvents':[]}
    for n in data.get('_notes',[]):
        if set(n)-{'_time','_lineIndex','_lineLayer','_type','_cutDirection'} or n.get('_type') not in (0,1,3):
            raise ValueError('unsupported V2 note/mod data')
        d={'b':n['_time'],'x':n['_lineIndex'],'y':n['_lineLayer']}
        if n['_type']==3:out['bombNotes'].append(d)
        else:out['colorNotes'].append(dict(d,c=n['_type'],d=n['_cutDirection'],a=0))
    placeholders = 0
    for w in data.get('_obstacles',[]):
        if set(w)-{'_time','_lineIndex','_type','_duration','_width'} or w.get('_type') not in (0,1):
            raise ValueError('unsupported V2 wall/mod data')
        if is_empty_wall_placeholder(w):
            placeholders += 1
            continue
        crouch=w['_type']==1
        out['obstacles'].append({'b':w['_time'],'x':w['_lineIndex'],'y':2 if crouch else 0,
            'd':w['_duration'],'w':w['_width'],'h':3 if crouch else 5})
    rotations=[]
    for e in data.get('_events',[]):
        if set(e)-{'_time','_type','_value','_floatValue'} or type(e.get('_type')) is not int:
            raise ValueError('unsupported V2 event/rotation/mod data')
        if e['_type'] in (14,15) and allow_rotations:
            # BSMG Spawn Rotations / legacy lightshow table: early14, late15;
            # 0..7 => -60,-45,-30,-15,15,30,45,60 degrees. Never mod-light lanes.
            value=e.get('_value')
            if type(value) is not int or not 0<=value<=7:raise ValueError('invalid V2 rotation value')
            if '_floatValue' in e and (type(e['_floatValue']) not in (int,float) or not math.isfinite(e['_floatValue'])):raise ValueError('invalid V2 rotation float')
            rotations.append({'b':e['_time'],'e':e['_type']-14,'r':(-60,-45,-30,-15,15,30,45,60)[value]})
            continue
        if not 0<=e['_type']<=13:raise ValueError('unsupported V2 event/rotation/mod data')
        out['basicBeatmapEvents'].append({'b':e['_time'],'et':e['_type'],'i':e['_value'],'f':e.get('_floatValue',1.0)})
    if rotations:out['rotationEvents']=rotations
    if normalization is not None:
        normalization['empty_v2_wall_placeholders'] = placeholders
    return out


def import_song(source,output,ffmpeg='ffmpeg'):
    source=Path(source).resolve();output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source):raise ValueError('new output outside source required')
    infos=[p for p in source.iterdir() if p.name.lower()=='info.dat'];
    if len(infos)!=1:raise ValueError('one Info.dat required')
    original=json.loads(infos[0].read_text(encoding='utf-8-sig'))
    if not str(original.get('_version','')).startswith('2.') or original.get('_songTimeOffset',0)!=0:
        raise ValueError('constant-offset-free InfoV2 required')
    if any(original.get('_customData',{}).get(k) for k in ('_requirements','_suggestions','_customEnvironment','_customEnvironmentHash')):
        raise ValueError('mod/environment requirements unsupported')
    audio=prepare.local_file(source,original['_songFilename'])
    info={k:original[k] for k in ('_songName','_songSubName','_songAuthorName','_levelAuthorName','_beatsPerMinute') if k in original}
    info.update(_version='2.1.0',_songTimeOffset=0,_songFilename='audio.wav',_difficultyBeatmapSets=[])
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.additive-import-',dir=output.parent) as tmp:
        stage=Path(tmp)/'input';stage.mkdir()
        ignored_placeholders = {}
        for group in original.get('_difficultyBeatmapSets',[]):
            if group.get('_beatmapCharacteristicName')!='Standard':raise ValueError('only Standard supported')
            ds=[]
            for diff in group.get('_difficultyBeatmaps',[]):
                if any(diff.get('_customData',{}).get(k) for k in ('_requirements','_suggestions')):raise ValueError('mod requirements unsupported')
                name=diff['_difficulty']
                if name not in prepare.DIFFICULTIES or any(x['_difficulty']==name for x in ds):raise ValueError('unknown/duplicate difficulty')
                raw=prepare.local_file(source,diff['_beatmapFilename']).read_bytes()
                normalization = {}
                normalized=convert_map(json.loads(raw.decode('utf-8-sig')), normalization=normalization)
                if normalization['empty_v2_wall_placeholders']:
                    ignored_placeholders[name] = normalization['empty_v2_wall_placeholders']
                filename=name+'.dat';(stage/filename).write_bytes(prepare.canonical(normalized))
                ds.append({'_difficulty':name,'_difficultyRank':diff['_difficultyRank'],'_beatmapFilename':filename,
                    '_noteJumpMovementSpeed':diff['_noteJumpMovementSpeed'],'_noteJumpStartBeatOffset':diff['_noteJumpStartBeatOffset']})
            info['_difficultyBeatmapSets'].append({'_beatmapCharacteristicName':'Standard','_difficultyBeatmaps':ds})
        # Decoder is executed without shell; no source/plugin/script is executed.
        subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(audio),'-vn','-ac','2','-ar','44100','-c:a','pcm_s16le',str(stage/'audio.wav')],check=True,timeout=120)
        (stage/'Info.dat').write_bytes(prepare.canonical(info))
        checked=prepare.load_song(stage)
        report={'source_audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'source_info_sha256':hashlib.sha256(infos[0].read_bytes()).hexdigest(),
            'title':checked['title'],'duration_seconds':checked['samples']/44100,'note_counts':{k:len(v['colorNotes']) for k,v in checked['maps'].items()},
            'discarded_editor_metadata':'bookmarks and cosmetic Info/difficulty labels/contributors only; no playable notes/walls/bombs/basic events discarded',
            'ignored_v2_wall_placeholders': ignored_placeholders,
            'stock_modified':False,'deployed':False}
        (stage/'import-report.json').write_bytes(prepare.canonical(report));stage.rename(output)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experimental',required=True,action='store_true');p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(import_song(a.source,a.output),indent=2))
if __name__=='__main__':main()
