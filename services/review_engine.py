from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from data.repos import CardRepo, ReviewRepo, SessionRepo
from domain import Card, Rating, ReviewMode
from services.fsrs_service import review as fsrs_review


def _local_day_start_utc_iso() -> str:
    now = datetime.now().astimezone()
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc).isoformat()


@dataclass
class SessionState:
    session_id: int
    mode: ReviewMode
    deck_id: Optional[int]
    is_cram: bool
    queue: list[int] = field(default_factory=list)
    index: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ratings: dict[str, int] = field(
        default_factory=lambda: {"FAIL": 0, "HARD": 0, "GOOD": 0, "EASY": 0})
    last_shown_at: Optional[datetime] = None


class ReviewEngine:
    def __init__(self, cards: CardRepo, reviews: ReviewRepo, sessions: SessionRepo):
        self.cards = cards
        self.reviews = reviews
        self.sessions = sessions

    def build_queue(self, deck_id: Optional[int], mode: ReviewMode,
                    limit: Optional[int], *,
                    daily_new: int | None = None,
                    daily_review: int | None = None) -> list[int]:
        if mode == ReviewMode.FSRS:
            cards = self.cards.due(deck_id)
        elif mode == ReviewMode.RANDOM:
            cards = self.cards.all_ordered(deck_id, by_created=False)
            random.shuffle(cards)
        else:
            cards = self.cards.all_ordered(deck_id, by_created=True)

        if daily_new is not None or daily_review is not None:
            counts = self.reviews.today_counts(_local_day_start_utc_iso())
            new_left = None if daily_new is None else max(0, daily_new - counts["new"])
            rev_left = None if daily_review is None else max(0, daily_review - counts["review"])
            filtered = []
            for c in cards:
                if c.suspended:
                    continue
                if c.reps == 0:
                    if new_left is None or new_left > 0:
                        filtered.append(c)
                        if new_left is not None:
                            new_left -= 1
                else:
                    if rev_left is None or rev_left > 0:
                        filtered.append(c)
                        if rev_left is not None:
                            rev_left -= 1
            cards = filtered

        if limit:
            cards = cards[:limit]
        return [c.id for c in cards]

    def start(self, deck_id: Optional[int], mode: ReviewMode, is_cram: bool,
              limit: Optional[int],
              daily_new: int | None = None,
              daily_review: int | None = None) -> SessionState:
        if is_cram:
            daily_new, daily_review = None, None
        q = self.build_queue(deck_id, mode, limit,
                             daily_new=daily_new, daily_review=daily_review)
        sid = self.sessions.create(deck_id, mode.value, len(q), is_cram)
        return SessionState(session_id=sid, mode=mode, deck_id=deck_id,
                            is_cram=is_cram, queue=q)

    def current(self, state: SessionState) -> Optional[Card]:
        if state.index >= len(state.queue):
            return None
        return self.cards.get(state.queue[state.index])

    def rate(self, state: SessionState, card: Card, rating: Rating,
             duration_ms: int | None = None) -> Optional[datetime]:
        was_new = card.reps == 0
        next_due: Optional[datetime] = None
        if state.is_cram:
            self.sessions.add_temp_review(state.session_id, card.id, rating)
        else:
            values, next_due = fsrs_review(card, rating)
            self.cards.save_schedule(card.id, values)
            self.reviews.log(card.id, state.session_id, rating, card.state,
                             values["state"], card.due, next_due,
                             duration_ms, state.mode.value, was_new=was_new)
        state.ratings[rating.value] += 1
        state.index += 1
        return next_due

    def finish(self, state: SessionState) -> None:
        self.sessions.finish(state.session_id, state.ratings)