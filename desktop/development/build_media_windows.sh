#!/usr/bin/env bash
# Native Windows/MSYS2 UCRT64 build from pinned source. Testing payload, not release.
# No game inputs, downloads of prebuilt codec DLLs, host installs or PS4 operations.
set -euo pipefail
[[ "${MSYSTEM:-}" == UCRT64 ]] || { echo 'Run inside a native Windows MSYS2 UCRT64 shell' >&2; exit 2; }
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$(realpath -m "${1:?fresh project-local temp output required}")"
[[ "$OUT" == "$ROOT"/temp/* && ! -e "$OUT" ]] || { echo 'Choose fresh project-local temp output' >&2; exit 2; }
mkdir -p "$OUT/downloads" "$OUT/gnupg" "$OUT/payload/bin" "$OUT/payload/lib" "$OUT/payload/legal"
chmod 700 "$OUT/gnupg"
# Native Windows curl uses the Windows TLS stack, avoiding MSYS Python's
# repeatedly-reset OpenSSL handshakes. Integrity/signature gates below remain.
NATIVE_CURL="$(cygpath -u "${WINDIR:?Windows directory required}")/System32/curl.exe"
[[ -f "$NATIVE_CURL" ]] || { echo 'Native Windows curl is required' >&2; exit 2; }
export ROOT OUT NATIVE_CURL
python - <<'PY'
import json,os,pathlib,hashlib,tarfile,subprocess
root=pathlib.Path(os.environ['ROOT']);out=pathlib.Path(os.environ['OUT'])
ff=json.loads((root/'desktop/development/media-linux-lock.json').read_text())['ffmpeg']
codecs=json.loads((root/'desktop/development/codecs-linux-lock.json').read_text())['sources']
def fetch(url, limit):
 if not url.startswith('https://'):raise ValueError('Source must use HTTPS')
 result=subprocess.run([os.environ['NATIVE_CURL'],'--fail','--location',
  '--proto','=https','--proto-redir','=https','--retry','3','--retry-all-errors',
  '--connect-timeout','30','--max-time','180','--max-filesize',str(limit),
  '--silent','--show-error',url],check=True,stdout=subprocess.PIPE)
 if len(result.stdout)>limit:raise ValueError('Oversized source')
 return result.stdout
for key in ['source','signature','key']:
 data=fetch(ff[key],20000001)
 if len(data)>20000000 or hashlib.sha256(data).hexdigest()!=ff[key+'_sha256']:raise ValueError('FFmpeg pinned source mismatch:'+key)
 (out/'downloads'/key).write_bytes(data)
archives=[(out/'downloads/source','ffmpeg-'+ff['version'])]
for row in codecs:
 data=fetch(row['url'],10000001)
 if len(data)>10000000 or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Xiph pinned source mismatch')
 file=out/'downloads'/(row['name']+'.tar.xz');file.write_bytes(data);archives.append((file,row['name']+'-'+row['version']))
for file,stem in archives:
 with tarfile.open(file,'r:xz') as tar:
  if any((p.name!=stem and not p.name.startswith(stem+'/')) or p.issym() or p.islnk() or not(p.isfile() or p.isdir()) for p in tar.getmembers()):raise ValueError('Unexpected source archive member')
  tar.extractall(out,filter='data')
(out/'fingerprint.txt').write_text(ff['fingerprint'])
PY
gpg --homedir "$OUT/gnupg" --batch --no-auto-key-retrieve --import "$OUT/downloads/key"
gpg --homedir "$OUT/gnupg" --batch --no-auto-key-retrieve --status-fd 1 --verify "$OUT/downloads/signature" "$OUT/downloads/source" > "$OUT/signature-proof.txt"
grep -F "[GNUPG:] VALIDSIG $(cat "$OUT/fingerprint.txt") " "$OUT/signature-proof.txt"
# Explicit profile mirrors tested Linux features, but targets Windows UCRT/PE.
mapfile -t FLAGS < <(python - <<'PY'
import ast,os,pathlib
p=pathlib.Path(os.environ['ROOT'])/'desktop/development/build_media_linux.py'
for node in ast.parse(p.read_text()).body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in node.targets):
  print('\n'.join(ast.literal_eval(node.value)));break
else:raise ValueError('Missing reviewed FFmpeg flags')
PY
)
unset CFLAGS CPPFLAGS LDFLAGS LIBRARY_PATH PKG_CONFIG_PATH PKG_CONFIG_LIBDIR
export CC=gcc CXX=g++
(cd "$OUT/ffmpeg-8.0.1"; ./configure --target-os=mingw32 --arch=x86_64 --cc=gcc --cxx=g++ "${FLAGS[@]}"; make -j4) > "$OUT/ffmpeg-build.log" 2>&1
cp "$OUT/ffmpeg-8.0.1/ffmpeg.exe" "$OUT/ffmpeg-8.0.1/ffprobe.exe" "$OUT/payload/bin/"
for STEM in libogg-1.3.6 libvorbis-1.3.7; do
 (
  cd "$OUT/$STEM"
  export CPPFLAGS="-I$OUT/deps/include" LDFLAGS="-L$OUT/deps/lib -static-libgcc"
  export PKG_CONFIG_LIBDIR="$OUT/deps/lib/pkgconfig"
  ./configure --host=x86_64-w64-mingw32 --prefix="$OUT/deps" --enable-shared --disable-static
  make -j4; make install
 ) > "$OUT/$STEM-build.log" 2>&1
done
for LIB in libogg-0.dll libvorbis-0.dll libvorbisenc-2.dll; do
 cp "$OUT/deps/bin/$LIB" "$OUT/payload/lib/$LIB"
 objdump -p "$OUT/payload/lib/$LIB" | grep 'DLL Name:' >> "$OUT/dll-imports.txt"
done
for TOOL in ffmpeg ffprobe; do "$OUT/payload/bin/$TOOL.exe" -version; done
cp "$OUT/ffmpeg-8.0.1/COPYING.LGPLv2.1" "$OUT/ffmpeg-8.0.1/LICENSE.md" "$OUT/payload/legal/"
cp "$ROOT/desktop/development/media-linux-lock.json" "$OUT/payload/legal/source-lock.json"
cp "$ROOT/desktop/development/codecs-linux-lock.json" "$OUT/payload/legal/codecs-source-lock.json"
cp "$ROOT/desktop/development/build_media_windows.sh" "$OUT/payload/legal/"
cp "$OUT/libogg-1.3.6/COPYING" "$OUT/payload/legal/libogg-COPYING"
cp "$OUT/libvorbis-1.3.7/COPYING" "$OUT/payload/legal/libvorbis-COPYING"
python - <<'PY'
import json,os,pathlib,hashlib,subprocess
out=pathlib.Path(os.environ['OUT']);payload=out/'payload'
record={'target':'windows-x64','recipe':'build_media_windows.sh','ffmpeg':'8.0.1','ogg':'1.3.6','vorbis':'1.3.7','signature_checked':True,'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],'packages':subprocess.check_output(['pacman','-Q'],text=True).splitlines(),'release_approved':False}
for name in ['build-command.json','codecs-build-command.json']:(payload/'legal'/name).write_text(json.dumps(record,indent=2)+'\n')
inventory={p.relative_to(payload).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(payload.rglob('*')) if p.is_file()}
(payload/'manifest.json').write_text(json.dumps(inventory,indent=2)+'\n')
print(json.dumps({'payload':str(payload),'files':len(inventory),'candidate_only':True},indent=2))
PY
