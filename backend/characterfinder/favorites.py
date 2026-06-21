"""角色/艺术家收藏与最近查看（json 持久化，key 为 entry_key）。"""
from __future__ import annotations
import json
from pathlib import Path
from backend.config import settings


class _JsonSetStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            return []

    def _save(self, items: list[str]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


class FavoritesDB(_JsonSetStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path if path is not None else settings.CF_FAVORITES_PATH)

    def get_all(self) -> list[str]:
        return self._load()

    def is_favorite(self, entry_key: str) -> bool:
        return entry_key in self._load()

    def toggle(self, entry_key: str) -> bool:
        items = self._load()
        if entry_key in items:
            items.remove(entry_key); self._save(items); return False
        items.append(entry_key); self._save(items); return True


class ArtistFavoritesDB(FavoritesDB):
    pass  # 结构同 FavoritesDB，独立文件以便前端分类展示


class SearchHistoryDB(_JsonSetStore):
    MAX = 100

    def __init__(self, path: Path | None = None):
        super().__init__(path if path is not None else settings.CF_RECENT_PATH)

    def get_all(self) -> list[str]:
        return self._load()

    def add(self, entry_key: str) -> None:
        items = self._load()
        if entry_key in items:
            items.remove(entry_key)
        items.insert(0, entry_key)
        del items[self.MAX:]
        self._save(items)
