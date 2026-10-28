#!/usr/bin/env python3
"""Regenerate the embedded plugin logo from OrBeats' owned desktop artwork."""
import hashlib
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]


def main():
    source = ROOT / 'desktop/src-tauri/icons/icon.png'
    image = Image.open(source).convert('RGBA').resize((512, 512), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    data = output.getvalue()
    text = ('// Owned OrBeats icon; desktop/src-tauri/icons/icon.png resized to512px.\n'
            '// PNG SHA256 ' + hashlib.sha256(data).hexdigest() + '\n'
            '#pragma once\n#include <stddef.h>\nnamespace OrBeatsBrand {\n'
            'static const unsigned char kLogoPng[]={\n')
    text += ''.join('    ' + ','.join('0x%02x' % x for x in data[i:i+24]) + ',\n'
                    for i in range(0, len(data), 24))
    text += '};\nstatic const size_t kLogoBytes=sizeof(kLogoPng);\n}\n'
    target = ROOT / 'beat_saber_deluxe/include/orbeats_branding.h'
    target.write_text(text)
    print(f'Embedded {len(data)} PNG bytes; SHA256 {hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
