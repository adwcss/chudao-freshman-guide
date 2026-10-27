"""Chinese local BM25 with explicit topic/proper-name matching; no paid API."""
from collections import Counter
import math
import re
from .splitter import split_all

TOPICS = {
    "学费": ["学费", "缴费", "交费", "费用", "收费", "交钱"],
    "报到": ["报到", "开学", "入学", "接站", "校门"],
    "资助": ["资助", "贷款", "助学", "绿色通道", "奖学金"],
    "宿舍": ["宿舍", "馨园", "沁园", "住宿", "公寓", "床位", "选寝", "睡眠", "中间位", "水电", "电费", "水费"],
    "一卡通": ["一卡通", "校园卡", "充值", "饭卡"],
    "档案": ["档案", "党团", "团关系", "党关系", "组织关系", "党组织", "团组织"],
    "户口": ["户口", "迁移"],
    "军训": ["军训"],
    "专业": ["专业", "院系", "学院"],
    "交通": ["地址", "导航", "快递", "邮寄", "车站", "高铁"],
    "地图": ["图书馆", "厚德楼", "体育场", "餐厅", "食堂", "教学中心", "汽车工程", "游泳馆", "泳池", "致远楼", "笃行楼", "敏行楼", "励志楼", "博学楼", "明德楼", "文体中心", "实训中心", "综合楼", "沁园", "馨园", "篮球场", "网球场", "停车场", "月亮湖", "太阳湖", "光明路", "第二操场", "操场", "御花园", "馨创超市", "创业慧享", "天旗台", "名人文场", "广场", "快递", "诊所", "热水房", "水果店", "国行", "慧享"],
    "材料": ["材料", "证件", "行李", "准备", "带什么", "录取通知书"],
    "学校": ["校训", "学校概况", "学校简介", "学校代码", "国标代码"],
    "竞赛": ["竞赛", "比赛", "大赛", "参赛", "蓝桥杯", "挑战杯", "互联网+", "建模"],
    "社团": ["社团", "协会", "俱乐部", "学生会", "招新", "加入社团", "兴趣社团", "动漫", "摄影", "汉服", "电竞", "篮球", "合唱", "书画", "记者团", "国旗护卫队", "红十字", "志愿者", "英语角", "cosplay", "二次元"],
    "学生会": ["学生组织", "社团联合会", "社联", "主席团", "学代会", "办公室", "宣传部", "学习部", "文体部", "生活权益部", "组织部", "外联", "纪检部", "团委", "青年志愿者", "青协", "青年传媒", "艺术团", "新媒体中心"],
}
TRUST_LABELS = {"official_verified": "官方入口已核对", "map_reference": "交接地图参考", "third_party": "第三方参考", "inherited_reference": "交接资料待核对"}
STOP = {"学校", "新生", "河南", "科技", "职业", "大学", "怎么", "如何", "哪里", "在哪", "哪些", "什么", "时候", "可以", "请问", "一下", "告诉", "我们", "我的", "那个", "今年", "现在", "同学"}


def terms(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1) if run[i:i + 2] not in STOP)
    return tokens


def topics(text):
    return {name for name, aliases in TOPICS.items() if any(alias in text for alias in aliases)}


def rewrite(question, history):
    """Resolve follow-up references using user turns only, never generated text."""
    if not topics(question) and re.search(r"^(那|那么|这个|它|那里|还|需要|要带|多少钱|什么时候)", question) and len(question) <= 28:
        previous = next((item["content"] for item in reversed(history) if item.get("role") == "user"), "")
        if previous:
            return previous + "；追问：" + question
    return question


class Retriever:
    def __init__(self, root):
        self.chunks = split_all(root)
        self.counts = [Counter(terms(c["section"] + " " + c["text"])) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        self.df = Counter(t for c in self.counts for t in c)

    def search(self, query, top_k=3):
        query = query.replace("饭卡", "一卡通").replace("交钱", "缴费").replace("交费", "缴费")
        query_topics = topics(query)
        if not query_topics or re.search(r"彩票|股票|天气|食谱|量子|密码|管理员|系统提示|忽略.*指令|奖学金.*(?:多少|金额)", query):
            return []
        aliases = [a for name in query_topics for a in TOPICS[name] if a in query]
        focus = []
        if re.search(r"行李|生活用品|洗漱用品", query):
            focus = ["行李", "生活用品"]
        elif re.search(r"材料|带什么|要带", query) and not re.search(r"户口|档案|党团", query):
            focus = ["必备材料", "入学准备", "材料"]
        elif re.search(r"报到点|报到处|接待处", query):
            focus = ["地点安排", "报到处", "接待处"]
        elif re.search(r"报到.*(?:时间|什么时候)|什么时候.*报到", query):
            focus = ["报到时间"]
        elif re.search(r"床位|选寝|睡眠|中间位", query):
            focus = ["床位", "六人寝" if "六人" in query else "四人寝" if "四人" in query else "床位"]
        elif "学费" in query or "缴费" in query:
            focus = ["缴费", "学费"]
        elif "军训" in query:
            focus = ["军训动员", "时间"] if re.search(r"什么时候|时间|开始|几号", query) else ["军训"]
        elif "专业" in query or "院系" in query:
            focus = ["学院", "专业一览", "专业设置"]
        else:
            focus = [a for a in aliases if len(a) >= 3 or a in {"馨园", "沁园", "水电", "户口", "快递", "宿舍"}]
        query_terms = set(terms(query)) | set(aliases)
        results = []
        n = len(self.chunks)
        for chunk, counts, length in zip(self.chunks, self.counts, self.lengths):
            named_focus = [word for word in ("建模", "蓝桥杯", "挑战杯") if word in query]
            if named_focus and chunk["source"].startswith("大学生") and not any(word in chunk["text"] for word in named_focus):
                continue
            if chunk["source"] == "宿舍床位选择参考.md" and (("六人" in query and "四人" in chunk["section"]) or ("四人" in query and "六人" in chunk["section"])):
                continue
            body = chunk["text"]
            matched = {a for a in aliases if a in body or a in chunk["section"]}
            if not matched:
                continue
            score = 0.0
            for term in query_terms:
                freq = counts.get(term, 0)
                if freq:
                    idf = math.log(1 + (n - self.df[term] + .5) / (self.df[term] + .5))
                    score += idf * freq * 2.2 / (freq + 1.2 * (.25 + .75 * length / self.average))
            score += 4 * len(matched) + 2 * sum(a in chunk["section"] for a in aliases)
            score += 18 * sum(term in chunk["section"] for term in focus)
            if re.search(r"竞赛|大赛|比赛", query) and not re.search(r"社团|协会", query) and chunk["source"] == "大学生竞赛指南.md":
                score += 30
            if re.search(r"社团|协会", query) and chunk["source"] == "大学生社团指南.md":
                score += 20
            if re.search(r"学生会|学生组织", query) and chunk["source"] == "大学生学生会与学生组织指南.md":
                score += 20
            if chunk["verified"]:
                score += 1
            if body.startswith("# "):
                score *= .25
            results.append({**chunk, "score": round(score, 3), "trust_label": TRUST_LABELS[chunk["source_type"]]})
        results.sort(key=lambda c: c["score"], reverse=True)
        # 绝对阈值：最高分都不足，说明只是字面巧合，判定为无匹配
        # 实测：巧合命中约 9~14.5 分（如"布拉格广场"仅靠"广场"命中 14.2），
        # 正常有效问题最低约 17 分（宿舍/接站/户口 17~20，其余 22+），故取 15。
        MIN_SCORE = 15
        # Short exact section queries (e.g. “几号接站”) must survive the cutoff.
        generic = {"宿舍", "广场", "学院", "专业", "比赛", "社团", "大赛", "协会", "入学", "校门", "车站"}
        exact_section = results and any(a in results[0]["section"] for a in aliases if a not in generic)
        if not results or (results[0]["score"] < MIN_SCORE and not exact_section):
            return []
        chosen = []
        for chunk in results:
            if results and chunk["score"] < results[0]["score"] * .45:
                continue
            normalized = re.sub(r"[\s#]+", "", chunk["text"])
            if any(normalized == re.sub(r"[\s#]+", "", c["text"]) for c in chosen):
                continue
            chosen.append(chunk)
            if len(chosen) == top_k:
                break
        return chosen
