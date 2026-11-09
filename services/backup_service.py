from __future__ import annotations
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


class BackupService:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.dir = self.db_path.parent

    def list_backups(self) -> list[dict]:
        out = []
        for p in sorted(self.dir.glob(f"{self.db_path.stem}.bak-*.sqlite3"), reverse=True):
            st = p.stat()
            out.append({
                "path": p,
                "filename": p.name,
                "size": st.st_size,
                "created": datetime.fromtimestamp(st.st_mtime),
            })
        return out

    def validate(self, path: Path) -> tuple[bool, str]:
        if not path.exists():
            return False, "الملف غير موجود."
        try:
            conn = sqlite3.connect(path)
            try:
                r = conn.execute("PRAGMA integrity_check").fetchone()
                if r[0] != "ok":
                    return False, f"فحص التكامل فشل: {r[0]}"
                tables = {x[0] for x in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"cards", "decks"}.issubset(tables):
                    return False, "قاعدة البيانات لا تحتوي الجداول المطلوبة."
            finally:
                conn.close()
            return True, ""
        except sqlite3.DatabaseError as e:
            return False, f"ملف SQLite تالف: {e}"

    def create_safety_backup(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = self.db_path.with_suffix(f".bak-{ts}.sqlite3")
        if self.db_path.exists():
            shutil.copy2(self.db_path, dest)
        return dest

    def restore(self, backup_path: Path) -> Path:
        ok, err = self.validate(backup_path)
        if not ok:
            raise ValueError(err)

        safety = self.create_safety_backup()
        staged = self.db_path.with_suffix(".restore.tmp")
        shutil.copy2(backup_path, staged)

        ok, err = self.validate(staged)
        if not ok:
            staged.unlink(missing_ok=True)
            raise ValueError(f"النسخة الاحتياطية تالفة بعد النسخ: {err}")

        os.replace(staged, self.db_path)

        ok, err = self.validate(self.db_path)
        if not ok:
            shutil.copy2(safety, self.db_path)
            raise ValueError(f"فشل التحقق بعد الاستعادة، تم التراجع: {err}")

        return safety