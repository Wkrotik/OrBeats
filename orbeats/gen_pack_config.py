import json, base64, struct, sys, re, os
sys.path.insert(0, 'tools')
import build_pack_mode_bundles as bpm

PACKS = [p.strip() for p in sys.argv[1].split(',') if p.strip()]
label = '2pack' if len(PACKS) == 2 else ('%dpack' % len(PACKS))
dump = '/workspace/ps4_dump/CUSA12878-patch/Media/StreamingAssets/aa/catalog.json'
manifest = {e['pack']: e for e in bpm.load_manifest('pack_modes_bundles')}

# --- 1) merged catalog patched for exactly PACKS ---
cat_out = 'catalog_pack_modes_%s.json' % label
results = [manifest[p] for p in PACKS if p in manifest]
n = bpm.write_merged_catalog(dump, results, cat_out)
print('catalog %s: %d entries patched -> %s' % (label, n, cat_out))

# verify patched CRCs match deployed bundles for PACKS, others origin
cat = json.load(open(cat_out))
ex = bytearray(base64.b64decode(cat['m_ExtraDataString']))
n2 = len(ex); i = 0; info = {}
while i < n2:
    if ex[i] != 7:
        i += 1; continue
    try:
        ln = ex[i+1]; po = i+2+ln; ln = ex[po]; po = po+1+ln
        jslen = struct.unpack_from('<I', ex, po)[0]; po += 4
    except Exception:
        i += 1; continue
    if jslen <= 0 or jslen > 400000 or po + jslen > n2:
        i += 1; continue
    s = ex[po:po+jslen].decode('utf-16-le', 'replace')
    for p in PACKS + ['billieeilish', 'lizzo', 'camellia']:
        if ('%s_pack_assets_all' % p) in s and '"m_BundleName"' in s:
            cr = re.search(r'"m_Crc":(\d+)', s)
            info[p] = cr.group(1) if cr else '?'
    i = po + jslen
print('  patched CRCs in catalog:', {p: info.get(p) for p in PACKS})
cnt, nz, bad = bpm.validate_catalog_dataindexes(cat)
print('  dataIndex validation: total=%d bad=%d' % (cnt, bad))

# --- 2) redirects: 38 songs + catalog + PACKS only ---
base = json.load(open('redirects.json'))
red = base['redirects']
# drop all pack redirects, keep songs + catalog
for k in list(red):
    if 'pack_assets_all' in k:
        del red[k]
# add PACKS
for p in PACKS:
    me = manifest[p]
    orig_name = 'Media/StreamingAssets/aa/PS4/%s_pack_assets_all_%s.bundle' % (p, me.get('catalogBundleName') or '')
    # the redirect key is the file name (m_Hash). Find it from the original bundle name pattern.
    # Use the known file hash from the deployed patched bundle name:
    key = '%s_pack_assets_all_%s.bundle' % (p, me['patchedBundle'].split('assets_all_')[-1].replace('_modes', '').replace('.bundle', ''))
    val = me['patchedBundle']
    red[key] = val
red_json = base.copy(); red_json['redirects'] = red
out_r = 'redirects_%s.json' % label
json.dump(red_json, open(out_r, 'w'), indent=2)
print('redirects %s: %d entries -> %s' % (label, len(red), out_r))
print('  pack redirects:', [k.split('/')[-1] for k in red if 'pack_assets_all' in k])
