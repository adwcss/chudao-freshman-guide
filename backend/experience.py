"""Explainable local decision support, based on received reference data."""
import hashlib
from .dorm import DORM_ROOMS
from .club import CLUBS
from .contest import COMPETITIONS
from .studentorg import ORGS

INTERESTS = {
    "coding": ("编程与技术", ["编程", "计算机", "软件", "算法", "人工智能", "机器人", "电子", "硬件"]),
    "science": ("数学与研究", ["数学", "建模", "研究", "实验", "学术", "论文"]),
    "english": ("语言与表达", ["英语", "语言", "演讲", "辩论", "口语"]),
    "business": ("创业与商业", ["创业", "商业", "营销", "经济", "管理", "路演"]),
    "art": ("艺术与设计", ["艺术", "设计", "绘画", "书画", "音乐", "摄影", "汉服", "动漫"]),
    "sports": ("运动与竞技", ["体育", "篮球", "运动", "健身", "竞技"]),
    "volunteer": ("志愿与公益", ["志愿", "公益", "服务", "社区", "环保"]),
    "media": ("写作与新媒体", ["写作", "宣传", "新闻", "传媒", "记者", "摄影", "视频", "新媒体"]),
    "service": ("组织与协作", ["组织", "统筹", "协调", "服务", "权益", "团队", "办公室"]),
}
PRIORITIES = {"quiet": "安静与睡眠", "light": "采光与通风", "access": "出入方便", "dry": "远离卫浴"}
REFERENCE_NOTE = "交接参考资料，未确认本校实际开设、招新、参赛资格或学分认定。请向学院、团委及赛事主办方核对。"


def validate_profile(value):
    if not isinstance(value, dict):
        raise ValueError("偏好格式无效")
    interests = value.get("interests", [])
    if not isinstance(interests, list) or len(interests) > len(INTERESTS) or any(not isinstance(i, str) or i not in INTERESTS for i in interests):
        raise ValueError("兴趣选项无效")
    priorities = value.get("priorities", {})
    if not isinstance(priorities, dict) or any(k not in PRIORITIES or type(v) is not int or not 0 <= v <= 3 for k, v in priorities.items()):
        raise ValueError("床位偏好无效")
    room = value.get("room", "liuren")
    hours = value.get("hours", "medium")
    college = value.get("college", "")
    if not all(isinstance(v, str) for v in (room, hours, college)) or room not in DORM_ROOMS or hours not in {"low", "medium", "high"} or college not in ["", *COMPETITIONS]:
        raise ValueError("偏好选项无效")
    return {"interests": list(dict.fromkeys(interests)), "priorities": {k: priorities.get(k, 1) for k in PRIORITIES}, "room": room, "hours": hours, "college": college}


def identity(kind, name):
    return kind + "-" + hashlib.sha256(name.encode()).hexdigest()[:12]


class Experience:
    def __init__(self):
        self.items = {}
        for room_id, room in DORM_ROOMS.items():
            for bed in room["beds"]:
                key = f"bed-{room_id}-{bed['id']}"
                self.items[key] = {**bed, "id": key, "bed_id": bed["id"], "kind": "bed", "room": room_id, "name": room["name"] + " · " + bed["name"], "category": " / ".join(bed["tags"]), "intro": bed["fit"], "source": "宿舍床位选择参考.md", "note": "示意偏好参考，编号非学校分配编号；此处不能预订或选定实际床位。"}
        for category, items in COMPETITIONS.items():
            for item in items:
                key = identity("contest", item["name"])
                if key in self.items:
                    self.items[key]["categories"].append(category)
                    continue
                self.items[key] = {**item, "id": key, "kind": "contest", "category": category, "categories": [category], "source": "大学生竞赛指南.md", "note": REFERENCE_NOTE}
        for kind, items, filename in [("club", CLUBS, "大学生社团指南.md"), ("union", ORGS, "大学生学生会与学生组织指南.md")]:
            for item in items:
                key = identity(kind, item["name"])
                self.items[key] = {**item, "id": key, "kind": kind, "intro": item.get("intro", item.get("summary", "")), "source": filename, "note": REFERENCE_NOTE}

    def catalog(self):
        return {"items": list(self.items.values()), "interests": [{"id": k, "label": v[0]} for k, v in INTERESTS.items()], "priorities": PRIORITIES, "colleges": list(COMPETITIONS), "note": REFERENCE_NOTE}

    def recommendations(self, raw_profile):
        profile = validate_profile(raw_profile)
        groups = {k: [] for k in ("bed", "contest", "club", "union")}
        for item in self.items.values():
            reasons = []
            cautions = []
            score = 0
            if item["kind"] == "bed":
                if item["room"] != profile["room"]:
                    continue
                metrics = item["metrics"]
                for key, weight in profile["priorities"].items():
                    score += weight * metrics[key]
                    if weight >= 2:
                        reasons.append(f"{PRIORITIES[key]}：图上位置参考 {metrics[key]}/3 × 偏好权重 {weight}")
                cautions = item["cons"]
                if not any(profile["priorities"].values()):
                    reasons = ["全部权重为 0，床位并列；请先调整你在意的因素。"]
            else:
                corpus = " ".join(str(item.get(k, "")) for k in ("name", "intro", "audience", "activities", "works", "fit"))
                for interest in profile["interests"]:
                    label, words = INTERESTS[interest]
                    matching_text = corpus.replace("电子竞技", "电竞") if interest == "coding" else corpus
                    hits = [w for w in words if w in matching_text]
                    if hits:
                        score += 3 + min(len(hits), 3)
                        reasons.append(f"符合「{label}」：资料包含 { '、'.join(hits[:3]) }")
                if item["kind"] == "contest" and profile["college"]:
                    if profile["college"] in item["categories"]:
                        score += 8
                        reasons.append("交接指南列于你选择的专业方向；资格仍需核对。")
                    elif not any("通用" in c for c in item["categories"]):
                        continue
                if score == 0:
                    continue
                if profile["hours"] == "low":
                    cautions.append("可投入时间较少：先参加体验、做小练习，再确认长期投入；项目型比赛需了解团队任务。")
                elif profile["hours"] == "high":
                    cautions.append("可先尝试一项持续任务；投入多少时间不能保证获奖或录取。")
                cautions.append(item["note"])
            groups[item["kind"]].append({**item, "score": score, "reasons": reasons, "cautions": cautions})
        for kind in groups:
            groups[kind].sort(key=lambda x: (-x["score"], x["id"]))
            groups[kind] = groups[kind][:6]
        return {"groups": groups, "profile": profile, "method": "本地规则匹配。分数仅用于同类排序，不是适配概率、录取率或官方评定；同分并列，依据来自交接资料。"}

    def saved_items(self, rows):
        result = []
        for row in rows:
            if row["item"] in self.items:
                item = self.items[row["item"]]
                result.append({**item, "status": row["status"], "actions": self.actions(item)})
        return result

    @staticmethod
    def actions(item):
        return {
            "bed": ["核对学校分配规则与实际房型", "现场看门窗、卫浴和安全通道", "与室友沟通作息，再确认实际位置"],
            "contest": ["向学院核对参赛资格、校内选拔与认定", "阅读主办方当届通知，记录真实截止日期", "找一份往届题目或项目样例，完成小练习"],
            "club": ["向团委确认本校是否开设及招新安排", "参加一次体验活动，问清费用与时间投入", "结合课表确定是否持续参与"],
            "union": ["确认本校部门名称、岗位与招新条件", "准备一段经历介绍和一份相关小作品", "了解值班和活动安排，再决定报名"],
        }[item["kind"]]
