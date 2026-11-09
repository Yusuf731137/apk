from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class TTSWorker(QThread):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, cache, text: str, lang: str, provider, voice: str, rate: float):
        super().__init__()
        self.cache, self.text, self.lang, self.provider = cache, text, lang, provider
        self.voice, self.rate = voice, rate
        self._cancelled = False

    def cancel(self): self._cancelled = True

    def run(self):
        try:
            if self._cancelled: return
            p = self.cache.get_or_create(self.text, self.lang, self.provider, self.voice, self.rate)
            if not self._cancelled:
                self.done.emit(str(p))
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(str(e))


class WaveformWorker(QThread):
    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, path: Path, points: int = 200):
        super().__init__()
        self.path, self.points = path, points

    def run(self):
        try:
            from services.waveform import extract_peaks
            peaks = extract_peaks(self.path, self.points)
            if peaks is None:
                self.failed.emit("soundfile غير متاح")
            else:
                self.done.emit(peaks)
        except Exception as e:
            self.failed.emit(str(e))


class ImportWorker(QThread):
    done = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.failed.emit(str(e))