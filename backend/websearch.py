"""Public verification links plus an opt-in SerpAPI-style web search.

Local mode never touches the network. When GUIDE_ALLOW_WEB=true and a key is
given, needs_web queries are forwarded to a fixed HTTPS endpoint only.
"""
from urllib.parse import urlencode
import json
import re
import urllib.request


def verification_links(query):
    # Fixed topic vocabulary: never place the full question, history or key in a URL.
    topic = "新生 入学须知"
    for words, value in [(("军训",), "新生 军训"), (("学费", "住宿费", "收费"), "新生 收费通知"),
                         (("社团", "学生会", "招新"), "社团 学生组织 招新"),
                         (("图书馆", "开放", "营业"), "图书馆 开放通知"),
                         (("报到", "接站", "入学"), "新生 报到 入学须知"),
                         (("竞赛", "比赛", "蓝桥", "建模"), "竞赛 通知")]:
        if any(word in query for word in words):
            topic = value
            break
    scoped = "site:hnvust.cn 河南科技职业大学 " + topic
    links = [{"label": "学校官网", "url": "https://www.hnvust.cn/"},
             {"label": "搜索学校网站的相关通知", "url": "https://www.baidu.com/s?" + urlencode({"wd": scoped})}]
    if "蓝桥" in query:
        links.append({"label": "蓝桥杯主办方入口", "url": "https://dasai.lanqiao.cn/"})
    if "数学建模" in query:
        links.append({"label": "全国数学建模竞赛组委会", "url": "https://www.mcm.edu.cn/"})
    return links


def needs_web(query):
    """Time-sensitive facts that local docs cannot confirm should trigger a net lookup."""
    return re.search(r"(?:报到|接站|军训).*(?:时间|什么时候|几号|日期|多久|几天)|(?:什么时候|几号|日期).*(?:报到|接站|军训)|(?:今年|20\d{2}|最新).*(?:报到|接站|军训)|多少钱|多少元|收费标准|学费多少|住宿费多少|开放时间|几点|营业时间", query) is not None


def web_search(query, settings):
    """Optional SerpAPI-style web results. Raises on any failure; caller falls back.

    Returns a list of {rank, title, snippet, url} directly usable in the UI.
    """
    scope = "河南科技职业大学 新生 "
    for words, value in [(("军训",), "军训 时间"), (("学费", "住宿费", "收费"), "收费 通知"),
                         (("报到", "接站"), "报到 时间"), (("宿舍", "寝室"), "宿舍 安排"),
                         (("社团", "学生会", "招新"), "社团 学生组织 招新")]:
        if any(word in query for word in words):
            scope = "河南科技职业大学 新生 " + value
            break
    params = urlencode({"engine": settings.web_engine, "num": 5, "q": scope, "api_key": settings.web_key})
    # Fixed HTTPS host only: an invalid engine is already rejected by web_enabled().
    request = urllib.request.Request("https://serpapi.com/search.json?" + params, method="GET")
    request.add_header("Accept", "application/json")
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read(262144))
    items = []
    for entry in data.get("organic_results", []) or []:
        title = str(entry.get("title") or "").strip()
        link = str(entry.get("link") or "").strip()
        snippet = str(entry.get("snippet") or "").strip()
        if not title or not link or not link.startswith(("http://", "https://")):
            continue
        items.append({"rank": len(items) + 1, "title": title[:200], "snippet": snippet[:320], "url": link})
        if len(items) >= 5:
            break
    return items
