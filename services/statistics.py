from __future__ import annotations
from typing import Optional
from data.repos import StatsRepo


class Statistics:
    def __init__(self, repo: StatsRepo): self.repo = repo
    def overview(self, deck_id: Optional[int] = None): return self.repo.overview(deck_id)
    def grades(self, deck_id: Optional[int] = None): return self.repo.grade_distribution(deck_id)
    def trend(self, days: int = 30, deck_id: Optional[int] = None):
        return self.repo.reviews_in_range(days, deck_id)
    def ratings(self, deck_id: Optional[int] = None):
        return self.repo.rating_counts(deck_id)