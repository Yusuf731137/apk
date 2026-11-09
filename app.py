from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from data.database import DB
from core_paths import db_path
from core.i18n import I18n
from services.settings import Settings
from services.audio_cache import AudioCache
from services.tts import TTSRegistry
from data.repos import (
    DeckRepo, CardRepo, FieldRepo, ReviewRepo, SessionRepo,
    StatsRepo, AudioCacheRepo, SettingsRepo, FolderRepo,
)
from ui.main_window import MainWindow
from ui.theme import apply_theme


class AppContext:
    def __init__(self, db_path_):
        self.db = DB(db_path_)
        self.decks = DeckRepo(self.db)
        self.cards = CardRepo(self.db)
        self.fields = FieldRepo(self.db)
        self.reviews = ReviewRepo(self.db)
        self.sessions = SessionRepo(self.db)
        self.stats = StatsRepo(self.db)
        self.folders = FolderRepo(self.db)
        self.audio_cache_repo = AudioCacheRepo(self.db)
        self.settings = Settings(SettingsRepo(self.db))
        self.cache = AudioCache(self.audio_cache_repo)
        self.tts = TTSRegistry()
        self.i18n: I18n | None = None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Midad")

    ctx = AppContext(db_path())
    ctx.i18n = I18n(app, ctx.settings)

    apply_theme(app, ctx.settings.get("general.theme", "dark"))

    win = MainWindow(ctx)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())