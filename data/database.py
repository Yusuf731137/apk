from __future__ import annotations
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 3


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


def _backup(db_path: Path) -> Path:
    bak = db_path.with_suffix(f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}.sqlite3")
    shutil.copy2(db_path, bak)
    return bak


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        if existed:
            _backup(self.path)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                self._bootstrap(conn)
        finally:
            conn.close()

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            with c:
                yield c
        finally:
            c.close()

    def _bootstrap(self, conn: sqlite3.Connection) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS decks(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS cards(
            id INTEGER PRIMARY KEY, deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            front TEXT NOT NULL, back TEXT NOT NULL,
            state INTEGER NOT NULL DEFAULT 1, step INTEGER NOT NULL DEFAULT 0,
            stability REAL, difficulty REAL, due TEXT NOT NULL, last_review TEXT,
            reps INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0,
            learning_steps INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS cards_due_idx ON cards(deck_id, due)")
        conn.execute("UPDATE cards SET state=1, step=0 WHERE state=0")

        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        version = row["version"] if row else 0
        if version < 1:
            version = 1
        if version < 2:
            self._migrate_v2(conn)
            version = 2
        if version < 3:
            self._migrate_v3(conn)
            version = 3
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))

    def _migrate_v2(self, conn: sqlite3.Connection) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS folders(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            parent_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL)""")
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(decks)")}
        if "folder_id" not in cols:
            conn.execute("ALTER TABLE decks ADD COLUMN folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL")
        if "modified_at" not in cols:
            conn.execute("ALTER TABLE decks ADD COLUMN modified_at TEXT")
        conn.execute("UPDATE decks SET modified_at = created_at WHERE modified_at IS NULL")
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(cards)")}
        if "modified_at" not in cols:
            conn.execute("ALTER TABLE cards ADD COLUMN modified_at TEXT")
        conn.execute("UPDATE cards SET modified_at = created_at WHERE modified_at IS NULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS fields(
            id INTEGER PRIMARY KEY, deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'TEXT',
            side TEXT NOT NULL DEFAULT 'FRONT', language TEXT NOT NULL DEFAULT '',
            font_size INTEGER NOT NULL DEFAULT 16,
            tts_provider TEXT, tts_voice TEXT, tts_rate REAL DEFAULT 1.0,
            source TEXT NOT NULL DEFAULT 'MANUAL',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, modified_at TEXT,
            UNIQUE(deck_id, name COLLATE NOCASE))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS card_field_values(
            card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE RESTRICT,
            value TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
            PRIMARY KEY(card_id, field_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS review_logs(
            id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            session_id INTEGER, ts TEXT NOT NULL, rating TEXT NOT NULL,
            prev_state INTEGER, new_state INTEGER, prev_due TEXT, new_due TEXT,
            duration_ms INTEGER, mode TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_logs_card ON review_logs(card_id, ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_logs_ts ON review_logs(ts)")
        conn.execute("""CREATE TABLE IF NOT EXISTS review_sessions(
            id INTEGER PRIMARY KEY, deck_id INTEGER REFERENCES decks(id) ON DELETE SET NULL,
            mode TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
            card_count INTEGER NOT NULL DEFAULT 0, is_cram INTEGER NOT NULL DEFAULT 0,
            ratings_json TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS temporary_session_reviews(
            id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
            card_id INTEGER NOT NULL, rating TEXT NOT NULL, ts TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS audio_cache(
            key TEXT PRIMARY KEY, file_path TEXT NOT NULL, text TEXT NOT NULL,
            lang TEXT, provider TEXT, voice TEXT, params_json TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS app_settings(
            key TEXT PRIMARY KEY, value TEXT NOT NULL)""")

        now = _utcnow()
        for deck in conn.execute("SELECT id FROM decks").fetchall():
            existing = conn.execute("SELECT COUNT(*) c FROM fields WHERE deck_id=?",
                                    (deck["id"],)).fetchone()["c"]
            if existing:
                continue
            ids = {}
            for name, side, order in (("Front", "FRONT", 0), ("Back", "BACK", 1)):
                cur = conn.execute(
                    """INSERT INTO fields(deck_id, name, type, side, sort_order, created_at, modified_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (deck["id"], name, "TEXT", side, order, now, now))
                ids[side] = cur.lastrowid
            for c in conn.execute("SELECT id, front, back FROM cards WHERE deck_id=?",
                                  (deck["id"],)).fetchall():
                conn.execute("""INSERT OR REPLACE INTO card_field_values(card_id, field_id, value, updated_at)
                                VALUES (?,?,?,?)""", (c["id"], ids["FRONT"], c["front"], now))
                conn.execute("""INSERT OR REPLACE INTO card_field_values(card_id, field_id, value, updated_at)
                                VALUES (?,?,?,?)""", (c["id"], ids["BACK"], c["back"], now))

    def _migrate_v3(self, conn: sqlite3.Connection) -> None:
        def _ensure(table: str, col: str, ddl: str) -> None:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD {ddl}")

        _ensure("review_logs", "was_new", "was_new INTEGER NOT NULL DEFAULT 0")
        _ensure("cards", "suspended", "suspended INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_logs_was_new_ts ON review_logs(was_new, ts)")