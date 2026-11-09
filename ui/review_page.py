from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QStackedWidget, QMessageBox, QSpinBox, QCheckBox,
    QGraphicsOpacityEffect,
)

from domain import Rating, ReviewMode, FieldType, FieldSide
from services.review_engine import ReviewEngine, SessionState
from services.fsrs_service import preview_intervals
from ui.components import AudioPlayer
from ui.workers import TTSWorker


class ReviewPage(QWidget):
    finished = pyqtSignal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.engine = ReviewEngine(ctx.cards, ctx.reviews, ctx.sessions)
        self.state: SessionState | None = None
        self.current = None
        self.revealed = False
        self.card_started_at: datetime | None = None
        self._tts_worker: TTSWorker | None = None
        self._flip_anim: QPropertyAnimation | None = None
        self._flipping = False
        self._active_tts_field = None

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(16)

        top = QHBoxLayout()
        self.back_btn = QPushButton("← عودة")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.clicked.connect(self._exit)
        self.title = QLabel("جلسة مراجعة"); self.title.setObjectName("pageTitle")
        self.counter = QLabel(""); self.counter.setObjectName("muted")
        top.addWidget(self.back_btn); top.addStretch()
        top.addWidget(self.title); top.addStretch(); top.addWidget(self.counter)
        root.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_setup())
        self.stack.addWidget(self._build_card())
        self.stack.addWidget(self._build_done())
        root.addWidget(self.stack, 1)

    # ---------- setup ----------
    def _build_setup(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(14)
        lay.addWidget(QLabel("المجموعة"))
        self.deck_combo = QComboBox()
        lay.addWidget(self.deck_combo)
        lay.addWidget(QLabel("الوضع"))
        self.mode_combo = QComboBox()
        for m in ReviewMode:
            self.mode_combo.addItem({
                ReviewMode.FSRS: "FSRS", ReviewMode.RANDOM: "عشوائي",
                ReviewMode.CREATED: "بترتيب الإنشاء",
            }[m], m)
        lay.addWidget(self.mode_combo)
        lay.addWidget(QLabel("حد البطاقات (اختياري)"))
        self.limit_spin = QSpinBox(); self.limit_spin.setRange(0, 10000); self.limit_spin.setValue(0)
        self.limit_spin.setSpecialValueText("بلا حد")
        lay.addWidget(self.limit_spin)
        self.cram_check = QCheckBox("جلسة تحفيظ مؤقتة (لا تُعدّل جدولة FSRS ولا الحدود اليومية)")
        lay.addWidget(self.cram_check)
        start = QPushButton("ابدأ الجلسة"); start.setObjectName("primaryButton")
        start.clicked.connect(self._start)
        lay.addWidget(start, 0, Qt.AlignmentFlag.AlignRight)
        lay.addStretch()
        return w

    # ---------- card ----------
    def _build_card(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(16)

        self.card_frame = QFrame(); self.card_frame.setObjectName("card")
        cf = QVBoxLayout(self.card_frame)
        cf.setContentsMargins(30, 30, 30, 30)
        cf.setSpacing(14)
        self.side_lbl = QLabel("السؤال"); self.side_lbl.setObjectName("muted")
        self.side_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.deck_lbl = QLabel(""); self.deck_lbl.setObjectName("muted")
        self.deck_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content = QLabel(""); self.content.setWordWrap(True)
        self.content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content.setStyleSheet("font-size: 34px; font-weight: 700;")
        self.content.setMinimumHeight(160)
        self.audio = AudioPlayer()
        self.audio.request_tts.connect(self._generate_tts_current)
        cf.addWidget(self.side_lbl)
        cf.addWidget(self.deck_lbl)
        cf.addWidget(self.content, 1)
        cf.addWidget(self.audio)
        lay.addWidget(self.card_frame, 1)

        self.flip_btn = QPushButton("اقلب البطاقة (Space)")
        self.flip_btn.setObjectName("primaryButton")
        self.flip_btn.clicked.connect(self._flip)
        lay.addWidget(self.flip_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.rating_row_widget = QWidget()
        rating_row = QHBoxLayout(self.rating_row_widget)
        self.rating_buttons: dict[Rating, QPushButton] = {}
        for key, title in (
            (Rating.FAIL, "لم أتذكر (1)"), (Rating.HARD, "بصعوبة (2)"),
            (Rating.GOOD, "جيد (3)"), (Rating.EASY, "سهل (4)"),
        ):
            b = QPushButton(title); b.setObjectName(f"rating_{key.value}")
            b.clicked.connect(lambda _=False, k=key: self._rate(k))
            rating_row.addWidget(b)
            self.rating_buttons[key] = b
        lay.addWidget(self.rating_row_widget)
        self.rating_row_widget.hide()
        return w

    # ---------- done ----------
    def _build_done(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_title = QLabel("اكتملت الجلسة 🎉")
        self.done_title.setObjectName("pageTitle")
        self.done_stats = QLabel(""); self.done_stats.setObjectName("muted")
        self.done_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back = QPushButton("عودة"); back.setObjectName("primaryButton")
        back.clicked.connect(self._exit)
        lay.addWidget(self.done_title, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.done_stats, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(20)
        lay.addWidget(back, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    # ---------- helpers ----------
    def _flip_half_ms(self) -> int:
        try:
            v = self.ctx.settings.get_int("review.flip_duration_ms")
            return max(60, min(v, 800)) // 2 if v else 150
        except Exception:
            return 150

    def refresh_decks(self):
        current = self.deck_combo.currentData()
        self.deck_combo.clear()
        self.deck_combo.addItem("كل المجموعات", None)
        for d in self.ctx.decks.list():
            self.deck_combo.addItem(d.name, d.id)
        i = self.deck_combo.findData(current)
        if i >= 0:
            self.deck_combo.setCurrentIndex(i)

    def prepare(self):
        self.refresh_decks()
        self.stack.setCurrentIndex(0)

    # ---------- session ----------
    def _start(self):
        deck_id = self.deck_combo.currentData()
        mode = self.mode_combo.currentData()
        limit = self.limit_spin.value() or None

        def _limit_or_none(key: str) -> int | None:
            v = self.ctx.settings.get_int(key)
            return None if v < 0 else v

        daily_new = _limit_or_none("review.new_per_day")
        daily_review = _limit_or_none("review.review_per_day")

        self.state = self.engine.start(
            deck_id, mode, self.cram_check.isChecked(), limit,
            daily_new=daily_new, daily_review=daily_review)
        if not self.state.queue:
            QMessageBox.information(
                self, "لا بطاقات",
                "لا توجد بطاقات مطابقة (تحقّق من الحدود اليومية أو فلترة المجموعة).")
            return
        self.stack.setCurrentIndex(1)
        self._show_current()

    def _show_current(self):
        if self._flip_anim is not None:
            try: self._flip_anim.stop()
            except Exception: pass
            self._flip_anim = None
        self._flipping = False
        self.card_frame.setGraphicsEffect(None)
        self.card_frame.setEnabled(True)
        self.flip_btn.setEnabled(True)

        card = self.engine.current(self.state)
        if card is None:
            self._finish(); return
        self.current = self.ctx.cards.view(card.id)
        self.revealed = False
        self.side_lbl.setText("السؤال")
        self.deck_lbl.setText(self.current.deck_name)
        self.rating_row_widget.hide()
        self.flip_btn.show()
        self._render_side(show_front=True)
        remaining = len(self.state.queue) - self.state.index
        self.counter.setText(f"{remaining} متبقية")
        self.card_started_at = datetime.now(timezone.utc)
        if self.ctx.settings.get_bool("review.auto_pronounce_front"):
            QTimer.singleShot(
                self.ctx.settings.get_int("review.auto_pronounce_delay_ms"),
                self._auto_speak_front)

    def _auto_speak_front(self):
        if self.revealed:
            return
        self._generate_tts_current()

    def _render_side(self, show_front: bool):
        side = FieldSide.FRONT if show_front else FieldSide.BACK
        fields = self.current.fields_for(side)
        parts = []
        for f in fields:
            val = self.current.values.get(f.id, "").strip()
            if not val:
                continue
            parts.append(val)
        self.content.setText("\n\n".join(parts) if parts else "—")
        tts_field = next((f for f in fields if f.type == FieldType.TTS), None)
        self._active_tts_field = tts_field
        self.audio.set_source(None)

    def _flip(self):
        if not self.current or self.revealed or self._flipping:
            return
        self._flipping = True
        self.flip_btn.setEnabled(False)

        effect = QGraphicsOpacityEffect(self.card_frame)
        self.card_frame.setGraphicsEffect(effect)
        half = self._flip_half_ms()

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(half)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def on_faded_out():
            self.revealed = True
            self.side_lbl.setText("الإجابة")
            self._render_side(show_front=False)
            self.flip_btn.hide()
            self.rating_row_widget.show()
            try:
                prev = preview_intervals(self.current.card)
                for k, b in self.rating_buttons.items():
                    base = {Rating.FAIL: "لم أتذكر", Rating.HARD: "بصعوبة",
                            Rating.GOOD: "جيد", Rating.EASY: "سهل"}[k]
                    b.setText(f"{base} ({prev[k.value]})")
            except Exception:
                pass

            fade_in = QPropertyAnimation(effect, b"opacity", self)
            fade_in.setDuration(half)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

            def done():
                self.card_frame.setGraphicsEffect(None)
                self.flip_btn.setEnabled(True)
                self._flipping = False
                self._flip_anim = None
                if self.ctx.settings.get_bool("review.auto_pronounce_back"):
                    QTimer.singleShot(200, self._generate_tts_current)

            fade_in.finished.connect(done)
            self._flip_anim = fade_in
            fade_in.start()

        fade_out.finished.connect(on_faded_out)
        self._flip_anim = fade_out
        fade_out.start()

    def _rate(self, rating: Rating):
        if not self.current or not self.revealed or self._flipping:
            return
        duration_ms = None
        if self.card_started_at:
            duration_ms = int(
                (datetime.now(timezone.utc) - self.card_started_at).total_seconds() * 1000)
            duration_ms = max(0, min(duration_ms, 3_600_000))
        try:
            self.engine.rate(self.state, self.current.card, rating, duration_ms=duration_ms)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"تعذر حفظ المراجعة: {e}")
            return
        self._show_current()

    def _generate_tts_current(self):
        if not self.current:
            return
        field = self._active_tts_field
        text = (self.current.values.get(field.id, "") if field else self.content.text()).strip()
        if not text:
            return
        provider_name = (field.tts_provider if field else None) or self.ctx.settings.get("tts.provider", "system")
        voice = (field.tts_voice if field else None) or ""
        rate = (field.tts_rate if field else 1.0) or 1.0
        lang = (field.language if field else "") or ""
        provider = self.ctx.tts.get(provider_name)
        if self._tts_worker and self._tts_worker.isRunning():
            self._tts_worker.cancel()
        self._tts_worker = TTSWorker(self.ctx.cache, text, lang, provider, voice, rate)
        self._tts_worker.done.connect(
            lambda p: (self.audio.set_source(Path(p)), self.audio.play()))
        self._tts_worker.failed.connect(lambda m: QMessageBox.warning(self, "TTS", m))
        self._tts_worker.start()

    def _finish(self):
        self.engine.finish(self.state)
        ratings = self.state.ratings
        self.done_stats.setText(
            f"تمت مراجعة {sum(ratings.values())} بطاقة.\n"
            f"لم أتذكر: {ratings['FAIL']} · بصعوبة: {ratings['HARD']} · "
            f"جيد: {ratings['GOOD']} · سهل: {ratings['EASY']}")
        self.stack.setCurrentIndex(2)

    def _exit(self):
        if self.state and self.state.index < len(self.state.queue):
            try:
                self.engine.finish(self.state)
            except Exception:
                pass
        self.state = None
        self.finished.emit()
        self.stack.setCurrentIndex(0)

    def keyPressEvent(self, ev):
        if self.stack.currentIndex() != 1:
            return
        if ev.key() == Qt.Key.Key_Space and not self.revealed:
            self._flip()
        elif ev.key() == Qt.Key.Key_1: self._rate(Rating.FAIL)
        elif ev.key() == Qt.Key.Key_2: self._rate(Rating.HARD)
        elif ev.key() == Qt.Key.Key_3: self._rate(Rating.GOOD)
        elif ev.key() == Qt.Key.Key_4: self._rate(Rating.EASY)
        else:
            super().keyPressEvent(ev)