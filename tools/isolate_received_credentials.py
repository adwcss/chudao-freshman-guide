"""Record deny-list fingerprints of received keys without exposing or using them."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
# 原始交接材料改为放在项目根目录 received/ 下（含 新生指南.zip 与 赛事要求.txt），不再硬编码来源机器路径
INPUTS = ROOT / "received"


def main():
    occurrences = []
    with zipfile.ZipFile(INPUTS / "新生指南.zip") as archive:
        env = archive.read("新生指南/backend/.env").decode("utf-8-sig")
    texts = [("新生指南.zip/backend/.env", env), ("赛事要求.txt", (INPUTS / "赛事要求.txt").read_text(encoding="utf-8-sig"))]
    fingerprints = set()
    for location, text in texts:
        for key in set(re.findall(r"sk-[A-Za-z0-9_-]{16,}", text)):
            fingerprint = hashlib.sha256(key.encode()).hexdigest()
            fingerprints.add(fingerprint)
            occurrences.append({"location": location, "fingerprint": fingerprint, "used": False})
    config = ROOT / "config"
    config.mkdir(exist_ok=True)
    (config / "blocked_key_fingerprints.json").write_text(json.dumps(sorted(fingerprints), indent=2) + "\n", encoding="utf-8")
    report = {"date": "2026-10-08", "key_occurrences": occurrences, "distinct_received_keys": len(fingerprints), "actions": ["Working copy excludes received .env", "Received keys are blocked by fingerprint", "Remote calls disabled by default", "No key validity or balance checks performed"]}
    (ROOT / "docs/credential-isolation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(fingerprints)} blocked key fingerprints at {len(occurrences)} locations. No API calls.")


if __name__ == "__main__":
    main()
