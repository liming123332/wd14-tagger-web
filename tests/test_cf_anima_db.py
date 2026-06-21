import sqlite3
import pytest
from backend.characterfinder.anima_db import AnimaCharacterDB, AnimaArtistDB

# characters 表 DDL（与 sdcf scripts/import_anima.py 生成结构一致）
CHAR_DDL = """
CREATE TABLE characters (
    character TEXT, copyright TEXT, name TEXT, trigger TEXT, core_tags TEXT,
    count INTEGER, url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT,
    image_version INTEGER
);
CREATE INDEX idx_char_search ON characters(search_blob);
"""
ARTIST_DDL = """
CREATE TABLE artists (
    artist TEXT, name TEXT, name_lower TEXT, trigger TEXT, count INTEGER,
    url TEXT, imgname TEXT, thumbname TEXT, score REAL, search_blob TEXT,
    image_version INTEGER
);
"""


def _achar(tmp_path):
    p = tmp_path / "anima_characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    c.execute(
        "INSERT INTO characters(character,copyright,name,trigger,core_tags,count,thumbname,imgname,search_blob) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "001_(darling_in_the_franxx)",
            "darling_in_the_franxx",
            "001 (Darling In The Franxx)",
            "001 (darling in the franxx), darling in the franxx",
            "1girl, blue skin",
            111,
            "001 (darling in the franxx), darling in the franxx.webp",
            "001 (darling in the franxx), darling in the franxx.png",
            "001 darling_in_the_franxx",
        ),
    )
    c.commit(); c.close()
    return AnimaCharacterDB(p)


def test_search_and_get_by_character(tmp_path):
    db = _achar(tmp_path)
    rows, total = db.search("001")
    assert total == 1 and "darling" in rows[0]["copyright"]
    got = db.get_by_character("001_(darling_in_the_franxx)")
    assert got is not None and got["thumbname"].endswith(".webp")


def test_list_copyrights(tmp_path):
    db = _achar(tmp_path)
    cops = db.list_copyrights()
    # list_copyrights 返回 list[dict]（dict 化后），用键名访问
    assert any("darling" in c["copyright"] for c in cops)


def _achar_multi(tmp_path):
    """插 5 行不同 character（count 各异），用于分页语义测试。"""
    p = tmp_path / "anima_characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    rows = [
        ("char_a", "series_x", "Char A", "char a", "1girl", 100, "a.webp", "a.png", "char a series_x"),
        ("char_b", "series_x", "Char B", "char b", "1girl", 90, "b.webp", "b.png", "char b series_x"),
        ("char_c", "series_y", "Char C", "char c", "1girl", 80, "c.webp", "c.png", "char c series_y"),
        ("char_d", "series_y", "Char D", "char d", "1girl", 70, "d.webp", "d.png", "char d series_y"),
        ("char_e", "series_z", "Char E", "char e", "1girl", 60, "e.webp", "e.png", "char e series_z"),
    ]
    for r in rows:
        c.execute(
            "INSERT INTO characters(character,copyright,name,trigger,core_tags,count,thumbname,imgname,search_blob) VALUES(?,?,?,?,?,?,?,?,?)",
            r,
        )
    c.commit(); c.close()
    return AnimaCharacterDB(p)


def test_char_search_total_pagination(tmp_path):
    """AnimaCharacterDB.search 的 total = COUNT(*)（符合筛选总数），不受 limit 影响。"""
    db = _achar_multi(tmp_path)
    rows, total = db.search("", limit=2, offset=0)
    assert total == 5, "total 必须是筛选总数（5），而不是 limit 后行数"
    assert len(rows) == 2, "limit=2 应只返回 2 行"


def test_char_get_by_character_dict_get_contract(tmp_path):
    """get_by_character 返回值必须支持 .get() 访问（防回归到 sqlite3.Row）。"""
    db = _achar(tmp_path)
    got = db.get_by_character("001_(darling_in_the_franxx)")
    assert got is not None
    assert got.get("name") == "001 (Darling In The Franxx)", "返回 dict 必须支持 .get() 访问"
    assert got.get("nonexistent_key") is None, "dict.get() 对缺失键应返回 None"


# ------------------------- AnimaArtistDB -------------------------

def _aartist(tmp_path):
    p = tmp_path / "anima_artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    c.execute(
        "INSERT INTO artists(artist,name,name_lower,trigger,count,url,imgname,thumbname,score,search_blob) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "ciloranko",
            "Ciloranko",
            "ciloranko",
            "ciloranko",
            500,
            "https://example.com/ciloranko",
            "ciloranko.png",
            "ciloranko.webp",
            9.5,
            "ciloranko",
        ),
    )
    c.commit(); c.close()
    return AnimaArtistDB(p)


def test_artist_search_returns_tuple(tmp_path):
    """AnimaArtistDB.search 必须返回 (list[dict], int)。"""
    db = _aartist(tmp_path)
    rows, total = db.search("ciloranko")
    assert total == 1
    assert isinstance(rows[0], dict) and rows[0]["artist"] == "ciloranko"


def test_artist_get_by_artist_dict(tmp_path):
    """AnimaArtistDB.get_by_artist 必须返回 dict | None。"""
    db = _aartist(tmp_path)
    got = db.get_by_artist("ciloranko")
    assert got is not None
    assert isinstance(got, dict)
    assert got.get("name") == "Ciloranko", "返回 dict 必须支持 .get() 访问"
    assert got.get("nonexistent_key") is None
    assert db.get_by_artist("nope") is None
