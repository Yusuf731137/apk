from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QTranslator, Qt
from PyQt6.QtWidgets import QApplication


_AR = {
    # nav
    "Dashboard": "لوحة التحكم",
    "Review": "المراجعة",
    "Cards": "البطاقات",
    "Decks": "المجموعات",
    "Statistics": "الإحصائيات",
    "Import": "استيراد",
    "Settings": "الإعدادات",
    "Backups": "النسخ الاحتياطية",
    # page titles
    "Deck Dashboard": "لوحة المجموعة",
    "Review Session": "جلسة المراجعة",
    "Edit Deck": "تعديل المجموعة",
    "Field Editor": "محرر الحقل",
    "New Card": "بطاقة جديدة",
    "Edit Card": "تعديل البطاقة",
    # buttons
    "Save": "حفظ", "Cancel": "إلغاء", "Create": "إنشاء",
    "Edit": "تعديل", "Delete": "حذف", "Add": "إضافة",
    "Start Session": "ابدأ الجلسة", "Flip Card": "اقلب البطاقة",
    "Back": "عودة", "Restore": "استعادة", "Refresh": "تحديث",
    "Test Audio": "اختبار الصوت",
    # ratings
    "Fail": "لم أتذكر", "Hard": "بصعوبة", "Good": "جيد", "Easy": "سهل",
    # review
    "Question": "السؤال", "Answer": "الإجابة",
    "Session Complete": "اكتملت الجلسة",
    # filters
    "All": "الكل", "New": "جديدة", "Learning": "قيد التعلم",
    "Due": "مستحقة", "Review Filter": "مراجعة", "Suspended": "معلّقة",
    # sorts
    "Created": "تاريخ الإنشاء", "Alphabetical": "أبجدي",
    "Last Review": "آخر مراجعة", "Due Date": "الاستحقاق",
    "Difficulty": "الصعوبة", "Stability": "الاستقرار",
    # settings
    "Language": "اللغة", "Theme": "الثيم",
    "Dark": "داكن", "Light": "فاتح",
    "Auto-Pronounce Front": "نطق تلقائي (أمامي)",
    "Auto-Pronounce Back": "نطق تلقائي (خلفي)",
    "New cards per day": "بطاقات جديدة في اليوم",
    "Reviews per day": "مراجعات في اليوم",
    "Default audio speed": "سرعة الصوت الافتراضية",
    "Flip animation duration (ms)": "مدة حركة القلب (مللي ثانية)",
    "Language changed": "تم تغيير اللغة",
}


class I18n:
    """Runtime translation + layout direction manager.

    Attempts to load translations/midad_<lang>.qm if present; otherwise
    uses the built-in Arabic dictionary. English uses source strings as-is.
    """

    def __init__(self, app: QApplication, settings):
        self.app = app
        self.settings = settings
        self.lang = settings.get("general.language", "ar") or "ar"
        self._qt_translator: Optional[QTranslator] = None
        self._listeners: list[Callable[[], None]] = []
        self.apply(self.lang, notify=False)

    def on_change(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def tr(self, source: str) -> str:
        if self.lang == "ar":
            return _AR.get(source, source)
        return source

    def apply(self, lang: str, notify: bool = True) -> None:
        self.lang = "ar" if lang == "ar" else "en"
        self.settings.set("general.language", self.lang)

        if self._qt_translator:
            self.app.removeTranslator(self._qt_translator)
            self._qt_translator = None
        qm = Path(__file__).resolve().parent.parent / "translations" / f"midad_{self.lang}.qm"
        if qm.exists():
            t = QTranslator()
            if t.load(str(qm)):
                self._qt_translator = t
                self.app.installTranslator(t)

        self.app.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self.lang == "ar"
            else Qt.LayoutDirection.LeftToRight)

        if notify:
            for fn in list(self._listeners):
                try:
                    fn()
                except Exception:
                    pass