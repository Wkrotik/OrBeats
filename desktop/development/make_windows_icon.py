"""Convert the owned OrBeats PNG into the Windows resource icon; no game art."""

from pathlib import Path

from PIL import Image

source = Path(__file__).resolve().parents[1] / "src-tauri/icons/icon.png"
image = Image.open(source).convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
image.save(
    source.with_suffix(".ico"),
    format="ICO",
    sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)],
)
