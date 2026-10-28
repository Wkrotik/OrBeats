"""Shared companion wire codec. No FTP; bounded, canonical UTF8/little endian."""
import math
import re
import struct

from native_hash import fnv
from additive_lighting import NATIVE_ENVIRONMENTS

MAGIC=b'BSDALIB1'
MAX_SONGS=64
MAX_BYTES=131072
BASE='/data/GoldHEN/AFR/CUSA12878/additive'
DIFFS=('Easy','Normal','Hard','Expert','ExpertPlus')


def paths(song):
    id=song['id']
    if not re.fullmatch(r'bsd_additive_[0-9a-f]{24}',id):raise ValueError('invalid own level ID')
    return (f'{BASE}/{id}.bundle',f'{BASE}/{id}-media/song-cover.png',f'{BASE}/{id}-media/preview.wav')


def encode(songs):
    if not isinstance(songs,list) or not 0<=len(songs)<=MAX_SONGS:raise ValueError('library exceeds the current resource budget')
    version4 = any(s.get('modes') for s in songs)
    version3 = version4 or any(s.get('presentation') for s in songs)
    version2 = version3 or any(s.get('environment') for s in songs)
    seen=set();out=bytearray(struct.pack('<I',len(songs)))
    def integer(v,low,high,fmt='<I'):
        if type(v) is not int or not low<=v<=high:raise ValueError('invalid integer bound')
        out.extend(struct.pack(fmt,v))
    def real(v,low,high):
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:raise ValueError('invalid float bound')
        out.extend(struct.pack('<f',v))
    def text(v,limit):
        if not isinstance(v,str) or not v or any(ord(c)<32 or ord(c)==127 for c in v):raise ValueError('invalid text')
        b=v.encode('utf8')
        if len(b)>=limit:raise ValueError('text too long')
        integer(len(b),1,limit-1);out.extend(b)
    for s in songs:
        paths(s)
        if s['id'] in seen:raise ValueError('duplicate level ID')
        seen.add(s['id'])
        if not re.fullmatch('[0-9a-f]{64}',s['sha256']):raise ValueError('invalid bundle digest')
        for key,limit in [('id',81),('title',256),('author',256),('sha256',65)]:text(s[key],limit)
        integer(s['bytes'],1,200000000);integer(s['fnv'],0,2**64-1,'<Q')
        real(s['bpm'],1,1000);real(s['duration'],1,1800)
        real(s['preview_duration'],1,min(30,s['duration']));integer(s['mask'],0 if version4 else 1,31)
        if len(s['stats'])!=5:raise ValueError('five stats entries required')
        for i,d in enumerate(s['stats']):
            if len(d)!=5:raise ValueError('bad difficulty stats')
            if not s['mask']&(1<<i) and any(d):raise ValueError('unused difficulty has data')
            for v in d[:3]:integer(v,0,200000)
            real(d[3],.1 if s['mask']&(1<<i) else 0,100);real(d[4],-20,20)
        for key,low in [('cover',1),('preview',44)]:
            integer(s[key]['bytes'],low,6000000);integer(s[key]['fnv'],0,2**64-1,'<Q')
        if version2:
            environment = s.get('environment', 'stock')
            if environment not in NATIVE_ENVIRONMENTS | {'stock'}:
                raise ValueError('unreviewed library environment')
            text(environment, 64)
        if version3:
            from additive_presentation import validate, COLORS
            profile = validate(s.get('presentation') or dict(lufs=-14, offset=0, colors=[{} for _ in range(5)]))
            real(profile['lufs'], -100, 100); real(profile['offset'], -10, 10)
            for d, palette in enumerate(profile['colors']):
                if palette and not version4 and not s['mask'] & (1 << d): raise ValueError('unused difficulty has palette data')
                integer(sum(1 << i for i, k in enumerate(COLORS) if k in palette), 0, 511)
                for k in COLORS:
                    if k in palette:
                        for v in palette[k]: real(v, 0, 1)
        if version4:
            from additive_modes import MODES
            modes = s.get('modes', {})
            if not isinstance(modes, dict) or set(modes) - set(MODES[1:]): raise ValueError('invalid native modes')
            integer(sum(1 << i for i,k in enumerate(MODES[1:]) if k in modes),0,15)
            if not s.get('mask',31) and not modes: raise ValueError('no playable characteristic')
            for k in MODES[1:]:
                if k not in modes: continue
                mode = modes[k]; integer(mode['mask'],1,31)
                if len(mode['stats']) != 5: raise ValueError('five native mode stats required')
                for idx,row in enumerate(mode['stats']):
                    if len(row)!=5: raise ValueError('invalid native mode stats')
                    for n in row[:3]: integer(n,0,100000)
                    real(row[3],0,100); real(row[4],-10,10)
                    if mode['mask']&(1<<idx):
                        if row[0]<=0 or row[3]<.1: raise ValueError('invalid active native mode stats')
                    elif any(row): raise ValueError('inactive native mode stats')
    if len(out)+20>MAX_BYTES:raise ValueError('oversized library')
    return (b'BSDALIB4' if version4 else b'BSDALIB3' if version3 else b'BSDALIB2' if version2 else MAGIC)+struct.pack('<IQ',len(out),fnv(out))+out


def decode(data):
    if not isinstance(data,bytes) or not 24<=len(data)<=MAX_BYTES or data[:8] not in (MAGIC,b'BSDALIB2',b'BSDALIB3',b'BSDALIB4'):raise ValueError('bad library header')
    length,digest=struct.unpack_from('<IQ',data,8)
    if length!=len(data)-20 or fnv(data[20:])!=digest:raise ValueError('library checksum/length mismatch')
    offset=20
    def take(fmt):
        nonlocal offset
        n=struct.calcsize(fmt)
        if offset+n>len(data):raise ValueError('truncated library')
        v=struct.unpack_from(fmt,data,offset);offset+=n;return v[0] if len(v)==1 else list(v)
    def text():
        nonlocal offset
        n=take('<I')
        if n>256 or offset+n>len(data):raise ValueError('invalid string length')
        b=data[offset:offset+n];offset+=n;return b.decode('utf8')
    count=take('<I')
    if not 0<=count<=MAX_SONGS:raise ValueError('invalid count')
    songs=[]
    for _ in range(count):
        s=dict(zip(('id','title','author','sha256'),(text() for j in range(4))))
        s.update(zip(('bytes','fnv','bpm','duration','preview_duration','mask'),(take(f) for f in ('<I','<Q','<f','<f','<f','<I'))))
        s['stats']=[take('<IIIff') for j in range(5)]
        for k in ('cover','preview'):s[k]={'bytes':take('<I'),'fnv':take('<Q')}
        if data[:8] in (b'BSDALIB2', b'BSDALIB3',b'BSDALIB4'):
            environment = text()
            if environment not in NATIVE_ENVIRONMENTS | {'stock'}:
                raise ValueError('unreviewed library environment')
            if environment != 'stock':
                s['environment'] = environment
        if data[:8] in (b'BSDALIB3',b'BSDALIB4'):
            from additive_presentation import COLORS
            profile = dict(lufs=take('<f'), offset=take('<f'), colors=[])
            for _ in range(5):
                flags = take('<I')
                if flags > 511: raise ValueError('invalid palette flags')
                profile['colors'].append({k:take('<ffff') for i,k in enumerate(COLORS) if flags & (1 << i)})
            if profile['lufs'] != -14 or profile['offset'] or any(profile['colors']): s['presentation'] = profile
        if data[:8] == b'BSDALIB4':
            from additive_modes import MODES
            flags = take('<I')
            if flags>15: raise ValueError('invalid native mode flags')
            modes={}
            for i,k in enumerate(MODES[1:]):
                if flags&(1<<i): modes[k]={'mask':take('<I'),'stats':[[take('<I'),take('<I'),take('<I'),take('<f'),take('<f')] for _ in range(5)]}
            if modes: s['modes']=modes
        songs.append(s)
    if offset!=len(data) or encode(songs)!=data:raise ValueError('noncanonical library')
    return songs


def descriptor(manifest,bundle,cover,preview,seconds):
    stats=[];mask=0
    for i,d in enumerate(DIFFS):
        v=manifest['difficulty_stats'].get(d)
        if v:mask|=1<<i
        stats.append([v[k] for k in ('notes','bombs','obstacles','njs','jump_offset')] if v else [0]*5)
    import hashlib
    if len(bundle)!=manifest['bundle']['bytes'] or hashlib.sha256(bundle).hexdigest()!=manifest['bundle']['sha256']:raise ValueError('prepared bundle digest mismatch')
    result = {'id':manifest['level_id'],'title':manifest['song_name'],'author':manifest['song_author'],
        'sha256':manifest['bundle']['sha256'],'bytes':len(bundle),'fnv':fnv(bundle),
        'bpm':manifest['bpm'],'duration':manifest['duration_seconds'],'preview_duration':seconds,'mask':mask,'stats':stats,
        'cover':{'bytes':len(cover),'fnv':fnv(cover)},'preview':{'bytes':len(preview),'fnv':fnv(preview)}}
    from additive_modes import MODES
    modes = {}
    for k in MODES[1:]:
        rows=[];mask=0
        for i,d in enumerate(DIFFS):
            v=manifest['difficulty_stats'].get(k+'/'+d)
            if v:mask|=1<<i
            rows.append([v[n] for n in ('notes','bombs','obstacles','njs','jump_offset')] if v else [0]*5)
        if mask:modes[k]={'mask':mask,'stats':rows}
    if modes:result['modes']=modes
    if manifest.get('environment'):
        if manifest['environment'] not in NATIVE_ENVIRONMENTS:
            raise ValueError('unreviewed prepared environment')
        result['environment'] = manifest['environment']
    if manifest.get('presentation'): result['presentation'] = manifest['presentation']
    return result
