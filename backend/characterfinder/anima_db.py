"""
anima_db.py — SQLite DAO for the AnimaDex-derived character and artist catalogues.

Reads anima_characters.db / anima_artists.db (populated by sdcf
scripts/import_anima.py from the animadex.net offline export). The UI fetches
cover images on-demand from https://blobs.animadex.net and caches them locally.

No external dependencies — uses stdlib sqlite3 only.

Ported from sd-character-finder/wildcard_creator/anima_db.py:
- Default DB paths resolve lazily inside __init__ via backend.characterfinder.paths
  (ANIMA_CHARACTERS_DB / ANIMA_ARTISTS_DB), so monkeypatching paths.X takes
  effect at construction time (see _DEFAULT_* NOTE below; mirrors Task 8 fix
  in character_db.py / artist_db.py).
- Module-level singletons removed (_anima_character_db / _anima_artist_db /
  get_anima_character_db / get_anima_artist_db / _get_db_path) — DB instances
  are injected by backend.deps.py (Task 7).
- search() now returns tuple[list[dict], int] (added COUNT(*) total) to match
  CharacterDB/ArtistDB contract for paginated callers (Task 9/11). The sdcf
  original returned only list[dict].
- Single-row getters (get_by_character / get_by_artist) already returned
  dict | None in sdcf — kept as-is so callers can use row.get("field").
- URL helpers (character_thumb_url etc.) kept — they are pure functions, not
  singletons, and downstream code may use them.

Note on search() signature: the sdcf parameter for copyright filtering is named
``copyright`` (NOT ``copyright_filter``). Kept verbatim per Controller ruling.
Task 9 callers must use ``db.search(query, copyright=..., ...)``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from backend.characterfinder import paths

_R2_BASE = "https://blobs.animadex.net"
_CHAR_THUMB_PREFIX = "Outputs/thumbs"
_CHAR_IMG_PREFIX = "Outputs"
_ARTIST_THUMB_PREFIX = "ArtistOutputs/thumbs"
_ARTIST_IMG_PREFIX = "ArtistOutputs"

# NOTE: 不在模块顶层把 paths.ANIMA_CHARACTERS_DB / ANIMA_ARTISTS_DB 绑定到默认参数
# （_DEFAULT_*_DB = paths.X）。顶层绑定会在 import 时固化 Path 对象，之后测试用
# monkeypatch 改 paths.ANIMA_CHARACTERS_DB 无法影响已绑定的默认值，导致跨测试状态泄漏
# （与 Task 8 修过的 character_db.py / artist_db.py 同源缺陷，此处一并修复）。
# 改为 __init__ 内惰性读取 paths.X，保证 monkeypatch 随时生效。


def _r2_quote(name: str) -> str:
    """Quote an R2 object name while preserving the characters the UI/URLs need.

    AnimaDex stores thumbnail filenames derived from the trigger, e.g.
    ``2b (nier_automata), nier (series).webp``.  R2 accepts the raw spaces and
    commas, so we keep them unescaped to keep URLs readable.
    """
    from urllib.parse import quote

    return quote(name, safe="(),")


def character_thumb_url(thumbname: str) -> str:
    return f"{_R2_BASE}/{_CHAR_THUMB_PREFIX}/{_r2_quote(thumbname)}"


def character_image_url(imgname: str) -> str:
    return f"{_R2_BASE}/{_CHAR_IMG_PREFIX}/{_r2_quote(imgname)}"


def artist_thumb_url(thumbname: str) -> str:
    return f"{_R2_BASE}/{_ARTIST_THUMB_PREFIX}/{_r2_quote(thumbname)}"


def artist_image_url(imgname: str) -> str:
    return f"{_R2_BASE}/{_ARTIST_IMG_PREFIX}/{_r2_quote(imgname)}"


class AnimaCharacterDB:
    def __init__(self, path: Optional[Path] = None):
        self.path = path if path is not None else paths.ANIMA_CHARACTERS_DB
        self._ensure_exists()

    def _ensure_exists(self):
        if not self.path.exists():
            raise FileNotFoundError(
                f"Anima character database not found at {self.path}. "
                "Run: python scripts/import_anima.py --token YOUR_TOKEN"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def count(self, query: str = "") -> int:
        with self._connect() as conn:
            if query:
                sql = "SELECT COUNT(*) FROM characters WHERE search_blob LIKE ?"
                params = (f"%{query}%",)
            else:
                sql = "SELECT COUNT(*) FROM characters"
                params = ()
            return conn.execute(sql, params).fetchone()[0]

    def search(
        self,
        query: str = "",
        copyright: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search characters by search_blob, optionally filtered by copyright.

        Returns (list of dict rows, total match count). Total reflects all rows
        matching the filters (ignoring limit/offset), to support pagination —
        consistent with CharacterDB/ArtistDB.search.

        Note: the copyright filter parameter is named ``copyright`` (not
        ``copyright_filter``), matching the sdcf original signature.
        """
        with self._connect() as conn:
            conditions = []
            params: list[Any] = []
            if query:
                conditions.append("search_blob LIKE ?")
                params.append(f"%{query}%")
            if copyright:
                conditions.append("copyright = ?")
                params.append(copyright)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""

            count_params = list(params)
            sql_count = f"SELECT COUNT(*) FROM characters {where}"
            total = conn.execute(sql_count, count_params).fetchone()[0]

            sql = (
                f"SELECT * FROM characters {where} "
                "ORDER BY count DESC, name LIMIT ? OFFSET ?"
            )
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows], total

    def get_by_character(self, character: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM characters WHERE character = ?", (character,)
            ).fetchone()
            return dict(row) if row else None

    def list_copyrights(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT copyright, COUNT(*) AS n FROM characters "
                "WHERE copyright IS NOT NULL AND copyright != '' "
                "GROUP BY copyright ORDER BY n DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]


class AnimaArtistDB:
    def __init__(self, path: Optional[Path] = None):
        self.path = path if path is not None else paths.ANIMA_ARTISTS_DB
        self._ensure_exists()

    def _ensure_exists(self):
        if not self.path.exists():
            raise FileNotFoundError(
                f"Anima artist database not found at {self.path}. "
                "Run: python scripts/import_anima.py --token YOUR_TOKEN"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def count(self, query: str = "") -> int:
        with self._connect() as conn:
            if query:
                sql = "SELECT COUNT(*) FROM artists WHERE search_blob LIKE ?"
                params = (f"%{query}%",)
            else:
                sql = "SELECT COUNT(*) FROM artists"
                params = ()
            return conn.execute(sql, params).fetchone()[0]

    def search(
        self,
        query: str = "",
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search artists by search_blob.

        Returns (list of dict rows, total match count). Total reflects all rows
        matching the filter (ignoring limit/offset), to support pagination —
        consistent with CharacterDB/ArtistDB.search.
        """
        with self._connect() as conn:
            if query:
                where = "WHERE search_blob LIKE ?"
                count_params: list[Any] = [f"%{query}%"]
            else:
                where = ""
                count_params = []

            sql_count = f"SELECT COUNT(*) FROM artists {where}"
            total = conn.execute(sql_count, count_params).fetchone()[0]

            if query:
                sql = (
                    f"SELECT * FROM artists {where} "
                    "ORDER BY count DESC, name LIMIT ? OFFSET ?"
                )
                params = [f"%{query}%", limit, offset]
            else:
                sql = "SELECT * FROM artists ORDER BY count DESC, name LIMIT ? OFFSET ?"
                params = [limit, offset]
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows], total

    def get_by_artist(self, artist: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artists WHERE artist = ?", (artist,)
            ).fetchone()
            return dict(row) if row else None
