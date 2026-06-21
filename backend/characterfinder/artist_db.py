"""
artist_db.py — SQLite-backed artist style reference browser for the Character Finder.

Reads artists.db (populated by sdcf scrape_artists.py).
No external dependencies — uses stdlib sqlite3 only.

Ported from sd-character-finder/wildcard_creator/artist_db.py:
- _DEFAULT_DB now resolves via backend.characterfinder.paths.ARTISTS_DB
- Module-level singleton (get_artist_db) removed —
  DB instances are injected by backend.deps.py (Task 7).
- search() now returns tuple[list[dict], int] (added COUNT(*) total) to match
  CharacterDB's contract for paginated callers (Task 9/11).
- get_by_id / get_by_name now return dict | None (dict(row) wrapped) so callers
  can use row.get("field") (Task 8/9/11).

Usage:
    from backend.characterfinder.artist_db import ArtistDB
    db = ArtistDB()
    rows, total = db.search("hammer")
    artist = db.get_by_name("hammer_(sunset_beach)")
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from backend.characterfinder import paths

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFAULT_DB = paths.ARTISTS_DB


# ---------------------------------------------------------------------------
# ArtistDB
# ---------------------------------------------------------------------------

class ArtistDB:
    def __init__(self, db_path: Path = _DEFAULT_DB):
        self._path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._write_lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            # Prevents 'database disk image is malformed' on git pull updates by discarding orphaned WAL files
            try:
                wal = self._path.with_name(self._path.name + "-wal")
                shm = self._path.with_name(self._path.name + "-shm")
                if wal.exists():
                    wal.unlink()
                if shm.exists():
                    shm.unlink()
            except Exception:
                pass

            self._conn = sqlite3.connect(str(self._path), check_same_thread=False, timeout=15.0)
            self._conn.row_factory = sqlite3.Row
            try:
                self._conn.execute("PRAGMA journal_mode=DELETE")
                self._conn.execute("PRAGMA busy_timeout=15000")
                self._conn.execute("PRAGMA synchronous=NORMAL")
            except sqlite3.OperationalError:
                pass
            self._migrate()
        return self._conn

    def _migrate(self) -> None:
        """Ensure schema exists (for fresh DBs)."""
        with self._write_lock:
            ddl = """
            CREATE TABLE IF NOT EXISTS artists (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                tag           TEXT NOT NULL,
                display_name  TEXT NOT NULL,
                image_url_1   TEXT,
                image_url_2   TEXT,
                ref_count     INTEGER DEFAULT 0,
                source        TEXT DEFAULT 'danbooru',
                rank          INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_artist_name   ON artists(name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_artist_tag    ON artists(tag COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_artist_source ON artists(source);
            CREATE INDEX IF NOT EXISTS idx_artist_rank   ON artists(rank);
            """
            self._conn.executescript(ddl)
            self._conn.commit()

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        source: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Search artists by name/tag with optional source filter.

        Returns (list of dicts, total match count). Total reflects all rows
        matching the filters (ignoring limit/offset), to support pagination —
        consistent with CharacterDB.search.
        """
        conn = self._get_conn()
        params: list = []
        where_clauses = []

        if query and query.strip():
            terms = [t.strip() for t in query.strip().split() if t.strip()]
            if terms:
                term_conditions = []
                for term in terms:
                    term_conditions.append("(name LIKE ? OR tag LIKE ? OR display_name LIKE ?)")
                    like = f"%{term}%"
                    params.extend([like, like, like])
                where_clauses.append("(" + " AND ".join(term_conditions) + ")")

        if source and source != "all":
            where_clauses.append("source = ?")
            params.append(source)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql_count = f"SELECT COUNT(*) FROM artists {where_sql}"
        sql = f"SELECT * FROM artists {where_sql} ORDER BY rank ASC LIMIT ? OFFSET ?"

        count_params = list(params)
        params.extend([limit, offset])

        try:
            total = conn.execute(sql_count, count_params).fetchone()[0]
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows], total
        except Exception as e:
            logger.error(
                f"search failed: query={query!r}, source={source!r}, error={e}",
                exc_info=True,
            )
            return [], 0

    def count(
        self,
        query: str = "",
        source: str | None = None,
    ) -> int:
        """Count total artists matching filters."""
        conn = self._get_conn()
        params: list = []
        where_clauses = []

        if query and query.strip():
            terms = [t.strip() for t in query.strip().split() if t.strip()]
            if terms:
                term_conditions = []
                for term in terms:
                    term_conditions.append("(name LIKE ? OR tag LIKE ? OR display_name LIKE ?)")
                    like = f"%{term}%"
                    params.extend([like, like, like])
                where_clauses.append("(" + " AND ".join(term_conditions) + ")")

        if source and source != "all":
            where_clauses.append("source = ?")
            params.append(source)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"SELECT COUNT(*) FROM artists {where_sql}"

        row = conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    def get_by_id(self, artist_id: int) -> Optional[dict]:
        """Get a single artist by ID. Returns dict | None."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM artists WHERE id = ?", (artist_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_by_name(self, name: str) -> Optional[dict]:
        """Get a single artist by exact name match. Returns dict | None."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM artists WHERE name = ? COLLATE NOCASE", (name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_sources(self) -> list[str]:
        """Return all distinct sources in the DB."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT DISTINCT source FROM artists ORDER BY source")
        return [row[0] for row in cursor.fetchall()]

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def total_count(self) -> int:
        """Total number of artists in the DB."""
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM artists").fetchone()
        return row[0] if row else 0

    def count_unique(self) -> int:
        """Count distinct canonical artist entities across all sources.

        Deduplication strips a leading '@' and normalizes spaces so the same
        artist appearing in Danbooru and Anima counts once.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT COALESCE(NULLIF(tag, ''), NULLIF(name, ''), display_name) AS token FROM artists"
        ).fetchall()
        seen: set[str] = set()
        for (token,) in rows:
            if not token:
                continue
            key = token.strip().lower().lstrip("@")
            key = key.replace("_", " ")
            key = " ".join(key.split())
            if key:
                seen.add(key)
        return len(seen)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
