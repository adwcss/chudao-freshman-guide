"""Build a credential-free source release, Git bundle and clean-copy smoke report.

Run after committing source changes: python -X utf8 -I -S tools/package_release.py
Only the standard library and local Git are used. No HTTP/model requests are made.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import __version__

OUTPUT = ROOT / "output"
PREFIX = f"freshman-guide-{__version__}"
ZIP = OUTPUT / (PREFIX + ".zip")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_key(data, name):
    # Inspect only matches; never print the matched credential.
    for candidate in re.findall(rb"sk-[A-Za-z0-9_-]{16,}", data):
        if digest(candidate) in BLOCKED:
            raise RuntimeError("Received credential detected in " + name)


if git("status", "--porcelain").strip():
    raise SystemExit("Commit source changes before packaging.")
BLOCKED = set(json.loads((ROOT / "config/blocked_key_fingerprints.json").read_text(encoding="utf-8")))
OUTPUT.mkdir(exist_ok=True)
bundle = OUTPUT / "history.bundle"
subprocess.run(["git", "bundle", "create", str(bundle), "--all"], cwd=ROOT, check=True)
subprocess.run(["git", "bundle", "verify", str(bundle)], cwd=ROOT, check=True, capture_output=True)

# Audit every historical blob as well as the current files, without displaying keys.
objects = git("rev-list", "--objects", "--all").splitlines()
blobs_scanned = 0
for entry in objects:
    oid = entry.split(b" ", 1)[0].decode("ascii")
    if git("cat-file", "-t", oid).strip() == b"blob":
        check_key(git("cat-file", "blob", oid), "Git history blob")
        blobs_scanned += 1

files = {}
for item in git("ls-files", "-z").decode("utf-8").split("\0"):
    if not item:
        continue
    path = Path(item)
    if path.name == ".env" or any(p in {".venv", "venv", ".runtime", ".git"} for p in path.parts) or "backend/vectorstore/db" in item:
        raise RuntimeError("Excluded runtime/private file is tracked: " + item)
    data = (ROOT / path).read_bytes()
    check_key(data, item)
    files[item] = data
for item in ["output/pdf/初到-技术与复现说明.pdf", "output/screenshots/plan.png", "output/screenshots/bed-comparison.png", "output/screenshots/mobile-plan.png", "output/screenshots/map-110.png", "output/screenshots/tasks-120.png", "output/screenshots/mobile-tasks-120.png", "output/screenshots/mobile-task-form-120.png"]:
    files[item] = (ROOT / item).read_bytes()
files["history.bundle"] = bundle.read_bytes()
for item in ["output/screenshots/arrival-130.png", "output/screenshots/itinerary-130.png", "output/screenshots/mobile-arrival-130.png", "output/screenshots/mobile-itinerary-130.png"]:
    files[item] = (ROOT / item).read_bytes()

for item in ["output/screenshots/preparation-140.png", "output/screenshots/preparation-overview-140.png", "output/screenshots/mobile-preparation-140.png", "output/screenshots/mobile-preparation-overview-140.png"]:
    files[item] = (ROOT / item).read_bytes()

for item in ["output/screenshots/intro-150.png", "output/screenshots/custom-grid-150.png", "output/screenshots/custom-image-150.png", "output/screenshots/mobile-custom-150.png", "output/screenshots/mobile-appearance-settings-150.png"]:
    files[item] = (ROOT / item).read_bytes()

for item in ["mascot-lines-160.png", "mascot-color-160.png", "mascot-background-160.png", "custom-image-160.png", "mobile-mascot-background-160.png", "mobile-appearance-settings-160.png", "mobile-mascot-lines-160.png", "mobile-mascot-color-160.png", "mascot-pose-gallery-160.png", "mascot-wave-160.png", "mascot-reading-160.png", "mascot-point-160.png"]:
    files["output/screenshots/" + item] = (ROOT / "output/screenshots" / item).read_bytes()
for item in ["chibi-wave-160.png", "chibi-read-160.png", "chibi-ready-160.png", "chibi-guide-160.png", "chibi-think-160.png", "chibi-cheer-160.png", "mobile-chibi-read-160.png", "mascot-inspect-160.png"]:
    files["output/screenshots/" + item] = (ROOT / "output/screenshots" / item).read_bytes()

for item in ["creative-side-160.png", "creative-laugh-160.png", "creative-back-160.png", "creative-rest-160.png", "mascot-expression-gallery-160.png"]:
    files["output/screenshots/" + item] = (ROOT / "output/screenshots" / item).read_bytes()

smoke_code = r'''
import json, time
from pathlib import Path
started = time.perf_counter()
import sys
sys.path.insert(0, str(Path.cwd()))
from backend.main import Application
from backend.planner import validate_task, backup, validate_backup, calendar
from backend.orientation import CASES, route_text
from backend.preparation import memo_text, backup as prep_backup
app = Application()
stats = app.stats()
assert stats["document_count"] == 19 and stats["chunk_count"] == 235
assert not stats["remote_enabled"] and stats["remote_calls"] == 0
prepared = app.answerer.prepare("新生报到需要准备哪些材料？", [])
answer, mode = app.answerer.generate("新生报到需要准备哪些材料？", prepared)
assert mode == "local_evidence" and "【1】" in answer and prepared["sources"]
assert prepared["sources"][0]["source"] == "入学准备清单.md"
for item in ["frontend/index.html", "frontend/app.js", "frontend/style.css", "校园地图.png", "启动新生指南.cmd"]:
    assert Path(item).is_file()
for item in ["frontend/appearance.js", "frontend/appearance.css"]:
    assert Path(item).is_file()
assert 'id="appearance-dialog"' in Path("frontend/index.html").read_text(encoding="utf-8")
assert Path("frontend/assets/school-mascot.png").read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
assert json.loads(Path("frontend/assets/mascot-lines.json").read_text(encoding="utf-8"))["paths"]
for pose in ("wave", "reading", "point"):
    assert Path(f"frontend/assets/mascot-{pose}.png").is_file()
    assert json.loads(Path(f"frontend/assets/mascot-{pose}-lines.json").read_text(encoding="utf-8"))["paths"]
for pose in ("wave", "read", "ready", "guide", "think", "cheer"):
    assert Path(f"frontend/assets/chibi-{pose}.png").is_file()
    assert json.loads(Path(f"frontend/assets/chibi-{pose}-lines.json").read_text(encoding="utf-8"))["paths"]
for pose in ("side", "laugh", "back-v2", "rest"):
    assert Path(f"frontend/assets/creative-{pose}.png").is_file()
    assert json.loads(Path(f"frontend/assets/creative-{pose}-lines.json").read_text(encoding="utf-8"))["paths"]
assert len(json.loads(Path("docs/mascot-assets.json").read_text(encoding="utf-8"))) == 14
session = "release-smoke-000001"
app.store.check(session, "admission", True)
assert "admission" in app.store.checklist(session)
profile = {"interests": ["coding"], "priorities": {"quiet": 3, "light": 0, "access": 0, "dry": 0}}
recommend = app.experience.recommendations(profile)
assert recommend["groups"]["bed"][0]["position"] == "middle"
assert any(item["name"] == "计算机协会" for item in recommend["groups"]["club"])
app.store.set_profile(session, recommend["profile"])
app.store.set_saved(session, "bed-liuren-2", "doing")
assert app.store.saved(session)[0]["status"] == "doing"
assert app.store.profile(session)["interests"] == ["coding"]
assert len(CASES) == 9
app.store.answer_scenario(session, "notice", 1)
assert app.store.rehearsal(session) == {"notice": 1}
route = app.store.change_itinerary(session, {"revision": 0, "action": "preset", "preset": "study"})
route = app.store.change_itinerary(session, {"revision": route["revision"], "action": "visit", "place": "tushuguan", "visited": True})
assert "图书馆 · 已到访" in route_text(route) and "不是实际道路" in route_text(route)
assert app.store.itinerary(session) == route
ready = app.store.change_preparation(session, {"revision": 0, "action": "plan", "plan": {"departure": "2026-10-20", "arrival": "2026-10-21", "dorm": "qinyuan-1-9"}})
ready = app.store.change_preparation(session, {"revision": 1, "action": "item", "id": "towel", "item": {"quantity": 2, "status": "buy"}})
assert "到校购买 · 毛巾 × 2" in memo_text(ready, app.store.checklist(session), app.store.rehearsal(session), route)
restored_prep = app.store.change_preparation("release-prep-0000001", {"revision": 0, "action": "restore", "backup": prep_backup(ready)})
assert restored_prep["packing"] == ready["packing"] and restored_prep["plan"] == ready["plan"]
assert app.preparation(session)["state"] == ready
task = validate_task({"title": "核对通知", "due": "2026-10-18"}, app.experience.items)
app.store.put_task(session, task)
assert len(app.store.tasks(session)) == 1
restored = validate_backup(backup(app.store.tasks(session)), app.experience.items)
assert app.store.merge_tasks("release-restore-00001", restored)["added"] == 1
assert "DTSTART;VALUE=DATE:20261018" in calendar(app.store.tasks(session), app.experience.items)
print(json.dumps({"success": True, "health": stats, "cold_load_seconds": round(time.perf_counter() - started, 3), "answer_has_citations": True, "persisted_checklist": True, "source_root": "freshly extracted release", "python_site_disabled": True}, ensure_ascii=False))
'''
tmp = ROOT / "tmp"
tmp.mkdir(exist_ok=True)
with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(PREFIX + "/" + name, data)
with tempfile.TemporaryDirectory(prefix="release-smoke-", dir=tmp) as temp:
    copied = Path(temp) / PREFIX
    with zipfile.ZipFile(ZIP) as archive:
        for member in archive.infolist():
            target = (Path(temp) / member.filename).resolve()
            if not target.is_relative_to(Path(temp).resolve()):
                raise RuntimeError("Archive path escapes test directory")
        archive.extractall(temp)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GUIDE_") and k != "DEEPSEEK_API_KEY"}
    result = subprocess.run([sys.executable, "-X", "utf8", "-I", "-S", "-c", smoke_code], cwd=copied, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if result.returncode:
        raise RuntimeError("Clean-copy smoke failed:\n" + result.stderr)
    report = json.loads(result.stdout)
assert report["health"]["version"] == __version__
verification = json.loads((ROOT / "docs/verification.json").read_text(encoding="utf-8"))
report.update({"date": "2026-10-15", "git_head": git("rev-parse", "HEAD").decode().strip(), "git_bundle_verified": True, "historical_blobs_scanned": blobs_scanned, "received_key_matches": 0, "http_regressions": f"{verification['tests']} checks in docs/verification.json; clean-copy test uses direct application loading"})
report_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
(OUTPUT / "release-verification.json").write_bytes(report_bytes)
files["output/release-verification.json"] = report_bytes
manifest = {"version": __version__, "date": "2026-10-15", "git_head": report["git_head"], "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in sorted(files.items())}}
files["release-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(PREFIX + "/" + name, data)
with zipfile.ZipFile(ZIP) as archive:
    assert archive.testzip() is None
    assert len(archive.infolist()) == len(files)
    for name, details in manifest["files"].items():
        assert digest(archive.read(PREFIX + "/" + name)) == details["sha256"]
release = {"zip": ZIP.name, "bytes": ZIP.stat().st_size, "sha256": digest(ZIP.read_bytes()), "file_count": len(files), "crc_check": True, "smoke": report}
(OUTPUT / "release-summary.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(release, ensure_ascii=False, indent=2))
