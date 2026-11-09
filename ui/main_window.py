from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QStackedWidget, QStatusBar,
)
from ui.review_page import ReviewPage
from ui.deck_pages import DeckListPage, DeckHomePage, EditDeckDialog
from ui.misc_pages import (
    DashboardPage, CardsPage, ImportPage, StatsPage, SettingsPage, BackupsPage,
)


class MainWindow(QMainWindow):
    NAV_KEYS = ("Dashboard", "Review", "Cards", "Decks",
                "Statistics", "Import", "Backups", "Settings")
    NAV_AR = ("الرئيسية", "المراجعة", "البطاقات", "المجموعات",
              "الإحصائيات", "استيراد", "النسخ الاحتياطية", "الإعدادات")

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("مِداد")
        self.resize(1180, 760)
        self._drag = None

        root = QWidget(); lay = QVBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._titlebar())
        body = QHBoxLayout(); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        self.sidebar = self._sidebar()
        body.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self._build_pages()
        body.addWidget(self.stack, 1)
        lay.addLayout(body, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))

        self.ctx.i18n.on_change(self._retranslate)
        self._retranslate()
        self._show(0)

    def _titlebar(self) -> QWidget:
        bar = QFrame(); bar.setObjectName("titlebar"); bar.setFixedHeight(46)
        lay = QHBoxLayout(bar); lay.setContentsMargins(18, 0, 8, 0)
        logo = QLabel("مِداد"); logo.setObjectName("brand")
        subtitle = QLabel("مساحة تعلّم"); subtitle.setObjectName("muted")
        lay.addWidget(logo); lay.addWidget(subtitle); lay.addStretch()
        min_btn = QPushButton("—"); min_btn.setFixedWidth(32); min_btn.clicked.connect(self.showMinimized)
        close_btn = QPushButton("×"); close_btn.setFixedWidth(32); close_btn.clicked.connect(self.close)
        lay.addWidget(min_btn); lay.addWidget(close_btn)
        bar.mousePressEvent = self._tb_press
        bar.mouseMoveEvent = self._tb_move
        return bar

    def _tb_press(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _tb_move(self, ev):
        if self._drag and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def _sidebar(self) -> QWidget:
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(220)
        lay = QVBoxLayout(side); lay.setContentsMargins(12, 20, 12, 12); lay.setSpacing(6)
        self.nav: list[QPushButton] = []
        for i, name in enumerate(self.NAV_AR):
            b = QPushButton(f"  {name}"); b.setObjectName("navButton")
            b.clicked.connect(lambda _=False, idx=i: self._show(idx))
            self.nav.append(b); lay.addWidget(b)
        lay.addStretch()
        return side

    def _build_pages(self):
        self.dashboard = DashboardPage(self.ctx)
        self.review = ReviewPage(self.ctx)
        self.cards_page = CardsPage(self.ctx)
        self.decks_page = DeckListPage(self.ctx)
        self.stats_page = StatsPage(self.ctx)
        self.import_page = ImportPage(self.ctx)
        self.backups_page = BackupsPage(self.ctx, on_restored=self._reload_after_restore)
        self.settings_page = SettingsPage(self.ctx)
        self.deck_home = DeckHomePage(self.ctx)

        self.decks_page.open_deck = self._open_deck
        self.deck_home.review_btn.clicked.connect(self._review_from_deck)
        self.deck_home.edit_btn.clicked.connect(self._edit_deck)

        order = [self.dashboard, self.review, self.cards_page, self.decks_page,
                 self.stats_page, self.import_page, self.backups_page,
                 self.settings_page, self.deck_home]
        for p in order:
            self.stack.addWidget(p)
        self.review.finished.connect(lambda: self._show(0))

    def _retranslate(self):
        i = self.ctx.i18n
        for btn, key in zip(self.nav, self.NAV_KEYS):
            btn.setText("  " + i.tr(key))
            # nav labels can be overridden by _AR; for Arabic also use _AR direct
            if i.lang == "ar":
                idx = self.NAV_KEYS.index(key)
                btn.setText("  " + self.NAV_AR[idx])

    def _show(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav):
            b.setProperty("active", i == index)
            b.style().unpolish(b); b.style().polish(b)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()
        if page is self.review:
            page.prepare()

    def _open_deck(self, deck_id: int):
        self.deck_home.load(deck_id)
        self.stack.setCurrentWidget(self.deck_home)
        for b in self.nav:
            b.setProperty("active", False); b.style().unpolish(b); b.style().polish(b)

    def _review_from_deck(self):
        deck_id = self.deck_home.deck_id
        if deck_id is None:
            return
        self._show(1)
        idx = self.review.deck_combo.findData(deck_id)
        if idx >= 0:
            self.review.deck_combo.setCurrentIndex(idx)

    def _edit_deck(self):
        if self.deck_home.deck_id is None:
            return
        dlg = EditDeckDialog(self.ctx, self.deck_home.deck_id, self)
        if dlg.exec():
            self.deck_home.load(self.deck_home.deck_id)

    def _reload_after_restore(self):
        from data.database import DB
        self.ctx.db = DB(self.ctx.db.path)
        for name in ("decks", "cards", "fields", "reviews", "sessions",
                     "stats", "folders", "audio_cache_repo"):
            old = getattr(self.ctx, name, None)
            if old is not None:
                old.db = self.ctx.db
        for page in (self.dashboard, self.cards_page, self.decks_page,
                     self.stats_page, self.review):
            if hasattr(page, "refresh"):
                try: page.refresh()
                except Exception: pass
        self.statusBar().showMessage("تمت استعادة قاعدة البيانات.", 4000)