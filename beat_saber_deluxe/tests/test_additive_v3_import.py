"""No network/game input: timing-preserving vanilla V3 import regression."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import wave

import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v3_import',ROOT/'development/scripts/import_v3_additive.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)


def chart():
    return {'version':'3.3.0','bpmEvents':[{'b':0,'m':240},{'b':1,'m':120},{'b':4,'m':60}],
            'colorNotes':[{'b':2,'x':0,'y':1,'a':0,'c':1,'d':2}],
            'bombNotes':[{'b':3,'x':1,'y':0}],
            'obstacles':[{'b':0.5,'x':-1,'y':2,'d':5,'w':1,'h':3}],
            'basicBeatmapEvents':[{'b':5,'et':3,'i':1,'f':1}],
            'customData':{'lighter':{'test editor':{}},'time':43},
            'basicEventTypesWithKeywords':{'d':[]},'useNormalEventsAsCompatibleEvents':True,
            '_fxEventsCollection':{'_il':[],'_fl':[]}}


def test_tempo_seconds_and_wall_both_endpoints_preserved():
    source=chart();before=copy.deepcopy(source);out=imp.convert_map(source,120)
    assert source==before and out['version']=='3.3.0'
    # Independent hand-computed piecewise seconds, not reusing Tempo.time:
    # beat0→1 @240 =.25sec, beat1→4 @120 =1.5sec, thereafter1sec/beat.
    assert out['colorNotes'][0]['b']==pytest.approx(1.5)  #.75sec
    assert out['bombNotes'][0]['b']==pytest.approx(2.5)  #1.25sec
    assert out['basicBeatmapEvents'][0]['b']==pytest.approx(5.5)  #2.75sec
    w=out['obstacles'][0]
    assert w['b']==pytest.approx(.25)  #.125sec
    assert w['d']==pytest.approx(6.25)  #end3.25sec -start.125sec
    assert (w['x'],w['y'],w['w'],w['h'])==(-1,2,1,3)
    assert 'bpmEvents' not in out and 'customData' not in out


def test_constant_bpm_no_events_is_identity_and_no_lights_are_fabricated():
    d=chart();d['bpmEvents']=[]
    out=imp.convert_map(d,120)
    for k in ('colorNotes','bombNotes','obstacles','basicBeatmapEvents'):assert out[k]==d[k]


@pytest.mark.parametrize('events',[[{'b':0,'m':0}],[{'b':0,'m':float('nan')}],
    [{'b':True,'m':120}],[{'b':1,'m':120},{'b':1,'m':140}],
    [{'b':2,'m':120},{'b':0,'m':140}],[{'b':0,'m':120,'custom':1}],None])
def test_bad_tempo_is_not_silently_dropped(events):
    d=chart();d['bpmEvents']=events
    with pytest.raises(ValueError):imp.convert_map(d,120)


@pytest.mark.parametrize('key,value',[('sliders',[{}]),('burstSliders',[{}]),('rotationEvents',[{}]),
    ('lightColorEventBoxGroups',[{}]),('vfxEventBoxGroups',[{}]),('customData',{'requirements':['Noodle Extensions']}),
    ('_fxEventsCollection',{'_il':[{}]}),('basicEventTypesWithKeywords',{'d':[{}]}),('unknown',[])])
def test_unsupported_geometry_and_lighting_refused(key,value):
    d=chart();d[key]=value
    with pytest.raises(ValueError):imp.convert_map(d,120)


def test_import_three_difficulties_roundtrip_without_fabricated_easy_normal(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    pytest.importorskip('UnityPy')
    source=tmp_path/'source';source.mkdir()
    with wave.open(str(source/'audio.wav'),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(bytes([0,2,0,2])*44100*4)
    info={'_version':'2.1.0','_songName':'Synthetic second','_songAuthorName':'Fixture',
          '_beatsPerMinute':120,'_songFilename':'audio.wav','_songTimeOffset':0,
          '_difficultyBeatmapSets':[{'_beatmapCharacteristicName':'Standard','_difficultyBeatmaps':[]}]}
    for index,(name,rank) in enumerate([('Hard',5),('Expert',7),('ExpertPlus',9)]):
        d=chart();d['colorNotes'][0]['x']=index
        (source/(name+'.dat')).write_text(json.dumps(d))
        info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps'].append({'_difficulty':name,'_difficultyRank':rank,
            '_beatmapFilename':name+'.dat','_noteJumpMovementSpeed':11+index,'_noteJumpStartBeatOffset':-.5})
    (source/'Info.dat').write_text(json.dumps(info));before={p.name:p.read_bytes() for p in source.iterdir()}
    out=tmp_path/'normalized';report=imp.import_song(source,out)
    assert {p.name:p.read_bytes() for p in source.iterdir()}==before
    assert report['note_counts']=={'Hard':1,'Expert':1,'ExpertPlus':1}
    song=imp.prepare.load_song(out);assert set(song['maps'])=={'Hard','Expert','ExpertPlus'}
    prepared=tmp_path/'prepared'
    manifest=imp.prepare.prepare(out,ROOT/'custom_songs/quick_test.bundle',prepared)
    assert manifest['difficulties']==['Hard','Expert','ExpertPlus']
    assert imp.prepare.validate(prepared,song)==manifest
    with pytest.raises(ValueError):imp.import_song(source,out)


@pytest.mark.parametrize('x,width,valid',[(-4,1,True),(-1,1,True),(4,1,True),(7,1,True),(-5,1,False),(7,2,False)])
def test_bounded_decorative_walls_do_not_relax_note_lanes(tmp_path,x,width,valid):
    folder=tmp_path/'song';imp.prepare.generate_probe(folder)
    p=folder/'Easy.dat';d=json.loads(p.read_text())
    d['obstacles']=[{'b':1,'x':x,'y':2,'d':1,'w':width,'h':3}];p.write_text(json.dumps(d))
    if valid:assert imp.prepare.load_song(folder)['maps']['Easy']['obstacles']==d['obstacles']
    else:
        with pytest.raises(ValueError):imp.prepare.load_song(folder)
    d['colorNotes'][0]['x']=-1;p.write_text(json.dumps(d))
    with pytest.raises(ValueError):imp.prepare.load_song(folder)


def arc():
    return {'b':.5,'c':0,'x':1,'y':0,'d':1,'mu':.75,
            'tb':5.5,'tx':0,'ty':2,'tc':4,'tmu':1.25,'m':2}


def test_arc_geometry_and_piecewise_head_tail_seconds_preserved():
    source=chart();source['sliders']=[arc()];before=copy.deepcopy(source)
    out=imp.convert_map(source,120);a=out['sliders'][0]
    assert source==before
    assert a['b']==pytest.approx(.25)       # beat.5 ->.125sec
    assert a['tb']==pytest.approx(6.5)      # beat5.5 ->3.25sec
    assert {k:v for k,v in a.items() if k not in ('b','tb')}=={k:v for k,v in arc().items() if k not in ('b','tb')}
    imp.prepare.validate_arcs(out['sliders'],7)


@pytest.mark.parametrize('field,bad',[('b',True),('b',-1),('tb',.5),('tb',0),('tb',float('inf')),
    ('x',4),('tx',-1),('y',3),('ty',True),('c',2),('d',9),('tc',1.5),('m',3),
    ('mu',float('nan')),('mu',-1),('tmu',101),('customData',{'animation':1})])
def test_bad_arc_refused_by_both_importer_and_bundle_validator(tmp_path,field,bad):
    a=arc();a[field]=bad;d=chart();d['sliders']=[a]
    with pytest.raises(ValueError,match='arc'):imp.convert_map(d,120)
    folder=tmp_path/'song';imp.prepare.generate_probe(folder)
    path=folder/'Easy.dat';bm=json.loads(path.read_bytes());bm['sliders']=[a];path.write_text(json.dumps(bm))
    with pytest.raises(ValueError,match='arc'):imp.prepare.load_song(folder)


@pytest.mark.parametrize('entries',[{},None,[{}],[1]])
def test_bad_arc_list_or_record_refused(entries):
    d=chart();d['sliders']=entries
    with pytest.raises(ValueError,match='arc'):imp.convert_map(d,120)


def test_arc_tail_beyond_audio_refused(tmp_path):
    folder=tmp_path/'song';imp.prepare.generate_probe(folder)
    path=folder/'Easy.dat';d=json.loads(path.read_bytes());a=arc();a['tb']=100;d['sliders']=[a];path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='tail beat'):imp.prepare.load_song(folder)


def test_arc_constant_tempo_unityfs_roundtrip_and_empty_map_identity(tmp_path):
    pytest.importorskip('UnityPy');folder=tmp_path/'song';imp.prepare.generate_probe(folder)
    before=imp.prepare.load_song(folder)
    # Absent and explicit empty arcs must not give old songs different IDs.
    for path in folder.glob('*.dat'):
        if path.name.lower()=='info.dat':continue
        d=json.loads(path.read_bytes());d.pop('sliders',None);path.write_text(json.dumps(d))
    assert imp.prepare.load_song(folder)['source_sha256']==before['source_sha256']
    path=folder/'Easy.dat';d=json.loads(path.read_bytes());a=arc();d['sliders']=[a];path.write_text(json.dumps(d))
    normalized=imp.convert_map(d,120);assert normalized['sliders']==[a]
    song=imp.prepare.load_song(folder);out=tmp_path/'bundle'
    manifest=imp.prepare.prepare(folder,ROOT/'custom_songs/quick_test.bundle',out)
    assert imp.prepare.validate(out,song)==manifest
    assert manifest['note_counts']=={name:9 for name in imp.prepare.DIFFICULTIES}


def test_named_unsupported_features_and_expert_context(tmp_path):
    d=chart();d['burstSliders']=[{}]
    with pytest.raises(ValueError,match=r'burstSliders \(chains\)'):imp.convert_map(d,120)
    folder=tmp_path/'song';imp.prepare.generate_probe(folder)
    path=folder/'Easy.dat';path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match=r'Easy \(Easy.dat\).*chains'):
        imp.import_song(folder,tmp_path/'normalized')

@pytest.mark.parametrize('custom', [
    {'_requirements': [], '_suggestions': [], '_warnings': [], '_information': []},
    {'_customEnvironment': '', '_customEnvironmentHash': ''},
    {'_editorOffset': 0, '_editorOldOffset': 2.5},
])
def test_empty_mod_metadata_and_editor_offsets_are_not_requirements(custom):
    imp.cosmetic_only(custom, set())


@pytest.mark.parametrize('custom', [
    {'_requirements': ['Noodle Extensions']}, {'_suggestions': ['Chroma']},
    {'_customEnvironment': 'custom room'}, {'_requirements': ''},
    {'_editorOffset': True}, {'_editorOffset': float('nan')},
    {'_unknown': []},
])
def test_nonempty_or_unknown_mod_metadata_still_refused(custom):
    with pytest.raises(ValueError, match='custom metadata'):
        imp.cosmetic_only(custom, set())


def test_v2_empty_metadata_and_lighting_only_chart_import(tmp_path):
    if not shutil.which('ffmpeg'): pytest.skip('ffmpeg required')
    folder = tmp_path / 'source'; imp.prepare.generate_probe(folder)
    info_path = folder / 'Info.dat'; info = json.loads(info_path.read_bytes())
    info['_customData'] = {'_contributors': [], '_customEnvironment': '', '_customEnvironmentHash': ''}
    for d in info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']:
        d['_customData'] = {'_requirements': [], '_suggestions': [], '_editorOffset': 0}
        chart = {'_version': '2.0.0', '_notes': [], '_obstacles': [], '_BPMChanges': [],
                 '_events': [{'_time': 1, '_type': 0, '_value': 1}], '_bookmarks': []}
        if d['_difficulty'] != 'Easy':
            chart['_notes'] = [{'_time': 1, '_lineIndex': 0, '_lineLayer': 1, '_type': 1, '_cutDirection': 2}]
        (folder / d['_beatmapFilename']).write_text(json.dumps(chart))
    info_path.write_text(json.dumps(info))
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    out = tmp_path / 'normalized'; report = imp.import_song(folder, out)
    assert report['skipped_difficulties'] == ['Easy (lighting-only; no playable objects)']
    assert report['note_counts'] == {'Normal': 1, 'Hard': 1, 'Expert': 1, 'ExpertPlus': 1}
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert 'Easy' not in imp.prepare.load_song(out)['maps']
    # A lighting-only pack cannot masquerade as a playable song.
    for d in info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']:
        p = folder / d['_beatmapFilename']; chart = json.loads(p.read_bytes()); chart['_notes'] = []; p.write_text(json.dumps(chart))
    with pytest.raises(ValueError, match='No playable'):
        imp.import_song(folder, tmp_path / 'lighting-only')


@pytest.mark.parametrize('difficulty,expected', [('Easy',10),('Normal',10),('Hard',10),('Expert',12),('ExpertPlus',16)])
@pytest.mark.parametrize('value', [0, -1, -100])
def test_native_default_njs_sentinel(difficulty, expected, value):
    assert imp.prepare.resolve_note_jump_speed(difficulty,value) == expected
    assert imp.prepare.resolve_note_jump_speed(difficulty,13.5) == 13.5


@pytest.mark.parametrize('value', [True,False,None,'0',float('nan'),float('inf'),101,.05])
def test_invalid_njs_never_becomes_default(value):
    with pytest.raises(ValueError,match='NJS'):
        imp.prepare.resolve_note_jump_speed('Expert',value)


def test_import_default_njs_and_missing_offset_preserves_charts(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    source=tmp_path/'source';imp.prepare.generate_probe(source)
    path=source/'Info.dat';info=json.loads(path.read_text())
    for d in info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']:
        d['_noteJumpMovementSpeed']=0
        d.pop('_noteJumpStartBeatOffset',None)
    info['_difficultyBeatmapSets'][0]['_difficultyBeatmaps'][0].pop('_noteJumpMovementSpeed')
    path.write_text(json.dumps(info));before=path.read_bytes()
    report=imp.import_song(source,tmp_path/'normalized')
    assert report['default_njs']=={'Easy':10,'Normal':10,'Hard':10,'Expert':12,'ExpertPlus':16}
    normalized=json.loads((tmp_path/'normalized/Info.dat').read_text())
    for d in normalized['_difficultyBeatmapSets'][0]['_difficultyBeatmaps']:
        assert d['_noteJumpMovementSpeed']==report['default_njs'][d['_difficulty']]
        assert d['_noteJumpStartBeatOffset']==0
    assert path.read_bytes()==before


def test_editor_bookmarks_and_cosmetic_colors_are_not_gameplay_mods():
    d=chart();expected=imp.convert_map(d,120)
    d['customData'].update(bookmarks=[{'b':140,'n':'Chorus','c':[1,.8,.25,1]}],bookmarksUseOfficialBpmEvents=True)
    assert imp.convert_map(d,120)==expected
    imp.cosmetic_only({'_envColorLeftBoost':{'r':1,'g':0,'b':0},'_obstacleColor':{'r':1,'g':1,'b':1}}, {'_envColorLeftBoost','_obstacleColor'})
    d['customData']['bookmarks'][0]['position']=[4,0]
    with pytest.raises(ValueError,match='bookmark'):imp.convert_map(d,120)
    with pytest.raises(ValueError,match='requirements'):imp.cosmetic_only({'_requirements':['Noodle Extensions']},set())


def test_descriptive_info_timing_does_not_retime_audio_or_notes(tmp_path):
    if not shutil.which('ffmpeg'): pytest.skip('ffmpeg required')
    root=tmp_path/'source';imp.prepare.generate_probe(root)
    original=imp.prepare.load_song(root)
    path=root/'Info.dat';info=json.loads(path.read_bytes())
    info['_customData']={'_firstNoteBeat':5,'_introPadSeconds':1.765}
    path.write_text(json.dumps(info))
    before={p.name:p.read_bytes() for p in root.iterdir()}
    out=tmp_path/'normalized';report=imp.import_song(root,out)
    assert {p.name:p.read_bytes() for p in root.iterdir()}==before
    song=imp.prepare.load_song(out)
    assert report['duration_seconds']==original['samples']/44100
    assert song['samples']==original['samples'] and song['maps']==original['maps']


@pytest.mark.parametrize('key',['_firstNoteBeat','_introPadSeconds'])
@pytest.mark.parametrize('value',[True,False,None,'5',-1,float('nan'),float('inf'),100001])
def test_timing_annotations_are_bounded_numbers_not_playback_mods(key,value):
    with pytest.raises(ValueError,match='timing annotation'):
        imp.cosmetic_only({key:value},{'_firstNoteBeat','_introPadSeconds'})
    with pytest.raises(ValueError,match='custom metadata'):
        imp.cosmetic_only({key:1},set())
