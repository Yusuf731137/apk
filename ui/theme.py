from __future__ import annotations

DARK = {
    "bg": "#111111", "bg2": "#1E1E1E", "card": "#181818",
    "accent": "#C47ACB", "border": "#373737",
    "text": "#FFFFFF", "muted": "#A0A0A0",
    "fail": "#E74C3C", "hard": "#F39C12",
    "good": "#2196D2", "easy": "#66BB6A",
}
LIGHT = {
    "bg": "#f5f7f4", "bg2": "#ffffff", "card": "#ffffff",
    "accent": "#167c68", "border": "#e6ebe7",
    "text": "#23332f", "muted": "#77847f",
    "fail": "#b83c34", "hard": "#946625",
    "good": "#2f7951", "easy": "#4b67a0",
}

_current = DARK

def palette() -> dict:
    return _current

def qss(t: dict) -> str:
    return f"""
    * {{ font-family: "Segoe UI", "Noto Sans Arabic"; font-size: 14px; color: {t['text']}; }}
    QMainWindow, QWidget {{ background: {t['bg']}; }}
    #titlebar {{ background: {t['bg2']}; border-bottom: 1px solid {t['border']}; }}
    #brand {{ color: {t['accent']}; font-size: 18px; font-weight: 800; }}
    #sidebar {{ background: {t['bg2']}; border-left: 1px solid {t['border']}; }}
    #navButton {{ text-align: right; padding: 12px 14px; border: 0; border-radius: 10px;
                  background: transparent; color: {t['muted']}; }}
    #navButton:hover {{ background: {t['card']}; color: {t['accent']}; }}
    #navButton[active="true"] {{ background: {t['card']}; color: {t['accent']}; font-weight: 700; }}
    #pageTitle {{ font-size: 26px; font-weight: 750; color: {t['text']}; }}
    #muted {{ color: {t['muted']}; }}
    #card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 14px; }}
    #statNumber {{ font-size: 30px; color: {t['accent']}; font-weight: 750; }}
    #primaryButton {{ color: {t['bg']}; background: {t['accent']}; border: 1px solid {t['accent']};
                      border-radius: 10px; padding: 10px 17px; font-weight: 650; }}
    #primaryButton:hover {{ background: {t['accent']}; opacity: 0.9; }}
    #secondaryButton {{ color: {t['text']}; background: {t['bg2']}; border: 1px solid {t['border']};
                        border-radius: 10px; padding: 10px 17px; }}
    #secondaryButton:hover {{ background: {t['card']}; }}
    #rating_FAIL {{ background: {t['fail']}; color: white; border-radius: 12px; padding: 14px; font-weight: 700; }}
    #rating_HARD {{ background: {t['hard']}; color: white; border-radius: 12px; padding: 14px; font-weight: 700; }}
    #rating_GOOD {{ background: {t['good']}; color: white; border-radius: 12px; padding: 14px; font-weight: 700; }}
    #rating_EASY {{ background: {t['easy']}; color: white; border-radius: 12px; padding: 14px; font-weight: 700; }}
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
      background: {t['bg2']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 8px;
    }}
    QPushButton {{ cursor: pointer; }}
    QTableWidget {{ background: {t['card']}; border: 1px solid {t['border']}; gridline-color: {t['border']}; }}
    QHeaderView::section {{ background: {t['bg2']}; color: {t['muted']};
                            border: 0; padding: 8px; font-weight: 700; }}
    QTableWidget::item:selected {{ background: {t['accent']}; color: {t['bg']}; }}
    QStatusBar {{ background: {t['bg2']}; color: {t['muted']}; }}
    """

def apply_theme(app, name: str = "dark"):
    global _current
    _current = DARK if name == "dark" else LIGHT
    app.setStyleSheet(qss(_current))