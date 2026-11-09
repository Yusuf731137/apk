from __future__ import annotations
import hashlib
import json
from pathlib import Path

from core_paths import cache_dir
from data.repos import AudioCacheRepo
from services.tts import TTSProvider


class AudioCache:
    def __init__(self, repo: AudioCacheRepo):
        self.repo = repo
        self.dir = cache_dir()

    @staticmethod
    def make_key(text: str, lang: str, provider: str, voice: str, params: dict) -> str:
        h = hashlib.sha256()
        h.update(text.strip().encode("utf-8"))
        h.update(b"|")
        h.update(lang.lower().encode("utf-8"))
        h.update(b"|")
        h.update(provider.encode("utf-8"))
        h.update(b"|")
        h.update(voice.encode("utf-8"))
        h.update(b"|")
        h.update(json.dumps(params, sort_keys=True).encode("utf-8"))
        return h.hexdigest()

    def get_or_create(self, text: str, lang: str, provider: TTSProvider,
                      voice: str, rate: float) -> Path:
        params = {"rate": rate}
        key = self.make_key(text, lang, provider.name, voice, params)
        row = self.repo.get(key)
        if row:
            path = Path(row["file_path"])
            if path.exists():
                return path
            self.repo.remove(key)
        out = self.dir / f"{key}.wav"
        provider.synthesize(text, voice or None, lang, rate, out)
        self.repo.put(key, str(out), text, lang, provider.name, voice,
                      params, out.stat().st_size)
        return out