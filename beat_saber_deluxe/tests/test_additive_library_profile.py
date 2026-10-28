"""Review bindings without requiring downloaded song/audio/private game inputs."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]


def test_compiled_two_song_profiles_match_independent_manifest_fixtures(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('clang++ required')
    cpp=tmp_path/'profiles.cpp';exe=tmp_path/'profiles'
    cpp.write_text(r'''
#include "additive_library_profile.h"
#include <stdio.h>
using namespace BsdAdditive;
int main(){
 printf("[");
 for(size_t i=0;i<kReviewedSongCount;++i){const ReviewedSong& p=kReviewedSongs[i];
  printf("%s{\"id\":\"%s\",\"title\":\"%s\",\"author\":\"%s\",\"path\":\"%s\",\"asset\":\"%s\",\"sha\":\"%s\",\"bytes\":%zu,\"bpm\":%.9g,\"duration\":%.9g,\"mask\":%u,\"preview_seconds\":%.9g,\"cover\":\"%s\",\"preview\":\"%s\",\"stats\":[",
   i?",":"",p.id,p.title,p.author,p.path,p.asset,p.sha256,p.bytes,p.bpm,p.duration,p.difficulty_mask,p.preview_duration,p.cover.path,p.preview.path);
  for(int j=0;j<5;++j){auto& d=p.difficulties[j];printf("%s[%d,%d,%d,%.9g,%.9g]",j?",":"",d.notes,d.bombs,d.obstacles,d.njs,d.jump_offset);}
  printf("]}");
 }
 printf("]\n");
}
''')
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-I'+str(ROOT/'include'),str(cpp),'-o',str(exe)],check=True,capture_output=True)
    profiles=json.loads(subprocess.run([str(exe)],check=True,capture_output=True,text=True).stdout)
    assert len(profiles)==2
    assert profiles[0]['id']!=profiles[1]['id'] and profiles[0]['path']!=profiles[1]['path']
    for i,(p,file) in enumerate(zip(profiles,['additive-full-map-manifest.json','additive-second-map-manifest.json'])):
        m=json.loads((ROOT/'development/fixtures'/file).read_text())
        assert p['id']==m['level_id'] and p['title']==m['song_name'] and p['author']==m['song_author']
        assert p['path']=='/data/GoldHEN/AFR/CUSA12878/additive/'+m['bundle']['file']
        assert p['asset']==m['asset_name'] and p['sha']==m['bundle']['sha256'] and p['bytes']==m['bundle']['bytes']
        assert p['bpm']==m['bpm'] and p['duration']==pytest.approx(m['duration_seconds'],abs=.01)
        assert p['preview_seconds']==(10 if i==0 else 20)
        assert p['cover'].endswith(p['id']+'-media/song-cover.png')
        assert p['preview'].endswith(p['id']+'-media/preview.wav')
        mask=0
        for j,diff in enumerate(['Easy','Normal','Hard','Expert','ExpertPlus']):
            if diff not in m['difficulty_stats']:
                assert p['stats'][j]==[0]*5
                continue
            mask|=1<<j;d=m['difficulty_stats'][diff]
            assert p['stats'][j]==pytest.approx([d[k] for k in ['notes','bombs','obstacles','njs','jump_offset']])
        assert p['mask']==mask
    assert profiles[1]['mask']==28
