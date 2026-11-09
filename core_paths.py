import os
from pathlib import Path


def data_dir() -> Path:
    storage_dir = os.environ.get("FLET_APP_STORAGE_DATA")
    d = Path(storage_dir) if storage_dir else Path.home() / ".midad-flashcards"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "cards.sqlite3"


def cache_dir() -> Path:
    d = data_dir() / "audio_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d