"""Validated personal tasks and offline calendar export; dates are user supplied."""
from datetime import date, datetime, timedelta, timezone
import json
import re
import uuid

STATUSES = ("todo", "doing", "done", "archived")
PRIORITIES = ("low", "normal", "high")
LIMIT = 100
FORMAT = "freshman-guide-tasks"


def validate_task(value, catalog):
    if not isinstance(value, dict):
        raise ValueError("任务格式无效。")
    task = {}
    for field, limit in (("title", 100), ("notes", 600)):
        text = value.get(field, "")
        if not isinstance(text, str) or len(text) > limit or any((ord(c) < 32 and c not in "\n\t") or 0xD800 <= ord(c) <= 0xDFFF for c in text):
            raise ValueError(f"{ '任务标题' if field == 'title' else '备注' }格式无效或过长。")
        task[field] = text.strip()
    if not task["title"]:
        raise ValueError("请填写任务标题。")
    due = value.get("due", "")
    if not isinstance(due, str):
        raise ValueError("计划日期无效。")
    if due:
        try:
            if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", due):
                raise ValueError
            date.fromisoformat(due)
        except ValueError:
            raise ValueError("请选择2000–2099年内有效的计划日期。") from None
    task["due"] = due
    for field, choices, default in (("priority", PRIORITIES, "normal"), ("status", STATUSES, "todo")):
        choice = value.get(field, default)
        if not isinstance(choice, str) or choice not in choices:
            raise ValueError("任务优先级或进度无效。")
        task[field] = choice
    source = value.get("source_item", "")
    action = value.get("action_no")
    if not isinstance(source, str) or (source and source not in catalog):
        raise ValueError("任务关联选项无效。")
    if source and (type(action) is not int or action not in range(3)):
        raise ValueError("关联建议编号无效。")
    if not source and action is not None:
        raise ValueError("没有关联选项的任务不能带建议编号。")
    task.update(source_item=source, action_no=action)
    if "id" in value:
        identity = value["id"]
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", identity):
            raise ValueError("任务标识无效。")
        task["id"] = identity
    return task


def task_identity(task):
    if task["source_item"]:
        return ("source", task["source_item"], task["action_no"])
    return ("manual", json.dumps({k: v for k, v in task.items() if k != "id"}, sort_keys=True, ensure_ascii=False))


def validate_backup(value, catalog):
    if not isinstance(value, dict) or value.get("format") != FORMAT or type(value.get("format_version")) is not int or value["format_version"] != 1:
        raise ValueError("请选择“导出任务备份”生成的JSON文件。")
    rows = value.get("tasks")
    if not isinstance(rows, list) or len(rows) > LIMIT:
        raise ValueError("备份必须包含至多100项任务。")
    return [validate_task(row, catalog) for row in rows]


def backup(tasks):
    return {"format": FORMAT, "format_version": 1, "tasks": tasks,
            "note": "个人计划日期，不是官方赛程。导入只合并任务，不覆盖现有进度。"}


def new_id():
    return str(uuid.uuid4())


def calendar(tasks, catalog):
    def escape(text):
        return text.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")

    def fold(line):
        # RFC 5545: at most 75 octets, never split a UTF-8 code point.
        lines, current, size = [], "", 0
        for char in line:
            length = len(char.encode("utf-8"))
            if size + length > 75:
                lines.append(current); current, size = " ", 1
            current += char; size += length
        lines.append(current)
        return "\r\n".join(lines)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Freshman Guide//Personal Tasks//ZH", "CALSCALE:GREGORIAN"]
    for task in tasks:
        if not task["due"] or task["status"] not in ("todo", "doing"):
            continue
        day = date.fromisoformat(task["due"])
        description = "个人计划日期，请自行核对正式通知。"
        if task["source_item"]:
            description += "\n关联：" + catalog[task["source_item"]]["name"]
        if task["notes"]:
            description += "\n" + task["notes"]
        lines += ["BEGIN:VEVENT", "UID:" + task["id"] + "@freshman-guide.local", "DTSTAMP:" + stamp,
                  "DTSTART;VALUE=DATE:" + day.strftime("%Y%m%d"),
                  "DTEND;VALUE=DATE:" + (day + timedelta(days=1)).strftime("%Y%m%d"),
                  "SUMMARY:" + escape("待办：" + task["title"]), "DESCRIPTION:" + escape(description),
                  "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
