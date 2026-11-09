"""Local-only TTS providers: system SAPI (pyttsx3) and Piper (offline neural)."""
from __future__ import annotations
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class TTSProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def available_voices(self) -> list[dict]:
        """[{id, name, language}]"""

    @abstractmethod
    def synthesize(self, text: str, voice: Optional[str], lang: str,
                   rate: float, out_path: Path) -> None:
        """Generate audio file at out_path."""


class SystemTTS(TTSProvider):
    """Local TTS via pyttsx3 — uses OS SAPI/NSSpeech/Speech Dispatcher voices."""
    name = "system"

    def available_voices(self) -> list[dict]:
        try:
            import pyttsx3
        except ImportError:
            return []
        try:
            engine = pyttsx3.init()
            out = []
            for v in engine.getProperty("voices"):
                langs = getattr(v, "languages", []) or []
                lang = ""
                if langs:
                    first = langs[0]
                    if isinstance(first, bytes):
                        try:
                            lang = first.decode("utf-8", errors="ignore")
                        except Exception:
                            lang = ""
                    else:
                        lang = str(first)
                out.append({"id": v.id, "name": v.name, "language": lang})
            try: engine.stop()
            except Exception: pass
            return out
        except Exception:
            return []

    def synthesize(self, text: str, voice: Optional[str], lang: str,
                   rate: float, out_path: Path) -> None:
        import pyttsx3
        engine = pyttsx3.init()
        try:
            if voice:
                try:
                    engine.setProperty("voice", voice)
                except Exception:
                    pass
            engine.setProperty("rate", int(165 * max(0.5, min(2.0, rate))))
            out_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(text, str(out_path))
            engine.runAndWait()
        finally:
            try: engine.stop()
            except Exception: pass
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("لم يُنتج محرك النظام أي صوت.")


class PiperTTS(TTSProvider):
    """Offline neural TTS via Piper (https://github.com/rhasspy/piper).

    Requires `pip install piper-tts` and a downloaded model (.onnx + .onnx.json)
    placed under ~/.midad-flashcards/piper_models/.
    Run scripts/download_piper_model.py to fetch a model.
    """
    name = "piper"

    def __init__(self):
        self._bin = self._find_binary()

    def is_available(self) -> bool:
        return self._bin is not None

    @staticmethod
    def _find_binary() -> Optional[str]:
        for candidate in ("piper", "piper.exe", "piper-tts"):
            p = shutil.which(candidate)
            if p:
                return p
        return None

    @staticmethod
    def _models_dir() -> Path:
        from core_paths import data_dir
        d = data_dir() / "piper_models"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def available_voices(self) -> list[dict]:
        if not self._bin:
            return []
        out = []
        for onnx in sorted(self._models_dir().glob("*.onnx")):
            name = onnx.stem
            lang = ""
            if "_" in name:
                lang = name.split("_")[0]
            out.append({"id": name, "name": name, "language": lang})
        return out

    def synthesize(self, text: str, voice: Optional[str], lang: str,
                   rate: float, out_path: Path) -> None:
        if not self._bin:
            raise RuntimeError("Piper غير مثبّت. نفّذ: pip install piper-tts")
        model = self._models_dir() / f"{voice}.onnx" if voice else None
        if not model or not model.exists():
            models = list(self._models_dir().glob("*.onnx"))
            if not models:
                raise RuntimeError(
                    "لا نماذج Piper متاحة. شغّل: python scripts/download_piper_model.py")
            model = models[0]
        length_scale = str(1.0 / max(0.5, min(2.0, rate)))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import subprocess
        cmd = [self._bin, "--model", str(model), "--output_file", str(out_path),
               "--length_scale", length_scale]
        try:
            result = subprocess.run(cmd, input=text.encode("utf-8"),
                                    capture_output=True, timeout=45)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("انتهت مهلة توليد Piper TTS.") from e
        if result.returncode != 0:
            msg = (result.stderr or b"").decode("utf-8", errors="ignore")[:200]
            raise RuntimeError(f"Piper فشل: {msg}")
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("Piper لم يُنتج ملف صوت.")


class TTSRegistry:
    def __init__(self):
        self._providers: dict[str, TTSProvider] = {}
        self.register(SystemTTS())
        try:
            piper = PiperTTS()
            if piper.is_available():
                self.register(piper)
        except Exception:
            pass

    def register(self, p: TTSProvider) -> None:
        self._providers[p.name] = p

    def get(self, name: str) -> TTSProvider:
        if name in self._providers:
            return self._providers[name]
        return self._providers["system"]

    def names(self) -> list[str]:
        return list(self._providers.keys())