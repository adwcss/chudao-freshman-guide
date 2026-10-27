"""Inspect the received baseline without downloading models or calling an API.

Run: python -X utf8 -I -S tools/inspect_handover.py
This reads source files and the copied database; it does not rebuild the index.
"""

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import runpy
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def inspect():
    source_files = sorted(
        list((ROOT / "backend").rglob("*.py"))
        + list((ROOT / "frontend").rglob("*.py"))
    )
    syntax_errors = []
    for path in source_files:
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as error:
            syntax_errors.append({"file": str(path.relative_to(ROOT)), "error": str(error)})

    # The received splitter was reviewed: it imports only os/re and reads documents.
    splitter = runpy.run_path(str(ROOT / "backend/retriever/splitter.py"))
    chunks = splitter["split_all"](str(ROOT))
    by_source = Counter(chunk["source"] for chunk in chunks)
    supplement = [chunk for chunk in chunks if chunk["source"] == "入学指南补充.md"]
    campus_map = [chunk for chunk in chunks if chunk["source"] == "校园地图.md"]

    # Extract static route definitions without importing Streamlit or creating a UI.
    frontend_tree = ast.parse((ROOT / "frontend/app.py").read_text(encoding="utf-8"))
    route_steps = []
    for node in ast.walk(frontend_tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "route_steps" for target in node.targets
        ):
            route_steps = ast.literal_eval(node.value)
    route_queries = [
        {"displayed": step["question"], "sent_to_service": step["title"] + "在哪?"}
        for step in route_steps
    ]

    database = ROOT / "backend/vectorstore/db/chroma.sqlite3"
    database_summary = {"present": database.is_file()}
    if database.is_file():
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "embeddings" in tables:
                database_summary["embedding_rows"] = connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            if "collections" in tables:
                database_summary["collections"] = [
                    {"name": row[0], "dimension": row[1]}
                    for row in connection.execute("SELECT name, dimension FROM collections")
                ]

    return {
        "scope": "Local baseline inspection; no API calls, model inference, or service startup",
        "python_files_checked": len(source_files),
        "syntax_errors": syntax_errors,
        "expected_document_count": len(splitter["DOC_FILES"]),
        "documents_found": len(by_source),
        "split_chunk_count": len(chunks),
        "chunks_per_source": dict(by_source),
        "supplement_chunks_contain_2024": any("2024" in chunk["text"] for chunk in supplement),
        "supplement_chunks_preserve_header_year_caveat": any("2024级参考信息" in chunk["text"] for chunk in supplement),
        "supplement_chunks_preserve_source_url": any("https://" in chunk["text"] for chunk in supplement),
        "map_chunks_preserve_disclaimer": any("地图为示意" in chunk["text"] for chunk in campus_map),
        "map_contains_swimming_facility": any("游泳馆" in chunk["text"] for chunk in campus_map),
        "map_file_present": (ROOT / "校园地图.png").is_file(),
        "route_queries": route_queries,
        "copied_database": database_summary,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save the UTF-8 inspection result")
    args = parser.parse_args()
    result = json.dumps(inspect(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
