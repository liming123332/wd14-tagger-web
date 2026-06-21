import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.config.settings.CF_FAVORITES_PATH", tmp_path / "cf/fav.json")
    monkeypatch.setattr("backend.config.settings.CF_RECENT_PATH", tmp_path / "cf/recent.json")
    monkeypatch.setattr("backend.characterfinder.paths.ARTISTS_DB", tmp_path / "cf/artists.db")
    for f in (deps.get_artist_db, deps.get_cf_overlay, deps.get_cf_artist_favorites, deps.get_cf_recent):
        f.cache_clear()
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/artists.db")
    c.executescript("CREATE TABLE artists(id INTEGER PRIMARY KEY, name TEXT, tag TEXT, display_name TEXT, image_url_1 TEXT, image_url_2 TEXT, ref_count INTEGER, source TEXT DEFAULT 'danbooru', rank INTEGER)")
    c.execute("INSERT INTO artists(id,name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(1,'ebifurya','ebifurya','ebifurya','http://x/1.jpg','http://x/2.jpg',1,'danbooru')")
    c.commit(); c.close()
    return create_app()


def test_artist_search_and_detail(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/artists", params={"query": "ebi", "source": "danbooru"})
    assert r.json()["total"] == 1
    it = r.json()["items"][0]
    assert it["entry_key"] == "artist:danbooru:1"
    d = client.get("/api/cf/artist", params={"source": "danbooru", "key": "1"}).json()
    assert "ebifurya" in d["locked_tags"]
    assert "/api/cf/asset" in d["thumb1_url"]


def test_random(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/random", params={"type": "artists", "source": "danbooru", "size": 5})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


# Task 11 Fix Important-1：anima 详情 key 不存在时必须返回 404（而非 500 KeyError）。
# anima artists 表 DDL 与 tests/test_cf_anima_db.py 保持一致（sdcf import_anima.py 结构）。
_ANIMA_ARTIST_DDL = """
CREATE TABLE artists (
    artist TEXT, name TEXT, name_lower TEXT, trigger TEXT, count INTEGER,
    url TEXT, imgname TEXT, thumbname TEXT, score REAL, search_blob TEXT,
    image_version INTEGER
);
"""


def test_anima_artist_detail_404_on_missing_key(tmp_path, monkeypatch):
    # 复用 _app 的 danbooru 基线配置，再叠加 anima 路径 + 空 anima db
    app = _app(tmp_path, monkeypatch)
    anima_db_path = tmp_path / "cf/anima_artists.db"
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_ARTISTS_DB", anima_db_path)
    # 建一个空的 anima artists db：表存在但无任何行，get_by_artist 返回 None
    c = sqlite3.connect(anima_db_path)
    c.executescript(_ANIMA_ARTIST_DDL)
    c.commit(); c.close()
    # _app 未 cache_clear anima 工厂，此处补上，确保新 path 生效
    deps.get_anima_artist_db.cache_clear()
    client = TestClient(app)
    r = client.get("/api/cf/artist", params={"source": "anima", "key": "nonexistent"})
    assert r.status_code == 404

