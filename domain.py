from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class FieldType(str, Enum):
    TEXT = "TEXT"
    TTS = "TTS"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    HTML = "HTML"


class FieldSide(str, Enum):
    FRONT = "FRONT"
    BACK = "BACK"
    BOTH = "BOTH"


class FieldSource(str, Enum):
    MANUAL = "MANUAL"
    AI = "AI"
    IMPORTED = "IMPORTED"


class ReviewMode(str, Enum):
    FSRS = "FSRS"
    RANDOM = "RANDOM"
    CREATED = "CREATED"


class Rating(str, Enum):
    FAIL = "FAIL"
    HARD = "HARD"
    GOOD = "GOOD"
    EASY = "EASY"


class Grade(str, Enum):
    NEW = "NEW"
    F = "F"; E = "E"; D = "D"; C = "C"; B = "B"; A = "A"


@dataclass(frozen=True)
class Folder:
    id: int
    name: str
    parent_id: Optional[int]


@dataclass(frozen=True)
class Deck:
    id: int
    name: str
    description: str
    folder_id: Optional[int]
    created_at: datetime
    modified_at: datetime


@dataclass(frozen=True)
class Card:
    id: int
    deck_id: int
    front: str
    back: str
    state: int
    step: int
    stability: Optional[float]
    difficulty: Optional[float]
    due: datetime
    last_review: Optional[datetime]
    reps: int
    lapses: int
    learning_steps: int
    created_at: datetime
    modified_at: datetime
    suspended: bool = False


@dataclass(frozen=True)
class FieldDef:
    id: int
    deck_id: int
    name: str
    type: FieldType
    side: FieldSide
    language: str
    font_size: int
    tts_provider: Optional[str]
    tts_voice: Optional[str]
    tts_rate: float
    source: FieldSource
    sort_order: int


@dataclass
class CardView:
    card: Card
    deck_name: str
    values: dict[int, str] = field(default_factory=dict)
    fields: list[FieldDef] = field(default_factory=list)

    def fields_for(self, side: FieldSide) -> list[FieldDef]:
        out = []
        for f in sorted(self.fields, key=lambda x: x.sort_order):
            if f.side == side or f.side == FieldSide.BOTH:
                out.append(f)
        return out


@dataclass(frozen=True)
class ReviewLogRow:
    id: int
    card_id: int
    session_id: Optional[int]
    ts: datetime
    rating: Rating
    prev_state: Optional[int]
    new_state: Optional[int]
    prev_due: Optional[datetime]
    new_due: Optional[datetime]
    duration_ms: Optional[int]
    mode: Optional[str]


@dataclass
class SessionSummary:
    session_id: int
    reviewed: int
    duration_seconds: float
    rating_counts: dict[str, int]
    next_due: Optional[datetime]