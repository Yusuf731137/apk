from __future__ import annotations
from datetime import datetime, timezone
from fsrs import Card as FsrsCard, Rating as FsrsRating, Scheduler, State
from domain import Card, Rating


_RATINGS = {
    Rating.FAIL: FsrsRating.Again,
    Rating.HARD: FsrsRating.Hard,
    Rating.GOOD: FsrsRating.Good,
    Rating.EASY: FsrsRating.Easy,
}


def _scheduler() -> Scheduler:
    return Scheduler()


def _state(card: Card) -> State:
    if card.state == 0:
        return State.Learning
    return State(card.state)


def _to_fsrs(card: Card) -> FsrsCard:
    return FsrsCard(
        card_id=card.id, state=_state(card), step=card.step,
        stability=card.stability, difficulty=card.difficulty,
        due=card.due, last_review=card.last_review)


def review(card: Card, rating: Rating, now: datetime | None = None) -> tuple[dict, datetime]:
    sched = _scheduler()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    updated, _log = sched.review_card(_to_fsrs(card), _RATINGS[rating], review_datetime=now)
    values = {
        "state": int(updated.state), "step": updated.step,
        "stability": updated.stability, "difficulty": updated.difficulty,
        "due": updated.due, "last_review": updated.last_review,
        "reps": card.reps + 1,
        "lapses": card.lapses + int(_state(card) == State.Review and rating == Rating.FAIL),
        "learning_steps": card.learning_steps + int(_state(card) in (State.Learning, State.Relearning)),
    }
    return values, updated.due


def preview_intervals(card: Card, now: datetime | None = None) -> dict[str, str]:
    sched = _scheduler()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    out: dict[str, str] = {}
    for key, fsrs_r in _RATINGS.items():
        updated, _ = sched.review_card(_to_fsrs(card), fsrs_r, review_datetime=now)
        sec = max(0, int((updated.due - now).total_seconds()))
        if sec < 3600: out[key.value] = f"{max(1, sec // 60)}د"
        elif sec < 86400: out[key.value] = f"{max(1, sec // 3600)}س"
        else: out[key.value] = f"{max(1, sec // 86400)}ي"
    return out