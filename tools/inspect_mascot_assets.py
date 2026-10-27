"""Inspect selected alpha assets and keep HTML dimensions accurate (dev only)."""
import hashlib
import json
from pathlib import Path
import re
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "frontend/assets"
rows, sizes = [], {}
for file in sorted(folder.glob("*.png")):
    with Image.open(file) as picture:
        assert picture.mode == "RGBA"
        alpha = list(picture.getextrema()[-1])
        assert alpha[0] == 0
        size = list(picture.size)
    outline = "mascot-lines.json" if file.stem == "school-mascot" else file.stem + "-lines.json"
    sizes[file.stem] = size
    rows.append({"name": file.stem, "size": size, "alpha_range": alpha,
                 "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                 "strokes": len(json.loads((folder / outline).read_text(encoding="utf-8"))["paths"])})
assert len(rows) == 14
(ROOT / "docs/mascot-assets.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
html = ROOT / "frontend/index.html"
def dimensions(match):
    name = match[1]
    if name not in sizes:
        return match[0]
    width, height = sizes[name]
    return f'src="/assets/{name}.png" width="{width}" height="{height}"'
html.write_text(re.sub(r'src="/assets/([a-z-]+)\.png" width="[0-9]+" height="[0-9]+"', dimensions,
                       html.read_text(encoding="utf-8")), encoding="utf-8")
print(json.dumps({"images": len(rows), "alpha_valid": True, "total_png_bytes": sum(p.stat().st_size for p in folder.glob("*.png"))}))
