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


def _char_db_multi(tmp_path):
    """插 5 行不同角色（name/rank 各异），用于分页语义测试。"""
    p = tmp_path / "characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    rows = [
        ("hatsune miku", "vocaloid", "hatsune miku, vocaloid", "http://x/1.jpg", 1, "danbooru"),
        ("saber", "fate", "saber, fate", "http://x/2.jpg", 2, "danbooru"),
        ("rem", "re:zero", "rem, re:zero", "http://x/3.jpg", 3, "danbooru"),
        ("megurine luka", "vocaloid", "megurine luka, vocaloid", "http://x/4.jpg", 4, "danbooru"),
        ("asuna", "sword art online", "asuna, sao", "http://x/5.jpg", 5, "danbooru"),
    ]
    for r in rows:
        c.execute("INSERT INTO characters(name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?)", r)
    c.commit(); c.close()
    return CharacterDB(p)


def test_char_search_total_pagination(tmp_path):
    """CharacterDB.search 的 total = COUNT(*)（符合筛选总数），不受 limit 影响。"""
    db = _char_db_multi(tmp_path)
    rows, total = db.search("", limit=2, offset=0)
    assert total == 5, "total 必须是筛选总数（5），而不是 limit 后行数"
    assert len(rows) == 2, "limit=2 应只返回 2 行"


def test_artist_search_total_pagination(tmp_path):
    """ArtistDB.search 的 total = COUNT(*)（符合筛选总数），不受 limit 影响。"""
    p = tmp_path / "artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    artists = [
        ("ebifurya", "ebifurya", "ebifurya", "http://x/1.jpg", "http://x/2.jpg", 1, "danbooru"),
        ("artist_b", "artist_b", "Artist B", "http://x/3.jpg", "http://x/4.jpg", 2, "danbooru"),
        ("artist_c", "artist_c", "Artist C", "http://x/5.jpg", "http://x/6.jpg", 3, "danbooru"),
        ("artist_d", "artist_d", "Artist D", "http://x/7.jpg", "http://x/8.jpg", 4, "danbooru"),
        ("artist_e", "artist_e", "Artist E", "http://x/9.jpg", "http://x/10.jpg", 5, "danbooru"),
    ]
    for a in artists:
        c.execute("INSERT INTO artists(name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(?,?,?,?,?,?,?)", a)
    c.commit(); c.close()
    adb = ArtistDB(p)
    rows, total = adb.search("", limit=2)
    assert total == 5, "total 必须是筛选总数（5），而不是 limit 后行数"
    assert len(rows) == 2, "limit=2 应只返回 2 行"


def test_char_get_by_id_dict_get_contract(tmp_path):
    """get_by_id 返回值必须支持 .get() 访问（防回归到 sqlite3.Row）。"""
    db = _char_db(tmp_path)
    got = db.get_by_id(1)
    assert got is not None
    assert got.get("name") == "hatsune miku", "返回 dict 必须支持 .get() 访问"
    assert got.get("nonexistent_key") is None, "dict.get() 对缺失键应返回 None"
