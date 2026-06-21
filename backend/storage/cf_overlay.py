"""Overlay 存储：cf_overlay.db（sqlite）+ overlay/<safe_key>/ 替换图。"""
from __future__ import annotations
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from backend.models import CfOverlay, CategoryData


def _safe_name(entry_key: str) -> str:
    # 文件系统安全：把 entry_key 中的路径分隔/非法字符替换为 _
    return re.sub(r"[^A-Za-z0-9_.-]", "_", entry_key)


class CfOverlayStore:
    def __init__(self, db_path: Path, overlay_dir: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.overlay_dir = Path(overlay_dir)
        self.overlay_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """CREATE TABLE IF NOT EXISTS overlay (
                entry_key TEXT PRIMARY KEY, kind TEXT NOT NULL,
                custom_tags TEXT, categories TEXT, extras TEXT,
                image_override TEXT, model TEXT,
                gen_threshold REAL, char_threshold REAL,
                raw_tags TEXT, created_at TEXT, updated_at TEXT);
            """
        )
        self._conn.commit()

    def _dir_for(self, entry_key: str) -> Path:
        if "/" in entry_key or "\\" in entry_key:
            raise ValueError("bad entry_key")
        return self.overlay_dir / _safe_name(entry_key)

    def image_path(self, entry_key: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
            raise ValueError("bad image name")
        return self._dir_for(entry_key) / filename

    def set_image(self, entry_key: str, filename: str) -> None:
        self._dir_for(entry_key).mkdir(parents=True, exist_ok=True)

    def _row_to(self, r: sqlite3.Row) -> CfOverlay:
        return CfOverlay(
            entry_key=r["entry_key"], kind=r["kind"],
            custom_tags=json.loads(r["custom_tags"] or "[]"),
            categories={k: CategoryData(**v) for k, v in json.loads(r["categories"] or "{}").items()},
            extras=CategoryData(**(json.loads(r["extras"] or "null") or {})),
            image_override=r["image_override"], model=r["model"],
            gen_threshold=r["gen_threshold"], char_threshold=r["char_threshold"],
            raw_tags=json.loads(r["raw_tags"] or "{}"),
            created_at=r["created_at"] or "", updated_at=r["updated_at"] or "",
        )

    def get(self, entry_key: str) -> CfOverlay | None:
        r = self._conn.execute("SELECT * FROM overlay WHERE entry_key=?", (entry_key,)).fetchone()
        return self._row_to(r) if r else None

    def upsert(self, ov: CfOverlay) -> CfOverlay:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        existing = self.get(ov.entry_key)
        ov.created_at = existing.created_at or now if existing else now
        ov.updated_at = now
        with self._lock:
            self._conn.execute(
                """INSERT INTO overlay(entry_key,kind,custom_tags,categories,extras,image_override,
                      model,gen_threshold,char_threshold,raw_tags,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(entry_key) DO UPDATE SET
                      kind=excluded.kind, custom_tags=excluded.custom_tags,
                      categories=excluded.categories, extras=excluded.extras,
                      image_override=excluded.image_override, model=excluded.model,
                      gen_threshold=excluded.gen_threshold, char_threshold=excluded.char_threshold,
                      raw_tags=excluded.raw_tags, updated_at=excluded.updated_at""",
                (ov.entry_key, ov.kind, json.dumps(ov.custom_tags, ensure_ascii=False),
                 json.dumps({k: v.model_dump() for k, v in ov.categories.items()}, ensure_ascii=False),
                 json.dumps(ov.extras.model_dump(), ensure_ascii=False), ov.image_override,
                 ov.model, ov.gen_threshold, ov.char_threshold,
                 json.dumps(ov.raw_tags), ov.created_at, ov.updated_at),
            )
            self._conn.commit()
        return ov

    def delete(self, entry_key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM overlay WHERE entry_key=?", (entry_key,))
            self._conn.commit()
        import shutil
        d = self._dir_for(entry_key)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
