import sqlite3
import json
from datetime import datetime
from pathlib import Path


class Database:
    def __init__(self):
        self.data_dir = Path.home() / ".pomato"
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "pomato.db"
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pomodoro_entries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT NOT NULL,
                    session_no  INTEGER NOT NULL,
                    start_time  TEXT NOT NULL,
                    end_time    TEXT NOT NULL,
                    content     TEXT,
                    tags        TEXT DEFAULT '[]',
                    skipped     INTEGER DEFAULT 0,
                    created_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_reports (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    date         TEXT UNIQUE NOT NULL,
                    raw_entries  TEXT NOT NULL,
                    ai_summary   TEXT,
                    final_report TEXT,
                    exported_at  TEXT,
                    created_at   TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entries_date
                    ON pomodoro_entries(date);

                CREATE TABLE IF NOT EXISTS todos (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT    NOT NULL,
                    priority    INTEGER NOT NULL DEFAULT 1,
                    status      TEXT    NOT NULL DEFAULT 'pending',
                    todo_date   TEXT    NOT NULL,
                    due_date    TEXT,
                    note        TEXT    DEFAULT '',
                    sort_order  INTEGER NOT NULL DEFAULT 0,
                    pomodoro_id INTEGER,
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL,
                    FOREIGN KEY (pomodoro_id) REFERENCES pomodoro_entries(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
                CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);

                CREATE TABLE IF NOT EXISTS reminders (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT    NOT NULL,
                    remind_time TEXT    NOT NULL,
                    remind_date TEXT,
                    repeat_type TEXT    NOT NULL DEFAULT 'none',
                    repeat_days TEXT    DEFAULT '',
                    enabled     INTEGER NOT NULL DEFAULT 1,
                    snooze_min  INTEGER NOT NULL DEFAULT 10,
                    last_triggered TEXT,
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_reminders_enabled ON reminders(enabled);
            """)

            # Migration: add todo_date column if missing (added in TASK-02)
            try:
                conn.execute("ALTER TABLE todos ADD COLUMN todo_date TEXT")
            except Exception:
                pass
            # Backfill: set todo_date from created_at date for existing rows
            conn.execute(
                "UPDATE todos SET todo_date = substr(created_at, 1, 10) WHERE todo_date IS NULL"
            )
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_todo_date ON todos(todo_date)")
            except Exception:
                pass

            # Migration: add remind_date column for one-time dated reminders
            try:
                conn.execute("ALTER TABLE reminders ADD COLUMN remind_date TEXT")
            except Exception:
                pass

    def add_entry(self, date_str, session_no, start_time, end_time,
                  content, tags=None, skipped=False):
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO pomodoro_entries
                   (date, session_no, start_time, end_time, content, tags, skipped, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (date_str, session_no, start_time, end_time,
                 content, tags_json, 1 if skipped else 0, now),
            )
            return cursor.lastrowid

    def get_entries_by_date(self, date_str):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pomodoro_entries WHERE date=? ORDER BY start_time, end_time",
                (date_str,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d["tags"])
            result.append(d)
        return result

    def update_entry(self, entry_id, content, tags, start_time=None, end_time=None):
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        with self._get_conn() as conn:
            if start_time is not None and end_time is not None:
                conn.execute(
                    "UPDATE pomodoro_entries SET content=?, tags=?, start_time=?, end_time=? WHERE id=?",
                    (content, tags_json, start_time, end_time, entry_id),
                )
            else:
                conn.execute(
                    "UPDATE pomodoro_entries SET content=?, tags=? WHERE id=?",
                    (content, tags_json, entry_id),
                )

    def delete_entry(self, entry_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM pomodoro_entries WHERE id=?", (entry_id,))

    def save_report(self, date_str, raw_entries, ai_summary=None, final_report=None):
        raw_json = json.dumps(raw_entries, ensure_ascii=False)
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO daily_reports
                       (date, raw_entries, ai_summary, final_report, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                       raw_entries=excluded.raw_entries,
                       ai_summary=excluded.ai_summary,
                       final_report=excluded.final_report""",
                (date_str, raw_json, ai_summary, final_report, now),
            )

    def get_report(self, date_str):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM daily_reports WHERE date=?", (date_str,)
            ).fetchone()
        if row:
            d = dict(row)
            d["raw_entries"] = json.loads(d["raw_entries"])
            return d
        return None

    def get_all_report_dates(self):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT date FROM daily_reports ORDER BY date DESC"
            ).fetchall()
        return [row["date"] for row in rows]

    def get_today_session_count(self, date_str):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM pomodoro_entries WHERE date=? AND skipped=0",
                (date_str,),
            ).fetchone()
        return row["cnt"] if row else 0

    def get_next_session_no(self, date_str):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(session_no), 0) as max_no FROM pomodoro_entries WHERE date=?",
                (date_str,),
            ).fetchone()
        return (row["max_no"] if row else 0) + 1

    def get_latest_valid_entry_content(self, date_str):
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT content FROM pomodoro_entries
                   WHERE date=? AND skipped=0 AND content IS NOT NULL AND TRIM(content) != ''
                   ORDER BY start_time DESC, end_time DESC LIMIT 1""",
                (date_str,),
            ).fetchone()
        return row["content"] if row else ""

    def search_reports(self, keyword: str):
        kw = (keyword or "").strip()
        if not kw:
            dates = self.get_all_report_dates()
            return [self.get_report(d) for d in dates if self.get_report(d)]

        like_pattern = f"%{kw}%"
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM daily_reports
                   WHERE date LIKE ? OR final_report LIKE ? OR ai_summary LIKE ?
                   ORDER BY date DESC""",
                (like_pattern, like_pattern, like_pattern),
            ).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["raw_entries"] = json.loads(d["raw_entries"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Todo CRUD methods (TASK-02)
    # ------------------------------------------------------------------

    def add_todo(self, title, priority=1, due_date=None, note="", todo_date=None):
        now = datetime.now().isoformat()
        if todo_date is None:
            todo_date = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO todos
                   (title, priority, status, todo_date, due_date, note, sort_order, created_at, updated_at)
                   VALUES (?, ?, 'pending', ?, ?, ?, 0, ?, ?)""",
                (title, priority, todo_date, due_date, note, now, now),
            )
            return cursor.lastrowid

    def get_todos(self, date_str=None, include_done=True):
        with self._get_conn() as conn:
            if date_str:
                if include_done:
                    rows = conn.execute(
                        """SELECT * FROM todos WHERE todo_date=?
                           ORDER BY priority DESC, sort_order ASC""",
                        (date_str,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT * FROM todos WHERE todo_date=? AND status != 'done'
                           ORDER BY priority DESC, sort_order ASC""",
                        (date_str,),
                    ).fetchall()
            else:
                if include_done:
                    rows = conn.execute(
                        "SELECT * FROM todos ORDER BY priority DESC, sort_order ASC",
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT * FROM todos WHERE status != 'done'
                           ORDER BY priority DESC, sort_order ASC""",
                    ).fetchall()
        return [dict(r) for r in rows]

    def get_todo(self, todo_id):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM todos WHERE id=?", (todo_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_todo(self, todo_id, **kwargs):
        if not kwargs:
            return
        allowed = {"title", "priority", "status", "due_date", "note", "sort_order", "pomodoro_id", "todo_date"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [todo_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE todos SET {set_clause} WHERE id=?", values)

    def delete_todo(self, todo_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))

    def reorder_todos(self, ordered_ids):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            for idx, tid in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE todos SET sort_order=?, updated_at=? WHERE id=?",
                    (idx, now, tid),
                )

    def carry_over_todos(self, yesterday_str, today_str):
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM todos
                   WHERE todo_date=? AND status IN ('pending', 'in_progress')""",
                (yesterday_str,),
            ).fetchall()
            now = datetime.now().isoformat()
            count = 0
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) as mo FROM todos WHERE todo_date=?",
                (today_str,),
            ).fetchone()["mo"]
            for row in rows:
                count += 1
                max_order += 1
                conn.execute(
                    """INSERT INTO todos
                       (title, priority, status, todo_date, due_date, note, sort_order, pomodoro_id, created_at, updated_at)
                       VALUES (?, ?, 'pending', ?, ?, ?, ?, NULL, ?, ?)""",
                    (row["title"], row["priority"], today_str,
                     row["due_date"], row["note"], max_order, now, now),
                )
            return count

    # ------------------------------------------------------------------
    # Reminder CRUD methods (TASK-03)
    # ------------------------------------------------------------------

    def add_reminder(self, title, remind_time, remind_date=None,
                     repeat_type="none", repeat_days="", snooze_min=10):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO reminders
                   (title, remind_time, remind_date, repeat_type, repeat_days,
                    enabled, snooze_min, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (title, remind_time, remind_date, repeat_type, repeat_days,
                 snooze_min, now, now),
            )
            return cursor.lastrowid

    def get_enabled_reminders(self):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE enabled=1 ORDER BY remind_time",
            ).fetchall()
        return [dict(r) for r in rows]

    def get_reminder(self, reminder_id):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM reminders WHERE id=?", (reminder_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_reminders(self):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders ORDER BY remind_time",
            ).fetchall()
        return [dict(r) for r in rows]

    def update_reminder(self, reminder_id, **kwargs):
        if not kwargs:
            return
        allowed = {"title", "remind_time", "remind_date", "repeat_type",
                   "repeat_days", "enabled", "snooze_min", "last_triggered"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [reminder_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE reminders SET {set_clause} WHERE id=?", values)

    def delete_reminder(self, reminder_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))

    def mark_reminder_triggered(self, reminder_id, date_str):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE reminders SET last_triggered=?, updated_at=? WHERE id=?",
                (date_str, now, reminder_id),
            )
