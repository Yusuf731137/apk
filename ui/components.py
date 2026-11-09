from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QSlider, QComboBox,
)
from ui.theme import palette, qss  # qss unused here; palette only


class StatCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        self.value = QLabel("0"); self.value.setObjectName("statNumber")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)
        cap = QLabel(title); cap.setObjectName("muted")
        lay.addWidget(self.value); lay.addWidget(cap)


class BarChart(QWidget):
    """Vertical bar chart for grade distribution."""
    def __init__(self, labels: list[str], colors: list[str]):
        super().__init__()
        self.labels, self.colors = labels, colors
        self.values = [0] * len(labels)
        self.setMinimumHeight(180)

    def set_values(self, values: list[int]):
        self.values = list(values)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not w or not h: return
        pad_l, pad_r, pad_t, pad_b = 20, 20, 20, 40
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b
        n = len(self.values)
        if n == 0: return
        bw = max(12, chart_w // n - 8)
        mx = max(self.values) or 1
        accent = QColor(palette()["text"])
        for i, (lab, val, col) in enumerate(zip(self.labels, self.values, self.colors)):
            bar_h = int((val / mx) * (chart_h - 4))
            x = pad_l + i * (chart_w // n) + (chart_w // n - bw) // 2
            y = pad_t + (chart_h - bar_h)
            p.setBrush(QBrush(QColor(col)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, bw, bar_h, 4, 4)
            p.setPen(QPen(accent))
            p.drawText(x - 20, y - 6, bw + 40, 16, Qt.AlignmentFlag.AlignCenter, str(val))
            p.drawText(x - 20, pad_t + chart_h + 8, bw + 40, 20,
                       Qt.AlignmentFlag.AlignCenter, lab)


class WaveformWidget(QWidget):
    seek = pyqtSignal(float)  # 0.0-1.0 fraction

    def __init__(self):
        super().__init__()
        self.peaks: list[float] = []
        self.progress = 0.0
        self.setMinimumHeight(70)

    def set_peaks(self, peaks: list[float]):
        self.peaks = list(peaks)
        self.update()

    def set_progress(self, p: float):
        self.progress = max(0.0, min(1.0, p))
        self.update()

    def mousePressEvent(self, ev):
        if self.width() > 0:
            frac = ev.position().x() / self.width()
            self.seek.emit(max(0.0, min(1.0, frac)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not self.peaks or w <= 0:
            p.setPen(QColor(palette()["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "لا توجد بيانات موجة (ثبّت soundfile)" if not self.peaks else "")
            return
        accent = QColor(palette()["accent"])
        dim = QColor(palette()["border"])
        n = len(self.peaks)
        bw = max(1, w // n)
        mid = h / 2
        for i, amp in enumerate(self.peaks):
            bh = max(2, int(amp * (h - 6)))
            x = i * bw
            color = accent if (i / n) <= self.progress else dim
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(x, int(mid - bh / 2), max(1, bw - 1), bh)


class AudioPlayer(QFrame):
    """Play/pause, seek, waveform, speed, time display."""
    request_tts = pyqtSignal()  # emitted when no source & user clicks play

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.9)

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(44)
        self.play_btn.clicked.connect(self._toggle)
        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setObjectName("muted")
        self.speed = QComboBox()
        for s in ("0.5", "0.75", "1.0", "1.25", "1.5", "2.0"):
            self.speed.addItem(f"{s}×", float(s))
        self.speed.setCurrentText("1.0×")
        self.speed.currentIndexChanged.connect(self._apply_speed)
        row.addWidget(self.play_btn)
        row.addWidget(self.time_lbl, 1)
        row.addWidget(self.speed)
        self.wave = WaveformWidget()
        self.wave.seek.connect(self._seek)
        lay.addLayout(row)
        lay.addWidget(self.wave)

        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(self._on_dur)
        self.player.playbackStateChanged.connect(self._on_state)
        self._duration = 0
        self._has_source = False

    def set_source(self, path: Path | None):
        self._has_source = path is not None and path.exists()
        if not self._has_source:
            self.player.setSource(QUrl())
            self.wave.set_peaks([])
            self.time_lbl.setText("0:00 / 0:00")
            return
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.wave.set_peaks([])
        self._load_waveform(path)

    def _load_waveform(self, path: Path):
        from ui.workers import WaveformWorker
        self._wf = WaveformWorker(path)
        self._wf.done.connect(self.wave.set_peaks)
        self._wf.start()

    def _toggle(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        if not self._has_source:
            self.request_tts.emit()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def play(self):
        if self._has_source: self.player.play()

    def stop(self):
        self.player.stop()

    def _seek(self, frac: float):
        if self._duration: self.player.setPosition(int(self._duration * frac))

    def _apply_speed(self, _):
        rate = self.speed.currentData() or 1.0
        self.player.setPlaybackRate(float(rate))

    def _on_pos(self, ms: int):
        if self._duration:
            self.wave.set_progress(ms / self._duration)
        self.time_lbl.setText(f"{self._fmt(ms)} / {self._fmt(self._duration)}")

    def _on_dur(self, ms: int):
        self._duration = ms

    def _on_state(self, st):
        from PyQt6.QtMultimedia import QMediaPlayer
        self.play_btn.setText("⏸" if st == QMediaPlayer.PlaybackState.PlayingState else "▶")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = ms // 1000
        return f"{s//60}:{s%60:02d}"