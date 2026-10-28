#!/usr/bin/env python3
"""Exp304: local song art/preview preparation ONLY. No FTP or game injection.

Produces a square512px PNG and the map's declared preview as PCM16 stereo WAV.
Optional playlist art uses the same design target; this is NOT a claimed native
sprite/atlas requirement. Runtime binding is deliberately a separate experiment.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess
import wave

from PIL import Image, ImageOps

ICON_SIZE=512
MAX_IMAGE_BYTES=32*1024*1024


def number(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('invalid '+name)
    return float(value)


def source_file(root,value):
    if not isinstance(value,str) or not value or '\\' in value:
        raise ValueError('invalid source filename')
    p=(root/value).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('source filename escapes directory or is missing')
    if not p.is_file() and p.parent.is_dir():
        matches = [entry for entry in p.parent.iterdir() if entry.name.casefold() == p.name.casefold()]
        if len(matches) != 1:
            raise ValueError('source filename is missing or ambiguous')
        p = matches[0].resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():
        raise ValueError('source filename escapes directory or is missing')
    return p


def image_info(path):
    if path.stat().st_size>MAX_IMAGE_BYTES:
        raise ValueError('image exceeds32MiB')
    with Image.open(path) as im:
        if im.format not in ('PNG','JPEG') or min(im.size)<1 or max(im.size)>4096:
            raise ValueError('expected PNG/JPEG, up to4096px per side')
        im.load()
        return list(im.size)


def normalize_cover(source,target):
    original=image_info(source)
    with Image.open(source) as im:
        ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(ICON_SIZE,ICON_SIZE),
                     method=Image.Resampling.LANCZOS).save(target,format='PNG')
    return original


def file_record(path):
    return {'file':path.name,'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def verify(folder):
    folder=Path(folder)
    m=json.loads((folder/'media-manifest.json').read_text())
    if m.get('schema')!=1 or m.get('runtime_bound') is not False:
        raise ValueError('unexpected media preparation schema/status')
    for key in ('song_cover','preview','pack_cover'):
        record=m.get(key)
        if record is None:
            if key=='pack_cover':continue
            raise ValueError('missing '+key)
        name=record.get('file','')
        if name!={'song_cover':'song-cover.png','preview':'preview.wav','pack_cover':'pack-cover.png'}[key]:
            raise ValueError('invalid media filename')
        p=folder/name
        if not p.is_file() or p.is_symlink() or file_record(p)!=record:
            raise ValueError('media hash/size mismatch: '+key)
        if key!='preview' and image_info(p)!=[ICON_SIZE,ICON_SIZE]:
            raise ValueError('cover dimension mismatch')
    start=number(m.get('preview_start_seconds'),'preview start')
    duration=number(m.get('preview_duration_seconds'),'preview duration')
    if start<0 or not 1<=duration<=30:raise ValueError('preview bounds')
    with wave.open(str(folder/'preview.wav'),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(2,2,44100,'NONE'):
            raise ValueError('preview must be PCM16 stereo44100')
        if abs(w.getnframes()/44100-duration)>1/44100:
            raise ValueError('preview duration mismatch')
    return m


def prepare(source,level_manifest,output,pack_cover=None,ffmpeg='ffmpeg'):
    source=Path(source).resolve();output=Path(output)
    info_paths=[p for p in source.iterdir() if p.name.lower()=='info.dat']
    if len(info_paths)!=1:raise ValueError('expected one Info.dat')
    info=json.loads(info_paths[0].read_text(encoding='utf-8-sig'))
    level=json.loads(Path(level_manifest).read_text())
    level_id=level.get('level_id','')
    if (not isinstance(level_id,str) or not re.fullmatch(r'bsd_additive_[0-9a-f]{24}',level_id) or
        level.get('song_name')!=info.get('_songName')):
        raise ValueError('prepared level/source song mismatch')
    full_duration=number(level.get('duration_seconds'),'song duration')
    separate_preview = info.get('_orbeatsPreviewFilename')
    start=0 if separate_preview else number(info.get('_previewStartTime',0),'preview start')
    duration=number(info.get('_previewDuration',min(10,full_duration)),'preview duration')
    if start<0 or not 1<=duration<=30 or start+duration>full_duration:
        raise ValueError('preview outside song or1..30second range')
    cover=source_file(source,info.get('_coverImageFilename'))
    audio=source_file(source,separate_preview or info.get('_songFilename'))
    image_info(cover)
    if pack_cover:image_info(Path(pack_cover))
    if output.exists():raise ValueError('use a new output directory; no overwrite')
    output.mkdir(parents=True)
    original=normalize_cover(cover,output/'song-cover.png')
    if pack_cover:normalize_cover(Path(pack_cover),output/'pack-cover.png')
    # Output -ss/-t can retain an extra codec/resampler block for Ogg sources.
    # Trim in the final44100Hz sample domain; verify rejects short/truncated audio.
    start_sample=round(start*44100);end_sample=start_sample+round(duration*44100)
    trim=f'aresample=44100,atrim=start_sample={start_sample}:end_sample={end_sample},asetpts=PTS-STARTPTS'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(audio),
                    '-map','0:a:0','-vn','-af',trim,'-ar','44100','-ac','2',
                    '-c:a','pcm_s16le',str(output/'preview.wav')],check=True,
                   capture_output=True,text=True,timeout=120)
    manifest={'schema':1,'level_id':level_id,'song_name':info['_songName'],
              'runtime_bound':False,'icon_target_pixels':[ICON_SIZE,ICON_SIZE],
              'native_playlist_dimensions_verified':False,
              'source_cover_pixels':original,
              'source_info_sha256':hashlib.sha256(info_paths[0].read_bytes()).hexdigest(),
              'source_audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),
              'source_cover_sha256':hashlib.sha256(cover.read_bytes()).hexdigest(),
              'preview_start_seconds':start,'preview_duration_seconds':duration,
              'song_cover':file_record(output/'song-cover.png'),
              'preview':file_record(output/'preview.wav'),
              'pack_cover':file_record(output/'pack-cover.png') if pack_cover else None}
    (output/'media-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return verify(output)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experimental',action='store_true',required=True)
    ap.add_argument('--song-dir',type=Path)
    ap.add_argument('--level-manifest',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--pack-cover',type=Path)
    ap.add_argument('--verify',type=Path)
    args=ap.parse_args()
    if args.verify:
        result=verify(args.verify)
    else:
        if not all((args.song_dir,args.level_manifest,args.output)):
            ap.error('--song-dir, --level-manifest and --output required')
        result=prepare(args.song_dir,args.level_manifest,args.output,args.pack_cover)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
