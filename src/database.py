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
            """)

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
                "SELECT * FROM pomodoro_entries WHERE date=? ORDER BY session_no",
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
                   ORDER BY session_no DESC LIMIT 1""",
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
