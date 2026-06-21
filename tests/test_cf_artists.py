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
