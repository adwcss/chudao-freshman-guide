"""Package fourteen selected PNGs, SVG stroke data, prompts and provenance."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
assets = ROOT / "frontend/assets"
target = ROOT / "output/school-mascot-assets-1.6.0.zip"
metadata = json.loads((ROOT / "docs/mascot-assets.json").read_text(encoding="utf-8"))
assert len(metadata) == 14
files = {}
for entry in metadata:
    name = entry["name"]
    data = (assets / (name + ".png")).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    assert entry["alpha_range"][0] == 0
    files["PNG/" + name + ".png"] = data
    outline = "mascot-lines.json" if name == "school-mascot" else name + "-lines.json"
    files["SVG路径/" + outline] = (assets / outline).read_bytes()
for name in ["mascot-assets.json", "mascot-asset-provenance.json", "mascot-pose-prompts.json", "chibi-asset-prompts.json", "creative-asset-prompts.json", "校园形象与开场-1.6.0.md"]:
    files["说明/" + name] = (ROOT / "docs" / name).read_bytes()
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for name, data in files.items():
        archive.writestr(name, data)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
report = {"success": True, "file": target.name, "images": len(metadata), "entries": len(files), "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
(ROOT / "output/mascot-assets-release.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
