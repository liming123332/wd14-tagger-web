import sqlite3
import pytest
from backend.characterfinder.character_db import CharacterDB
from backend.characterfinder.artist_db import ArtistDB

# characters.db 的 DDL（与 sdcf scrape_characters.py 一致）
CHAR_DDL = """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, series TEXT,
    tags TEXT NOT NULL, image_url TEXT, rank INTEGER UNIQUE,
    danbooru_tag TEXT, source TEXT DEFAULT 'danbooru'
);
"""
ARTIST_DDL = """
CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tag TEXT NOT NULL,
    display_name TEXT NOT NULL, image_url_1 TEXT, image_url_2 TEXT,
    ref_count INTEGER DEFAULT 0, source TEXT DEFAULT 'danbooru', rank INTEGER
);
"""


def _char_db(tmp_path):
    p = tmp_path / "characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    c.execute("INSERT INTO characters(name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?)",
              ("hatsune miku", "vocaloid", "hatsune miku, vocaloid, 1girl, long hair", "http://x/miku.jpg", 1, "danbooru"))
    c.execute("INSERT INTO characters(name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?)",
              ("saber", "fate", "saber, fate/stay night, 1girl", "http://x/saber.jpg", 2, "danbooru"))
    c.commit(); c.close()
    return CharacterDB(p)


def test_search_and_get(tmp_path):
    db = _char_db(tmp_path)
    rows, total = db.search("miku")
    assert total == 1 and rows[0]["name"] == "hatsune miku"
    got = db.get("hatsune miku")
    assert got is not None and "1girl" in got["tags"]


def test_list_series(tmp_path):
    db = _char_db(tmp_path)
    series = db.list_series()
    names = [s[0] for s in series]
    assert "vocaloid" in names and "fate" in names


def test_count_by_source(tmp_path):
    db = _char_db(tmp_path)
    assert db.count_by_source("danbooru") == 2
    assert db.count_by_source("e621") == 0


def test_char_get_by_id(tmp_path):
    db = _char_db(tmp_path)
    g = db.get_by_id(1)
    assert isinstance(g, dict) and g["name"] == "hatsune miku"
    assert db.get_by_id(999) is None


def test_artist_get_by_name(tmp_path):
    p = tmp_path / "artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    c.execute("INSERT INTO artists(name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(?,?,?,?,?,?,?)",
              ("ebifurya", "ebifurya", "ebifurya", "http://x/1.jpg", "http://x/2.jpg", 1, "danbooru"))
    c.commit(); c.close()
    adb = ArtistDB(p)
    a = adb.get_by_name("ebifurya")
    assert a is not None and isinstance(a, dict) and a["tag"] == "ebifurya"


def test_artist_get_by_id(tmp_path):
    p = tmp_path / "artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    c.execute("INSERT INTO artists(name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(?,?,?,?,?,?,?)",
              ("ebifurya", "ebifurya", "ebifurya", "http://x/1.jpg", "http://x/2.jpg", 1, "danbooru"))
    c.commit(); c.close()
    adb = ArtistDB(p)
    a = adb.get_by_id(1)
    assert isinstance(a, dict) and a["tag"] == "ebifurya"
    assert adb.get_by_id(999) is None


def test_artist_search_returns_tuple(tmp_path):
    """ArtistDB.search 必须返回 (list[dict], int) 以匹配 CharacterDB 契约。"""
    p = tmp_path / "artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    c.execute("INSERT INTO artists(name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(?,?,?,?,?,?,?)",
              ("ebifurya", "ebifurya", "ebifurya", "http://x/1.jpg", "http://x/2.jpg", 1, "danbooru"))
    c.commit(); c.close()
    adb = ArtistDB(p)
    rows, total = adb.search("ebi")
    assert total == 1
    assert isinstance(rows[0], dict) and rows[0]["tag"] == "ebifurya"
