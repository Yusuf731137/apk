from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from domain import (
    Card, CardView, Deck, FieldDef, FieldSide, FieldSource, FieldType,
    Folder, Rating, ReviewLogRow,
)
from data.database import DB


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _folder(r) -> Folder:
    return Folder(r["id"], r["name"], r["parent_id"])


def _deck(r) -> Deck:
    return Deck(r["id"], r["name"], r["description"], r["folder_id"],
                _dt(r["created_at"]) or datetime.now(timezone.utc),
                _dt(r["modified_at"]) or datetime.now(timezone.utc))


def _card(r) -> Card:
    keys = r.keys()
    return Card(
        id=r["id"], deck_id=r["deck_id"], front=r["front"], back=r["back"],
        state=r["state"], step=r["step"], stability=r["stability"], difficulty=r["difficulty"],
        due=_dt(r["due"]) or datetime.now(timezone.utc), last_review=_dt(r["last_review"]),
        reps=r["reps"], lapses=r["lapses"], learning_steps=r["learning_steps"],
        created_at=_dt(r["created_at"]) or datetime.now(timezone.utc),
        modified_at=_dt(r["modified_at"]) or datetime.now(timezone.utc),
        suspended=bool(r["suspended"]) if "suspended" in keys else False)


def _field(r) -> FieldDef:
    return FieldDef(
        id=r["id"], deck_id=r["deck_id"], name=r["name"], type=FieldType(r["type"]),
        side=FieldSide(r["side"]), language=r["language"], font_size=r["font_size"],
        tts_provider=r["tts_provider"], tts_voice=r["tts_voice"],
        tts_rate=r["tts_rate"] or 1.0, source=FieldSource(r["source"]),
        sort_order=r["sort_order"])


class FolderRepo:
    def __init__(self, db: DB): self.db = db
    def list(self) -> list[Folder]:
        with self.db.conn() as c:
            return [_folder(r) for r in c.execute("SELECT * FROM folders ORDER BY name")]
    def create(self, name: str, parent_id: Optional[int] = None) -> Folder:
        with self.db.conn() as c:
            cur = c.execute("INSERT INTO folders(name, parent_id, created_at) VALUES (?,?,?)",
                            (name.strip(), parent_id, _now()))
            return _folder(c.execute("SELECT * FROM folders WHERE id=?", (cur.lastrowid,)).fetchone())
    def delete(self, folder_id: int) -> None:
        with self.db.conn() as c:
            c.execute("DELETE FROM folders WHERE id=?", (folder_id,))


class DeckRepo:
    def __init__(self, db: DB): self.db = db
    def list(self) -> list[Deck]:
        with self.db.conn() as c:
            return [_deck(r) for r in c.execute("SELECT * FROM decks ORDER BY name COLLATE NOCASE")]
    def get(self, deck_id: int) -> Optional[Deck]:
        with self.db.conn() as c:
            r = c.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone()
            return _deck(r) if r else None
    def create(self, name: str, description: str = "", folder_id: Optional[int] = None) -> Deck:
        name = name.strip()
        if not name:
            raise ValueError("اسم المجموعة مطلوب.")
        now = _now()
        with self.db.conn() as c:
            cur = c.execute(
                "INSERT INTO decks(name, description, folder_id, created_at, modified_at) VALUES (?,?,?,?,?)",
                (name, description.strip(), folder_id, now, now))
            deck_id = cur.lastrowid
            for fname, side, order in (("Front", "FRONT", 0), ("Back", "BACK", 1)):
                c.execute(
                    """INSERT INTO fields(deck_id, name, type, side, sort_order, created_at, modified_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (deck_id, fname, "TEXT", side, order, now, now))
            return _deck(c.execute("SELECT * FROM decks WHERE id=?", (deck_id,)).fetchone())
    def update(self, deck_id: int, name: str, description: str, folder_id: Optional[int]) -> None:
        with self.db.conn() as c:
            c.execute("UPDATE decks SET name=?, description=?, folder_id=?, modified_at=? WHERE id=?",
                      (name.strip(), description.strip(), folder_id, _now(), deck_id))
    def delete(self, deck_id: int) -> None:
        with self.db.conn() as c:
            count = c.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
            if count <= 1:
                raise ValueError("يجب الإبقاء على مجموعة واحدة على الأقل.")
            c.execute("DELETE FROM decks WHERE id=?", (deck_id,))


class FieldRepo:
    def __init__(self, db: DB): self.db = db
    def for_deck(self, deck_id: int) -> list[FieldDef]:
        with self.db.conn() as c:
            return [_field(r) for r in
                    c.execute("SELECT * FROM fields WHERE deck_id=? ORDER BY sort_order", (deck_id,))]
    def get(self, field_id: int) -> Optional[FieldDef]:
        with self.db.conn() as c:
            r = c.execute("SELECT * FROM fields WHERE id=?", (field_id,)).fetchone()
            return _field(r) if r else None
    def create(self, deck_id: int, name: str, ftype: FieldType, side: FieldSide,
               language: str = "", font_size: int = 16, sort_order: int = 0,
               tts_provider: Optional[str] = None, tts_voice: Optional[str] = None,
               tts_rate: float = 1.0, source: FieldSource = FieldSource.MANUAL) -> FieldDef:
        now = _now()
        with self.db.conn() as c:
            cur = c.execute(
                """INSERT INTO fields(deck_id, name, type, side, language, font_size,
                   tts_provider, tts_voice, tts_rate, source, sort_order, created_at, modified_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (deck_id, name.strip(), ftype.value, side.value, language, font_size,
                 tts_provider, tts_voice, tts_rate, source.value, sort_order, now, now))
            return _field(c.execute("SELECT * FROM fields WHERE id=?", (cur.lastrowid,)).fetchone())
    def update(self, field_id: int, **changes) -> None:
        allowed = {"name", "type", "side", "language", "font_size", "tts_provider",
                   "tts_voice", "tts_rate", "source", "sort_order"}
        parts, values = [], []
        for k, v in changes.items():
            if k not in allowed:
                continue
            if k in {"type", "side", "source"} and hasattr(v, "value"):
                v = v.value
            parts.append(f"{k}=?")
            values.append(v)
        if not parts:
            return
        parts.append("modified_at=?")
        values.append(_now())
        values.append(field_id)
        with self.db.conn() as c:
            c.execute(f"UPDATE fields SET {', '.join(parts)} WHERE id=?", values)
    def delete(self, field_id: int) -> None:
        with self.db.conn() as c:
            used = c.execute("SELECT COUNT(*) FROM card_field_values WHERE field_id=?",
                             (field_id,)).fetchone()[0]
            if used:
                raise ValueError("لا يمكن حذف حقل يحتوي على بيانات. احذف القيم أولًا.")
            c.execute("DELETE FROM fields WHERE id=?", (field_id,))
    def reorder(self, deck_id: int, ordered_ids: list[int]) -> None:
        with self.db.conn() as c:
            for order, fid in enumerate(ordered_ids):
                c.execute("UPDATE fields SET sort_order=? WHERE id=? AND deck_id=?",
                          (order, fid, deck_id))


class CardRepo:
    def __init__(self, db: DB): self.db = db

    def list(self, deck_id: int | None = None, status: str | None = None,
             sort_by: str | None = None, descending: bool = False) -> list[Card]:
        conds, params = [], []
        if deck_id is not None:
            conds.append("deck_id = ?"); params.append(deck_id)
        if status == "new":
            conds.append("reps = 0 AND suspended = 0")
        elif status == "learning":
            conds.append("state IN (1, 3) AND suspended = 0")
        elif status == "review":
            conds.append("state = 2 AND reps > 0 AND suspended = 0")
        elif status == "due":
            conds.append("due <= ? AND suspended = 0"); params.append(_now())
        elif status == "suspended":
            conds.append("suspended = 1")
        q = "SELECT * FROM cards"
        if conds:
            q += " WHERE " + " AND ".join(conds)
        direction = "DESC" if descending else "ASC"
        col_map = {"created": "created_at", "alpha": "front", "due": "due",
                   "difficulty": "difficulty", "stability": "stability"}
        if sort_by == "last_review":
            q += f" ORDER BY (last_review IS NULL), last_review {direction}, id {direction}"
        else:
            col = col_map.get(sort_by or "created", "created_at")
            q += f" ORDER BY {col} {direction}, id {direction}"
        with self.db.conn() as c:
            return [_card(r) for r in c.execute(q, params)]

    def get(self, card_id: int) -> Optional[Card]:
        with self.db.conn() as c:
            r = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
            return _card(r) if r else None

    def create(self, deck_id: int, values: dict[int, str]) -> int:
        if not values:
            raise ValueError("يجب تعبئة حقل واحد على الأقل.")
        now = _now()
        with self.db.conn() as c:
            primary = next(iter(values.values()))
            secondary = list(values.values())[1] if len(values) > 1 else ""
            cur = c.execute(
                """INSERT INTO cards(deck_id, front, back, due, created_at, modified_at)
                   VALUES (?,?,?,?,?,?)""",
                (deck_id, primary, secondary, now, now, now))
            card_id = cur.lastrowid
            for fid, val in values.items():
                c.execute("""INSERT INTO card_field_values(card_id, field_id, value, updated_at)
                             VALUES (?,?,?,?)""", (card_id, fid, val, now))
            return card_id

    def update_values(self, card_id: int, values: dict[int, str]) -> None:
        now = _now()
        with self.db.conn() as c:
            card = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
            if not card:
                raise ValueError("البطاقة غير موجودة.")
            for fid, val in values.items():
                c.execute("""INSERT INTO card_field_values(card_id, field_id, value, updated_at)
                             VALUES (?,?,?,?)
                             ON CONFLICT(card_id, field_id) DO UPDATE SET
                             value=excluded.value, updated_at=excluded.updated_at""",
                          (card_id, fid, val, now))
            first, second = self._front_back_values(c, card_id, card["deck_id"])
            c.execute("UPDATE cards SET front=?, back=?, modified_at=? WHERE id=?",
                      (first, second, now, card_id))

    def delete(self, card_id: int) -> None:
        with self.db.conn() as c:
            c.execute("DELETE FROM cards WHERE id=?", (card_id,))

    def view(self, card_id: int) -> Optional[CardView]:
        with self.db.conn() as c:
            r = c.execute(
                """SELECT cards.*, decks.name AS deck_name FROM cards
                   JOIN decks ON decks.id = cards.deck_id WHERE cards.id=?""",
                (card_id,)).fetchone()
            if not r:
                return None
            fields = [_field(fr) for fr in c.execute(
                "SELECT * FROM fields WHERE deck_id=? ORDER BY sort_order", (r["deck_id"],))]
            vals = {vr["field_id"]: vr["value"] for vr in c.execute(
                "SELECT field_id, value FROM card_field_values WHERE card_id=?", (card_id,))}
            return CardView(card=_card(r), deck_name=r["deck_name"], values=vals, fields=fields)

    def due(self, deck_id: Optional[int] = None, now: Optional[datetime] = None) -> list[Card]:
        now = (now or datetime.now(timezone.utc)).isoformat()
        q = "SELECT * FROM cards WHERE due <= ? AND suspended = 0"
        params: tuple = (now,)
        if deck_id is not None:
            q += " AND deck_id=?"
            params += (deck_id,)
        q += " ORDER BY state ASC, due ASC, id ASC"
        with self.db.conn() as c:
            return [_card(r) for r in c.execute(q, params)]

    def all_ordered(self, deck_id: Optional[int], by_created: bool) -> list[Card]:
        q = "SELECT * FROM cards WHERE suspended = 0"
        params: tuple = ()
        if deck_id is not None:
            q += " AND deck_id=?"
            params = (deck_id,)
        q += " ORDER BY created_at ASC, id ASC" if by_created else " ORDER BY id ASC"
        with self.db.conn() as c:
            return [_card(r) for r in c.execute(q, params)]

    def save_schedule(self, card_id: int, values: dict) -> None:
        due = values["due"].isoformat() if hasattr(values["due"], "isoformat") else values["due"]
        lr = values["last_review"]
        lr = lr.isoformat() if hasattr(lr, "isoformat") else lr
        with self.db.conn() as c:
            c.execute(
                """UPDATE cards SET state=?, step=?, stability=?, difficulty=?, due=?,
                   last_review=?, reps=?, lapses=?, learning_steps=?, modified_at=? WHERE id=?""",
                (values["state"], values["step"], values["stability"], values["difficulty"],
                 due, lr, values["reps"], values["lapses"], values["learning_steps"],
                 _now(), card_id))

    @staticmethod
    def _front_back_values(c: sqlite3.Connection, card_id: int, deck_id: int) -> tuple[str, str]:
        rows = c.execute(
            """SELECT f.id, f.side, f.sort_order, cfv.value FROM fields f
               LEFT JOIN card_field_values cfv ON cfv.field_id=f.id AND cfv.card_id=?
               WHERE f.deck_id=? ORDER BY f.sort_order""",
            (card_id, deck_id)).fetchall()
        front = next((r["value"] for r in rows if r["side"] in ("FRONT", "BOTH") and r["value"]), "")
        back = next((r["value"] for r in rows if r["side"] in ("BACK", "BOTH") and r["value"]), "")
        return front, back


class ReviewRepo:
    def __init__(self, db: DB): self.db = db

    def log(self, card_id, session_id, rating, prev_state, new_state,
            prev_due, new_due, duration_ms=None, mode=None, was_new: bool = False):
        dur = None
        if duration_ms is not None:
            try:
                dur = max(0, min(int(duration_ms), 3_600_000))
            except (TypeError, ValueError):
                dur = None
        with self.db.conn() as c:
            c.execute(
                """INSERT INTO review_logs(card_id, session_id, ts, rating,
                   prev_state, new_state, prev_due, new_due, duration_ms, mode, was_new)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (card_id, session_id, _now(), rating.value, prev_state, new_state,
                 prev_due.isoformat() if prev_due else None,
                 new_due.isoformat() if new_due else None, dur, mode, int(was_new)))

    def today_counts(self, since_iso: str) -> dict[str, int]:
        with self.db.conn() as c:
            new = c.execute(
                "SELECT COUNT(*) FROM review_logs WHERE ts >= ? AND was_new=1",
                (since_iso,)).fetchone()[0]
            review = c.execute(
                "SELECT COUNT(*) FROM review_logs WHERE ts >= ? AND was_new=0",
                (since_iso,)).fetchone()[0]
        return {"new": new, "review": review}


class SessionRepo:
    def __init__(self, db: DB): self.db = db
    def create(self, deck_id: Optional[int], mode: str, card_count: int, is_cram: bool) -> int:
        with self.db.conn() as c:
            cur = c.execute(
                "INSERT INTO review_sessions(deck_id, mode, started_at, card_count, is_cram) VALUES (?,?,?,?,?)",
                (deck_id, mode, _now(), card_count, int(is_cram)))
            return cur.lastrowid
    def finish(self, session_id: int, ratings: dict[str, int]) -> None:
        with self.db.conn() as c:
            c.execute("UPDATE review_sessions SET ended_at=?, ratings_json=? WHERE id=?",
                      (_now(), json.dumps(ratings), session_id))
    def add_temp_review(self, session_id: int, card_id: int, rating: Rating) -> None:
        with self.db.conn() as c:
            c.execute("INSERT INTO temporary_session_reviews(session_id, card_id, rating, ts) VALUES (?,?,?,?)",
                      (session_id, card_id, rating.value, _now()))


class AudioCacheRepo:
    def __init__(self, db: DB): self.db = db
    def get(self, key: str):
        with self.db.conn() as c:
            return c.execute("SELECT * FROM audio_cache WHERE key=?", (key,)).fetchone()
    def put(self, key: str, path: str, text: str, lang: str, provider: str,
            voice: str, params: dict, size: int) -> None:
        with self.db.conn() as c:
            c.execute("""INSERT OR REPLACE INTO audio_cache(key, file_path, text, lang, provider, voice,
                        params_json, size_bytes, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                      (key, path, text, lang, provider, voice, json.dumps(params), size, _now()))
    def all_rows(self):
        with self.db.conn() as c:
            return c.execute("SELECT * FROM audio_cache").fetchall()
    def remove(self, key: str) -> None:
        with self.db.conn() as c:
            c.execute("DELETE FROM audio_cache WHERE key=?", (key,))


class SettingsRepo:
    def __init__(self, db: DB): self.db = db
    def get(self, key: str) -> Optional[str]:
        with self.db.conn() as c:
            r = c.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else None
    def set(self, key: str, value: str) -> None:
        with self.db.conn() as c:
            c.execute("""INSERT INTO app_settings(key, value) VALUES (?,?)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value))
    def all(self) -> dict[str, str]:
        with self.db.conn() as c:
            return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM app_settings")}


class StatsRepo:
    def __init__(self, db: DB): self.db = db

    def overview(self, deck_id: Optional[int] = None) -> dict:
        now = _now()
        with self.db.conn() as c:
            if deck_id is None:
                total = c.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
                new = c.execute("SELECT COUNT(*) FROM cards WHERE reps=0").fetchone()[0]
                due = c.execute("SELECT COUNT(*) FROM cards WHERE due <= ? AND suspended=0", (now,)).fetchone()[0]
            else:
                total = c.execute("SELECT COUNT(*) FROM cards WHERE deck_id=?", (deck_id,)).fetchone()[0]
                new = c.execute("SELECT COUNT(*) FROM cards WHERE deck_id=? AND reps=0", (deck_id,)).fetchone()[0]
                due = c.execute("SELECT COUNT(*) FROM cards WHERE deck_id=? AND due <= ? AND suspended=0",
                                (deck_id, now)).fetchone()[0]
        return {"total": total, "new": new, "due": due}

    def grade_distribution(self, deck_id: Optional[int] = None) -> dict[str, int]:
        with self.db.conn() as c:
            q = "SELECT state, reps, lapses, stability FROM cards"
            params: tuple = ()
            if deck_id is not None:
                q += " WHERE deck_id=?"
                params = (deck_id,)
            rows = c.execute(q, params).fetchall()
        out = {"NEW": 0, "F": 0, "E": 0, "D": 0, "C": 0, "B": 0, "A": 0}
        for r in rows:
            if r["reps"] == 0:
                out["NEW"] += 1; continue
            if r["state"] in (1, 3) or (r["lapses"] > 0 and (r["stability"] or 0) < 0.5):
                out["F"] += 1; continue
            s = r["stability"] or 0
            if s < 1: out["E"] += 1
            elif s < 3: out["D"] += 1
            elif s < 7: out["C"] += 1
            elif s < 21: out["B"] += 1
            else: out["A"] += 1
        return out

    def reviews_in_range(self, days: int, deck_id: Optional[int] = None) -> list[tuple[str, int]]:
        with self.db.conn() as c:
            if deck_id is not None:
                rows = c.execute(
                    """SELECT substr(ts,1,10) as d, COUNT(*) n FROM review_logs rl
                       JOIN cards c ON c.id=rl.card_id
                       WHERE date(rl.ts) >= date('now', ?) AND c.deck_id=?
                       GROUP BY d ORDER BY d""",
                    (f"-{days} days", deck_id)).fetchall()
            else:
                rows = c.execute(
                    """SELECT substr(ts,1,10) as d, COUNT(*) n FROM review_logs
                       WHERE date(ts) >= date('now', ?)
                       GROUP BY d ORDER BY d""",
                    (f"-{days} days",)).fetchall()
        return [(r["d"], r["n"]) for r in rows]

    def rating_counts(self, deck_id: Optional[int] = None) -> dict[str, int]:
        with self.db.conn() as c:
            if deck_id is not None:
                rows = c.execute(
                    """SELECT rating, COUNT(*) n FROM review_logs rl
                       JOIN cards c ON c.id=rl.card_id WHERE c.deck_id=? GROUP BY rating""",
                    (deck_id,)).fetchall()
            else:
                rows = c.execute("SELECT rating, COUNT(*) n FROM review_logs GROUP BY rating").fetchall()
        base = {"FAIL": 0, "HARD": 0, "GOOD": 0, "EASY": 0}
        for r in rows:
            base[r["rating"]] = r["n"]
        return base