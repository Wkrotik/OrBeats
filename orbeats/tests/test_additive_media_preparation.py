"""Exp304 deterministic local-only media prep; no copyrighted song fixture/network."""
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import wave

from PIL import Image
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('additive_media',ROOT/'development/scripts/prepare_additive_media.py')
media=importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


@pytest.fixture
def source(tmp_path):
    folder=tmp_path/'song';folder.mkdir()
    # Different samples each second let us verify excerpt offsets, not just silence.
    with wave.open(str(folder/'song.wav'),'wb') as w:
        w.setparams((2,2,44100,0,'NONE','not compressed'))
        w.writeframes(b''.join(struct.pack('<hh',i*2000,i*2000)*44100 for i in range(4)))
    Image.new('RGB',(250,250),(20,100,200)).save(folder/'cover.jpg')
    info={'_songName':'Synthetic media test','_songFilename':'song.wav',
          '_coverImageFilename':'cover.jpg','_previewStartTime':1,'_previewDuration':2}
    (folder/'Info.dat').write_text(json.dumps(info))
    level=tmp_path/'level.json'
    level.write_text(json.dumps({'level_id':'bsd_additive_'+'a'*24,
                                'song_name':info['_songName'],'duration_seconds':4}))
    return folder,level,tmp_path/'media'


def prepare(source,**kwargs):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    return media.prepare(*source,**kwargs)


def test_cover_and_preview_use_actual_source_and_declared_excerpt(source):
    folder,_,out=source
    m=prepare(source)
    assert m['source_cover_pixels']==[250,250]
    assert m['icon_target_pixels']==[512,512]
    assert m['native_playlist_dimensions_verified'] is False
    assert m['runtime_bound'] is False
    assert m['pack_cover'] is None
    with Image.open(out/'song-cover.png') as im:
        assert im.size==(512,512) and im.mode=='RGB' and im.format=='PNG'
    with wave.open(str(folder/'song.wav'),'rb') as original:
        original.setpos(44100);expected=original.readframes(2*44100)
    with wave.open(str(out/'preview.wav'),'rb') as preview:
        assert preview.readframes(preview.getnframes())==expected
    assert media.verify(out)==m


def test_optional_pack_cover_normalized_without_changing_original(source):
    original=source[0]/'pack.png';Image.new('RGBA',(1024,512),(100,60,10,20)).save(original)
    before=original.read_bytes()
    m=prepare(source,pack_cover=original)
    assert original.read_bytes()==before
    with Image.open(source[2]/m['pack_cover']['file']) as im:assert im.size==(512,512)


@pytest.mark.parametrize('key,value',[('_previewStartTime',-1),('_previewStartTime',3),
                                     ('_previewDuration',0),('_previewDuration',31),
                                     ('_previewStartTime',True),('_previewDuration',float('nan'))])
def test_bad_preview_bounds_before_output_created(source,key,value):
    p=source[0]/'Info.dat';info=json.loads(p.read_text());info[key]=value;p.write_text(json.dumps(info))
    with pytest.raises(ValueError):media.prepare(*source)
    assert not source[2].exists()


def test_source_path_escape_refused(source):
    p=source[0]/'Info.dat';info=json.loads(p.read_text());info['_songFilename']='../outside.wav';p.write_text(json.dumps(info))
    with pytest.raises(ValueError,match='escapes'):media.prepare(*source)


def test_source_symlink_escape_refused(source):
    outside=source[0].parent/'external.jpg';Image.new('RGB',(2,2)).save(outside)
    cover=source[0]/'cover.jpg';cover.unlink();cover.symlink_to(outside)
    with pytest.raises(ValueError,match='escapes'):media.prepare(*source)


def test_level_mismatch_refused(source):
    p=source[1];m=json.loads(p.read_text());m['song_name']='Different';p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='mismatch'):media.prepare(*source)


def test_no_overwrite(source):
    source[2].mkdir()
    with pytest.raises(ValueError,match='no overwrite'):media.prepare(*source)


def test_hash_tampering_refused(source):
    prepare(source)
    with (source[2]/'preview.wav').open('ab') as f:f.write(b'x')
    with pytest.raises(ValueError,match='hash'):media.verify(source[2])


def test_manifest_cannot_escape_directory(source):
    prepare(source);p=source[2]/'media-manifest.json';m=json.loads(p.read_text())
    m['song_cover']['file']='../cover.png';p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='filename'):media.verify(source[2])


def test_verify_does_not_claim_native_binding(source):
    prepare(source);p=source[2]/'media-manifest.json';m=json.loads(p.read_text())
    m['runtime_bound']=True;p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='status'):media.verify(source[2])


def test_fractional_ogg_preview_is_sample_exact_not_extra_decoder_block(source):
    import subprocess
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    folder,_,out=source
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(folder/'song.wav'),
                    '-c:a','libvorbis',str(folder/'audio.ogg')],check=True)
    p=folder/'Info.dat';info=json.loads(p.read_text());info.update(
        _songFilename='audio.ogg',_previewStartTime=1.3,_previewDuration=1.2)
    p.write_text(json.dumps(info));prepare(source)
    decoded=folder/'full-decoded.wav'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(folder/'audio.ogg'),
                    '-ac','2','-ar','44100','-c:a','pcm_s16le',str(decoded)],check=True)
    with wave.open(str(decoded),'rb') as w:
        w.setpos(round(1.3*44100));expected=w.readframes(round(1.2*44100))
    with wave.open(str(out/'preview.wav'),'rb') as w:
        assert w.getnframes()==round(1.2*44100)
        assert w.readframes(w.getnframes())==expected
    assert media.verify(out)['preview_duration_seconds']==1.2


@pytest.mark.parametrize('start,duration',[(.7,1.3),(1.7,20)])
def test_ogg_preview_is_trimmed_in_final_sample_domain(source,start,duration):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required')
    import subprocess
    folder,level,out=source
    seconds=24 if duration==20 else 4
    with wave.open(str(folder/'song.wav'),'wb') as w:
        w.setparams((2,2,44100,0,'NONE','not compressed'))
        w.writeframes(struct.pack('<hh',2000,-2000)*44100*seconds)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(folder/'song.wav'),
                    '-c:a','libvorbis',str(folder/'song.ogg')],check=True,timeout=30)
    info=json.loads((folder/'Info.dat').read_text())
    info.update(_songFilename='song.ogg',_previewStartTime=start,_previewDuration=duration)
    (folder/'Info.dat').write_text(json.dumps(info))
    meta=json.loads(level.read_text());meta['duration_seconds']=seconds;level.write_text(json.dumps(meta))
    result=media.prepare(folder,level,out)
    assert media.verify(out)==result
    with wave.open(str(out/'preview.wav'),'rb') as w:
        assert w.getnframes()==round(duration*44100)
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,44100)
        samples=struct.unpack('<hh',w.readframes(1));assert samples[0]>1000 and samples[1]<-1000


def test_case_only_cover_filename_mismatch_is_unambiguous(source):
    folder,_,_=source
    (folder/'cover.jpg').rename(folder/'Cover.jpg')
    m=prepare(source)
    assert m['source_cover_pixels']==[250,250]


def test_ambiguous_case_cover_and_outside_symlink_still_refused(source,tmp_path):
    folder,_,_=source
    content=(folder/'cover.jpg').read_bytes();(folder/'cover.jpg').unlink()
    (folder/'Cover.jpg').write_bytes(content);(folder/'COVER.JPG').write_bytes(content)
    with pytest.raises(ValueError,match='ambiguous'):media.source_file(folder,'cover.jpg')
    (folder/'COVER.JPG').unlink();(folder/'Cover.jpg').unlink()
    outside=tmp_path/'secret.jpg';outside.write_bytes(content);(folder/'Cover.jpg').symlink_to(outside)
    with pytest.raises(ValueError,match='escapes'):media.source_file(folder,'cover.jpg')
