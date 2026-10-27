"""Configuration is offline by default. A key alone never enables paid requests."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    allow_remote: bool = False
    api_key: str = ""
    model: str = "deepseek-chat"
    allow_web: bool = False
    web_key: str = ""
    web_engine: str = "bing"
    data_dir: Path = ROOT / ".runtime"

    @classmethod
    def load(cls):
        # Deliberately do not load the received backend/.env or DEEPSEEK_API_KEY.
        return cls(
            allow_remote=os.environ.get("GUIDE_ALLOW_REMOTE_LLM", "false").lower() == "true",
            api_key=os.environ.get("GUIDE_LLM_API_KEY", "").strip(),
            model=os.environ.get("GUIDE_LLM_MODEL", "deepseek-chat"),
            allow_web=os.environ.get("GUIDE_ALLOW_WEB", "false").lower() == "true",
            web_key=os.environ.get("GUIDE_WEB_API_KEY", "").strip(),
            web_engine=(os.environ.get("GUIDE_WEB_ENGINE", "bing") or "bing").strip().lower() or "bing",
            data_dir=Path(os.environ.get("GUIDE_DATA_DIR", str(ROOT / ".runtime"))),
        )

    def remote_enabled(self):
        if not self.allow_remote or not self.api_key:
            return False
        blocked = json.loads((ROOT / "config/blocked_key_fingerprints.json").read_text(encoding="utf-8"))
        return hashlib.sha256(self.api_key.encode()).hexdigest() not in blocked

    def web_enabled(self):
        # Net search is opt-in and needs its own key; a bare flag alone never enables it.
        if not self.allow_web or not self.web_key:
            return False
        return self.web_engine in {"bing", "google"}

    def key_blocked(self):
        if not self.api_key:
            return False
        blocked = json.loads((ROOT / "config/blocked_key_fingerprints.json").read_text(encoding="utf-8"))
        return hashlib.sha256(self.api_key.encode()).hexdigest() in blocked
