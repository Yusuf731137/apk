from __future__ import annotations
import json
from data.repos import SettingsRepo

DEFAULTS = {
    "general.theme": "dark",
    "general.language": "ar",
    "review.mode": "FSRS",
    "review.new_per_day": "20",
    "review.review_per_day": "200",
    "review.auto_pronounce_front": "true",
    "review.auto_pronounce_back": "true",
    "review.auto_pronounce_delay_ms": "300",
    "audio.volume": "0.9",
    "audio.speed": "1.0",
    "tts.provider": "system",
    "tts.en_voice": "",
    "tts.ar_voice": "",
    "fsrs.desired_retention": "0.9",
    "fsrs.max_interval_days": "3650",
}

class Settings:
    def __init__(self, repo: SettingsRepo):
        self.repo = repo
        self._cache = dict(DEFAULTS)
        self._cache.update(repo.all())

    def get(self, key: str, default: str | None = None) -> str:
        return self._cache.get(key, default if default is not None else DEFAULTS.get(key, ""))

    def get_bool(self, key: str) -> bool:
        return self.get(key).lower() in ("1", "true", "yes", "on")

    def get_int(self, key: str) -> int:
        try: return int(self.get(key))
        except ValueError: return 0

    def get_float(self, key: str) -> float:
        try: return float(self.get(key))
        except ValueError: return 0.0

    def set(self, key: str, value: str) -> None:
        self._cache[key] = value
        self.repo.set(key, value)

    def all(self) -> dict[str, str]:
        return dict(self._cache)