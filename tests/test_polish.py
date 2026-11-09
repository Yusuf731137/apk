from __future__ import annotations
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from data.database import DB
from data.repos import (DeckRepo, CardRepo, FieldRepo, ReviewRepo,
                         SessionRepo, StatsRepo, SettingsRepo)
from domain import Rating, ReviewMode
from services.review_engine import ReviewEngine
from services.fsrs_service import review as fsrs_review
from services.settings import Settings
from services.backup_service import BackupService


@pytest.fixture
def ctx():
    tmp = tempfile.TemporaryDirectory()
    db = DB(Path(tmp.name) / "t.sqlite3")
    yield {
        "db": db, "tmp": tmp,
        "decks": DeckRepo(db), "cards": CardRepo(db), "fields": FieldRepo(db),
        "reviews": ReviewRepo(db), "sessions": SessionRepo(db),
        "stats": StatsRepo(db),
        "settings": Settings(SettingsRepo(db)),
    }
    tmp.cleanup()


def _seed(ctx, deck_name="D", n=1):
    d = ctx["decks"].create(deck_name)
    f = ctx["fields"].for_deck(d.id)
    ids = []
    for i in range(n):
        ids.append(ctx["cards"].create(d.id, {f[0].id: f"Q{i}", f[1].id: f"A{i}"}))
    return d, f, ids


# --- edit card preserves FSRS ---
def test_edit_card_preserves_fsrs_state(ctx):
    d, f, [cid] = _seed(ctx)
    values, due = fsrs_review(ctx["cards"].get(cid), Rating.GOOD)
    ctx["cards"].save_schedule(cid, values)
    before = ctx["cards"].get(cid)
    ctx["cards"].update_values(cid, {f[0].id: "NEW_Q", f[1].id: "NEW_A"})
    after = ctx["cards"].get(cid)
    assert after.front == "NEW_Q" and after.back == "NEW_A"
    assert after.state == before.state
    assert after.stability == before.stability
    assert after.difficulty == before.difficulty
    assert after.due == before.due
    assert after.reps == before.reps


# --- review duration ---
def test_review_duration_persisted(ctx):
    d, _, [cid] = _seed(ctx)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=False, limit=None)
    eng.rate(state, ctx["cards"].get(cid), Rating.GOOD, duration_ms=4321)
    with ctx["db"].conn() as c:
        row = c.execute(
            "SELECT duration_ms, was_new FROM review_logs WHERE card_id=? ORDER BY id DESC LIMIT 1",
            (cid,)).fetchone()
    assert row["duration_ms"] == 4321
    assert row["was_new"] == 1


def test_review_duration_negative_safe(ctx):
    d, _, [cid] = _seed(ctx)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=False, limit=None)
    eng.rate(state, ctx["cards"].get(cid), Rating.HARD, duration_ms=-500)
    with ctx["db"].conn() as c:
        row = c.execute("SELECT duration_ms FROM review_logs ORDER BY id DESC LIMIT 1").fetchone()
    assert row["duration_ms"] == 0


# --- daily limits ---
def test_daily_new_limit_enforced(ctx):
    d, _, _ = _seed(ctx, n=5)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    q = eng.build_queue(d.id, ReviewMode.FSRS, limit=None, daily_new=2, daily_review=None)
    assert len(q) == 2


def test_daily_new_limit_accounts_for_today(ctx):
    d, _, cids = _seed(ctx, n=5)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=False, limit=1)
    eng.rate(state, ctx["cards"].get(cids[0]), Rating.GOOD)
    q = eng.build_queue(d.id, ReviewMode.FSRS, limit=None, daily_new=2, daily_review=None)
    assert len(q) == 1


def test_cram_bypasses_daily_limits(ctx):
    d, _, _ = _seed(ctx, n=5)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=True, limit=None,
                      daily_new=1, daily_review=1)
    assert len(state.queue) == 5


# --- filters / sorts ---
def test_filter_new_learning_review(ctx):
    d, f, cids = _seed(ctx, n=3)
    values, _ = fsrs_review(ctx["cards"].get(cids[0]), Rating.GOOD)
    ctx["cards"].save_schedule(cids[0], values)
    assert len(ctx["cards"].list(d.id, status="new")) == 2


def test_sort_alpha_ascending(ctx):
    d, _, _ = _seed(ctx, n=3)
    cards = ctx["cards"].list(d.id, sort_by="alpha")
    fronts = [c.front for c in cards]
    assert fronts == sorted(fronts)


# --- backups ---
def test_backup_list_and_validate(ctx):
    svc = BackupService(ctx["db"].path)
    b = svc.create_safety_backup()
    assert b.exists()
    ok, err = svc.validate(b)
    assert ok, err
    listed = svc.list_backups()
    assert any(x["path"] == b for x in listed)


def test_backup_validate_rejects_garbage(tmp_path):
    bad = tmp_path / "bad.sqlite3"
    bad.write_text("not a database")
    svc = BackupService(tmp_path / "cards.sqlite3")
    ok, err = svc.validate(bad)
    assert not ok


def test_backup_restore_roundtrip(ctx):
    d, f, [cid] = _seed(ctx)
    svc = BackupService(ctx["db"].path)
    snap = svc.create_safety_backup()
    ctx["cards"].update_values(cid, {f[0].id: "CHANGED"})
    assert ctx["cards"].get(cid).front == "CHANGED"
    safety = svc.restore(snap)
    assert safety.exists()
    new_db = DB(ctx["db"].path)
    assert CardRepo(new_db).get(cid).front == "Q0"


# --- settings ---
def test_flip_duration_setting_present(ctx):
    ctx["settings"].set("review.flip_duration_ms", "240")
    assert ctx["settings"].get_int("review.flip_duration_ms") == 240


def test_settings_persistence_across_restart(ctx):
    ctx["settings"].set("review.auto_pronounce_front", "false")
    s2 = Settings(SettingsRepo(ctx["db"]))
    assert s2.get("review.auto_pronounce_front") == "false"


# --- i18n dictionary present ---
def test_i18n_arabic_dictionary():
    from core.i18n import _AR
    assert _AR["Save"] == "حفظ"
    assert _AR["Fail"] == "لم أتذكر"


# --- TTS registry ---
def test_tts_registry_has_system():
    from services.tts import TTSRegistry
    r = TTSRegistry()
    assert "system" in r.names()
    assert r.get("system").name == "system"