"""Personal departure planning and packing, entirely offline."""
from copy import deepcopy
from datetime import date
import re
import uuid
from .catalog import PLACES, TASKS
from .orientation import CASES, route_text

FORMAT = "freshman-guide-preparation"
CUSTOM_LIMIT = 20
STATUS = {"todo": "待准备", "packed": "已装好", "buy": "到校购买", "skip": "不需要"}
MODES = {"": "尚未填写", "rail": "火车 / 高铁", "road": "汽车 / 自驾", "air": "飞机", "other": "其他"}
DORMS = {p["id"]: p for p in PLACES if p["category"] == "宿舍区"}
_ROWS = [
    ("admission", "录取通知书", "证件与材料", "原件随身携带，具体要求对照入学须知。", True),
    ("identity", "身份证", "证件与材料", "原件随身保管，复印件要求另行核对。", True),
    ("photos", "所需照片与复印件", "证件与材料", "数量和规格以当年材料要求为准。", False),
    ("archive", "按要求携带的档案材料", "证件与材料", "确认是邮寄还是随身携带，不要擅自拆封。", False),
    ("phone", "手机与充电器", "旅途随身", "出发前检查电量和充电线。", False),
    ("power", "充电宝", "旅途随身", "携带条件按承运方要求自行核对。", False),
    ("water", "水杯", "旅途随身", "根据路程和个人习惯准备。", False),
    ("umbrella", "雨伞", "旅途随身", "出发前自行查看目的地天气。", False),
    ("clothes", "换洗衣物", "宿舍生活", "按季节与个人需要准备。", False),
    ("bedding", "床上用品", "宿舍生活", "尺寸及是否统一提供待核对，可选择到校购买。", False),
    ("towel", "毛巾", "宿舍生活", "可自带或到校购买。", False),
    ("wash", "牙刷与洗漱用品", "宿舍生活", "按个人使用习惯准备。", False),
    ("slippers", "拖鞋", "宿舍生活", "可自带或到校购买。", False),
    ("notebook", "笔与笔记本", "学习用品", "按需准备。", False),
    ("computer", "个人电脑及配件", "学习用品", "按专业和个人需要决定，贵重物品随身保管。", False),
]
ITEMS = [{"id": i, "title": t, "group": g, "note": n, "essential": e, "source": "入学准备清单.md", "custom": False} for i, t, g, n, e in _ROWS]
ITEMS_BY_ID = {item["id"]: item for item in ITEMS}


def text(value, limit, label):
    if not isinstance(value, str) or len(value) > limit or any((ord(c) < 32 and c not in "\n\t") or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(label + "格式无效或过长。")
    return value.strip()


def validate_plan(value):
    if not isinstance(value, dict):
        raise ValueError("请填写个人出行安排。")
    plan = {}
    for key in ("departure", "arrival"):
        day = value.get(key, "")
        if not isinstance(day, str) or (day and not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", day)):
            raise ValueError("请选择2000–2099年内的有效日期。")
        if day:
            try:
                date.fromisoformat(day)
            except ValueError:
                raise ValueError("计划日期无效。") from None
        plan[key] = day
    if plan["departure"] and plan["arrival"] and plan["arrival"] < plan["departure"]:
        raise ValueError("预计到校日期不能早于出发日期。")
    clock = value.get("time", "")
    if not isinstance(clock, str) or (clock and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock)):
        raise ValueError("预计到校时间无效。")
    mode, dorm = value.get("mode", ""), value.get("dorm", "")
    if not isinstance(mode, str) or mode not in MODES or not isinstance(dorm, str) or (dorm and dorm not in DORMS):
        raise ValueError("出行方式或宿舍区域无效。")
    plan.update(time=clock, mode=mode, dorm=dorm, room_note=text(value.get("room_note", ""), 80, "宿舍备注"), notes=text(value.get("notes", ""), 300, "出行备注"))
    return plan


def default_preparation():
    return {"revision": 0, "plan": validate_plan({}), "packing": {}, "custom": []}


def validate_entry(value, essential=False):
    if not isinstance(value, dict) or type(value.get("quantity")) is not int or not 1 <= value["quantity"] <= 99:
        raise ValueError("物品数量应为1–99的整数。")
    status = value.get("status")
    if not isinstance(status, str) or status not in (("todo", "packed") if essential else tuple(STATUS)):
        raise ValueError("物品状态无效；重要证件请亲自确认装好。")
    return {"quantity": value["quantity"], "status": status}


def packing_items(current):
    return [{**item, **current["packing"].get(item["id"], {"quantity": 1, "status": "todo"})} for item in ITEMS] + [{**item, "group": "我的补充", "essential": False, "note": "自己添加的物品。", "source": "", "custom": True} for item in current["custom"]]


def update_preparation(current, operation):
    if not isinstance(operation, dict) or type(operation.get("revision")) is not int or operation["revision"] != current["revision"]:
        raise ValueError("准备台已在其他页面更新，请重新读取后再保存。")
    result = deepcopy(current)
    action = operation.get("action")
    if action == "plan":
        result["plan"] = validate_plan(operation.get("plan"))
    elif action == "item":
        identifier = operation.get("id")
        if not isinstance(identifier, str):
            raise ValueError("物品标识无效。")
        if identifier in ITEMS_BY_ID:
            result["packing"][identifier] = validate_entry(operation.get("item"), ITEMS_BY_ID[identifier]["essential"])
        else:
            item = next((row for row in result["custom"] if row["id"] == identifier), None)
            if item is None:
                raise ValueError("物品不存在。")
            item.update(validate_entry(operation.get("item")))
    elif action == "add":
        if len(result["custom"]) >= CUSTOM_LIMIT:
            raise ValueError("最多补充20种物品，请先移除一项。")
        title = text(operation.get("title"), 60, "物品名称")
        if not title or any(row["title"] == title for row in packing_items(result)):
            raise ValueError("物品名称不能为空或与清单重复。")
        result["custom"].append({"id": "custom-" + str(uuid.uuid4()), "title": title, **validate_entry({"quantity": operation.get("quantity"), "status": "todo"})})
    elif action == "remove":
        identifier = operation.get("id")
        if not isinstance(identifier, str) or not any(row["id"] == identifier for row in result["custom"]):
            raise ValueError("仅能移除自己补充的物品。")
        result["custom"] = [row for row in result["custom"] if row["id"] != identifier]
    elif action == "restore":
        result.update(validate_backup(operation.get("backup")))
    else:
        raise ValueError("准备台操作无效。")
    result["revision"] = current["revision"] + 1
    return result


def backup(current):
    return {"format": FORMAT, "format_version": 1, "plan": current["plan"], "packing": current["packing"], "custom": current["custom"]}


def validate_backup(value):
    if not isinstance(value, dict) or value.get("format") != FORMAT or type(value.get("format_version")) is not int or value["format_version"] != 1:
        raise ValueError("请选择准备台导出的备份JSON。")
    plan = validate_plan(value.get("plan"))
    packed, custom = value.get("packing"), value.get("custom")
    if not isinstance(packed, dict) or any(key not in ITEMS_BY_ID for key in packed):
        raise ValueError("备份包含未知物品。")
    packed = {key: validate_entry(row, ITEMS_BY_ID[key]["essential"]) for key, row in packed.items()}
    if not isinstance(custom, list) or len(custom) > CUSTOM_LIMIT:
        raise ValueError("备份最多包含20种自定义物品。")
    rows, identifiers, titles = [], set(), {item["title"] for item in ITEMS}
    for row in custom:
        if not isinstance(row, dict):
            raise ValueError("自定义物品格式无效。")
        identifier, title = row.get("id"), text(row.get("title"), 60, "物品名称")
        if not isinstance(identifier, str) or not re.fullmatch(r"custom-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", identifier) or identifier in identifiers or not title or title in titles:
            raise ValueError("备份的物品名称或标识无效、重复。")
        rows.append({"id": identifier, "title": title, **validate_entry(row)})
        identifiers.add(identifier); titles.add(title)
    return {"plan": plan, "packing": packed, "custom": rows}


def readiness(current, checked, answers, today=None):
    today = today or date.today()
    day = current["plan"]["departure"]
    items = packing_items(current)
    return {"days_until_departure": (date.fromisoformat(day) - today).days if day else None,
            "packed": sum(item["status"] == "packed" for item in items), "total": len(items),
            "important_missing": [item for item in items if item["essential"] and item["status"] != "packed"],
            "pending_checks": [item for item in TASKS if not checked.get(item["id"], False)],
            "review_cases": [item for item in CASES if item["id"] in answers and answers[item["id"]] != item["recommended"]]}


def memo_text(current, checked, answers, itinerary):
    plan = current["plan"]
    lines = ["初到 · 我的出发备忘卡", "这是自己填写的出行计划，不是学校正式报到安排。", "",
             "出发日期：" + (plan["departure"] or "尚未填写"), "预计到校：" + (plan["arrival"] or "尚未填写") + (" " + plan["time"] if plan["time"] else ""),
             "出行方式：" + MODES[plan["mode"]], "宿舍区域：" + (DORMS[plan["dorm"]]["name"] if plan["dorm"] else "待学校分配后填写"),
             "宿舍备注：" + (plan["room_note"] or "未填写"), "出行备注：" + (plan["notes"] or "未填写"), "", "行李准备"]
    lines += [f"{STATUS[item['status']]} · {item['title']} × {item['quantity']}" for item in packing_items(current)]
    missing = readiness(current, checked, answers)
    lines += ["", "仍待亲自核对的准备事项"] + ["□ " + item["title"] for item in missing["pending_checks"]]
    if not missing["pending_checks"]:
        lines.append("现有清单已勾选，实际材料与安排仍以当年通知为准。")
    lines += ["", "需要复习的场景"] + [item["title"] for item in missing["review_cases"]]
    if not missing["review_cases"]:
        lines.append("当前没有保存为待复习的场景，未练习场景不计为已掌握。")
    lines += ["", route_text(itinerary), "", "行李建议参考入学准备清单.md，数量由自己填写；携带与采购条件需自行核对。"]
    return "\n".join(lines) + "\n"
