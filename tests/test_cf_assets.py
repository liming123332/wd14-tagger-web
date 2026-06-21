import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps
from backend.characterfinder import paths


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.characterfinder.paths.CHARACTERS_DB", tmp_path / "cf/characters.db")
    monkeypatch.setattr("backend.characterfinder.paths.COVERS_DIR", tmp_path / "cf/covers")
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_DIR", tmp_path / "cf/anima")
    for f in (deps.get_character_db, deps.get_artist_db, deps.get_anima_character_db,
              deps.get_anima_artist_db, deps.get_cf_overlay):
        f.cache_clear()
    # 建小 characters.db
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/characters.db")
    c.executescript("CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')")
    c.execute("INSERT INTO characters(id,name,image_url,source) VALUES(1,'miku','http://host/preview/miku.jpg','danbooru')")
    c.commit(); c.close()
    return create_app()


def test_local_cover_served(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    (tmp_path / "cf" / "covers").mkdir()
    (tmp_path / "cf" / "covers" / "miku.jpg").write_bytes(b"JPGDATA")
    r = client.get("/api/cf/asset", params={"kind": "char", "source": "danbooru", "key": "1", "which": "thumb"})
    assert r.status_code == 200 and r.content == b"JPGDATA"


def test_missing_falls_back_to_cdn(tmp_path, monkeypatch):
    # starlette 1.x TestClient 默认 follow_redirects=True，会跟随 307 到外部 URL；
    # 这里要直接断言重定向本身，故关闭跟随。
    client = TestClient(_app(tmp_path, monkeypatch), follow_redirects=False)
    r = client.get("/api/cf/asset", params={"kind": "char", "source": "danbooru", "key": "1", "which": "thumb"})
    assert r.status_code == 307
    assert r.headers["location"] == "http://host/preview/miku.jpg"
