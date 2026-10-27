"""Repeatable FAQ retrieval evaluation; no network or model calls."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.retriever.retriever import Retriever

CASES = [
    ("新生什么时候报到？", "报到时间"), ("学校在哪些站点接站？", "接站"),
    ("报到点在哪里？", "地点安排"), ("学费怎么交？", "缴费"),
    ("学费咋交", "缴费"), ("报到要带什么材料？", "必备材料"),
    ("党团组织关系怎么转？", "团"), ("生源地助学贷款怎么申请？", "贷款"),
    ("校园一卡通在哪里充值？", "充值"), ("户口迁移怎么办理？", "户口"),
    ("馨园宿舍在哪？", "馨园"), ("沁园宿舍在哪？", "沁园"),
    ("图书馆在哪里？", "图书馆"), ("第一餐厅在哪？", "第一餐厅"),
    ("宿舍水电费怎么交？", "水电"), ("学校快递地址怎么写？", "快递"),
    ("学校有哪些院系和专业？", "专业"), ("军训什么时候开始？", "军训"),
]


def evaluate():
    started = time.perf_counter()
    retriever = Retriever(ROOT)
    rows = []
    for question, expected in CASES:
        results = retriever.search(question)
        rows.append({"question": question, "expected_keyword": expected, "passed": bool(results) and expected in results[0]["section"] + results[0]["text"], "top_source": results[0]["source"] if results else None, "top_section": results[0]["section"] if results else None})
    growth = []
    for question, expected in [("六人寝的中间床位在哪里？", "六人寝"), ("计算机协会有哪些活动？", "计算机协会"), ("数学建模竞赛做什么？", "数学建模"), ("学生会宣传部做什么？", "宣传部")]:
        results = retriever.search(question)
        growth.append({"question": question, "expected_keyword": expected, "passed": bool(results) and expected in results[0]["section"], "top_source": results[0]["source"] if results else None})
    return {"growth": {"passed": sum(r["passed"] for r in growth), "total": len(growth), "cases": growth}, "kind": "Top-1 keyword coverage on an explicit FAQ set; not human answer-quality scoring", "passed": sum(r["passed"] for r in rows), "total": len(rows), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
