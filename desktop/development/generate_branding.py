"""Generate product assets from the owned root icon.svg (requires librsvg + Pillow).

PNG/ICO are platform-required derivatives; SVG stays canonical. No runtime tools.
"""
import io
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def main():
    renderer = shutil.which("rsvg-convert")
    if renderer is None:
        raise SystemExit("Install/use a local librsvg rsvg-convert to regenerate icons")
    source = ROOT / "icon.svg"
    for relative in ("orbeats/webapp/static/orbeats.svg", "desktop/ui/icon.svg"):
        target = ROOT / relative
        target.write_bytes(source.read_bytes())
    value = subprocess.check_output([renderer, "--width", "1024", "--height", "1024", str(source)])
    image = Image.open(io.BytesIO(value)).convert("RGBA")
    image.save(ROOT / "desktop/src-tauri/icons/icon.png", optimize=True)
    subprocess.run([sys.executable, str(ROOT / "desktop/development/make_windows_icon.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "orbeats/development/scripts/generate_plugin_branding.py")], check=True)
    print("Generated SVG copies, transparent desktop PNG/ICO and embedded plugin logo")


if __name__ == "__main__":
    main()
