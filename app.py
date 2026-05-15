#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
DB_PATH = ROOT / "polyglo.sqlite3"

DEFAULT_SEED_LANGUAGES = {
    "en": {"name": "English", "minimum_level": "C1", "sort": 1},
    "id": {"name": "Indonesian", "minimum_level": "A2", "sort": 2},
    "ja": {"name": "Japanese", "minimum_level": "N4", "sort": 3},
    "de": {"name": "German", "minimum_level": "B1", "sort": 4},
    "es": {"name": "Spanish", "minimum_level": "A2", "sort": 5},
}

LEVEL_RANKS = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
    "N5": 1,
    "N4": 2,
    "N3": 3,
    "N2": 4,
    "N1": 5,
}

# Spaced-repetition interval ladder in days.
# Stage advances on each successful recall; resets to 0 on failure.
REVIEW_INTERVALS = [1, 3, 7, 21, 60, 180]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso() -> str:
    return date.today().isoformat()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vocabulary_items (
                id TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                word TEXT NOT NULL,
                reading TEXT,
                part_of_speech TEXT NOT NULL,
                level TEXT NOT NULL,
                meaning_zh TEXT NOT NULL,
                meaning_en TEXT NOT NULL,
                example_sentence TEXT NOT NULL,
                example_translation_zh TEXT NOT NULL,
                collocation TEXT,
                note TEXT,
                mnemonic TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS languages (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                minimum_level TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 100,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_lessons (
                id TEXT PRIMARY KEY,
                lesson_date TEXT NOT NULL UNIQUE,
                scheduled_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                generated_message TEXT NOT NULL DEFAULT '',
                sent_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_lesson_items (
                id TEXT PRIMARY KEY,
                lesson_id TEXT NOT NULL,
                vocabulary_item_id TEXT NOT NULL,
                language TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lesson_id) REFERENCES daily_lessons(id) ON DELETE CASCADE,
                FOREIGN KEY (vocabulary_item_id) REFERENCES vocabulary_items(id) ON DELETE RESTRICT,
                UNIQUE (lesson_id, language)
            );

            CREATE TABLE IF NOT EXISTS review_logs (
                id TEXT PRIMARY KEY,
                vocabulary_item_id TEXT NOT NULL,
                review_date TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 5),
                recall_success INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                next_review_date TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (vocabulary_item_id) REFERENCES vocabulary_items(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        defaults = {
            "daily_schedule_time": "08:00",
            "duplicate_avoidance_days": "30",
            "require_review_for_ai_words": "true",
        }
        for key, value in defaults.items():
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value, now_iso()),
            )
        migrate_languages_from_settings(conn)


def migrate_languages_from_settings(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM languages").fetchone()["count"]
    if existing:
        return
    enabled_row = conn.execute(
        "SELECT value FROM settings WHERE key = 'enabled_languages'"
    ).fetchone()
    if not enabled_row:
        return
    try:
        enabled_codes = json.loads(enabled_row["value"])
    except json.JSONDecodeError:
        enabled_codes = []
    for index, code in enumerate(enabled_codes, start=1):
        meta = DEFAULT_SEED_LANGUAGES.get(code, {})
        minimum_row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (f"minimum_level_{code}",)
        ).fetchone()
        conn.execute(
            """
            INSERT INTO languages (
                code, name, minimum_level, sort_order, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(code) DO NOTHING
            """,
            (
                code,
                meta.get("name", code),
                minimum_row["value"] if minimum_row else meta.get("minimum_level", ""),
                meta.get("sort", index),
                now_iso(),
                now_iso(),
            ),
        )


def seed_db() -> int:
    samples = [
        ("en", "ameliorate", "", "verb", "C1", "改善、改良", "to make a bad situation better", "The new policy aims to ameliorate housing pressure among young workers.", "這項新政策旨在改善年輕工作者的居住壓力。", "ameliorate a problem; ameliorate conditions", "比 improve 更正式，常用於政策、社會問題、醫療或制度脈絡。", "melior 和 better 的概念相近。"),
        ("en", "scrutinize", "", "verb", "C1", "仔細檢查", "to examine something very carefully", "The committee will scrutinize the budget before approval.", "委員會會在核准前仔細審查預算。", "scrutinize evidence; scrutinize a proposal", "常用於正式審查或分析。", "像拿放大鏡 scan 每個細節。"),
        ("id", "memperbaiki", "", "verb", "A2", "修理、改善", "to repair or improve something", "Saya ingin memperbaiki jadwal belajar saya.", "我想改善我的學習時程。", "memperbaiki rumah; memperbaiki kesalahan", "來自 baik「好」，可用於修東西或改善狀況。", "baik 是好，讓東西變好就是 memperbaiki。"),
        ("id", "walaupun", "", "conjunction", "B1", "雖然、即使", "although; even though", "Walaupun hujan, kami tetap pergi ke pasar.", "雖然下雨，我們還是去市場。", "walaupun begitu", "比 tapi 更能帶出讓步語氣。", "wala-upun 可以想成 although。"),
        ("ja", "相談", "そうだん", "noun / suru-verb", "N4", "商量、諮詢", "consultation; discussion", "先生に進路について相談しました。", "我向老師商量了升學方向。", "相談する; 相談に乗る", "工作、學校、人際關係都很常見。", "相互談話，就是相談。"),
        ("ja", "準備", "じゅんび", "noun / suru-verb", "N4", "準備", "preparation", "旅行の準備はもう終わりましたか。", "旅行的準備已經完成了嗎？", "準備する; 準備ができる", "日常高頻，名詞也可接する變動詞。", "漢字意思和中文很接近。"),
        ("de", "Voraussetzung", "", "noun, feminine", "B1", "前提、必要條件", "prerequisite; condition", "Gute Planung ist eine wichtige Voraussetzung für den Erfolg.", "良好的規劃是成功的重要前提。", "eine Voraussetzung erfüllen", "常見於學業、制度、申請、專案語境。", "voraus 有 ahead / before 的味道。"),
        ("de", "zuverlässig", "", "adjective", "B1", "可靠的", "reliable; dependable", "Unsere neue Kollegin ist sehr zuverlässig.", "我們的新同事非常可靠。", "eine zuverlässige Quelle", "描述人、資料來源、系統都可用。", "像英文 reliable，重點是可以信賴。"),
        ("es", "aunque", "", "conjunction", "A2", "雖然、即使", "although; even though", "Aunque estoy cansado, quiero estudiar un poco más.", "雖然我很累，但我還想再讀一點。", "aunque + indicativo/subjuntivo", "非常高頻，語氣不同會影響後面動詞式。", "aun 有 even 的味道。"),
        ("es", "aprovechar", "", "verb", "B1", "利用、把握", "to take advantage of; to make good use of", "Quiero aprovechar el fin de semana para descansar.", "我想把握週末休息。", "aprovechar una oportunidad", "常用於時間、機會、資源。", "把可用的東西變成 provecho。"),
    ]
    inserted = 0
    with connect() as conn:
        for code, meta in DEFAULT_SEED_LANGUAGES.items():
            conn.execute(
                """
                INSERT INTO languages (
                    code, name, minimum_level, sort_order, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(code) DO NOTHING
                """,
                (
                    code,
                    meta["name"],
                    meta["minimum_level"],
                    meta["sort"],
                    now_iso(),
                    now_iso(),
                ),
            )
        for item in samples:
            exists = conn.execute(
                "SELECT 1 FROM vocabulary_items WHERE language = ? AND word = ?",
                (item[0], item[1]),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO vocabulary_items (
                    id, language, word, reading, part_of_speech, level,
                    meaning_zh, meaning_en, example_sentence, example_translation_zh,
                    collocation, note, mnemonic, source, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', 'active', ?, ?)
                """,
                (str(uuid.uuid4()), *item, now_iso(), now_iso()),
            )
            inserted += 1
    return inserted


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings = {row["key"]: row["value"] for row in rows}
    settings["duplicate_avoidance_days"] = int(settings.get("duplicate_avoidance_days", "30"))
    return settings


def list_languages(conn: sqlite3.Connection, enabled_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE enabled = 1" if enabled_only else ""
    rows = conn.execute(
        f"""
        SELECT code, name, minimum_level, sort_order, enabled
        FROM languages
        {where}
        ORDER BY sort_order, name
        """
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def language_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {row["code"]: row for row in list_languages(conn)}


def level_allowed(level: str, minimum: str) -> bool:
    if not minimum:
        return True
    item_level = level.upper()
    minimum_level = minimum.upper()
    if item_level in LEVEL_RANKS and minimum_level in LEVEL_RANKS:
        return LEVEL_RANKS[item_level] >= LEVEL_RANKS[minimum_level]
    return item_level == minimum_level


def lesson_payload(conn: sqlite3.Connection, lesson_id: str) -> dict[str, Any] | None:
    lesson = conn.execute("SELECT * FROM daily_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        return None
    items = conn.execute(
        """
        SELECT v.*, dli.sort_order
        FROM daily_lesson_items dli
        JOIN vocabulary_items v ON v.id = dli.vocabulary_item_id
        WHERE dli.lesson_id = ?
        ORDER BY dli.sort_order
        """,
        (lesson_id,),
    ).fetchall()
    payload = row_to_dict(lesson)
    payload["items"] = [row_to_dict(row) for row in items]
    return payload


def render_lesson_markdown(
    lesson_date: str,
    items: list[sqlite3.Row | dict[str, Any]],
    languages: dict[str, dict[str, Any]],
) -> str:
    lines = ["### Daily Vocabulary", f"Date: {lesson_date}", ""]
    for index, item in enumerate(items, start=1):
        data = row_to_dict(item) if isinstance(item, sqlite3.Row) else item
        lang = languages.get(data["language"], {}).get("name", data["language"])
        heading = f"#### {index}. {lang} - {data['level']}"
        reading = f" ({data['reading']})" if data.get("reading") else ""
        lines.extend(
            [
                heading,
                f"**{data['word']}**{reading} *({data['part_of_speech']})*  ",
                f"中文：{data['meaning_zh']}  ",
                f"English: {data['meaning_en']}",
                "",
                "Example:",
                data["example_sentence"],
                data["example_translation_zh"],
                "",
                f"Usage note: {data.get('note') or data.get('collocation') or '—'}",
                f"Memory hint: {data.get('mnemonic') or '—'}",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines).strip()


def generate_lesson(lesson_date: str, force: bool = False) -> dict[str, Any]:
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_lessons WHERE lesson_date = ?", (lesson_date,)
        ).fetchone()
        if existing and not force:
            payload = lesson_payload(conn, existing["id"])
            assert payload
            return payload
        if existing and force:
            conn.execute("DELETE FROM daily_lessons WHERE id = ?", (existing["id"],))

        settings = get_settings(conn)
        enabled_languages = list_languages(conn, enabled_only=True)
        if not enabled_languages:
            raise ValueError("No enabled languages. Add one in Settings before generating a lesson.")
        languages = {row["code"]: row for row in enabled_languages}
        avoid_since = (
            datetime.fromisoformat(lesson_date).date()
            - timedelta(days=settings["duplicate_avoidance_days"])
        ).isoformat()
        selected: list[sqlite3.Row] = []

        for language in enabled_languages:
            code = language["code"]
            minimum = language["minimum_level"]

            # Priority 1: words whose next_review_date is due today (bypass duplicate window).
            due_rows = conn.execute(
                """
                SELECT v.*, rr.next_review_date,
                       (SELECT COUNT(*) FROM review_logs WHERE vocabulary_item_id = v.id) AS review_count
                FROM vocabulary_items v
                JOIN (
                    SELECT r1.vocabulary_item_id, r1.next_review_date
                    FROM review_logs r1
                    WHERE r1.created_at = (
                        SELECT MAX(r2.created_at) FROM review_logs r2
                        WHERE r2.vocabulary_item_id = r1.vocabulary_item_id
                    )
                ) rr ON rr.vocabulary_item_id = v.id
                WHERE v.language = ? AND v.status = 'active' AND rr.next_review_date <= ?
                ORDER BY rr.next_review_date ASC
                """,
                (code, lesson_date),
            ).fetchall()
            allowed_due = [row for row in due_rows if level_allowed(row["level"], minimum)]
            if allowed_due:
                selected.append(allowed_due[0])
                continue

            # Priority 2: new words not seen within the duplicate avoidance window.
            rows = conn.execute(
                """
                SELECT v.*,
                       COUNT(r.id) AS review_count,
                       MAX(dl.lesson_date) AS last_seen
                FROM vocabulary_items v
                LEFT JOIN review_logs r ON r.vocabulary_item_id = v.id
                LEFT JOIN daily_lesson_items dli ON dli.vocabulary_item_id = v.id
                LEFT JOIN daily_lessons dl ON dl.id = dli.lesson_id
                WHERE v.language = ?
                  AND v.status = 'active'
                  AND v.id NOT IN (
                    SELECT dli2.vocabulary_item_id
                    FROM daily_lesson_items dli2
                    JOIN daily_lessons dl2 ON dl2.id = dli2.lesson_id
                    WHERE dl2.lesson_date >= ? AND dl2.lesson_date < ?
                  )
                GROUP BY v.id
                ORDER BY review_count ASC, COALESCE(last_seen, '') ASC, v.created_at ASC
                """,
                (code, avoid_since, lesson_date),
            ).fetchall()
            allowed = [row for row in rows if level_allowed(row["level"], minimum)]
            if not allowed:
                level_label = f" at {minimum}+" if minimum else ""
                raise ValueError(f"No active vocabulary item found for {language['name']}{level_label}")
            selected.append(allowed[0])

        lesson_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO daily_lessons (
                id, lesson_date, scheduled_time, status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (lesson_id, lesson_date, settings["daily_schedule_time"], now_iso(), now_iso()),
        )
        for row in selected:
            conn.execute(
                """
                INSERT INTO daily_lesson_items (
                    id, lesson_id, vocabulary_item_id, language, sort_order, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    lesson_id,
                    row["id"],
                    row["language"],
                    languages.get(row["language"], {}).get("sort_order", 100),
                    now_iso(),
                ),
            )
        message = render_lesson_markdown(lesson_date, selected, languages)
        conn.execute(
            "UPDATE daily_lessons SET generated_message = ?, updated_at = ? WHERE id = ?",
            (message, now_iso(), lesson_id),
        )
        payload = lesson_payload(conn, lesson_id)
        assert payload
        return payload


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return super().do_GET()
        try:
            with connect() as conn:
                if parsed.path == "/api/bootstrap":
                    languages = language_map(conn)
                    self.send_json(
                        {
                            "settings": get_settings(conn),
                            "languages": languages,
                            "languageList": list(languages.values()),
                            "today": today_iso(),
                        }
                    )
                    return
                if parsed.path == "/api/languages":
                    self.send_json(list_languages(conn))
                    return
                if parsed.path == "/api/generation-plan":
                    self.send_json(generation_plan(conn))
                    return
                if parsed.path == "/api/dashboard":
                    self.send_json(dashboard_payload(conn))
                    return
                if parsed.path == "/api/vocabulary":
                    query = parse_qs(parsed.query)
                    self.send_json(list_vocabulary(conn, query))
                    return
                if parsed.path == "/api/lessons":
                    self.send_json(list_lessons(conn))
                    return
                if parsed.path == "/api/today":
                    lesson = conn.execute(
                        "SELECT id FROM daily_lessons WHERE lesson_date = ?", (today_iso(),)
                    ).fetchone()
                    self.send_json(lesson_payload(conn, lesson["id"]) if lesson else None)
                    return
                if parsed.path == "/api/reviews":
                    self.send_json(list_reviews(conn))
                    return
            self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/lessons/generate":
                payload = self.read_json()
                self.send_json(generate_lesson(payload.get("date") or today_iso(), bool(payload.get("force"))))
                return
            if parsed.path == "/api/vocabulary":
                self.send_json(create_vocabulary(self.read_json()), 201)
                return
            if parsed.path == "/api/vocabulary/candidates":
                self.send_json(create_vocabulary_candidates(self.read_json()), 201)
                return
            if parsed.path == "/api/languages":
                self.send_json(create_language(self.read_json()), 201)
                return
            if parsed.path == "/api/reviews":
                self.send_json(create_review(self.read_json()), 201)
                return
            if parsed.path.endswith("/mark-sent") and parsed.path.startswith("/api/lessons/"):
                lesson_id = parsed.path.split("/")[3]
                self.send_json(mark_lesson_sent(lesson_id))
                return
            self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/vocabulary/"):
                item_id = parsed.path.split("/")[3]
                self.send_json(update_vocabulary(item_id, self.read_json()))
                return
            if parsed.path.startswith("/api/languages/"):
                code = parsed.path.split("/")[3]
                self.send_json(update_language(code, self.read_json()))
                return
            self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


def dashboard_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    today_row = conn.execute(
        "SELECT id FROM daily_lessons WHERE lesson_date = ?", (today_iso(),)
    ).fetchone()
    counts = conn.execute(
        """
        SELECT language, COUNT(*) AS total,
               SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
               SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft
        FROM vocabulary_items
        GROUP BY language
        """
    ).fetchall()
    recent = conn.execute(
        """
        SELECT dl.lesson_date, v.language, v.word, v.level
        FROM daily_lesson_items dli
        JOIN daily_lessons dl ON dl.id = dli.lesson_id
        JOIN vocabulary_items v ON v.id = dli.vocabulary_item_id
        ORDER BY dl.lesson_date DESC, dli.sort_order ASC
        LIMIT 20
        """
    ).fetchall()
    return {
        "todayLesson": lesson_payload(conn, today_row["id"]) if today_row else None,
        "counts": [row_to_dict(row) for row in counts],
        "pendingReviewCount": conn.execute(
            "SELECT COUNT(*) AS count FROM vocabulary_items WHERE source = 'ai' AND status = 'draft'"
        ).fetchone()["count"],
        "recentWords": [row_to_dict(row) for row in recent],
    }


def list_vocabulary(conn: sqlite3.Connection, query: dict[str, list[str]]) -> list[dict[str, Any]]:
    filters = []
    params: list[Any] = []
    for field in ("language", "status", "level", "source"):
        value = query.get(field, [""])[0]
        if value:
            filters.append(f"{field} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"SELECT * FROM vocabulary_items {where} ORDER BY language, level, word",
        params,
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def generation_plan(conn: sqlite3.Connection) -> dict[str, Any]:
    settings = get_settings(conn)
    enabled_languages = list_languages(conn, enabled_only=True)
    existing_rows = conn.execute(
        "SELECT language, word FROM vocabulary_items ORDER BY language, word"
    ).fetchall()
    recent_rows = conn.execute(
        """
        SELECT v.language, v.word
        FROM daily_lesson_items dli
        JOIN daily_lessons dl ON dl.id = dli.lesson_id
        JOIN vocabulary_items v ON v.id = dli.vocabulary_item_id
        WHERE dl.lesson_date >= ?
        ORDER BY dl.lesson_date DESC
        """,
        (
            (date.today() - timedelta(days=settings["duplicate_avoidance_days"])).isoformat(),
        ),
    ).fetchall()
    existing_by_language: dict[str, list[str]] = {}
    for row in existing_rows:
        existing_by_language.setdefault(row["language"], []).append(row["word"])
    recent_by_language: dict[str, list[str]] = {}
    for row in recent_rows:
        recent_by_language.setdefault(row["language"], []).append(row["word"])
    return {
        "date": today_iso(),
        "duplicate_avoidance_days": settings["duplicate_avoidance_days"],
        "candidate_defaults": {"source": "ai", "status": "draft"},
        "languages": enabled_languages,
        "existing_words": existing_by_language,
        "recent_lesson_words": recent_by_language,
        "required_fields": [
            "language",
            "word",
            "part_of_speech",
            "level",
            "meaning_zh",
            "meaning_en",
            "example_sentence",
            "example_translation_zh",
        ],
    }


def create_language(payload: dict[str, Any]) -> dict[str, Any]:
    code = (payload.get("code") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    if not code or not name:
        raise ValueError("Language code and name are required")
    with connect() as conn:
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM languages"
        ).fetchone()["max_sort"]
        conn.execute(
            """
            INSERT INTO languages (
                code, name, minimum_level, sort_order, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                code,
                name,
                payload.get("minimum_level", "").strip(),
                int(payload.get("sort_order") or max_sort + 1),
                1 if payload.get("enabled", True) else 0,
                now_iso(),
                now_iso(),
            ),
        )
        row = conn.execute(
            "SELECT code, name, minimum_level, sort_order, enabled FROM languages WHERE code = ?",
            (code,),
        ).fetchone()
        return row_to_dict(row)


def update_language(code: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"name", "minimum_level", "sort_order", "enabled"}
    fields = [key for key in payload if key in allowed]
    if not fields:
        raise ValueError("No valid fields supplied")
    values: list[Any] = []
    assignments = []
    for field in fields:
        assignments.append(f"{field} = ?")
        if field == "enabled":
            values.append(1 if payload[field] else 0)
        elif field == "sort_order":
            values.append(int(payload[field]))
        else:
            values.append(str(payload[field]).strip())
    with connect() as conn:
        conn.execute(
            f"UPDATE languages SET {', '.join(assignments)}, updated_at = ? WHERE code = ?",
            (*values, now_iso(), code),
        )
        row = conn.execute(
            "SELECT code, name, minimum_level, sort_order, enabled FROM languages WHERE code = ?",
            (code,),
        ).fetchone()
        if not row:
            raise ValueError("Language not found")
        return row_to_dict(row)


def list_lessons(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id FROM daily_lessons ORDER BY lesson_date DESC LIMIT 30"
    ).fetchall()
    return [lesson_payload(conn, row["id"]) for row in rows if lesson_payload(conn, row["id"])]


def list_reviews(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, v.word, v.language, v.level
        FROM review_logs r
        JOIN vocabulary_items v ON v.id = r.vocabulary_item_id
        ORDER BY r.review_date DESC, r.created_at DESC
        LIMIT 50
        """
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def create_vocabulary(payload: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        return insert_vocabulary(conn, payload)


def insert_vocabulary(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    required = [
        "language",
        "word",
        "part_of_speech",
        "level",
        "meaning_zh",
        "meaning_en",
        "example_sentence",
        "example_translation_zh",
    ]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    language = conn.execute(
        "SELECT 1 FROM languages WHERE code = ?", (payload["language"],)
    ).fetchone()
    if not language:
        raise ValueError(f"Language is not configured: {payload['language']}")
    item_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO vocabulary_items (
            id, language, word, reading, part_of_speech, level,
            meaning_zh, meaning_en, example_sentence, example_translation_zh,
            collocation, note, mnemonic, source, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            payload["language"],
            payload["word"],
            payload.get("reading", ""),
            payload["part_of_speech"],
            payload["level"],
            payload["meaning_zh"],
            payload["meaning_en"],
            payload["example_sentence"],
            payload["example_translation_zh"],
            payload.get("collocation", ""),
            payload.get("note", ""),
            payload.get("mnemonic", ""),
            payload.get("source", "manual"),
            payload.get("status", "draft"),
            now_iso(),
            now_iso(),
        ),
    )
    row = conn.execute("SELECT * FROM vocabulary_items WHERE id = ?", (item_id,)).fetchone()
    return row_to_dict(row)


def create_vocabulary_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    created = []
    skipped = []
    with connect() as conn:
        settings = get_settings(conn)
        require_review = settings.get("require_review_for_ai_words", "true") == "true"
        auto_status = "draft" if require_review else "active"
        for item in items:
            if not isinstance(item, dict):
                skipped.append({"reason": "Item is not an object", "item": item})
                continue
            candidate = {
                **item,
                "source": item.get("source", "ai"),
                "status": item.get("status", auto_status),
            }
            duplicate = conn.execute(
                """
                SELECT id, status, source
                FROM vocabulary_items
                WHERE language = ? AND lower(word) = lower(?)
                """,
                (candidate.get("language"), candidate.get("word", "")),
            ).fetchone()
            if duplicate:
                skipped.append(
                    {
                        "language": candidate.get("language"),
                        "word": candidate.get("word"),
                        "reason": "Duplicate vocabulary item",
                        "existing_id": duplicate["id"],
                    }
                )
                continue
            try:
                created.append(insert_vocabulary(conn, candidate))
            except ValueError as exc:
                skipped.append(
                    {
                        "language": candidate.get("language"),
                        "word": candidate.get("word"),
                        "reason": str(exc),
                    }
                )
    return {"created": created, "skipped": skipped}


def update_vocabulary(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "language",
        "word",
        "reading",
        "part_of_speech",
        "level",
        "meaning_zh",
        "meaning_en",
        "example_sentence",
        "example_translation_zh",
        "collocation",
        "note",
        "mnemonic",
        "source",
        "status",
    }
    fields = [key for key in payload if key in allowed]
    if not fields:
        raise ValueError("No valid fields supplied")
    assignments = ", ".join(f"{field} = ?" for field in fields)
    values = [payload[field] for field in fields]
    with connect() as conn:
        conn.execute(
            f"UPDATE vocabulary_items SET {assignments}, updated_at = ? WHERE id = ?",
            (*values, now_iso(), item_id),
        )
        row = conn.execute("SELECT * FROM vocabulary_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise ValueError("Vocabulary item not found")
        return row_to_dict(row)


def _compute_next_review(
    conn: sqlite3.Connection,
    item_id: str,
    recall_success: bool,
    review_date: str,
) -> str:
    if not recall_success:
        days = REVIEW_INTERVALS[0]
    else:
        past_successes = conn.execute(
            "SELECT COUNT(*) AS count FROM review_logs WHERE vocabulary_item_id = ? AND recall_success = 1",
            (item_id,),
        ).fetchone()["count"]
        stage = min(past_successes, len(REVIEW_INTERVALS) - 1)
        days = REVIEW_INTERVALS[stage]
    base = datetime.fromisoformat(review_date).date()
    return (base + timedelta(days=days)).isoformat()


def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    item_id = payload.get("vocabulary_item_id")
    if not item_id:
        raise ValueError("vocabulary_item_id is required")
    rating = int(payload.get("rating", 0))
    if rating < 0 or rating > 5:
        raise ValueError("rating must be between 0 and 5")
    recall_success = bool(payload.get("recall_success"))
    review_date = payload.get("review_date") or today_iso()
    next_review = payload.get("next_review_date")
    review_id = str(uuid.uuid4())
    with connect() as conn:
        if not next_review:
            next_review = _compute_next_review(conn, item_id, recall_success, review_date)
        conn.execute(
            """
            INSERT INTO review_logs (
                id, vocabulary_item_id, review_date, rating,
                recall_success, note, next_review_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                item_id,
                review_date,
                rating,
                1 if recall_success else 0,
                payload.get("note", ""),
                next_review,
                now_iso(),
            ),
        )
        row = conn.execute("SELECT * FROM review_logs WHERE id = ?", (review_id,)).fetchone()
        return row_to_dict(row)


def mark_lesson_sent(lesson_id: str) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            UPDATE daily_lessons
            SET status = 'sent', sent_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), now_iso(), lesson_id),
        )
        payload = lesson_payload(conn, lesson_id)
        if not payload:
            raise ValueError("Lesson not found")
        return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Polyglo local vocabulary scheduler.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed", action="store_true", help="Seed sample vocabulary before starting.")
    args = parser.parse_args()

    init_db()
    if args.seed:
        inserted = seed_db()
        print(f"Seeded {inserted} vocabulary items.")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Polyglo is running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
