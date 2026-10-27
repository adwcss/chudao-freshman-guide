"""Offline functional and HTTP regressions. No received key or external API used."""
from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.answer import Answerer
from backend.main import Application, handler_for
from backend.retriever.retriever import Retriever, rewrite
from backend.settings import Settings
from backend.store import Store
from backend.planner import validate_task, validate_backup, backup, calendar
from backend.websearch import verification_links
from backend.orientation import CASES, PRESETS, PLACES_BY_ID, validate_answer, update_route, route_text
from backend.preparation import ITEMS, default_preparation, update_preparation, validate_plan, readiness, memo_text, backup as prep_backup, validate_backup as validate_prep_backup
from datetime import date


class PreparationTests(unittest.TestCase):
    def test_reference_defaults_are_unconfirmed_and_source_exists(self):
        value = default_preparation()
        self.assertEqual(value["plan"]["departure"], "")
        self.assertEqual(value["plan"]["dorm"], "")
        self.assertEqual(len(ITEMS), 15)
        self.assertTrue(all((ROOT / row["source"]).is_file() for row in ITEMS))
        self.assertIsNone(readiness(value, {}, {})["days_until_departure"])

    def test_plan_dates_clock_types_and_dorm_identity(self):
        for bad in [{"departure": "2026-02-30"}, {"departure": "2026-10-20", "arrival": "2026-10-19"}, {"time": "24:00"}, {"dorm": "tushuguan"}, {"mode": []}, {"notes": "x"*301}, {"departure": True}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate_plan(bad)
        value = validate_plan({"departure": "2026-10-20", "arrival": "2026-10-21", "time": "23:59", "dorm": "qinyuan-1-9"})
        self.assertEqual(value["time"], "23:59")

    def test_countdown_today_future_and_past_and_no_safety_score(self):
        current = default_preparation(); current["plan"]["departure"] = "2026-10-20"
        for day, expected in [(19, 1), (20, 0), (21, -1)]:
            self.assertEqual(readiness(current, {}, {}, date(2026,10,day))["days_until_departure"], expected)
        self.assertEqual(len(readiness(current, {}, {})["important_missing"]), 2)
        self.assertNotIn("score", readiness(current, {}, {}))

    def test_item_quantity_type_and_essential_rules(self):
        for entry in [{"quantity": True, "status": "packed"}, {"quantity": 0, "status": "todo"}, {"quantity": 100, "status": "todo"}, {"quantity": 1, "status": "buy"}]:
            with self.assertRaises(ValueError): update_preparation(default_preparation(), {"revision": 0, "action": "item", "id": "identity", "item": entry})
        current = update_preparation(default_preparation(), {"revision": 0, "action": "item", "id": "towel", "item": {"quantity": 2, "status": "buy"}})
        self.assertEqual(current["packing"]["towel"]["quantity"], 2)

    def test_custom_cap_duplicate_and_remove_only_custom(self):
        current = default_preparation()
        for index in range(20): current = update_preparation(current, {"revision": current["revision"], "action": "add", "title": str(index), "quantity": 1})
        with self.assertRaises(ValueError): update_preparation(current, {"revision": current["revision"], "action": "add", "title": "extra", "quantity": 1})
        with self.assertRaises(ValueError): update_preparation(default_preparation(), {"revision": 0, "action": "add", "title": "身份证", "quantity": 1})
        with self.assertRaises(ValueError): update_preparation(current, {"revision": current["revision"], "action": "remove", "id": "identity"})
        current = update_preparation(current, {"revision": current["revision"], "action": "remove", "id": current["custom"][0]["id"]})
        self.assertEqual(len(current["custom"]), 19)

    def test_backup_roundtrip_and_invalid_batch_are_atomic(self):
        current = update_preparation(default_preparation(), {"revision": 0, "action": "add", "title": "眼镜盒", "quantity": 2})
        value = prep_backup(current)
        self.assertEqual(validate_prep_backup(value)["custom"], current["custom"])
        invalid = {**value, "packing": {"identity": {"quantity": 1, "status": "skip"}}}
        with self.assertRaises(ValueError): update_preparation(current, {"revision": 1, "action": "restore", "backup": invalid})
        self.assertEqual(current["revision"], 1)
        self.assertEqual(len(current["custom"]), 1)
        with self.assertRaises(ValueError): validate_prep_backup({**value, "custom": value["custom"]*2})

    def test_readiness_uses_real_checks_and_last_scenario_answer(self):
        value = readiness(default_preparation(), {"notice": True}, {"notice": 0})
        self.assertEqual(len(value["pending_checks"]), 10)
        self.assertEqual([c["id"] for c in value["review_cases"]], ["notice"])
        self.assertEqual(readiness(default_preparation(), {}, {"notice": 1})["review_cases"], [])

    def test_memo_names_statuses_user_text_and_route_boundaries(self):
        current = default_preparation(); current["plan"] = validate_plan({"dorm": "qinyuan-1-9", "notes": "自填备注"})
        text = memo_text(current, {}, {}, {"revision": 0, "stops": []})
        for expected in ["沁园1-9", "自填备注", "待准备 · 身份证", "不是学校正式", "数量由自己填写"]: self.assertIn(expected, text)

    def test_persistence_revision_conflict_and_other_records_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory); session = "preparation-0000001"
            store.check(session, "notice", True)
            store.answer_scenario(session, "notice", 1)
            value = store.change_preparation(session, {"revision": 0, "action": "add", "title": "眼镜盒", "quantity": 1})
            with self.assertRaises(ValueError): store.change_preparation(session, {"revision": 0, "action": "plan", "plan": {}})
            self.assertEqual(Store(directory).preparation(session), value)
            self.assertEqual(store.preparation("other"), default_preparation())
            store.change_preparation(session, {"revision": 1, "action": "restore", "backup": prep_backup(default_preparation())})
            self.assertTrue(store.checklist(session)["notice"])
            self.assertEqual(store.rehearsal(session), {"notice": 1})


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = Retriever(ROOT)

    def test_source_headers_and_year_survive(self):
        chunks = [c for c in self.retriever.chunks if c["source"] == "入学指南补充.md"]
        self.assertTrue(all(c["effective_year"] == 2024 and c["urls"] and "2024级参考" in c["source_header"] for c in chunks))

    def test_material_question_prioritizes_material_list(self):
        results = self.retriever.search("报到要带什么材料？")
        self.assertEqual(results[0]["section"], "一、必备材料")
        self.assertNotIn("报到时间", [c["section"] for c in results])

    def test_luggage_question_prioritizes_living_supplies(self):
        results = self.retriever.search("入学行李要准备什么？")
        self.assertEqual(results[0]["source"], "入学准备清单.md")
        self.assertEqual(results[0]["section"], "三、行李与生活")

    def test_military_date_reference_is_not_preparation_list(self):
        result = self.retriever.search("军训什么时候开始？")[0]
        self.assertEqual(result["section"], "一、军训动员（官方信息）")
        self.assertEqual(result["effective_year"], 2024)

    def test_reversed_date_and_duration_questions_never_call_model(self):
        answerer = Answerer(self.retriever, Settings(allow_remote=True, api_key="synthetic-new-key"))
        with patch("urllib.request.urlopen") as remote:
            for question in ["什么时候报到？", "几号接站？", "军训要几天？", "军训持续多久？"]:
                with self.subTest(question=question):
                    prepared = answerer.prepare(question, [])
                    answer, mode = answerer.generate(question, prepared)
                    self.assertIn("未确认当年", answer)
                    self.assertEqual(mode, "local_evidence")
                    self.assertFalse(prepared["remote_attempted"])
            remote.assert_not_called()

    def test_official_payment_entry_first(self):
        self.assertEqual(self.retriever.search("学费咋交")[0]["source"], "官方服务入口.md")

    def test_campus_proper_names(self):
        for question, expected in [("沁园在哪里", "沁园"), ("厚德楼在哪", "厚德楼"), ("图书馆在哪里", "图书馆")]:
            with self.subTest(question=question):
                self.assertIn(expected, self.retriever.search(question)[0]["section"])

    def test_unknown_question_has_no_evidence(self):
        self.assertEqual(self.retriever.search("学校明天的彩票号码是什么"), [])
        self.assertEqual(self.retriever.search("学校是否提供量子计算课程"), [])

    def test_history_uses_user_turns(self):
        history = [{"role": "user", "content": "馨园宿舍在哪"}, {"role": "assistant", "content": "虚构其他内容"}]
        self.assertIn("馨园宿舍", rewrite("那里怎么走", history))
        self.assertNotIn("虚构", rewrite("那里怎么走", history))
        self.assertEqual(rewrite("那学费呢", history), "那学费呢")

    def test_current_year_is_explicitly_unknown(self):
        answerer = Answerer(self.retriever, Settings())
        prepared = answerer.prepare("今年新生什么时候报到", [])
        answer, mode = answerer.generate("今年新生什么时候报到", prepared)
        self.assertIn("未确认当年", answer)
        self.assertEqual(mode, "local_evidence")

    def test_missing_opening_time_is_not_inferred_from_map(self):
        answerer = Answerer(self.retriever, Settings())
        prepared = answerer.prepare("图书馆开放时间是几点", [])
        self.assertIn("未确认该设施", prepared["warnings"][0])

    def test_missing_amount_is_not_inferred(self):
        answerer = Answerer(self.retriever, Settings())
        prepared = answerer.prepare("学费多少钱", [])
        self.assertIn("未确认当年具体收费金额", prepared["warnings"][0])

    def test_default_mode_never_calls_remote_even_with_inherited_env(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-unused-key", "GUIDE_LLM_API_KEY": "synthetic-unused-key", "GUIDE_ALLOW_REMOTE_LLM": "false"}), patch("urllib.request.urlopen") as remote:
            answerer = Answerer(self.retriever, Settings.load())
            prepared = answerer.prepare("学费怎么交", [])
            answerer.generate("学费怎么交", prepared)
            remote.assert_not_called()
            self.assertEqual(answerer.remote_calls, 0)

    def test_received_key_fingerprint_is_blocked_even_if_opted_in(self):
        synthetic_key = "synthetic-received-key"
        fingerprint = hashlib.sha256(synthetic_key.encode()).hexdigest()
        with patch("backend.settings.json.loads", return_value=[fingerprint]), patch("urllib.request.urlopen") as remote:
            settings = Settings(allow_remote=True, api_key=synthetic_key)
            self.assertFalse(settings.remote_enabled())
            answerer = Answerer(self.retriever, settings)
            prepared = answerer.prepare("学费怎么交", [])
            answerer.generate("学费怎么交", prepared)
            remote.assert_not_called()
            self.assertTrue(settings.key_blocked())

    def test_remote_failure_falls_back_without_exposing_exception(self):
        with patch("urllib.request.urlopen", side_effect=RuntimeError("sensitive upstream detail")):
            answerer = Answerer(self.retriever, Settings(allow_remote=True, api_key="synthetic-new-key"))
            prepared = answerer.prepare("学费怎么交", [])
            answer, mode = answerer.generate("学费怎么交", prepared)
            self.assertEqual(mode, "local_evidence")
            self.assertNotIn("sensitive upstream detail", answer)
            self.assertIn("外部模型不可用", prepared["warnings"][-1])
            self.assertIn("外部模型不可用", answer)
            self.assertTrue(prepared["remote_attempted"])
            self.assertEqual(answerer.remote_calls, 1)

    def test_mocked_remote_success_retains_citations_and_attempt_marker(self):
        candidate = "从学校官网进入校园支付平台，核对当年通知。【1】"
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": candidate}}]}).encode())
        with patch("urllib.request.urlopen", return_value=response) as remote:
            answerer = Answerer(self.retriever, Settings(allow_remote=True, api_key="synthetic-new-key"))
            prepared = answerer.prepare("学费怎么交", [])
            answer, mode = answerer.generate("学费怎么交", prepared)
            self.assertEqual((answer, mode), (candidate, "remote_llm"))
            self.assertTrue(prepared["remote_attempted"])
            self.assertEqual(remote.call_args.args[0].full_url, "https://api.deepseek.com/chat/completions")

    def test_invalid_remote_citation_falls_back_with_visible_warning(self):
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "模型编造内容。【99】"}}]}).encode())
        with patch("urllib.request.urlopen", return_value=response):
            answerer = Answerer(self.retriever, Settings(allow_remote=True, api_key="synthetic-new-key"))
            prepared = answerer.prepare("学费怎么交", [])
            answer, mode = answerer.generate("学费怎么交", prepared)
            self.assertEqual(mode, "local_evidence")
            self.assertNotIn("模型编造内容", answer)
            self.assertIn("引用不完整", answer)
            self.assertTrue(prepared["remote_attempted"])


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / "tmp/tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temp_root)
        self.store = Store(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_sessions_are_isolated(self):
        self.store.save("session-a", "user", "one")
        self.assertEqual(self.store.history("session-b"), [])

    def test_checklist_survives_new_connection(self):
        self.store.check("session-a", "admission", True)
        second = Store(self.directory.name)
        self.assertTrue(second.checklist("session-a")["admission"])

    def test_feedback_cannot_reference_another_session(self):
        answer = self.store.save("session-a", "assistant", "text")
        with self.assertRaises(ValueError):
            self.store.feedback("session-b", answer, "helpful")

    def test_clear_conversation_preserves_checklist(self):
        self.store.save("session-a", "user", "one")
        self.store.check("session-a", "admission", True)
        self.store.delete_history("session-a")
        self.assertEqual(self.store.history("session-a"), [])
        self.assertTrue(self.store.checklist("session-a")["admission"])


class HTTPFixture:
    @classmethod
    def setUpClass(cls):
        root = ROOT / "tmp/tests"
        root.mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(dir=root)
        cls.app = Application(Settings(data_dir=Path(cls.directory.name)))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(cls.app))
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.directory.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        sent_headers = {"Content-Type": "application/json"}
        sent_headers.update(headers or {})
        connection.request(method, path, json.dumps(data, ensure_ascii=False).encode() if data is not None else None, sent_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result


class PreparationHTTPTests(HTTPFixture, unittest.TestCase):
    def test_get_save_memo_export_and_no_remote(self):
        session = "prep-http-00000001"
        self.assertEqual(self.request("GET", "/preparation.js")[0], 200)
        self.assertEqual(self.request("GET", "/preparation.css")[0], 200)
        current = json.loads(self.request("GET", "/api/preparation?session="+session)[2])
        self.assertEqual(current["state"]["revision"], 0)
        saved = json.loads(self.request("POST", "/api/preparation", {"session": session, "operation": {"revision": 0, "action": "plan", "plan": {"departure": "2026-10-20", "dorm": "qinyuan-1-9"}}})[2])
        self.assertEqual(saved["state"]["revision"], 1)
        status, headers, body = self.request("GET", "/api/preparation/memo.txt?session="+session)
        self.assertEqual(status, 200); self.assertIn("text/plain", headers["Content-Type"]); self.assertIn("2026-10-20", body)
        full = json.loads(self.request("GET", "/api/export?session="+session)[2]); self.assertEqual(full["preparation"]["revision"], 1)
        self.assertEqual(self.app.stats()["remote_calls"], 0)

    def test_preview_does_not_write_and_restore_preserves_checklist(self):
        session = "prep-http-00000002"; value = prep_backup(default_preparation())
        self.app.store.check(session, "identity", True)
        self.assertEqual(self.request("POST", "/api/preparation/preview", {"session": session, "backup": value})[0], 200)
        self.assertEqual(self.app.store.preparation(session)["revision"], 0)
        self.assertEqual(self.request("POST", "/api/preparation", {"session": session, "operation": {"revision": 0, "action": "restore", "backup": value}})[0], 200)
        self.assertTrue(self.app.store.checklist(session)["identity"])

    def test_origin_session_and_stale_operations_rejected(self):
        operation = {"revision": 0, "action": "plan", "plan": {}}
        self.assertEqual(self.request("POST", "/api/preparation", {"session": "prep-http-00000003", "operation": operation}, {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.request("GET", "/api/preparation?session=bad")[0], 400)
        self.assertEqual(self.request("POST", "/api/preparation", {"session": "prep-http-00000003", "operation": operation})[0], 200)
        self.assertEqual(self.request("POST", "/api/preparation", {"session": "prep-http-00000003", "operation": operation})[0], 400)


class HTTPTests(HTTPFixture, unittest.TestCase):
    def test_health_reports_no_remote_calls(self):
        status, _, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["remote_enabled"])
        self.assertEqual(json.loads(body)["remote_calls"], 0)

    def test_ask_sse_and_persistence(self):
        session = "test-session-000001"
        status, headers, body = self.request("POST", "/api/ask", {"session": session, "question": "报到要带什么材料"})
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers["Content-Type"])
        frames = [frame for frame in body.split("\n\n") if frame]
        events = [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:])) for frame in frames]
        self.assertEqual(events[-1][0], "done")
        self.assertFalse(next(value["remote_attempted"] for name, value in events if name == "sources"))
        self.assertIn("录取通知书", "".join(value["text"] for name, value in events if name == "delta"))
        status, _, history = self.request("GET", "/api/history?session=" + session)
        self.assertEqual(len(json.loads(history)["messages"]), 2)
        self.assertFalse(json.loads(history)["messages"][1]["remote_attempted"])

    def test_origin_rejected(self):
        status, _, _ = self.request("POST", "/api/checklist", {"session": "test-session-000002", "task": "admission", "checked": True}, {"Origin": "https://example.invalid"})
        self.assertEqual(status, 403)

    def test_bad_host_rejected(self):
        status, _, _ = self.request("GET", "/api/health", headers={"Host": "evil.invalid"})
        self.assertEqual(status, 403)

    def test_private_and_traversal_paths_not_served(self):
        for path in ["/backend/.env", "/../docs/credential-isolation.json", "/.runtime/guide.sqlite3"]:
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_input_limits(self):
        status, _, _ = self.request("POST", "/api/ask", {"session": "test-session-000003", "question": "问" * 501})
        self.assertEqual(status, 400)

    def test_task_validation(self):
        status, _, _ = self.request("POST", "/api/checklist", {"session": "test-session-000004", "task": "not-a-task", "checked": "true"})
        self.assertEqual(status, 400)

    def test_static_page_has_csp(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("新生指南", body)


class AppearanceHTTPTests(HTTPFixture, unittest.TestCase):
    def test_appearance_assets_and_local_image_policy(self):
        for path, kind in [("/appearance.js", "text/javascript"), ("/appearance.css", "text/css")]:
            status, headers, content = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(kind, headers["Content-Type"])
            self.assertTrue(content)
        _, headers, page = self.request("GET", "/")
        self.assertIn("img-src 'self' data: blob:", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn('id="appearance-dialog"', page)
        self.assertIn('id="intro-dialog"', page)
        self.assertEqual(self.request("GET", "/freshman-appearance")[0], 404)

    def test_mascot_assets_available_without_exposing_arbitrary_paths(self):
        self.assertEqual(self.request("GET", "/assets/creative-back.png")[0], 404)
        self.assertEqual(self.request("GET", "/assets/creative-back-lines.json")[0], 404)
        for path in ["/assets/mascot-lines.json"] + [f"/assets/mascot-{pose}-lines.json" for pose in ("wave", "reading", "point")] + [f"/assets/chibi-{pose}-lines.json" for pose in ("wave", "read", "ready", "guide", "think", "cheer")] + [f"/assets/creative-{pose}-lines.json" for pose in ("side", "laugh", "back-v2", "rest")]:
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn("application/json", headers["Content-Type"])
            self.assertTrue(json.loads(body)["paths"])
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            for path in ["/assets/school-mascot.png"] + [f"/assets/mascot-{pose}.png" for pose in ("wave", "reading", "point")] + [f"/assets/chibi-{pose}.png" for pose in ("wave", "read", "ready", "guide", "think", "cheer")] + [f"/assets/creative-{pose}.png" for pose in ("side", "laugh", "back-v2", "rest")]:
                connection.request("GET", path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "image/png")
                self.assertEqual(response.read()[:8], b"\x89PNG\r\n\x1a\n")
        finally:
            connection.close()
        self.assertEqual(self.request("GET", "/assets/../../backend/settings.py")[0], 404)
        self.assertEqual(self.app.answerer.remote_calls, 0)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        from backend.experience import Experience
        self.experience = Experience()

    def test_quiet_priority_prefers_middle_beds_and_ties_remain_visible(self):
        result = self.experience.recommendations({"room": "liuren", "priorities": {"quiet": 3, "light": 0, "access": 0, "dry": 0}})
        beds = result["groups"]["bed"]
        self.assertEqual({b["bed_id"] for b in beds[:2]}, {"2", "5"})
        self.assertEqual(beds[0]["score"], beds[1]["score"])
        self.assertIn("偏好权重 3", beds[0]["reasons"][0])

    def test_light_priority_changes_recommendation_to_window(self):
        result = self.experience.recommendations({"room": "liuren", "priorities": {"quiet": 0, "light": 3, "access": 0, "dry": 0}})
        self.assertEqual({b["bed_id"] for b in result["groups"]["bed"][:2]}, {"3", "4"})

    def test_zero_weights_are_explicitly_tied(self):
        result = self.experience.recommendations({"priorities": dict.fromkeys(["quiet", "light", "access", "dry"], 0)})
        self.assertEqual({b["score"] for b in result["groups"]["bed"]}, {0})
        self.assertIn("全部权重为 0", result["groups"]["bed"][0]["reasons"][0])

    def test_no_interest_never_invents_club_match(self):
        result = self.experience.recommendations({})
        self.assertEqual(result["groups"]["club"], [])
        self.assertEqual(result["groups"]["union"], [])

    def test_coding_match_has_real_evidence_and_time_caution(self):
        result = self.experience.recommendations({"interests": ["coding"], "hours": "low"})
        names = [i["name"] for i in result["groups"]["club"]]
        self.assertIn("计算机协会", names)
        self.assertNotIn("电竞社", names)
        item = next(i for i in result["groups"]["club"] if i["name"] == "计算机协会")
        self.assertIn("资料包含", item["reasons"][0])
        self.assertTrue(any("时间较少" in c for c in item["cautions"]))

    def test_catalog_has_stable_unique_ids_and_valid_dorm_beds(self):
        from backend.experience import Experience
        self.assertEqual(set(self.experience.items), set(Experience().items))
        self.assertEqual(len([i for i in self.experience.items.values() if i["kind"] == "bed"]), 10)
        self.assertEqual(len({i["name"] for i in self.experience.items.values() if i["kind"] == "contest"}), len([i for i in self.experience.items.values() if i["kind"] == "contest"]))

    def test_invalid_profiles_reject_types_ranges_and_unrecognized_values(self):
        from backend.experience import validate_profile
        for profile in [None, [], {"interests": "coding"}, {"interests": [{}]}, {"room": {}}, {"hours": []}, {"college": "不存在"}, {"priorities": {"quiet": True}}, {"priorities": {"quiet": 4}}, {"priorities": {"extra": 1}}]:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_profile(profile)

    def test_reference_summaries_do_not_promise_official_recognition(self):
        for item in self.experience.items.values():
            if item["kind"] == "contest":
                self.assertNotIn("教育部", item["intro"])
                self.assertEqual(item["grad"], "待核对")

    def test_new_sources_remain_third_party_and_time_sensitive(self):
        retriever = Retriever(ROOT)
        chunks = [c for c in retriever.chunks if c["source"].startswith("大学生") or c["source"] == "宿舍床位选择参考.md"]
        self.assertTrue(chunks)
        self.assertTrue(all(c["source_type"] == "third_party" and not c["verified"] for c in chunks))
        answerer = Answerer(retriever, Settings(allow_remote=True, api_key="synthetic-new-key"))
        with patch("urllib.request.urlopen") as remote:
            prepared = answerer.prepare("计算机协会本校怎么报名", [])
            answerer.generate("计算机协会本校怎么报名", prepared)
            self.assertTrue(any("未确认本校" in w for w in prepared["warnings"]))
            remote.assert_not_called()

    def test_competition_intent_prefers_competition_and_room_excludes_other_room(self):
        retriever = Retriever(ROOT)
        results = retriever.search("数学建模竞赛做什么")
        self.assertEqual(results[0]["source"], "大学生竞赛指南.md")
        self.assertIn("数学建模", results[0]["section"])
        results = retriever.search("六人寝的中间床位在哪里")
        self.assertIn("六人", results[0]["section"])
        self.assertFalse(any("四人" in c["section"] for c in results))

    def test_plan_storage_is_persistent_isolated_and_capped(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(Path(directory))
            store.set_profile("a", {"interests": ["coding"]})
            store.set_saved("a", "bed-liuren-2", "planned")
            reopened = Store(Path(directory))
            self.assertEqual(reopened.profile("a")["interests"], ["coding"])
            self.assertIsNone(reopened.profile("b"))
            self.assertEqual(reopened.saved("b"), [])
            reopened.set_saved("a", "bed-liuren-2", "doing")
            self.assertEqual(reopened.saved("a")[0]["status"], "doing")
            for i in range(29): reopened.set_saved("a", "item" + str(i), "planned")
            with self.assertRaises(ValueError): reopened.set_saved("a", "too-many", "planned")
            reopened.set_saved("a", "bed-liuren-2", "removed")
            self.assertEqual(len(reopened.saved("a")), 29)


class DecisionHTTPTests(HTTPFixture, unittest.TestCase):
    def test_profile_save_read_recommend_and_export(self):
        session = "decision-session-00001"
        profile = {"interests": ["coding"], "priorities": {"quiet": 3, "light": 0, "access": 0, "dry": 0}}
        status, _, body = self.request("POST", "/api/profile", {"session": session, "profile": profile})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["groups"]["bed"][0]["position"], "middle")
        status, _, body = self.request("GET", "/api/profile?session=" + session)
        self.assertEqual(json.loads(body)["profile"]["interests"], ["coding"])
        item_id = result["groups"]["club"][0]["id"]
        status, _, _ = self.request("POST", "/api/saved", {"session": session, "item": item_id, "status": "planned"})
        self.assertEqual(status, 200)
        status, _, body = self.request("GET", "/api/export?session=" + session)
        exported = json.loads(body)
        self.assertEqual(exported["saved_items"][0]["id"], item_id)
        self.assertEqual(exported["profile"]["interests"], ["coding"])
        self.assertTrue(exported["saved_items"][0]["actions"])
        self.assertEqual(self.app.answerer.remote_calls, 0)

    def test_saved_session_isolation_and_authoritative_ids(self):
        a, b = "decision-session-00002", "decision-session-00003"
        self.assertEqual(self.request("POST", "/api/saved", {"session": a, "item": "bed-liuren-2", "status": "planned"})[0], 200)
        status, _, body = self.request("GET", "/api/saved?session=" + b)
        self.assertEqual(json.loads(body)["items"], [])
        for item, status in [("../../.env", "planned"), ([], "planned"), ("bed-liuren-2", "booked"), ("bed-liuren-2", {})]:
            self.assertEqual(self.request("POST", "/api/saved", {"session": a, "item": item, "status": status})[0], 400)

    def test_invalid_profile_and_cross_site_write_rejected(self):
        payload = {"session": "decision-session-00004", "profile": {"priorities": {"quiet": 99}}}
        self.assertEqual(self.request("POST", "/api/profile", payload)[0], 400)
        payload["profile"] = {}
        self.assertEqual(self.request("POST", "/api/profile", payload, {"Origin": "https://example.invalid"})[0], 403)

    def test_public_catalog_and_new_script_available(self):
        status, _, body = self.request("GET", "/api/explore")
        self.assertEqual(status, 200)
        self.assertEqual(len({x["id"] for x in json.loads(body)["items"]}), len(self.app.experience.items))
        self.assertEqual(self.request("GET", "/decision.js")[0], 200)


class PlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.experience import Experience
        cls.catalog = Experience().items

    def task(self, **fields):
        return validate_task({"title": "了解招新安排", **fields}, self.catalog)

    def test_valid_dates_and_invalid_types(self):
        with self.assertRaises(ValueError): self.task(notes="\ud800")
        self.assertEqual(self.task(due="2028-02-29")["due"], "2028-02-29")
        for fields in [{"due": "2026-02-29"}, {"due": []}, {"due": "2026-2-01"}, {"title": ""}, {"title": 3}, {"notes": "a" * 601}, {"status": []}, {"priority": True}, {"id": "../../.env"}, {"source_item": []}, {"source_item": "bed-liuren-2", "action_no": True}]:
            with self.subTest(fields=fields), self.assertRaises(ValueError): self.task(**fields)

    def test_tasks_reopen_isolate_and_archive_restore(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(Path(directory)); task = store.put_task("a", self.task(due="2026-10-18", notes="请向团委核对"))
            reopened = Store(Path(directory))
            self.assertEqual(reopened.tasks("a")[0]["notes"], "请向团委核对")
            self.assertEqual(reopened.tasks("b"), [])
            with self.assertRaises(ValueError): reopened.put_task("b", {**task, "status": "done"})
            reopened.put_task("a", {**task, "status": "archived"})
            self.assertEqual(reopened.tasks("a")[0]["status"], "archived")
            reopened.put_task("a", {**task, "status": "todo"})
            self.assertEqual(reopened.tasks("a")[0]["status"], "todo")

    def test_merge_deduplicates_and_keeps_existing_progress(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(Path(directory)); original = store.put_task("a", self.task(source_item="bed-liuren-2", action_no=0, status="done", notes="已有核对结果"))
            incoming = self.task(source_item="bed-liuren-2", action_no=0, status="todo")
            manual = self.task(title="手动任务")
            self.assertEqual(store.preview_tasks("a", [incoming, manual, manual]), {"added": 1, "skipped": 2})
            self.assertEqual(store.merge_tasks("a", [incoming, manual, manual]), {"added": 1, "skipped": 2})
            self.assertEqual(store.tasks("a")[0], original)
            self.assertEqual(store.merge_tasks("a", [manual])["added"], 0)

    def test_cap_and_overflow_merge_are_atomic(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(Path(directory)); store.merge_tasks("a", [self.task(title=str(i)) for i in range(99)])
            with self.assertRaises(ValueError): store.merge_tasks("a", [self.task(title="one"), self.task(title="two")])
            self.assertEqual(len(store.tasks("a")), 99)
            store.put_task("a", self.task(title="last"))
            with self.assertRaises(ValueError): store.put_task("a", self.task(title="overflow"))
            self.assertEqual(len(store.tasks("a")), 100)

    def test_bad_backup_is_rejected_before_any_merge(self):
        for value in [[], {"format": "wrong", "format_version": 1, "tasks": []}, {"format": "freshman-guide-tasks", "format_version": True, "tasks": []}, backup([self.task(), {"title": "bad", "source_item": "unknown"}]), backup([self.task()] * 101)]:
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError): validate_backup(value, self.catalog)
        self.assertEqual(len(validate_backup(backup([self.task()]), self.catalog)), 1)

    def test_calendar_escaping_all_day_dates_and_utf8_folding(self):
        tasks = []
        for fields in [{"due": "2026-12-31", "title": "中" * 70, "notes": "第一行,备注;\\\n第二行"}, {"due": "2026-10-19", "status": "done"}, {"due": "2026-10-19", "status": "archived"}, {}]:
            tasks.append({**self.task(**fields), "id": "73c8d2e9-35df-4f50-a577-40b26cfdb650"})
        output = calendar(tasks, self.catalog)
        unfolded = output.replace("\r\n ", "")
        self.assertEqual(output.count("BEGIN:VEVENT"), 1)
        self.assertIn("DTSTART;VALUE=DATE:20261231", output)
        self.assertIn("DTEND;VALUE=DATE:20270101", output)
        self.assertIn("第一行\\,备注\\;\\\\\\n第二行", unfolded)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in output.split("\r\n")))

    def test_unknown_and_time_questions_never_autosearch(self):
        with patch("urllib.request.urlopen") as remote:
            answerer = Answerer(Retriever(ROOT), Settings())
            for question in ["学校是否提供量子计算课程", "图书馆今天几点开门", "蓝桥杯今年报名截止日期"]:
                prepared = answerer.prepare(question, []); answerer.generate(question, prepared)
                self.assertTrue(prepared["check_links"])
                self.assertFalse(prepared["web_used"])
            remote.assert_not_called()

    def test_verification_link_never_contains_full_question_or_secrets(self):
        from urllib.parse import unquote_plus
        links = verification_links("我的身份证987654321密钥synthetic-secret 学费多少钱")
        text = unquote_plus(json.dumps(links, ensure_ascii=False))
        self.assertNotIn("987654321", text); self.assertNotIn("synthetic-secret", text)
        self.assertIn("site:hnvust.cn", text)

    def test_short_exact_query_and_offcampus_coincidence(self):
        retriever = Retriever(ROOT)
        self.assertTrue(retriever.search("几号接站？"))
        self.assertEqual(retriever.search("布拉格广场在哪里"), [])
        answerer = Answerer(retriever, Settings())
        prepared = {"query": "图书馆几点开放", "sources": [], "warnings": ["未确认该设施开放时间"], "remote_attempted": False}
        self.assertIn("未确认该设施", answerer.generate("图书馆几点开放", prepared)[0])


class PlannerHTTPTests(HTTPFixture, unittest.TestCase):
    def test_multibyte_full_backup_roundtrips(self):
        session = "planner-session-00007"
        tasks = [{"title": str(i) + "😀" * 97, "notes": "😀" * 600} for i in range(100)]
        value = backup(tasks)
        size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        self.assertGreater(size, 250000); self.assertLess(size, 500000)
        status, _, body = self.request("POST", "/api/tasks/import", {"session": session, "backup": value})
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["added"], 100)
        exported = json.loads(self.request("GET", "/api/tasks/backup?session=" + session)[2])
        self.assertEqual(exported["tasks"][0]["notes"], "😀" * 600)

    def test_linked_tasks_cannot_be_cloned_via_manual_creation(self):
        payload = {"session": "planner-session-00006", "task": {"title": "关联任务", "source_item": "bed-liuren-2", "action_no": 0}}
        self.assertEqual(self.request("POST", "/api/tasks", payload)[0], 400)

    def test_task_crud_export_and_isolation(self):
        session = "planner-session-00001"
        status, _, body = self.request("POST", "/api/tasks", {"session": session, "task": {"title": "准备介绍", "due": "2026-10-18", "priority": "high"}})
        self.assertEqual(status, 200); task = json.loads(body)["tasks"][0]
        self.assertEqual(self.request("POST", "/api/tasks", {"session": "planner-session-other", "task": {**task, "status": "done"}})[0], 400)
        self.assertEqual(json.loads(self.request("GET", "/api/tasks?session=planner-session-other")[2])["tasks"], [])
        for status in ["doing", "done", "archived", "todo"]:
            response = self.request("POST", "/api/tasks", {"session": session, "task": {**task, "status": status}})
            self.assertEqual(json.loads(response[2])["tasks"][0]["status"], status)
        exported = json.loads(self.request("GET", "/api/export?session=" + session)[2])
        self.assertEqual(exported["tasks"][0]["priority"], "high")
        status, headers, body = self.request("GET", "/api/tasks/calendar?session=" + session)
        self.assertEqual(status, 200); self.assertIn("BEGIN:VEVENT", body); self.assertIn("text/calendar", headers["Content-Type"])
        self.assertEqual(self.app.answerer.remote_calls, 0)

    def test_choice_steps_require_collection_and_deduplicate(self):
        session = "planner-session-00002"; payload = {"session": session, "item": "bed-liuren-2"}
        self.assertEqual(self.request("POST", "/api/tasks/from-choice", payload)[0], 400)
        self.request("POST", "/api/saved", {**payload, "status": "planned"})
        result = json.loads(self.request("POST", "/api/tasks/from-choice", payload)[2]); self.assertEqual(result["added"], 3)
        task = result["tasks"][0]; self.request("POST", "/api/tasks", {"session": session, "task": {**task, "status": "done"}})
        result = json.loads(self.request("POST", "/api/tasks/from-choice", payload)[2]); self.assertEqual(result["added"], 0)
        self.assertEqual(result["tasks"][0]["status"], "done")

    def test_import_preview_restore_and_invalid_batch_atomicity(self):
        source, target = "planner-session-00003", "planner-session-00004"
        self.request("POST", "/api/tasks", {"session": source, "task": {"title": "备份恢复", "status": "done"}})
        value = json.loads(self.request("GET", "/api/tasks/backup?session=" + source)[2])
        payload = {"session": target, "backup": value}
        preview = json.loads(self.request("POST", "/api/tasks/import-preview", payload)[2]); self.assertEqual(preview["added"], 1)
        self.assertEqual(json.loads(self.request("GET", "/api/tasks?session=" + target)[2])["tasks"], [])
        result = json.loads(self.request("POST", "/api/tasks/import", payload)[2]); self.assertEqual(result["tasks"][0]["status"], "done")
        self.assertNotEqual(result["tasks"][0]["id"], value["tasks"][0]["id"])
        self.assertEqual(json.loads(self.request("POST", "/api/tasks/import", payload)[2])["skipped"], 1)
        payload["backup"] = backup([{"title": "good"}, {"title": "bad", "due": "2026-02-30"}])
        self.assertEqual(self.request("POST", "/api/tasks/import", payload)[0], 400)
        self.assertEqual(len(json.loads(self.request("GET", "/api/tasks?session=" + target)[2])["tasks"]), 1)

    def test_import_bound_origin_and_planner_static(self):
        payload = {"session": "planner-session-00005", "backup": backup([])}
        self.assertEqual(self.request("POST", "/api/tasks/import", payload, {"Origin": "https://example.invalid"})[0], 403)
        # Oversized bodies are rejected from their headers before being read.
        # Sending the whole body can cause Windows to reset the closing socket.
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("POST", "/api/tasks/import", headers={"Content-Type": "application/json", "Content-Length": "524289"})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn("请求过大", response.read().decode())
        finally:
            connection.close()
        self.assertEqual(self.request("GET", "/planner.js")[0], 200)


class OrientationTests(unittest.TestCase):
    def test_cases_and_routes_only_reference_existing_material(self):
        self.assertEqual(len(CASES), 9)
        self.assertEqual(len({item["id"] for item in CASES}), 9)
        for item in CASES:
            self.assertEqual(len(item["options"]), len(item["explanations"]))
            self.assertTrue(0 <= item["recommended"] < len(item["options"]))
            self.assertTrue(all((ROOT / filename).is_file() for filename in item["sources"]))
        for item in PRESETS:
            self.assertTrue(all(identifier in PLACES_BY_ID for identifier in item["stops"]))
            self.assertEqual(len(item["stops"]), len(set(item["stops"])))

    def test_answer_rejects_foreign_cases_and_noninteger_choices(self):
        for identifier, choice in [("unknown", 0), ([], 0), ("notice", True), ("notice", "1"), ("notice", -1), ("notice", 3)]:
            with self.subTest(identifier=identifier, choice=choice), self.assertRaises(ValueError): validate_answer(identifier, choice)
        self.assertEqual(validate_answer("notice", 1)["recommended"], 1)

    def test_itinerary_bounds_duplicate_and_move_checks(self):
        route = {"revision": 0, "stops": []}
        for identifier in list(PLACES_BY_ID)[:8]:
            route = update_route(route, {"revision": route["revision"], "action": "add", "place": identifier})
        invalid = [{"action": "add", "place": "tushuguan"}, {"action": "add", "place": route["stops"][0]["id"]}, {"action": "move", "place": route["stops"][0]["id"], "delta": -1}, {"action": "move", "place": route["stops"][0]["id"], "delta": True}, {"action": "visit", "place": route["stops"][0]["id"], "visited": 1}, {"action": "remove", "place": "unknown"}, {"action": []}]
        for operation in invalid:
            with self.subTest(operation=operation), self.assertRaises(ValueError): update_route(route, {"revision": route["revision"], **operation})
        self.assertEqual(len(route["stops"]), 8)

    def test_rehearsal_and_itinerary_persist_separately_from_checklist(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(directory); store.check("a", "notice", True)
            store.answer_scenario("a", "notice", 0); store.answer_scenario("a", "notice", 1)
            route = store.change_itinerary("a", {"revision": 0, "action": "preset", "preset": "daily"})
            store.change_itinerary("a", {"revision": route["revision"], "action": "visit", "place": "kuaidi", "visited": True})
            reopened = Store(directory)
            self.assertEqual(reopened.rehearsal("a"), {"notice": 1})
            self.assertTrue(reopened.itinerary("a")["stops"][1]["visited"])
            self.assertEqual(reopened.rehearsal("b"), {}); self.assertEqual(reopened.itinerary("b")["stops"], [])
            self.assertEqual(reopened.checklist("a"), {"notice": True})

    def test_stale_revision_cannot_overwrite_progress_and_failures_are_atomic(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp/tests") as directory:
            store = Store(directory); route = store.change_itinerary("a", {"revision": 0, "action": "add", "place": "tushuguan"})
            with self.assertRaises(ValueError): store.change_itinerary("a", {"revision": 0, "action": "clear"})
            with self.assertRaises(ValueError): store.change_itinerary("a", {"revision": True, "action": "clear"})
            with self.assertRaises(ValueError): store.change_itinerary("a", {"revision": route["revision"], "action": "move", "place": "tushuguan", "delta": 1})
            self.assertEqual(store.itinerary("a"), route)

    def test_order_visit_preservation_remove_and_clear(self):
        route = update_route({"revision": 0, "stops": []}, {"revision": 0, "action": "preset", "preset": "study"})
        route = update_route(route, {"revision": 1, "action": "visit", "place": "tushuguan", "visited": True})
        route = update_route(route, {"revision": 2, "action": "move", "place": "tushuguan", "delta": -1})
        self.assertEqual(route["stops"][1], {"id": "tushuguan", "visited": True})
        route = update_route(route, {"revision": 3, "action": "preset", "preset": "study"})
        self.assertTrue(route["stops"][2]["visited"])
        self.assertIn("不是实际道路", route_text(route)); self.assertIn("3. 图书馆 · 已到访", route_text(route))
        route = update_route(route, {"revision": 4, "action": "remove", "place": "houde"})
        self.assertEqual(len(route["stops"]), 2)
        self.assertEqual(update_route(route, {"revision": 5, "action": "clear"})["stops"], [])


class OrientationHTTPTests(HTTPFixture, unittest.TestCase):
    def test_rehearsal_save_revisit_export_and_isolation(self):
        session = "orientation-test-0001"
        response = self.request("GET", "/api/orientation?session=" + session)
        self.assertEqual(response[0], 200); self.assertEqual(len(json.loads(response[2])["cases"]), 9)
        payload = {"session": session, "scenario": "notice", "choice": 1}
        self.assertEqual(json.loads(self.request("POST", "/api/orientation/answer", payload)[2])["answers"], {"notice": 1})
        self.assertEqual(json.loads(self.request("GET", "/api/checklist?session=" + session)[2])["checked"], {})
        self.assertEqual(json.loads(self.request("GET", "/api/orientation?session=orientation-test-0002")[2])["answers"], {})
        exported = json.loads(self.request("GET", "/api/export?session=" + session)[2]); self.assertEqual(exported["rehearsal"], {"notice": 1})
        self.assertEqual(self.app.answerer.remote_calls, 0)

    def test_route_operations_text_export_and_history_clear_preserve_state(self):
        session = "orientation-test-0003"
        payload = {"session": session, "operation": {"revision": 0, "action": "preset", "preset": "study"}}
        route = json.loads(self.request("POST", "/api/orientation/route", payload)[2])["itinerary"]
        self.assertEqual(len(route["stops"]), 3)
        self.assertEqual(self.request("POST", "/api/orientation/route", payload)[0], 400)
        status, headers, body = self.request("GET", "/api/orientation/route.txt?session=" + session)
        self.assertEqual(status, 200); self.assertIn("text/plain", headers["Content-Type"]); self.assertIn("3. 图书馆", body)
        self.request("DELETE", "/api/history", {"session": session})
        self.assertEqual(json.loads(self.request("GET", "/api/orientation?session=" + session)[2])["itinerary"], route)

    def test_orientation_origin_invalid_fields_and_static_allowlist(self):
        payload = {"session": "orientation-test-0004", "scenario": "notice", "choice": False}
        self.assertEqual(self.request("POST", "/api/orientation/answer", payload)[0], 400)
        self.assertEqual(self.request("POST", "/api/orientation/answer", {**payload, "choice": 1}, {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.request("GET", "/api/orientation?session=x")[0], 400)
        self.assertEqual(self.request("GET", "/orientation.js")[0], 200)
        self.assertEqual(self.request("GET", "/backend/orientation.py")[0], 404)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    capture = io.StringIO()
    result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "success": result.wasSuccessful(), "scope": "Offline unit and localhost HTTP checks; remote adapter mocked", "output": capture.getvalue()}
    (ROOT / "docs/verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(capture.getvalue())
    sys.exit(0 if result.wasSuccessful() else 1)
