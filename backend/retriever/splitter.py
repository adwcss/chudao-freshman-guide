"""Stable evidence chunks inheriting source, year and trust annotations."""
import hashlib
from pathlib import Path
import re

DOC_FILES = ["新生手册.txt", "招生简章.md", "学校概况.md", "校园地图.md", "入学指南补充.md", "档案与党团关系转接.md", "资助与绿色通道.md", "军训安排.md", "户口迁移.md", "入学准备清单.md", "报到准备材料.md", "院系专业设置.md", "宿舍水电与校园生活.md", "学校地址与导航.md", "官方服务入口.md", "大学生竞赛指南.md", "大学生社团指南.md", "大学生学生会与学生组织指南.md", "宿舍床位选择参考.md"]
HISTORICAL = {"新生手册.txt": 2024, "入学指南补充.md": 2024, "学校地址与导航.md": 2024, "军训安排.md": 2024}
THIRD_PARTY = {"入学准备清单.md", "报到准备材料.md", "宿舍水电与校园生活.md", "户口迁移.md", "资助与绿色通道.md", "军训安排.md", "大学生竞赛指南.md", "大学生社团指南.md", "大学生学生会与学生组织指南.md", "宿舍床位选择参考.md"}


def split_all(docs_dir):
    chunks = []
    for filename in DOC_FILES:
        path = Path(docs_dir) / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        parts = re.split(r"(?=^(?:#{2,3} |[一二三四五六七八九十]+、))", text, flags=re.M)
        header = parts[0].strip()
        urls = list(dict.fromkeys(url.rstrip("；;。），、") for url in re.findall(r"https?://[^\s<>]+", header)))
        verified = filename == "官方服务入口.md"
        kind = "official_verified" if verified else "map_reference" if filename == "校园地图.md" else "third_party" if filename in THIRD_PARTY else "inherited_reference"
        caveat = "本资料为交接参考，信息尚未逐项核对当年官方通知。"
        if verified:
            caveat = "学校官网服务入口于2026-10-08核对；具体通知与收费以官网最新发布为准。"
        elif kind == "map_reference":
            caveat = "交接地图为示意，图上位置不等同实地导航；建筑与开放情况以现场为准。"
        elif kind == "third_party":
            caveat = "含第三方参考，办理材料和政策以当年学校官方通知为准。"
        if filename in HISTORICAL:
            caveat = "包含2024级报到参考，不代表2026级或以后安排；时间、接站、缴费方式须核对当年通知。"
        for part in parts:
            part = part.strip()
            if not part:
                continue
            section = part.split("\n", 1)[0].lstrip("# ")
            chunk_id = hashlib.sha256((filename + "\n" + part).encode()).hexdigest()[:16]
            chunks.append({"id": chunk_id, "source": filename, "section": section, "text": part,
                           "source_header": header, "urls": urls, "source_type": kind,
                           "effective_year": HISTORICAL.get(filename), "collected_at": "2026-10-11" if filename.startswith("大学生") or filename == "宿舍床位选择参考.md" else "2026-10-07" if not verified else "2026-10-08",
                           "verified": verified, "caveat": caveat})
    return chunks
