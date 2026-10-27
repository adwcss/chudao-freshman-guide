"""One-process loopback application using only the Python standard library."""
import argparse
from collections import defaultdict, deque
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .answer import Answerer
from .catalog import FAQS, PLACES, ROUTE, TASKS
from .dorm import DORM_GALLERY, DORM_ROOMS
from .contest import COMPETITIONS, LEVEL_INFO, USAGE_NOTE, GRAD_NOTE, TIPS
from .club import CLUBS, CLUB_CATEGORIES, TIPS as CLUB_TIPS, NOTE as CLUB_NOTE
from .studentorg import INTRO as ORG_INTRO, ORG_CATEGORIES, ORGS, TIPS as ORG_TIPS, NOTE as ORG_NOTE
from .retriever.retriever import Retriever
from .settings import ROOT, Settings
from .store import Store
from .experience import Experience, validate_profile
from .planner import validate_task, validate_backup, backup, calendar
from .orientation import CASES, PRESETS, ROUTE_LIMIT, route_text
from .preparation import DORMS, MODES, STATUS, CUSTOM_LIMIT, packing_items, readiness, memo_text, backup as preparation_backup, validate_backup as validate_preparation_backup


def valid_session(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,64}", value):
        raise ValueError("会话标识无效，请刷新页面重新打开。")
    return value


class Application:
    def __init__(self, settings=None):
        self.settings = settings or Settings.load()
        self.retriever = Retriever(ROOT)
        self.answerer = Answerer(self.retriever, self.settings)
        self.store = Store(self.settings.data_dir)
        self.experience = Experience()
        self.requests = defaultdict(deque)
        self.rate_lock = threading.Lock()

    def stats(self):
        return {"version": __version__, "document_count": len({c["source"] for c in self.retriever.chunks}), "chunk_count": len(self.retriever.chunks),
                "updated_at": "2026-10-14", "answer_mode": "remote_llm" if self.settings.remote_enabled() else "local_evidence",
                "remote_enabled": self.settings.remote_enabled(), "received_key_blocked": self.settings.key_blocked(), "remote_calls": self.answerer.remote_calls,
                "web_enabled": self.settings.web_enabled()}

    def preparation(self, session):
        current = self.store.preparation(session)
        return {"state": current, "items": packing_items(current), "readiness": readiness(current, self.store.checklist(session), self.store.rehearsal(session)),
                "dorms": list(DORMS.values()), "modes": MODES, "statuses": STATUS, "custom_limit": CUSTOM_LIMIT}

    def allow_request(self, address):
        with self.rate_lock:
            now = time.monotonic()
            queue = self.requests[address]
            while queue and queue[0] < now - 60:
                queue.popleft()
            if len(queue) >= 30:
                return False
            queue.append(now)
            return True


def handler_for(application):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            # Never log questions, keys, sessions or full query strings.
            return

        def respond_headers(self, status, kind="application/json; charset=utf-8", length=None):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()

        def json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.respond_headers(status, length=len(body))
            self.wfile.write(body)

        def check_host(self):
            port = self.server.server_port
            return self.headers.get("Host", "") in {f"localhost:{port}", f"127.0.0.1:{port}"}

        def body(self):
            if not self.check_host():
                raise ValueError("请求来源不受支持。")
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                raise PermissionError("请求来源不受支持。")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("需要JSON请求。")
            size = int(self.headers.get("Content-Length", "0"))
            max_size = 524288 if urlsplit(self.path).path in {"/api/tasks/import", "/api/tasks/import-preview"} else 16384
            if size < 1 or size > max_size:
                self.close_connection = True
                raise ValueError("请求过大或为空。")
            self.connection.settimeout(15)
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("请求格式无效。")
            return payload

        def do_GET(self):
            try:
                if not self.check_host():
                    return self.json({"error": "请求来源不受支持。"}, 403)
                url = urlsplit(self.path)
                args = parse_qs(url.query)
                if url.path in {"/api/health", "/health"}:
                    return self.json({"status": "ok", **application.stats()})
                if url.path == "/api/stats":
                    return self.json(application.stats())
                if url.path == "/api/catalog":
                    return self.json({"faqs": FAQS, "places": PLACES, "route": ROUTE, "tasks": TASKS})
                if url.path == "/api/places":
                    return self.json({"places": PLACES})
                if url.path == "/api/explore":
                    return self.json(application.experience.catalog())
                if url.path in {"/api/orientation", "/api/orientation/route.txt"}:
                    session = valid_session(args.get("session", [""])[0])
                    route = application.store.itinerary(session)
                    if url.path.endswith(".txt"):
                        body = route_text(route).encode("utf-8")
                        self.respond_headers(200, "text/plain; charset=utf-8", len(body))
                        self.wfile.write(body)
                        return
                    return self.json({"cases": CASES, "presets": PRESETS, "route_limit": ROUTE_LIMIT, "answers": application.store.rehearsal(session), "itinerary": route})
                if url.path in {"/api/tasks", "/api/tasks/backup", "/api/tasks/calendar"}:
                    session = valid_session(args.get("session", [""])[0])
                    tasks = application.store.tasks(session)
                    if url.path == "/api/tasks":
                        return self.json({"tasks": tasks})
                    if url.path == "/api/tasks/backup":
                        return self.json(backup(tasks))
                    body = calendar(tasks, application.experience.items).encode("utf-8")
                    self.respond_headers(200, "text/calendar; charset=utf-8", len(body))
                    self.wfile.write(body)
                    return
                if url.path in {"/api/profile", "/api/saved"}:
                    session = valid_session(args.get("session", [""])[0])
                    if url.path == "/api/profile":
                        return self.json({"profile": application.store.profile(session)})
                    return self.json({"items": application.experience.saved_items(application.store.saved(session))})
                if url.path in {"/api/preparation", "/api/preparation/backup", "/api/preparation/memo.txt"}:
                    session = valid_session(args.get("session", [""])[0])
                    if url.path == "/api/preparation":
                        return self.json(application.preparation(session))
                    if url.path == "/api/preparation/backup":
                        return self.json(preparation_backup(application.store.preparation(session)))
                    data = memo_text(application.store.preparation(session), application.store.checklist(session), application.store.rehearsal(session), application.store.itinerary(session)).encode("utf-8")
                    self.respond_headers(200, "text/plain; charset=utf-8", len(data)); self.wfile.write(data)
                    return
                if url.path == "/api/dorm":
                    return self.json({"rooms": DORM_ROOMS, "gallery": DORM_GALLERY})
                if url.path == "/api/contest":
                    return self.json({"categories": list(COMPETITIONS.keys()), "competitions": COMPETITIONS, "level_info": LEVEL_INFO, "usage_note": USAGE_NOTE, "grad_note": GRAD_NOTE, "tips": TIPS})
                if url.path == "/api/club":
                    return self.json({"categories": CLUB_CATEGORIES, "clubs": CLUBS, "tips": CLUB_TIPS, "note": CLUB_NOTE})
                if url.path == "/api/studentorg":
                    return self.json({"title": "学生会与学生组织指南", "intro": ORG_INTRO, "categories": ORG_CATEGORIES, "orgs": ORGS, "tips": ORG_TIPS, "note": ORG_NOTE})
                if url.path in {"/api/history", "/api/checklist", "/api/export"}:
                    session = valid_session(args.get("session", [""])[0])
                    if url.path == "/api/history":
                        return self.json({"messages": application.store.history(session)})
                    if url.path == "/api/checklist":
                        return self.json({"checked": application.store.checklist(session)})
                    return self.json({"version": __version__, "messages": application.store.history(session, 100), "checklist": application.store.checklist(session), "profile": application.store.profile(session), "saved_items": application.experience.saved_items(application.store.saved(session)), "tasks": application.store.tasks(session), "rehearsal": application.store.rehearsal(session), "itinerary": application.store.itinerary(session), "preparation": application.store.preparation(session), "note": "本地资料参考，非学校正式通知；收藏床位不代表已预订；任务日期为个人计划；地图连线为探索顺序"})
                if url.path == "/api/sources":
                    documents = {}
                    for c in application.retriever.chunks:
                        documents.setdefault(c["source"], {"name": c["source"], "source_type": c["source_type"], "urls": c["urls"], "effective_year": c["effective_year"], "caveat": c["caveat"], "verified": c["verified"], "chunks": []})["chunks"].append({"id": c["id"], "section": c["section"], "text": c["text"]})
                    return self.json({"documents": list(documents.values())})
                if url.path == "/favicon.ico":
                    self.respond_headers(204, "image/x-icon", 0)
                    return
                files = {"/planner.js": (ROOT / "frontend/planner.js", "text/javascript; charset=utf-8"), "/decision.js": (ROOT / "frontend/decision.js", "text/javascript; charset=utf-8"), "/": (ROOT / "frontend/index.html", "text/html; charset=utf-8"), "/app.js": (ROOT / "frontend/app.js", "text/javascript; charset=utf-8"), "/style.css": (ROOT / "frontend/style.css", "text/css; charset=utf-8"), "/campus-map.png": (ROOT / "校园地图.png", "image/png"), "/school-map.jpg": (ROOT / "学校地图.jpg", "image/jpeg"),
                         "/dorm-images/siren-env.jpg": (ROOT / "frontend/images/dorm/四人间床位.jpg", "image/jpeg"), "/dorm-images/liuren-env.jpg": (ROOT / "frontend/images/dorm/六人间床位.jpg", "image/jpeg"), "/dorm-images/siren-plan.jpg": (ROOT / "frontend/images/dorm/四人宿舍俯视图.jpg", "image/jpeg"), "/dorm-images/liuren-plan.jpg": (ROOT / "frontend/images/dorm/六人宿舍俯视图.jpg", "image/jpeg"), "/dorm-images/siren-toilet.jpg": (ROOT / "四人间卫生间.jpg", "image/jpeg"), "/dorm-images/siren-sink.jpg": (ROOT / "四人间洗手台.jpg", "image/jpeg"), "/dorm-images/liuren-bath.jpg": (ROOT / "六人间浴室洗手台.jpg", "image/jpeg"), "/dorm-images/laundry.jpg": (ROOT / "四人间六人间洗衣房.jpg", "image/jpeg"),
                         "/club-images/club-01.png": (ROOT / "frontend/images/club/club-01.png", "image/png"), "/club-images/club-02.png": (ROOT / "frontend/images/club/club-02.png", "image/png"), "/club-images/club-03.png": (ROOT / "frontend/images/club/club-03.png", "image/png"), "/club-images/club-04.png": (ROOT / "frontend/images/club/club-04.png", "image/png"), "/club-images/club-05.png": (ROOT / "frontend/images/club/club-05.png", "image/png"), "/club-images/club-06.png": (ROOT / "frontend/images/club/club-06.png", "image/png"), "/club-images/club-07.png": (ROOT / "frontend/images/club/club-07.png", "image/png"), "/club-images/club-08.png": (ROOT / "frontend/images/club/club-08.png", "image/png"), "/club-images/club-09.png": (ROOT / "frontend/images/club/club-09.png", "image/png"), "/club-images/club-10.png": (ROOT / "frontend/images/club/club-10.png", "image/png"), "/club-images/club-11.png": (ROOT / "frontend/images/club/club-11.png", "image/png"), "/club-images/club-12.png": (ROOT / "frontend/images/club/club-12.png", "image/png"), "/club-images/club-13.png": (ROOT / "frontend/images/club/club-13.png", "image/png"), "/club-images/club-14.png": (ROOT / "frontend/images/club/club-14.png", "image/png"), "/club-images/club-15.png": (ROOT / "frontend/images/club/club-15.png", "image/png"), "/club-images/club-16.png": (ROOT / "frontend/images/club/club-16.png", "image/png"),
                         "/union-images/union-01.png": (ROOT / "frontend/images/union/union-01.png", "image/png"), "/union-images/union-02.png": (ROOT / "frontend/images/union/union-02.png", "image/png"), "/union-images/union-03.png": (ROOT / "frontend/images/union/union-03.png", "image/png"), "/union-images/union-04.png": (ROOT / "frontend/images/union/union-04.png", "image/png"), "/union-images/union-05.png": (ROOT / "frontend/images/union/union-05.png", "image/png"), "/union-images/union-06.png": (ROOT / "frontend/images/union/union-06.png", "image/png"), "/union-images/union-07.png": (ROOT / "frontend/images/union/union-07.png", "image/png"), "/union-images/union-08.png": (ROOT / "frontend/images/union/union-08.png", "image/png"), "/union-images/union-09.png": (ROOT / "frontend/images/union/union-09.png", "image/png"), "/union-images/union-10.png": (ROOT / "frontend/images/union/union-10.png", "image/png"), "/union-images/union-11.png": (ROOT / "frontend/images/union/union-11.png", "image/png"), "/union-images/union-12.png": (ROOT / "frontend/images/union/union-12.png", "image/png"), "/union-images/union-13.png": (ROOT / "frontend/images/union/union-13.png", "image/png"), "/union-images/union-14.png": (ROOT / "frontend/images/union/union-14.png", "image/png")}
                files["/orientation.js"] = (ROOT / "frontend/orientation.js", "text/javascript; charset=utf-8")
                files["/preparation.js"] = (ROOT / "frontend/preparation.js", "text/javascript; charset=utf-8")
                files["/preparation.css"] = (ROOT / "frontend/preparation.css", "text/css; charset=utf-8")
                files["/appearance.js"] = (ROOT / "frontend/appearance.js", "text/javascript; charset=utf-8")
                files["/appearance.css"] = (ROOT / "frontend/appearance.css", "text/css; charset=utf-8")
                files["/assets/school-mascot.png"] = (ROOT / "frontend/assets/school-mascot.png", "image/png")
                files["/assets/mascot-lines.json"] = (ROOT / "frontend/assets/mascot-lines.json", "application/json; charset=utf-8")
                for pose in ("wave", "reading", "point"):
                    files[f"/assets/mascot-{pose}.png"] = (ROOT / f"frontend/assets/mascot-{pose}.png", "image/png")
                    files[f"/assets/mascot-{pose}-lines.json"] = (ROOT / f"frontend/assets/mascot-{pose}-lines.json", "application/json; charset=utf-8")
                for pose in ("wave", "read", "ready", "guide", "think", "cheer"):
                    files[f"/assets/chibi-{pose}.png"] = (ROOT / f"frontend/assets/chibi-{pose}.png", "image/png")
                    files[f"/assets/chibi-{pose}-lines.json"] = (ROOT / f"frontend/assets/chibi-{pose}-lines.json", "application/json; charset=utf-8")
                for pose in ("side", "laugh", "back-v2", "rest"):
                    files[f"/assets/creative-{pose}.png"] = (ROOT / f"frontend/assets/creative-{pose}.png", "image/png")
                    files[f"/assets/creative-{pose}-lines.json"] = (ROOT / f"frontend/assets/creative-{pose}-lines.json", "application/json; charset=utf-8")
                if url.path in files:
                    path, mime = files[url.path]
                    body = path.read_bytes()
                    self.respond_headers(200, mime, len(body))
                    self.wfile.write(body)
                    return
                self.json({"error": "页面或接口不存在。"}, 404)
            except ValueError:
                self.json({"error": "会话参数无效，请刷新页面。"}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.json({"error": "本地服务暂时不可用，请重试。"}, 500)

        def do_POST(self):
            try:
                payload = self.body()
                session = valid_session(payload.get("session", ""))
                path = urlsplit(self.path).path
                if path == "/api/preparation":
                    application.store.change_preparation(session, payload.get("operation"))
                    return self.json(application.preparation(session))
                if path == "/api/preparation/preview":
                    candidate = validate_preparation_backup(payload.get("backup"))
                    return self.json({"plan": candidate["plan"], "items": packing_items(candidate), "note": "确认恢复将替换当前准备台的出行和行李；其他模块保持原记录。"})
                if path == "/api/orientation/answer":
                    application.store.answer_scenario(session, payload.get("scenario"), payload.get("choice"))
                    return self.json({"answers": application.store.rehearsal(session)})
                if path == "/api/orientation/route":
                    return self.json({"itinerary": application.store.change_itinerary(session, payload.get("operation"))})
                if path == "/api/tasks":
                    task = validate_task(payload.get("task"), application.experience.items)
                    if "id" not in task and task["source_item"]:
                        raise ValueError("关联建议请从收藏计划生成，避免重复任务。")
                    application.store.put_task(session, task)
                    return self.json({"tasks": application.store.tasks(session)})
                if path == "/api/tasks/import":
                    tasks = validate_backup(payload.get("backup"), application.experience.items)
                    result = application.store.merge_tasks(session, tasks)
                    return self.json({**result, "tasks": application.store.tasks(session)})
                if path == "/api/tasks/import-preview":
                    tasks = validate_backup(payload.get("backup"), application.experience.items)
                    return self.json({**application.store.preview_tasks(session, tasks), "titles": [task["title"] for task in tasks[:5]]})
                if path == "/api/tasks/from-choice":
                    item = payload.get("item")
                    if not isinstance(item, str) or not any(row["item"] == item for row in application.store.saved(session)):
                        raise ValueError("请先收藏此选项，再生成待办。")
                    choice = application.experience.items[item]
                    tasks = [validate_task({"title": text, "source_item": item, "action_no": index}, application.experience.items) for index, text in enumerate(application.experience.actions(choice))]
                    result = application.store.merge_tasks(session, tasks)
                    return self.json({**result, "tasks": application.store.tasks(session)})
                if path in {"/api/profile", "/api/recommend"}:
                    profile = validate_profile(payload.get("profile"))
                    if path == "/api/profile":
                        application.store.set_profile(session, profile)
                    return self.json(application.experience.recommendations(profile))
                if path == "/api/saved":
                    item = payload.get("item")
                    status = payload.get("status")
                    if not isinstance(item, str) or item not in application.experience.items or status not in ("planned", "doing", "done", "removed"):
                        raise ValueError("收藏项目或状态无效。")
                    application.store.set_saved(session, item, status)
                    return self.json({"items": application.experience.saved_items(application.store.saved(session))})
                if path == "/api/checklist":
                    task = payload.get("task")
                    if task not in {t["id"] for t in TASKS} or not isinstance(payload.get("checked"), bool):
                        raise ValueError("清单项目无效。")
                    application.store.check(session, task, payload["checked"])
                    return self.json({"checked": application.store.checklist(session)})
                if path == "/api/feedback":
                    if payload.get("value") not in {"helpful", "unhelpful"}:
                        raise ValueError("反馈选项无效。")
                    application.store.feedback(session, payload.get("answer"), payload["value"])
                    return self.json({"saved": True})
                if path != "/api/ask":
                    return self.json({"error": "接口不存在。"}, 404)
                question = payload.get("question")
                if not isinstance(question, str) or not question.strip() or len(question) > 500:
                    raise ValueError("请输入1–500字的问题。")
                if not application.allow_request(self.client_address[0]):
                    return self.json({"error": "提问过于频繁，请稍后重试。"}, 429)
                history = application.store.history(session, 8)
                prepared = application.answerer.prepare(question.strip(), history)
                answer, mode = application.answerer.generate(question.strip(), prepared)
                application.store.save(session, "user", question.strip())
                response_payload = {"sources": prepared["sources"], "warnings": prepared["warnings"], "mode": mode, "query": prepared["query"], "remote_attempted": prepared["remote_attempted"], "web_used": prepared.get("web_used", False), "web_results": prepared.get("web_results", []), "check_links": prepared["check_links"]}
                answer_id = application.store.save(session, "assistant", answer, response_payload)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

                def event(name, data):
                    self.wfile.write(("event: " + name + "\ndata: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode())
                    self.wfile.flush()

                event("status", {"stage": "retrieved", "source_count": len(prepared["sources"])})
                event("sources", response_payload)
                for index in range(0, len(answer), 28):
                    event("delta", {"text": answer[index:index + 28]})
                event("done", {"id": answer_id, "mode": mode})
            except PermissionError:
                self.json({"error": "请求来源不受支持。"}, 403)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.json({"error": str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "请求格式无效。"}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.json({"error": "本地服务暂时不可用，请重试。"}, 500)

        def do_DELETE(self):
            try:
                payload = self.body()
                if urlsplit(self.path).path != "/api/history":
                    return self.json({"error": "接口不存在。"}, 404)
                application.store.delete_history(valid_session(payload.get("session", "")))
                self.json({"deleted": True})
            except PermissionError:
                self.json({"error": "请求来源不受支持。"}, 403)
            except (ValueError, TypeError):
                self.json({"error": "请求格式无效。"}, 400)

    return Handler


def serve(port=8765):
    app = Application()
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(app))
    server.daemon_threads = True
    print(f"新生指南已启动：http://127.0.0.1:{port}/", flush=True)
    print("默认使用本地资料模式；外部模型请求：关闭" if not app.settings.remote_enabled() else "外部模型已显式启用，可能产生费用", flush=True)
    print("网络搜索：关闭（需 GUIDE_ALLOW_WEB=true 并配置 GUIDE_WEB_API_KEY）" if not app.settings.web_enabled() else "网络搜索已显式启用，仅在本地产档不足或涉时效问题时使用", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("服务已停止。", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.port)
