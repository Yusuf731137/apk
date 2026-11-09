"""Compile translations/*.ts to *.qm using lrelease (if available).

The app works without .qm files thanks to the built-in _AR dictionary
inside core/i18n.py. This script is optional.
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "translations"


def main() -> int:
    lrelease = shutil.which("lrelease") or shutil.which("pyside6-lrelease")
    if not lrelease:
        print("lrelease not found. The app will use built-in fallback translations.")
        return 0
    for ts in ROOT.glob("*.ts"):
        qm = ts.with_suffix(".qm")
        subprocess.run([lrelease, str(ts), "-qm", str(qm)], check=True)
        print("compiled", qm.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())