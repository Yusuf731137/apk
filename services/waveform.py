from __future__ import annotations
from pathlib import Path
from typing import Optional


def extract_peaks(path: Path, points: int = 200) -> Optional[list[float]]:
    """Return normalized peak amplitudes in [0,1], or None if libs missing."""
    try:
        import numpy as np
        import soundfile as sf
    except Exception:
        return None
    try:
        data, _sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:
        return None
    if data.size == 0:
        return [0.0] * points
    mono = data.mean(axis=1)
    n = len(mono)
    chunk = max(1, n // points)
    peaks: list[float] = []
    for i in range(points):
        seg = mono[i * chunk:(i + 1) * chunk]
        peaks.append(float(np.max(np.abs(seg))) if seg.size else 0.0)
    m = max(peaks) or 1.0
    return [p / m for p in peaks]