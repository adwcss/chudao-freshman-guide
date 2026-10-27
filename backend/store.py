"""Local SQLite persistence. Each operation uses its own connection/transaction."""
import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import uuid
from .planner import LIMIT, new_id, task_identity
from .orientation import update_route, validate_answer
from .preparation import default_preparation, update_preparation


class Store:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path = Path(directory) / "guide.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS session_messages ON messages(session, created_at);
                CREATE TABLE IF NOT EXISTS checklist(session TEXT NOT NULL, task TEXT NOT NULL, checked INTEGER NOT NULL, PRIMARY KEY(session,task));
                CREATE TABLE IF NOT EXISTS feedback(session TEXT NOT NULL, answer TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(session,answer));
                CREATE TABLE IF NOT EXISTS preferences(session TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS saved_items(session TEXT NOT NULL, item TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(session,item));
                CREATE TABLE IF NOT EXISTS personal_tasks(id TEXT PRIMARY KEY, session TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS personal_tasks_session ON personal_tasks(session);
                CREATE TABLE IF NOT EXISTS rehearsal_answers(session TEXT NOT NULL, scenario TEXT NOT NULL, choice INTEGER NOT NULL, PRIMARY KEY(session,scenario));
                CREATE TABLE IF NOT EXISTS campus_itinerary(session TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS departure_preparation(session TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def history(self, session, limit=60):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE session=? ORDER BY rowid DESC LIMIT ?", (session, limit)).fetchall()
        return [{"id": r["id"], "role": r["role"], "content": r["content"], **json.loads(r["payload"])} for r in reversed(rows)]

    def save(self, session, role, content, payload=None):
        message_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO messages(id,session,role,content,payload) VALUES(?,?,?,?,?)", (message_id, session, role, content, json.dumps(payload or {}, ensure_ascii=False)))
            db.execute("DELETE FROM messages WHERE session=? AND id NOT IN (SELECT id FROM messages WHERE session=? ORDER BY rowid DESC LIMIT 100)", (session, session))
        return message_id

    def checklist(self, session):
        with self.connect() as db:
            return {r["task"]: bool(r["checked"]) for r in db.execute("SELECT task,checked FROM checklist WHERE session=?", (session,))}

    def check(self, session, task, checked):
        with self.connect() as db:
            db.execute("INSERT INTO checklist VALUES(?,?,?) ON CONFLICT(session,task) DO UPDATE SET checked=excluded.checked", (session, task, int(checked)))

    def feedback(self, session, answer, value):
        with self.connect() as db:
            found = db.execute("SELECT 1 FROM messages WHERE id=? AND session=? AND role='assistant'", (answer, session)).fetchone()
            if not found:
                raise ValueError("回答不存在")
            db.execute("INSERT INTO feedback VALUES(?,?,?) ON CONFLICT(session,answer) DO UPDATE SET value=excluded.value", (session, answer, value))

    def delete_history(self, session):
        with self.connect() as db:
            db.execute("DELETE FROM feedback WHERE session=?", (session,))
            db.execute("DELETE FROM messages WHERE session=?", (session,))

    def profile(self, session):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM preferences WHERE session=?", (session,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def set_profile(self, session, profile):
        with self.connect() as db:
            db.execute("INSERT INTO preferences VALUES(?,?) ON CONFLICT(session) DO UPDATE SET payload=excluded.payload", (session, json.dumps(profile, ensure_ascii=False)))

    def saved(self, session):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT item,status FROM saved_items WHERE session=? ORDER BY rowid", (session,))]

    def set_saved(self, session, item, status):
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM saved_items WHERE session=? AND item=?", (session, item)).fetchone()
            if status == "removed":
                db.execute("DELETE FROM saved_items WHERE session=? AND item=?", (session, item))
            else:
                if not exists and db.execute("SELECT COUNT(*) FROM saved_items WHERE session=?", (session,)).fetchone()[0] >= 30:
                    raise ValueError("最多收藏30项，请先移除一项。")
                db.execute("INSERT INTO saved_items VALUES(?,?,?) ON CONFLICT(session,item) DO UPDATE SET status=excluded.status", (session, item, status))

    def tasks(self, session):
        with self.connect() as db:
            return [json.loads(r["payload"]) for r in db.execute("SELECT payload FROM personal_tasks WHERE session=? ORDER BY rowid", (session,))]

    def put_task(self, session, task):
        task = dict(task)
        with self.connect() as db:
            if "id" in task:
                row = db.execute("SELECT payload FROM personal_tasks WHERE id=? AND session=?", (task["id"], session)).fetchone()
                if not row:
                    raise ValueError("任务不存在于当前会话。")
                old = json.loads(row["payload"])
                if (old["source_item"], old["action_no"]) != (task["source_item"], task["action_no"]):
                    raise ValueError("任务的关联来源不能改变。")
                db.execute("UPDATE personal_tasks SET payload=? WHERE id=? AND session=?", (json.dumps(task, ensure_ascii=False), task["id"], session))
            else:
                # Serialize count + insert so concurrent requests cannot bypass the limit.
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT COUNT(*) FROM personal_tasks WHERE session=?", (session,)).fetchone()[0] >= LIMIT:
                    raise ValueError("当前会话最多保存100项任务（含归档）。")
                task["id"] = new_id()
                db.execute("INSERT INTO personal_tasks VALUES(?,?,?)", (task["id"], session, json.dumps(task, ensure_ascii=False)))
        return task

    def merge_tasks(self, session, tasks):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = [json.loads(row["payload"]) for row in db.execute("SELECT payload FROM personal_tasks WHERE session=?", (session,))]
            identities = {task_identity(task) for task in existing}
            additions = []
            for task in tasks:
                identity = task_identity(task)
                if identity not in identities:
                    additions.append({**task, "id": new_id()})
                    identities.add(identity)
            if len(existing) + len(additions) > LIMIT:
                raise ValueError("合并后超过100项任务，未导入任何任务。")
            for task in additions:
                db.execute("INSERT INTO personal_tasks VALUES(?,?,?)", (task["id"], session, json.dumps(task, ensure_ascii=False)))
        return {"added": len(additions), "skipped": len(tasks) - len(additions)}

    def preview_tasks(self, session, tasks):
        existing = self.tasks(session)
        identities = {task_identity(task) for task in existing}
        added = 0
        for task in tasks:
            identity = task_identity(task)
            if identity not in identities:
                added += 1
                identities.add(identity)
        if len(existing) + added > LIMIT:
            raise ValueError("合并后超过100项任务，请缩小备份范围。")
        return {"added": added, "skipped": len(tasks) - added}

    def rehearsal(self, session):
        with self.connect() as db:
            return {row["scenario"]: row["choice"] for row in db.execute("SELECT scenario,choice FROM rehearsal_answers WHERE session=?", (session,))}

    def answer_scenario(self, session, scenario, choice):
        validate_answer(scenario, choice)
        with self.connect() as db:
            db.execute("INSERT INTO rehearsal_answers VALUES(?,?,?) ON CONFLICT(session,scenario) DO UPDATE SET choice=excluded.choice", (session, scenario, choice))

    def itinerary(self, session):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM campus_itinerary WHERE session=?", (session,)).fetchone()
        return json.loads(row["payload"]) if row else {"revision": 0, "stops": []}

    def change_itinerary(self, session, operation):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM campus_itinerary WHERE session=?", (session,)).fetchone()
            current = json.loads(row["payload"]) if row else {"revision": 0, "stops": []}
            value = update_route(current, operation)
            db.execute("INSERT INTO campus_itinerary VALUES(?,?) ON CONFLICT(session) DO UPDATE SET payload=excluded.payload", (session, json.dumps(value, ensure_ascii=False)))
        return value

    def preparation(self, session):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM departure_preparation WHERE session=?", (session,)).fetchone()
        return json.loads(row["payload"]) if row else default_preparation()

    def change_preparation(self, session, operation):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM departure_preparation WHERE session=?", (session,)).fetchone()
            current = json.loads(row["payload"]) if row else default_preparation()
            result = update_preparation(current, operation)
            db.execute("INSERT INTO departure_preparation VALUES(?,?) ON CONFLICT(session) DO UPDATE SET payload=excluded.payload", (session, json.dumps(result, ensure_ascii=False)))
        return result
