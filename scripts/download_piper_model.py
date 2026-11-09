"""Download a Piper voice model to the app's models directory.

Usage:
    python scripts/download_piper_model.py [voice_name]

Voice examples:
    ar_JO-kareem-low         (Arabic, small)
    ar_JO-kareem-medium      (Arabic, medium - better quality)
    en_US-lessac-medium      (English US)
    en_GB-alan-medium        (English GB)
"""
import sys
import urllib.request
from pathlib import Path

VOICES = {
    "ar_JO-kareem-low": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/low/ar_JO-kareem-low.onnx",
    "ar_JO-kareem-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx",
    "en_US-lessac-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
    "en_GB-alan-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
}


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core_paths import data_dir

    out = data_dir() / "piper_models"
    out.mkdir(parents=True, exist_ok=True)

    name = sys.argv[1] if len(sys.argv) > 1 else "ar_JO-kareem-low"
    if name not in VOICES:
        print(f"Unknown voice: {name}")
        print("Available:", ", ".join(VOICES.keys()))
        return 1

    url = VOICES[name]
    onnx_target = out / f"{name}.onnx"
    json_target = out / f"{name}.onnx.json"

    print(f"Downloading model  -> {onnx_target}")
    urllib.request.urlretrieve(url, onnx_target)
    print(f"Downloading config -> {json_target}")
    urllib.request.urlretrieve(url + ".json", json_target)
    print("Done. Restart the app, then choose 'piper' as the TTS provider.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())