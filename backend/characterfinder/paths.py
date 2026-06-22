"""Character Finder 数据路径与 entry_key 编解码。"""
from __future__ import annotations
from backend.config import settings

_VALID_KINDS = ("char", "artist")
_VALID_SOURCES = ("danbooru", "e621", "anima")

CHARACTERS_DB = settings.CF_DIR / "characters.db"
ARTISTS_DB = settings.CF_DIR / "artists.db"
ANIMA_CHARACTERS_DB = settings.CF_DIR / "anima_characters.db"
ANIMA_ARTISTS_DB = settings.CF_DIR / "anima_artists.db"
DANBOORU_TAGS_CSV = settings.CF_DIR / "danbooru_tags.csv"
COVERS_DIR = settings.CF_COVERS_DIR
ARTIST_COVERS_DIR = settings.CF_ARTIST_COVERS_DIR
ANIMA_DIR = settings.CF_ANIMA_DIR
# animadex 内部拉取产物（fetch_anima.py 产生/读取；SOURCE_DIR/TOKEN_PATH 字面一致，注释互引）
ANIMA_SOURCE_DIR = settings.CF_DIR / "_anima_source"
ANIMA_TOKEN_PATH = ANIMA_SOURCE_DIR / ".token"
OVERLAY_DB = settings.CF_OVERLAY_DB
OVERLAY_DIR = settings.CF_OVERLAY_DIR


def entry_key(kind: str, source: str, key: str) -> str:
    """kind∈{char,artist}, source∈{danbooru,e621,anima}, key=库主键。"""
    if kind not in _VALID_KINDS:
        raise ValueError(f"bad kind {kind!r}")
    if source not in _VALID_SOURCES:
        raise ValueError(f"bad source {source!r}")
    if not key:
        raise ValueError("empty key")
    return f"{kind}:{source}:{key}"


def parse_entry_key(ek: str) -> tuple[str, str, str]:
    parts = ek.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"bad entry_key {ek!r}")
    kind, source, key = parts
    if kind not in _VALID_KINDS or source not in _VALID_SOURCES or not key:
        raise ValueError(f"bad entry_key {ek!r}")
    return kind, source, key
