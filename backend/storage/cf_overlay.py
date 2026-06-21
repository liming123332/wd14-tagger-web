"""Overlay 存储：cf_overlay.db（sqlite）+ overlay/<safe_key>/ 替换图。"""
from __future__ import annotations
import json
import re
import shutil
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
        # RLock（可重入）：upsert 持锁时会调用 self.get() 读 existing.created_at，
        # get 内部也获取同一把锁——普通 Lock 不可重入会在此死锁。RLock 允许同线程
        # 多次 acquire，跨线程仍互斥，既保证并发安全又不破坏 upsert→get 的嵌套调用。
        self._lock = threading.RLock()
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
        # 复用 image_path 的穿越校验（filename 含 / \ 或为 . .. 会抛 ValueError），
        # 同时用其 parent 建目录，避免忽略 filename 参数。
        self.image_path(entry_key, filename).parent.mkdir(parents=True, exist_ok=True)

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
        # check_same_thread=False 允许跨线程共享连接，但 sqlite 连接在 C 层非线程安全：
        # get_asset 是 FastAPI sync 端点（run_in_threadpool），列表页几十张卡片并发查 overlay
        # 时不加锁会触发 InterfaceError: bad parameter or other API misuse。execute/fetchone
        # 必须在锁内；_row_to 只读已 fetch 的 Row 字段、不碰连接，放锁外缩短临界区。
        with self._lock:
            r = self._conn.execute("SELECT * FROM overlay WHERE entry_key=?", (entry_key,)).fetchone()
        return self._row_to(r) if r else None

    def upsert(self, ov: CfOverlay) -> CfOverlay:
        # 读-改-写全部在锁内：避免并发 upsert 同一 entry_key 时双方都读到"不存在"
        # 而各自设置 created_at，后写覆盖前者的 created_at（TOCTOU 竞态）。
        with self._lock:
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            existing = self.get(ov.entry_key)
            ov.created_at = existing.created_at or now if existing else now
            ov.updated_at = now
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
                 json.dumps(ov.raw_tags, ensure_ascii=False), ov.created_at, ov.updated_at),
            )
            self._conn.commit()
        return ov

    def delete(self, entry_key: str) -> None:
        # DB 删除优先且独立于目录清理；即便 entry_key 异常（含 / \）导致
        # _dir_for 会抛 ValueError，也不应让已成功的 DB 删除回滚成整体异常。
        with self._lock:
            self._conn.execute("DELETE FROM overlay WHERE entry_key=?", (entry_key,))
            self._conn.commit()
        # 用 _safe_name 直接算路径，绕过 _dir_for 的校验，使目录清理幂等容错。
        d = self.overlay_dir / _safe_name(entry_key)
        try:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
