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
    monkeypatch.setattr("backend.characterfinder.paths.CHARACTERS_DB", tmp_path / "cf/characters.db")
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_CHARACTERS_DB", tmp_path / "cf/anima_characters.db")
    for f in (deps.get_character_db, deps.get_anima_character_db, deps.get_cf_overlay,
              deps.get_cf_favorites, deps.get_cf_recent):
        f.cache_clear()
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/characters.db")
    c.executescript("CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')")
    c.execute("INSERT INTO characters(id,name,series,tags,image_url,rank,source) VALUES(1,'miku','vocaloid','miku, vocaloid, 1girl','http://x/miku.jpg',1,'danbooru')")
    c.commit(); c.close()
    return create_app()


def test_search_returns_entry_shape(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/characters", params={"query": "miku", "source": "danbooru"})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 1
    it = d["items"][0]
    assert it["entry_key"] == "char:danbooru:1"
    assert it["name"] == "miku"
    assert "/api/cf/asset" in it["thumb_url"]


def test_get_detail_includes_locked_tags(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"})
    assert r.status_code == 200
    d = r.json()
    assert "miku" in d["locked_tags"]  # trigger 进锁定标签
    assert d["categories"] == {}  # 无 overlay 时为空


def test_series_endpoint(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/characters/series", params={"source": "danbooru"})
    assert r.status_code == 200
    assert any(s["series"] == "vocaloid" for s in r.json())
