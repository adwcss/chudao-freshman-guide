"""Offline arrival practice and schematic campus itinerary. No network calls."""
from .catalog import PLACES

PLACES_BY_ID = {place["id"]: place for place in PLACES}
ROUTE_LIMIT = 8
PRESETS = [
    {"id": "daily", "name": "认识生活服务", "detail": "先了解吃饭、取件和生活服务的位置。", "stops": ["canyin-1", "kuaidi", "xinChuang", "weishengzhen"]},
    {"id": "study", "name": "看看学习空间", "detail": "认识教学与学习场所，开放情况到场核对。", "stops": ["houde", "shixun-1", "tushuguan"]},
    {"id": "activity", "name": "课后校园探索", "detail": "了解运动场地和文体中心的图上位置。", "stops": ["wenti", "caochang-2", "tiyuchang", "lanqiu-2"]},
]


def case(identifier, stage, title, scene, options, recommended, explanations, sources, question, checklist=""):
    return {"id": identifier, "stage": stage, "title": title, "scene": scene,
            "options": options, "recommended": recommended, "explanations": explanations,
            "sources": sources, "question": question, "checklist": checklist}


CASES = [
    case("notice", "出发前", "群里发来的报到日期", "新生群里有人转发往年的报到截图。你准备买车票，但还没看到今年的入学须知。", ["按截图日期买票", "先核对当年入学须知和学校通知", "把往年日期自动顺延一年"], 1,
         ["往年截图不能确认当年安排，先核对年份和官方通知。", "当年通知是安排出行的依据。现有资料含2024级参考，不能直接当成今年日期。", "报到日期不会按固定规则顺延，仍需确认当年通知。"], ["入学指南补充.md", "官方服务入口.md"], "今年新生什么时候报到？", "notice"),
    case("materials", "出发前", "证件放在哪个包里", "行李已经收好，录取通知书、身份证和少量换洗用品还在桌上。", ["都塞进行李箱底部", "只带手机上的照片", "按须知核对材料，重要证件随身携带"], 2,
         ["报到时可能需要取用原件，重要证件适合放在便于取用的随身行李。", "电子照片不能自行替代学校要求的材料原件。", "按当年须知核对原件、复印件和照片；重要证件及贵重物品随身放好。"], ["入学准备清单.md"], "报到要带什么材料？", "identity"),
    case("payment", "出发前", "陌生人的缴费优惠", "群里有人说可以代交学费返利，让你扫描他发来的收款码。", ["先转一小笔试试", "从学校官网进入支付平台，核对当年通知", "对方发了学校照片，可以相信"], 1,
         ["小额转账也不能证明收款方属于学校，先核对官方渠道。", "现有资料提醒警惕代交学费返利。项目不收学费，入口和金额需以学校当年通知为准。", "照片不能验证收款方身份，缴费应从官方入口核对。"], ["入学准备清单.md", "官方服务入口.md"], "学费怎么交？", "payment"),
    case("pickup", "报到当天", "晚上到站，还有接站吗", "你预计晚上到站，网上看到往年接站安排写着“19点前”。", ["默认学校全天接站", "依据往年站点直接等待", "提前核对当年站点和时段，再安排后续交通"], 2,
         ["现有参考并未提供全天接站保证，必须先确认当前安排。", "往年站点和时段只是参考，不保证到达当天仍在运行。", "确认到达站点、日期和时段；未确认接站时另行安排交通，不把参考信息当成承诺。"], ["入学指南补充.md"], "学校在哪些站点接站？"),
    case("registration", "报到当天", "地图上看到了综合楼", "你到校后想办理注册。地图上有南、北两处综合楼，但还没看到今年学院报到指引。", ["先找当年院部报到指引，向现场工作人员确认", "随便选一处综合楼", "地图有坐标，就能确认办理窗口"], 0,
         ["地图用于认识位置，办理地点和流程需核对当年通知与现场指引。", "同名建筑可能不止一处，不能据名称自行推断报到点。", "图上坐标不代表业务窗口，也不代表当年的办理位置。"], ["校园地图.md", "入学指南补充.md"], "报到点在哪里？", "register"),
    case("dorm", "报到当天", "收藏了喜欢的床位", "你在指南里收藏了靠窗床位，到宿舍时发现分配的房型和预想不同。", ["收藏记录就是预订凭证", "以学校分配为准，结合现场位置再讨论", "照片能保证每栋宿舍都一样"], 1,
         ["本项目收藏只保存偏好，不与学校分配系统连接。", "房型、楼号和床位以实际分配为准，图片和位置分析帮助了解取舍。", "交接照片是环境参考，不能保证所有楼栋都一样。"], ["宿舍床位选择参考.md"], "六人寝的中间床位在哪里？", "dorm"),
    case("library", "入校后", "探索图书馆", "你把图书馆加进了探索行程，地图上也出现了连线。现在该怎么用它？", ["沿连线穿过建筑，认为是最短路线", "默认当前开放，不再查看通知", "按序了解地点，再核对路标、入口和开放情况"], 2,
         ["连线只说明你选的先后顺序，可能跨过建筑或封闭区域，不是可通行道路。", "交接地图不提供实时开放信息，需要核对现场标识与学校通知。", "行程帮助记住地点和顺序；实际路线、入口和开放情况仍需现场核对。"], ["校园地图.md"], "图书馆在哪里？"),
    case("club", "入校后", "想参加计算机协会", "你在指南里看到计算机协会的活动介绍，想直接交会费报名。", ["先向团委确认实际开设、招新条件与费用", "页面写了名字，就确认本校正在招新", "收藏后就算报名成功"], 0,
         ["社团页为高校常见形态参考，先确认本校实际组织、招新与投入，再决定体验。", "通用示例不等于本校实际开设，也不代表当前招新。", "收藏只记录兴趣，报名需通过本校实际招新渠道。"], ["大学生社团指南.md"], "计算机协会有哪些活动？"),
    case("contest", "入校后", "想用竞赛奖项加分", "你看到竞赛参考指南的等级标签，准备把获奖写成确定的考研加分。", ["所有标签对应统一加分", "所有学校都会认可", "核对当届资格，以及目标单位的认定规则"], 2,
         ["参考标签不是统一认定标准，不能推断具体加分。", "认定规则因单位和年度而异，不能保证普遍认可。", "先向学院确认参赛条件，再核对主办方当届通知及目标单位认定要求。"], ["大学生竞赛指南.md"], "数学建模竞赛做什么？"),
]
CASES_BY_ID = {item["id"]: item for item in CASES}


def validate_answer(case_id, choice):
    if not isinstance(case_id, str) or case_id not in CASES_BY_ID:
        raise ValueError("演练场景不存在。")
    if type(choice) is not int or not 0 <= choice < len(CASES_BY_ID[case_id]["options"]):
        raise ValueError("请选择场景中的一个选项。")
    return CASES_BY_ID[case_id]


def update_route(current, operation):
    if not isinstance(operation, dict) or type(operation.get("revision")) is not int:
        raise ValueError("行程请求无效，请刷新重试。")
    if operation["revision"] != current["revision"]:
        raise ValueError("行程已在其他页面更新，已重新读取；请再次操作。")
    stops = [dict(stop) for stop in current["stops"]]
    action = operation.get("action")
    if not isinstance(action, str):
        raise ValueError("行程操作无效。")
    if action in {"add", "remove", "move", "visit"}:
        identifier = operation.get("place")
        if not isinstance(identifier, str) or identifier not in PLACES_BY_ID:
            raise ValueError("请选择地图上的地点。")
        index = next((i for i, stop in enumerate(stops) if stop["id"] == identifier), None)
        if action == "add":
            if index is not None:
                raise ValueError("此地点已在行程中。")
            if len(stops) >= ROUTE_LIMIT:
                raise ValueError("一次探索最多安排8个地点，请先移除一项。")
            stops.append({"id": identifier, "visited": False})
        else:
            if index is None:
                raise ValueError("此地点不在当前行程中。")
            if action == "remove":
                stops.pop(index)
            elif action == "visit":
                if type(operation.get("visited")) is not bool:
                    raise ValueError("到访状态无效。")
                stops[index]["visited"] = operation["visited"]
            elif action == "move":
                delta = operation.get("delta")
                if type(delta) is not int or delta not in {-1, 1} or not 0 <= index + delta < len(stops):
                    raise ValueError("此地点无法继续向该方向移动。")
                stops[index], stops[index + delta] = stops[index + delta], stops[index]
    elif action == "preset":
        preset_id = operation.get("preset")
        preset = next((item for item in PRESETS if item["id"] == preset_id), None)
        if not preset:
            raise ValueError("参考行程不存在。")
        visited = {stop["id"]: stop["visited"] for stop in stops}
        stops = [{"id": identifier, "visited": visited.get(identifier, False)} for identifier in preset["stops"]]
    elif action == "clear":
        stops = []
    else:
        raise ValueError("不支持此行程操作。")
    return {"revision": current["revision"] + 1, "stops": stops}


def route_text(route):
    lines = ["初到 · 我的校园探索行程", "仅为个人安排。连线表示探索顺序，不是实际道路、最短路线或实时导航。", "地点来自交接示意地图；开放情况、入口与通行条件请核对现场。", ""]
    for i, stop in enumerate(route["stops"], 1):
        place = PLACES_BY_ID[stop["id"]]
        lines.extend([f"{i}. {place['name']} · {'已到访' if stop['visited'] else '尚未到访'}", place["note"], ""])
    if not route["stops"]:
        lines.append("尚未安排地点。")
    return "\n".join(lines) + "\n"
