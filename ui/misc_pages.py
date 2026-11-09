from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
    QPlainTextEdit, QFormLayout, QCheckBox, QSpinBox, QDoubleSpinBox,
    QDialog,
)
from ui.components import StatCard, BarChart
from services.statistics import Statistics


class DashboardPage(QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(14)
        t = QLabel("لوحة المعلومات"); t.setObjectName("pageTitle"); lay.addWidget(t)
        stats = QHBoxLayout()
        self.s_total = StatCard("البطاقات")
        self.s_due = StatCard("مستحق")
        self.s_new = StatCard("جديد")
        self.s_decks = StatCard("المجموعات")
        for w in (self.s_total, self.s_due, self.s_new, self.s_decks):
            stats.addWidget(w)
        lay.addLayout(stats)
        lay.addStretch()

    def refresh(self):
        st = Statistics(self.ctx.stats).overview()
        self.s_total.value.setText(str(st["total"]))
        self.s_due.value.setText(str(st["due"]))
        self.s_new.value.setText(str(st["new"]))
        self.s_decks.value.setText(str(len(self.ctx.decks.list())))


class CardsPage(QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(12)
        title = QLabel("البطاقات"); title.setObjectName("pageTitle"); lay.addWidget(title)

        top = QHBoxLayout()
        self.deck_combo = QComboBox(); self.deck_combo.currentIndexChanged.connect(self.refresh)
        self.filter_combo = QComboBox()
        for key, label in (
            ("all", "الكل"), ("new", "جديدة"), ("learning", "قيد التعلم"),
            ("due", "مستحقة"), ("review", "مراجعة"), ("suspended", "معلّقة"),
        ):
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        self.sort_combo = QComboBox()
        for key, label in (
            ("created", "تاريخ الإنشاء"), ("alpha", "أبجدي"),
            ("last_review", "آخر مراجعة"), ("due", "الاستحقاق"),
            ("difficulty", "الصعوبة"), ("stability", "الاستقرار"),
        ):
            self.sort_combo.addItem(label, key)
        self.sort_combo.currentIndexChanged.connect(self.refresh)

        add = QPushButton("＋ بطاقة"); add.setObjectName("primaryButton"); add.clicked.connect(self._add)
        edit = QPushButton("تعديل"); edit.setObjectName("secondaryButton"); edit.clicked.connect(self._edit)
        delete = QPushButton("حذف"); delete.setObjectName("secondaryButton"); delete.clicked.connect(self._delete)
        top.addWidget(self.deck_combo, 1)
        top.addWidget(self.filter_combo)
        top.addWidget(self.sort_combo)
        top.addWidget(add); top.addWidget(edit); top.addWidget(delete)
        lay.addLayout(top)

        self.count_lbl = QLabel(""); self.count_lbl.setObjectName("muted")
        lay.addWidget(self.count_lbl)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["أمامي", "خلفي", "المجموعة", "الحالة"])
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _: self._edit())
        lay.addWidget(self.table, 1)

    def refresh(self):
        decks = self.ctx.decks.list()
        cur = self.deck_combo.currentData()
        self.deck_combo.blockSignals(True)
        self.deck_combo.clear()
        self.deck_combo.addItem("الكل", None)
        for d in decks:
            self.deck_combo.addItem(d.name, d.id)
        i = self.deck_combo.findData(cur)
        if i >= 0:
            self.deck_combo.setCurrentIndex(i)
        self.deck_combo.blockSignals(False)

        status = self.filter_combo.currentData()
        sort_by = self.sort_combo.currentData()
        cards = self.ctx.cards.list(
            deck_id=self.deck_combo.currentData(),
            status=None if status == "all" else status,
            sort_by=sort_by,
        )
        self.table.setRowCount(len(cards))
        deck_names = {d.id: d.name for d in decks}
        for r, c in enumerate(cards):
            if c.suspended:
                state = "معلّقة"
            elif c.reps == 0:
                state = "جديدة"
            elif c.state in (1, 3):
                state = "قيد التعلم"
            else:
                state = "مراجعة"
            for col, v in enumerate((c.front, c.back, deck_names.get(c.deck_id, ""), state)):
                self.table.setItem(r, col, QTableWidgetItem(v))
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, c.id)
        self.count_lbl.setText(f"{len(cards)} بطاقة")

    def _selected_card_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self):
        deck_id = self.deck_combo.currentData()
        if deck_id is None:
            if not self.ctx.decks.list():
                QMessageBox.warning(self, "خطأ", "أنشئ مجموعة أولًا."); return
            deck_id = self.ctx.decks.list()[0].id
        dlg = CardEditorDialog(self.ctx, deck_id, card_id=None, parent=self)
        if dlg.exec():
            self.refresh()

    def _edit(self):
        cid = self._selected_card_id()
        if cid is None:
            QMessageBox.information(self, "تعديل", "اختر بطاقة أولًا."); return
        card = self.ctx.cards.get(cid)
        if not card:
            return
        dlg = CardEditorDialog(self.ctx, card.deck_id, card_id=cid, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete(self):
        cid = self._selected_card_id()
        if cid is None:
            return
        if QMessageBox.question(self, "تأكيد", "حذف البطاقة؟") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.cards.delete(cid)
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))


class CardEditorDialog(QDialog):
    def __init__(self, ctx, deck_id: int, card_id: int | None = None, parent=None):
        super().__init__(parent)
        self.ctx, self.deck_id, self.card_id = ctx, deck_id, card_id
        self.setWindowTitle("تعديل البطاقة" if card_id else "بطاقة جديدة")
        self.resize(520, 560)
        self.editors: dict[int, QPlainTextEdit] = {}

        view = ctx.cards.view(card_id) if card_id else None
        fields = view.fields if view else ctx.fields.for_deck(deck_id)

        lay = QVBoxLayout(self)
        for f in fields:
            label = QLabel(f"{f.name} ({f.side.value})")
            ed = QPlainTextEdit(); ed.setFixedHeight(70)
            if view and f.id in view.values:
                ed.setPlainText(view.values[f.id])
            lay.addWidget(label); lay.addWidget(ed)
            self.editors[f.id] = ed

        row = QHBoxLayout()
        save = QPushButton("حفظ"); save.setObjectName("primaryButton"); save.clicked.connect(self._save)
        cancel = QPushButton("إلغاء"); cancel.setObjectName("secondaryButton"); cancel.clicked.connect(self.reject)
        row.addStretch(); row.addWidget(cancel); row.addWidget(save)
        lay.addLayout(row)

    def _save(self):
        values = {fid: ed.toPlainText().strip() for fid, ed in self.editors.items()}
        values = {k: v for k, v in values.items() if v}
        if not values:
            QMessageBox.warning(self, "خطأ", "يجب تعبئة حقل واحد على الأقل."); return
        try:
            if self.card_id:
                self.ctx.cards.update_values(self.card_id, values)
            else:
                self.ctx.cards.create(self.deck_id, values)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))


class ImportPage(QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(12)
        lay.addWidget(QLabel("استيراد CSV (front,back[,deck] أو السؤال,الإجابة,المجموعة)"))
        row = QHBoxLayout()
        self.path = QLineEdit(); self.path.setReadOnly(True)
        browse = QPushButton("اختيار ملف"); browse.clicked.connect(self._browse)
        row.addWidget(self.path, 1); row.addWidget(browse)
        lay.addLayout(row)
        self.default_deck = QLineEdit("مستوردة")
        lay.addWidget(self.default_deck)
        run = QPushButton("استيراد"); run.setObjectName("primaryButton"); run.clicked.connect(self._run)
        lay.addWidget(run)
        lay.addStretch()

    def _browse(self):
        f, _ = QFileDialog.getOpenFileName(self, "CSV", "", "CSV (*.csv)")
        if f:
            self.path.setText(f)

    def _run(self):
        p = self.path.text()
        if not p:
            return
        try:
            import csv, io
            content = open(p, encoding="utf-8-sig").read()
            sample = content[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(io.StringIO(content), dialect=dialect)
            if reader.fieldnames is None:
                raise ValueError("ملف فارغ.")
            aliases = {"front": {"front", "question", "السؤال"},
                       "back": {"back", "answer", "الإجابة", "الاجابة"},
                       "deck": {"deck", "group", "المجموعة"}}
            cols = {t: next((n for n in reader.fieldnames
                             if n and n.strip().casefold() in names), None)
                    for t, names in aliases.items()}
            if not cols["front"] or not cols["back"]:
                raise ValueError("أعمدة front/back مطلوبة.")
            deck_cache: dict[str, int] = {}
            n = 0
            for i, row in enumerate(reader, start=2):
                front = (row.get(cols["front"]) or "").strip()
                back = (row.get(cols["back"]) or "").strip()
                if not front or not back:
                    raise ValueError(f"الصف {i}: قيمة فارغة.")
                deck_name = (row.get(cols["deck"]) or "").strip() if cols["deck"] else ""
                deck_name = deck_name or self.default_deck.text().strip() or "مستوردة"
                deck_id = deck_cache.get(deck_name)
                if deck_id is None:
                    existing = next((d for d in self.ctx.decks.list() if d.name == deck_name), None)
                    deck_id = existing.id if existing else self.ctx.decks.create(deck_name).id
                    deck_cache[deck_name] = deck_id
                fields = self.ctx.fields.for_deck(deck_id)
                front_field = next((f for f in fields if f.side.value in ("FRONT", "BOTH")), None)
                back_field = next((f for f in fields if f.side.value in ("BACK", "BOTH")), None)
                values = {}
                if front_field: values[front_field.id] = front
                if back_field: values[back_field.id] = back
                self.ctx.cards.create(deck_id, values)
                n += 1
            QMessageBox.information(self, "تم", f"تم استيراد {n} بطاقة.")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))


class StatsPage(QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(14)
        lay.addWidget(QLabel("الإحصائيات"))
        row = QHBoxLayout()
        self.deck_combo = QComboBox(); self.deck_combo.addItem("الكل", None)
        for d in ctx.decks.list():
            self.deck_combo.addItem(d.name, d.id)
        self.deck_combo.currentIndexChanged.connect(self.refresh)
        row.addWidget(QLabel("المجموعة")); row.addWidget(self.deck_combo, 1)
        lay.addLayout(row)
        self.chart = BarChart(["FAIL", "HARD", "GOOD", "EASY"],
                              ["#E74C3C", "#F39C12", "#2196D2", "#66BB6A"])
        lay.addWidget(self.chart)

    def refresh(self):
        st = Statistics(self.ctx.stats)
        r = st.ratings(self.deck_combo.currentData())
        self.chart.set_values([r["FAIL"], r["HARD"], r["GOOD"], r["EASY"]])


class SettingsPage(QWidget):
    def __init__(self, ctx):
        super().__init__(); self.ctx = ctx
        lay = QFormLayout(self); lay.setContentsMargins(30, 24, 30, 24)

        self.lang = QComboBox()
        self.lang.addItem("العربية", "ar"); self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(self.lang.findData(ctx.settings.get("general.language", "ar")))

        self.theme = QComboBox()
        self.theme.addItem("داكن", "dark"); self.theme.addItem("فاتح", "light")
        self.theme.setCurrentIndex(self.theme.findData(ctx.settings.get("general.theme")))

        self.tts_provider = QComboBox()
        for name in ctx.tts.names():
            self.tts_provider.addItem(name, name)
        self.tts_provider.setCurrentIndex(
            self.tts_provider.findData(ctx.settings.get("tts.provider", "system")))

        self.auto_front = QCheckBox(); self.auto_front.setChecked(ctx.settings.get_bool("review.auto_pronounce_front"))
        self.auto_back = QCheckBox(); self.auto_back.setChecked(ctx.settings.get_bool("review.auto_pronounce_back"))
        self.new_per_day = QSpinBox(); self.new_per_day.setRange(-1, 1000)
        self.new_per_day.setSpecialValueText("بلا حد")
        self.new_per_day.setValue(ctx.settings.get_int("review.new_per_day"))
        self.rev_per_day = QSpinBox(); self.rev_per_day.setRange(-1, 5000)
        self.rev_per_day.setSpecialValueText("بلا حد")
        self.rev_per_day.setValue(ctx.settings.get_int("review.review_per_day"))
        self.speed = QDoubleSpinBox(); self.speed.setRange(0.5, 2.0); self.speed.setSingleStep(0.25)
        self.speed.setValue(ctx.settings.get_float("audio.speed") or 1.0)
        self.flip_ms = QSpinBox(); self.flip_ms.setRange(60, 800); self.flip_ms.setSingleStep(20)
        self.flip_ms.setValue(ctx.settings.get_int("review.flip_duration_ms") or 300)

        lay.addRow("اللغة / Language", self.lang)
        lay.addRow("الثيم", self.theme)
        lay.addRow("مزوّد الصوت", self.tts_provider)
        lay.addRow("نطق تلقائي (أمامي)", self.auto_front)
        lay.addRow("نطق تلقائي (خلفي)", self.auto_back)
        lay.addRow("حد البطاقات الجديدة/يوم", self.new_per_day)
        lay.addRow("حد المراجعات/يوم", self.rev_per_day)
        lay.addRow("سرعة الصوت الافتراضية", self.speed)
        lay.addRow("مدة حركة القلب (ms)", self.flip_ms)

        save = QPushButton("حفظ"); save.setObjectName("primaryButton"); save.clicked.connect(self._save)
        lay.addRow(save)

        if "piper" not in ctx.tts.names():
            hint = QLabel(
                "لتشغيل TTS العصبي المحلي (Piper):\n"
                "  pip install piper-tts\n"
                "  python scripts/download_piper_model.py ar_JO-kareem-low")
            hint.setObjectName("muted"); hint.setWordWrap(True)
            lay.addRow(hint)

    def _save(self):
        s = self.ctx.settings
        s.set("general.theme", self.theme.currentData())
        s.set("tts.provider", self.tts_provider.currentData())
        s.set("review.auto_pronounce_front", "true" if self.auto_front.isChecked() else "false")
        s.set("review.auto_pronounce_back", "true" if self.auto_back.isChecked() else "false")
        s.set("review.new_per_day", str(self.new_per_day.value()))
        s.set("review.review_per_day", str(self.rev_per_day.value()))
        s.set("audio.speed", str(self.speed.value()))
        s.set("review.flip_duration_ms", str(self.flip_ms.value()))

        from PyQt6.QtWidgets import QApplication
        from ui.theme import apply_theme
        apply_theme(QApplication.instance(), s.get("general.theme"))

        new_lang = self.lang.currentData()
        if new_lang != s.get("general.language") and self.ctx.i18n:
            self.ctx.i18n.apply(new_lang)

        QMessageBox.information(self, "تم", "تم حفظ الإعدادات.")


class BackupsPage(QWidget):
    def __init__(self, ctx, on_restored):
        super().__init__(); self.ctx = ctx; self.on_restored = on_restored
        from services.backup_service import BackupService
        self.service = BackupService(ctx.db.path)
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(12)
        lay.addWidget(QLabel("النسخ الاحتياطية"))
        row = QHBoxLayout()
        refresh = QPushButton("تحديث القائمة"); refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.refresh)
        restore = QPushButton("استعادة المحدد"); restore.setObjectName("primaryButton")
        restore.clicked.connect(self._restore)
        row.addWidget(refresh); row.addStretch(); row.addWidget(restore)
        lay.addLayout(row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الملف", "التاريخ", "الحجم"])
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, 1)

    def refresh(self):
        backups = self.service.list_backups()
        self.table.setRowCount(len(backups))
        for r, b in enumerate(backups):
            for col, v in enumerate((b["filename"],
                                     b["created"].strftime("%Y-%m-%d %H:%M:%S"),
                                     f"{b['size']//1024} KB")):
                self.table.setItem(r, col, QTableWidgetItem(v))
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, str(b["path"]))

    def _restore(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "استعادة", "اختر نسخة أولًا."); return
        path = Path(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        if QMessageBox.question(
            self, "تأكيد الاستعادة",
            "سيتم استبدال قاعدة البيانات الحالية. سيُنشأ نسخ احتياطي أمني أولًا. متابعة؟"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            safety = self.service.restore(path)
            QMessageBox.information(self, "تمت الاستعادة",
                                    f"تمت الاستعادة بنجاح.\nنسخة أمان: {safety.name}")
            self.on_restored()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))