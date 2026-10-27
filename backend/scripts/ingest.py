"""Validate current documents without modifying the received vector database."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.retriever.splitter import split_all

if __name__ == "__main__":
    chunks = split_all(ROOT)
    print(json.dumps({"chunk_count": len(chunks), "documents": dict(Counter(c["source"] for c in chunks)), "note": "Default service indexes documents in memory on startup. Restart after edits. No model or API needed."}, ensure_ascii=False, indent=2))
