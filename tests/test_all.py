from __future__ import annotations
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.database import DB
from data.repos import (
    DeckRepo, CardRepo, FieldRepo, ReviewRepo, SessionRepo, StatsRepo, SettingsRepo,
)
from domain import FieldSide, FieldType, Rating, ReviewMode
from services.fsrs_service import review as fsrs_review, preview_intervals
from services.review_engine import ReviewEngine
from services.settings import Settings


@pytest.fixture
def ctx():
    tmp = tempfile.TemporaryDirectory()
    db = DB(Path(tmp.name) / "test.sqlite3")
    yield {
        "db": db, "decks": DeckRepo(db), "cards": CardRepo(db),
        "fields": FieldRepo(db), "reviews": ReviewRepo(db),
        "sessions": SessionRepo(db), "stats": StatsRepo(db),
        "settings": Settings(SettingsRepo(db)),
    }
    tmp.cleanup()


def test_migration_creates_default_fields(ctx):
    decks = ctx["decks"].list()
    assert len(decks) == 0  # fresh DB, no default deck until created
    d = ctx["decks"].create("Test")
    fields = ctx["fields"].for_deck(d.id)
    assert [f.name for f in fields] == ["Front", "Back"]
    assert fields[0].side == FieldSide.FRONT
    assert fields[1].side == FieldSide.BACK


def test_card_create_and_view(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    cid = ctx["cards"].create(d.id, {fields[0].id: "Q", fields[1].id: "A"})
    v = ctx["cards"].view(cid)
    assert v.values[fields[0].id] == "Q"
    assert v.values[fields[1].id] == "A"
    # front/back sync
    card = ctx["cards"].get(cid)
    assert card.front == "Q"
    assert card.back == "A"


def test_field_delete_blocked_with_values(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    ctx["cards"].create(d.id, {fields[0].id: "Q"})
    with pytest.raises(ValueError):
        ctx["fields"].delete(fields[0].id)


def test_fsrs_review_persists_and_logs(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    cid = ctx["cards"].create(d.id, {fields[0].id: "Q", fields[1].id: "A"})
    card = ctx["cards"].get(cid)
    values, due = fsrs_review(card, Rating.GOOD)
    ctx["cards"].save_schedule(cid, values)
    saved = ctx["cards"].get(cid)
    assert saved.reps == 1
    assert saved.due == due


def test_preview_intervals_keys():
    import tempfile
    from data.database import DB
    from data.repos import DeckRepo, FieldRepo, CardRepo
    tmp = tempfile.TemporaryDirectory()
    db = DB(Path(tmp.name) / "t.sqlite3")
    dr, fr, cr = DeckRepo(db), FieldRepo(db), CardRepo(db)
    d = dr.create("D"); f = fr.for_deck(d.id)
    cid = cr.create(d.id, {f[0].id: "Q", f[1].id: "A"})
    prev = preview_intervals(cr.get(cid))
    assert set(prev.keys()) == {"FAIL", "HARD", "GOOD", "EASY"}
    tmp.cleanup()


def test_review_engine_fsrs_mode_updates_card(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    cid = ctx["cards"].create(d.id, {fields[0].id: "Q", fields[1].id: "A"})
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=False, limit=None)
    assert cid in state.queue
    card = ctx["cards"].get(cid)
    eng.rate(state, card, Rating.GOOD)
    saved = ctx["cards"].get(cid)
    assert saved.reps == 1


def test_review_engine_cram_does_not_change_schedule(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    cid = ctx["cards"].create(d.id, {fields[0].id: "Q", fields[1].id: "A"})
    before = ctx["cards"].get(cid)
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    state = eng.start(d.id, ReviewMode.FSRS, is_cram=True, limit=None)
    card = ctx["cards"].get(cid)
    eng.rate(state, card, Rating.GOOD)
    after = ctx["cards"].get(cid)
    assert after.reps == before.reps
    assert after.due == before.due


def test_stats_overview_and_grades(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    cid = ctx["cards"].create(d.id, {fields[0].id: "Q", fields[1].id: "A"})
    ov = ctx["stats"].overview(d.id)
    assert ov["total"] == 1 and ov["new"] == 1
    grades = ctx["stats"].grade_distribution(d.id)
    assert grades["NEW"] == 1


def test_settings_persistence(ctx):
    s = ctx["settings"]
    s.set("review.auto_pronounce_front", "false")
    assert s.get("review.auto_pronounce_front") == "false"
    # reload
    s2 = Settings(SettingsRepo(ctx["db"]))
    assert s2.get("review.auto_pronounce_front") == "false"


def test_random_and_created_modes(ctx):
    d = ctx["decks"].create("D")
    fields = ctx["fields"].for_deck(d.id)
    for i in range(3):
        ctx["cards"].create(d.id, {fields[0].id: f"Q{i}"})
    eng = ReviewEngine(ctx["cards"], ctx["reviews"], ctx["sessions"])
    rnd = eng.start(d.id, ReviewMode.RANDOM, is_cram=True, limit=None)
    created = eng.start(d.id, ReviewMode.CREATED, is_cram=True, limit=None)
    assert len(rnd.queue) == 3
    # created order should be ascending by created_at, id
    assert created.queue == sorted(created.queue)