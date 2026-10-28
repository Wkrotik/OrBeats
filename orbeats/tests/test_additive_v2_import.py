"""No network or third-party songs: tiny V2 conversion/PCM fixtures only."""
import importlib.util
import json
from pathlib import Path
import shutil
import wave

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v2_import',ROOT/'development/scripts/import_v2_additive.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)


def v2():
    return {'_version':'2.0.0','_notes':[
        {'_time':1,'_lineIndex':1,'_lineLayer':0,'_type':0,'_cutDirection':1},
        {'_time':2,'_lineIndex':2,'_lineLayer':1,'_type':3,'_cutDirection':0}],
        '_obstacles':[{'_time':1,'_lineIndex':3,'_type':0,'_duration':1,'_width':1},
                      {'_time':2,'_lineIndex':0,'_type':1,'_duration':1,'_width':4}],
        '_events':[{'_time':1,'_type':2,'_value':3,'_floatValue':.5}],
        '_bookmarks':[{'_time':0,'_name':'editor only'}],'_BPMChanges':[]}


def test_geometry_bombs_basic_lights_preserved():
    d=imp.convert_map(v2())
    assert d['colorNotes']==[{'b':1,'x':1,'y':0,'c':0,'d':1,'a':0}]
    assert d['bombNotes']==[{'b':2,'x':2,'y':1}]
    assert [(w['y'],w['h']) for w in d['obstacles']]==[(0,5),(2,3)]
    assert d['basicBeatmapEvents']==[{'b':1,'et':2,'i':3,'f':.5}]
    assert '_bookmarks' not in d


@pytest.mark.parametrize('mutation',['bpm','rotation','modnote','modwall','modevent','unknown'])
def test_refuses_unsupported_instead_of_silent_drop(mutation):
    d=v2()
    if mutation=='bpm':d['_BPMChanges']=[{'_time':1,'_BPM':180}]
    if mutation=='rotation':d['_events'][0]['_type']=14
    if mutation=='modnote':d['_notes'][0]['_customData']={'position':[5,0]}
    if mutation=='modwall':d['_obstacles'][0]['_type']=5
    if mutation=='modevent':d['_events'][0]['_customData']={'color':[1,0,0]}
    if mutation=='unknown':d['_sliders']=[{}]
    with pytest.raises(ValueError):imp.convert_map(d)


def test_offline_import_full_audio_unchanged_source_and_bundle_geometry(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required for offline import')
    pytest.importorskip('UnityPy')
    source=tmp_path/'source';source.mkdir()
    pcm=bytes([0,2,0,2])*(44100*3)
    with wave.open(str(source/'audio.wav'),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(pcm)
    info={'_version':'2.0.0','_songName':'Tiny full-map fixture','_beatsPerMinute':120,'_songFilename':'audio.wav',
          '_songAuthorName':'Synthetic','_difficultyBeatmapSets':[{'_beatmapCharacteristicName':'Standard','_difficultyBeatmaps':[]}]}
    for i,name in enumerate(imp.prepare.DIFFICULTIES):
        d=v2();d['_events'][0]['_value']=i+1
        if name=='ExpertPlus':d['_obstacles']=[empty_wall() for _ in range(3)]+d['_obstacles']
        (source/(name+'.dat')).write_text(json.dumps(d))
        info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps'].append({'_difficulty':name,'_difficultyRank':i*2+1,
            '_beatmapFilename':name+'.dat','_noteJumpMovementSpeed':10+i,'_noteJumpStartBeatOffset':0})
    (source/'info.dat').write_text(json.dumps(info))
    before={p.name:p.read_bytes() for p in source.iterdir()}
    out=tmp_path/'normalized';r=imp.import_song(source,out)
    assert r['duration_seconds']==3
    assert r['ignored_v2_wall_placeholders']=={'ExpertPlus':3}
    assert {p.name:p.read_bytes() for p in source.iterdir()}==before
    prepared=tmp_path/'prepared'
    m=imp.prepare.prepare(out,ROOT/'custom_songs/quick_test.bundle',prepared)
    assert imp.prepare.validate(prepared,imp.prepare.load_song(out))==m
    assert m['difficulty_stats']['ExpertPlus']=={'notes':1,'bombs':1,'obstacles':2,'njs':14,'jump_offset':0}
    import UnityPy,gzip
    env=UnityPy.load(str(prepared/m['bundle']['file']));cab=next(v for v in next(iter(env.files.values())).files.values() if hasattr(v,'objects'))
    level=next(r.read_typetree() for r in env.objects if r.class_id==114)
    entries=level['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']
    assert len({e['_lightshowAsset']['m_PathID'] for e in entries})==5
    for i,e in enumerate(entries):
        t=cab.objects[e['_lightshowAsset']['m_PathID']].read_typetree()
        data=json.loads(gzip.decompress(t['m_Script'].encode('utf8','surrogateescape')))
        assert data['basicBeatmapEvents'][0]['i']==i+1
    clip=next(r.read_typetree() for r in env.objects if r.class_id==83)
    assert clip['m_LoadType']==0 and clip['m_PreloadAudioData'] and not clip['m_LoadInBackground']
    with pytest.raises(ValueError,match='new output'):imp.import_song(source,out)


def test_info_requirements_refused_before_decoder(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'Info.dat').write_text(json.dumps({'_version':'2.0.0','_customData':{'_requirements':['Noodle Extensions']}}))
    with pytest.raises(ValueError,match='requirements'):imp.import_song(source,tmp_path/'out',ffmpeg='must-not-run')
    assert not (tmp_path/'out').exists()


def test_chromapper_editor_grid_markers_are_not_runtime_tempo():
    import copy
    original = v2()
    original['_version'] = '2.2.0'
    original['_waypoints'] = []
    original['_customData'] = {'_time': 109.724, '_BPMChanges': [
        {'_time': 0.5, '_BPM': 67, '_beatsPerBar': 4, '_metronomeOffset': 4},
        {'_time': 1.5, '_BPM': 206, '_beatsPerBar': 4, '_metronomeOffset': 4}]}
    before = copy.deepcopy(original)
    assert imp.convert_map(original) == imp.convert_map(v2())
    assert original == before  # source bytes/objects are not rewritten


@pytest.mark.parametrize('custom', [
    {'_BPMChanges': 'invalid'}, {'_BPMChanges': [{'_time': 0}]},
    {'_BPMChanges': [{'_time': 0, '_BPM': 0}]},
    {'_BPMChanges': [{'_time': float('nan'), '_BPM': 120}]},
    {'_BPMChanges': [{'_time': 0, '_BPM': 120, 'animation': []}]},
    {'_requirements': ['Noodle Extensions']}, {'_customEvents': [{}]},
])
def test_editor_marker_allowlist_does_not_allow_real_mods_or_bad_values(custom):
    data = v2(); data['_customData'] = custom
    with pytest.raises(ValueError): imp.convert_map(data)


def test_nonempty_waypoints_are_not_silently_dropped():
    data = v2(); data['_waypoints'] = [{'_time': 1, '_lineIndex': 0}]
    with pytest.raises(ValueError, match='waypoints'): imp.convert_map(data)


def test_editor_bookmarks_do_not_change_object_timing():
    d=v2();d['_customData']={'_bookmarks':[{'_time':-1,'_name':'editor only'}], '_bookmarksUseOfficialBpmEvents':True}
    assert imp.convert_map(d)==imp.convert_map(v2())
    d['_customData']['_bookmarks'][0]['_position']=[9,9]
    with pytest.raises(ValueError,match='bookmark'):imp.convert_map(d)


def empty_wall():
    return {'_time':0,'_lineIndex':0,'_type':0,'_duration':0,'_width':0}


def test_exact_empty_v2_sentinels_reported_without_mutating_or_dropping_geometry():
    import copy
    source=v2();source['_obstacles']=[empty_wall() for _ in range(3)]+source['_obstacles']
    before=copy.deepcopy(source);normalization={}
    result=imp.convert_map(source,normalization=normalization)
    assert normalization=={'empty_v2_wall_placeholders':3}
    assert result==imp.convert_map(v2()) and source==before
    assert imp.is_empty_wall_placeholder(dict(empty_wall(),_time=0.0,_duration=0.0))
    # Reused statistics never leak a prior chart's count.
    imp.convert_map(v2(),normalization=normalization)
    assert normalization=={'empty_v2_wall_placeholders':0}


@pytest.mark.parametrize('mutation',[
    {'_time':1}, {'_time':True}, {'_time':float('nan')}, {'_time':float('inf')},
    {'_lineIndex':1}, {'_lineIndex':False}, {'_lineIndex':0.0},
    {'_type':1}, {'_type':False}, {'_type':0.0},
    {'_duration':1}, {'_duration':False}, {'_duration':float('nan')},
    {'_width':1}, {'_width':False}, {'_width':0.0}, {'_width':-1},
    {'_customData':{}}, {'_customData':{'_position':[0,0]}}, {'unknown':0},
])
def test_placeholder_allowlist_does_not_hide_nearby_walls_or_custom_data(mutation):
    wall=dict(empty_wall(),**mutation)
    assert not imp.is_empty_wall_placeholder(wall)
    source=v2();source['_obstacles']=[wall]
    if set(wall)-set(empty_wall()):
        with pytest.raises(ValueError,match='wall/mod'):imp.convert_map(source)
    else:
        # Unsupported/malformed geometry stays present for strict validation;
        # positive-width zero-duration authored walls are also not discarded.
        stats={};result=imp.convert_map(source,normalization=stats)
        assert len(result['obstacles'])==1 and stats['empty_v2_wall_placeholders']==0


def test_placeholder_missing_fields_is_not_a_sentinel():
    for key in empty_wall():
        wall=empty_wall();del wall[key]
        assert not imp.is_empty_wall_placeholder(wall)


def test_primary_v3_import_route_reports_exact_legacy_placeholders(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    spec=importlib.util.spec_from_file_location('primary_import',ROOT/'development/scripts/import_v3_additive.py')
    primary=importlib.util.module_from_spec(spec);spec.loader.exec_module(primary)
    folder=tmp_path/'source';primary.prepare.generate_probe(folder)
    info=json.loads((folder/'Info.dat').read_text())
    for d in info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']:
        data=v2()
        if d['_difficulty']=='ExpertPlus':data['_obstacles']=[empty_wall() for _ in range(3)]+data['_obstacles']
        (folder/d['_beatmapFilename']).write_text(json.dumps(data))
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    report=primary.import_song(folder,tmp_path/'out')
    assert report['ignored_v2_wall_placeholders']=={'ExpertPlus':3}
    assert report['note_counts']==dict.fromkeys(imp.prepare.DIFFICULTIES,1)
    song=primary.prepare.load_song(tmp_path/'out')
    for data in song['maps'].values():
        assert len(data['bombNotes'])==1 and len(data['obstacles'])==2
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==before


@pytest.mark.parametrize('width,duration',[(0,1),(0,0),(-1,0)])
def test_direct_v3_zero_width_geometry_still_refused(tmp_path,width,duration):
    # The exception is exclusively legacy V2 conversion, never the shared gate.
    folder=tmp_path/'source';imp.prepare.generate_probe(folder)
    path=folder/'ExpertPlus.dat';data=json.loads(path.read_text())
    data['obstacles']=[{'b':0,'x':0,'y':0,'d':duration,'w':width,'h':5}]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='wall geometry'):imp.prepare.load_song(folder)


def test_redundant_top_level_tempo_is_identity_only_with_explicit_exact_base():
    import copy
    original = v2()
    original['_BPMChanges'] = [{'_time': 1.25, '_BPM': 70, '_beatsPerBar': 4, '_metronomeOffset': 4}]
    before = copy.deepcopy(original)
    assert imp.convert_map(original, base_bpm=70) == imp.convert_map(v2())
    assert original == before
    for bpm in (None, True, 69.9999999, float('nan'), 0, '70'):
        with pytest.raises(ValueError): imp.convert_map(original, base_bpm=bpm)
    original['_BPMChanges'].append({'_time': 2, '_BPM': 71})
    with pytest.raises(ValueError): imp.convert_map(original, base_bpm=70)


@pytest.mark.parametrize('markers', [None, {}, 'none', [0], [{'_time': 0}],
    [{'_time': True, '_BPM': 70}], [{'_time': 0, '_BPM': 70, 'customData': {}}]])
def test_top_level_tempo_metadata_is_validated_even_for_constant_tempo(markers):
    data = v2(); data['_BPMChanges'] = markers
    with pytest.raises(ValueError): imp.convert_map(data, base_bpm=70)


def test_legacy_atlas_scalar_annotation_never_changes_chart_objects():
    original = v2(); original['_customData'] = {'_atlasBeatsMap': 285278464}
    assert imp.convert_map(original) == imp.convert_map(v2())
    assert original['_customData'] == {'_atlasBeatsMap': 285278464}
    for value in (-1, 2**32, True, 0.0, 'tag', {}, []):
        original['_customData']['_atlasBeatsMap'] = value
        with pytest.raises(ValueError): imp.convert_map(original)
