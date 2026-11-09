from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QFrame, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QSpinBox, QMessageBox, QFormLayout,
)
from domain import FieldSide, FieldType, FieldSource
from ui.components import BarChart
from ui.theme import palette


class DeckListPage(QWidget):
    open_deck = None  # callable(deck_id)

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(14)
        title = QLabel("المجموعات"); title.setObjectName("pageTitle")
        lay.addWidget(title)
        row = QHBoxLayout()
        self.name = QLineEdit(); self.name.setPlaceholderText("اسم المجموعة")
        self.desc = QLineEdit(); self.desc.setPlaceholderText("الوصف")
        add = QPushButton("إنشاء"); add.setObjectName("primaryButton")
        add.clicked.connect(self._create)
        row.addWidget(self.name, 1); row.addWidget(self.desc, 1); row.addWidget(add)
        lay.addLayout(row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الاسم", "الوصف", "البطاقات"])
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._open)
        lay.addWidget(self.table, 1)
        lay.addWidget(QLabel("انقر مرتين لفتح المجموعة"), 0, Qt.AlignmentFlag.AlignRight)

    def refresh(self):
        decks = self.ctx.decks.list()
        self.table.setRowCount(len(decks))
        for row, d in enumerate(decks):
            count = len(self.ctx.cards.list(d.id))
            for col, v in enumerate((d.name, d.description, str(count))):
                self.table.setItem(row, col, QTableWidgetItem(v))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, d.id)

    def _create(self):
        try:
            self.ctx.decks.create(self.name.text(), self.desc.text())
            self.name.clear(); self.desc.clear()
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))

    def _open(self, row, _col):
        item = self.table.item(row, 0)
        if item and self.open_deck:
            self.open_deck(item.data(Qt.ItemDataRole.UserRole))


class DeckHomePage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.deck_id = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(14)
        head = QHBoxLayout()
        back = QPushButton("← المجموعات"); back.setObjectName("secondaryButton")
        self.title = QLabel(""); self.title.setObjectName("pageTitle")
        self.edit_btn = QPushButton("تعديل"); self.edit_btn.setObjectName("secondaryButton")
        self.review_btn = QPushButton("مراجعة"); self.review_btn.setObjectName("primaryButton")
        head.addWidget(back); head.addWidget(self.title); head.addStretch()
        head.addWidget(self.edit_btn); head.addWidget(self.review_btn)
        lay.addLayout(head)
        self.desc = QLabel(""); self.desc.setObjectName("muted"); lay.addWidget(self.desc)

        stats = QHBoxLayout()
        from ui.components import StatCard
        self.stat_total = StatCard("إجمالي")
        self.stat_new = StatCard("جديد")
        self.stat_due = StatCard("مستحق")
        for w in (self.stat_total, self.stat_new, self.stat_due):
            stats.addWidget(w)
        lay.addLayout(stats)

        chart_card = QFrame(); chart_card.setObjectName("card")
        cl = QVBoxLayout(chart_card)
        cl.addWidget(QLabel("توزيع الدرجات (إتقان)"))
        self.chart = BarChart(
            ["جديد", "F", "E", "D", "C", "B", "A"],
            ["#4a4a4a", palette()["fail"], "#c0392b", palette()["hard"],
             palette()["good"], "#2980b9", palette()["easy"]])
        cl.addWidget(self.chart)
        lay.addWidget(chart_card)
        lay.addStretch()

    def load(self, deck_id: int):
        self.deck_id = deck_id
        d = self.ctx.decks.get(deck_id)
        if not d:
            return
        self.title.setText(d.name)
        self.desc.setText(d.description or "—")
        from services.statistics import Statistics
        st = Statistics(self.ctx.stats)
        ov = st.overview(deck_id)
        self.stat_total.value.setText(str(ov["total"]))
        self.stat_new.value.setText(str(ov["new"]))
        self.stat_due.value.setText(str(ov["due"]))
        grades = st.grades(deck_id)
        self.chart.set_values([grades[k] for k in ("NEW", "F", "E", "D", "C", "B", "A")])


class EditDeckDialog(QDialog):
    def __init__(self, ctx, deck_id: int, parent=None):
        super().__init__(parent)
        self.ctx, self.deck_id = ctx, deck_id
        self.setWindowTitle("تعديل المجموعة")
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        deck = ctx.decks.get(deck_id)

        form = QFormLayout()
        self.name = QLineEdit(deck.name)
        self.desc = QLineEdit(deck.description)
        form.addRow("الاسم", self.name); form.addRow("الوصف", self.desc)
        lay.addLayout(form)

        lay.addWidget(QLabel("الحقول"))
        self.field_list = QListWidget()
        lay.addWidget(self.field_list, 1)
        row = QHBoxLayout()
        add = QPushButton("＋ حقل جديد"); add.clicked.connect(self._add_field)
        edit = QPushButton("تعديل المحدد"); edit.clicked.connect(self._edit_field)
        delete = QPushButton("حذف المحدد"); delete.clicked.connect(self._delete_field)
        row.addWidget(add); row.addWidget(edit); row.addWidget(delete); row.addStretch()
        lay.addLayout(row)
        self._refresh_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _refresh_fields(self):
        self.field_list.clear()
        for f in self.ctx.fields.for_deck(self.deck_id):
            it = QListWidgetItem(f"{f.name}  ·  {f.type.value}  ·  {f.side.value}  ·  #{f.sort_order}")
            it.setData(Qt.ItemDataRole.UserRole, f.id)
            self.field_list.addItem(it)

    def _selected_field_id(self):
        it = self.field_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _add_field(self):
        dlg = FieldEditorDialog(self.ctx, self.deck_id, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_fields()

    def _edit_field(self):
        fid = self._selected_field_id()
        if fid is None:
            return
        dlg = FieldEditorDialog(self.ctx, self.deck_id, fid, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_fields()

    def _delete_field(self):
        fid = self._selected_field_id()
        if fid is None:
            return
        if QMessageBox.question(self, "تأكيد", "حذف الحقل؟") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.fields.delete(fid)
            self._refresh_fields()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))

    def _save(self):
        try:
            deck = self.ctx.decks.get(self.deck_id)
            self.ctx.decks.update(self.deck_id, self.name.text(), self.desc.text(), deck.folder_id)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))


class FieldEditorDialog(QDialog):
    def __init__(self, ctx, deck_id: int, field_id: int | None, parent=None):
        super().__init__(parent)
        self.ctx, self.deck_id, self.field_id = ctx, deck_id, field_id
        self.setWindowTitle("محرر الحقل")
        self.resize(480, 520)
        lay = QFormLayout(self)

        self.name = QLineEdit()
        self.type = QComboBox()
        for t in FieldType: self.type.addItem(t.value, t)
        self.side = QComboBox()
        for s in FieldSide: self.side.addItem(s.value, s)
        self.lang = QLineEdit()
        self.font = QSpinBox(); self.font.setRange(8, 72); self.font.setValue(16)
        self.provider = QComboBox()
        for name in ctx.tts.names():
            self.provider.addItem(name, name)
        self.voice = QComboBox()
        self.rate = QComboBox()
        for s in ("0.5", "0.75", "1.0", "1.25", "1.5", "2.0"):
            self.rate.addItem(f"{s}×", float(s))
        self.source = QComboBox()
        for s in FieldSource: self.source.addItem(s.value, s)
        self.order = QSpinBox(); self.order.setRange(0, 999)

        lay.addRow("الاسم", self.name)
        lay.addRow("النوع", self.type)
        lay.addRow("الجانب", self.side)
        lay.addRow("اللغة", self.lang)
        lay.addRow("حجم الخط", self.font)
        lay.addRow("مزوّد الصوت", self.provider)
        lay.addRow("الصوت", self.voice)
        lay.addRow("السرعة", self.rate)
        lay.addRow("المصدر", self.source)
        lay.addRow("الترتيب", self.order)

        row = QHBoxLayout()
        test = QPushButton("اختبار الصوت"); test.setObjectName("secondaryButton")
        test.clicked.connect(self._test)
        row.addWidget(test); row.addStretch()
        lay.addRow(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addRow(buttons)

        self._load_voices()
        self.provider.currentIndexChanged.connect(self._load_voices)

        if field_id:
            f = ctx.fields.get(field_id)
            self.name.setText(f.name)
            self.type.setCurrentIndex(self.type.findData(f.type))
            self.side.setCurrentIndex(self.side.findData(f.side))
            self.lang.setText(f.language)
            self.font.setValue(f.font_size)
            if f.tts_provider:
                idx = self.provider.findData(f.tts_provider)
                if idx >= 0:
                    self.provider.setCurrentIndex(idx)
                    self._load_voices()
                    if f.tts_voice:
                        vi = self.voice.findData(f.tts_voice)
                        if vi >= 0:
                            self.voice.setCurrentIndex(vi)
            self.rate.setCurrentIndex(self.rate.findData(f.tts_rate or 1.0))
            self.source.setCurrentIndex(self.source.findData(f.source))
            self.order.setValue(f.sort_order)

    def _load_voices(self):
        provider_name = self.provider.currentData() or "system"
        try:
            voices = self.ctx.tts.get(provider_name).available_voices()
        except Exception:
            voices = []
        self.voice.clear()
        self.voice.addItem("— افتراضي —", "")
        for v in voices:
            label = f"{v['name']} [{v.get('language','')}]"
            self.voice.addItem(label, v["id"])

    def _test(self):
        from pathlib import Path
        try:
            provider = self.ctx.tts.get(self.provider.currentData() or "system")
            tmp = Path.home() / ".midad-flashcards" / "_test.wav"
            provider.synthesize("Hello. مرحبا.", self.voice.currentData() or None,
                                self.lang.text(), self.rate.currentData() or 1.0, tmp)
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtCore import QUrl
            self._test_player = QMediaPlayer()
            self._test_audio = QAudioOutput()
            self._test_player.setAudioOutput(self._test_audio)
            self._test_player.setSource(QUrl.fromLocalFile(str(tmp)))
            self._test_player.play()
        except Exception as e:
            QMessageBox.warning(self, "TTS", str(e))

    def _save(self):
        try:
            payload = dict(
                name=self.name.text().strip(),
                type=self.type.currentData(),
                side=self.side.currentData(),
                language=self.lang.text().strip(),
                font_size=self.font.value(),
                tts_provider=self.provider.currentData(),
                tts_voice=self.voice.currentData(),
                tts_rate=self.rate.currentData(),
                source=self.source.currentData(),
                sort_order=self.order.value(),
            )
            if not payload["name"]:
                raise ValueError("اسم الحقل مطلوب.")
            if self.field_id:
                self.ctx.fields.update(self.field_id, **payload)
            else:
                self.ctx.fields.create(self.deck_id, **payload)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", str(e))