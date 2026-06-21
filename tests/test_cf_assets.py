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
    # starlette 1.x TestClient TestClient 默认 follow_redirects=True，会跟随 307 到外部 URL；
    # 这里要直接断言重定向本身，故关闭跟随。
    client = TestClient(_app(tmp_path, monkeypatch), follow_redirects=False)
    r = client.get("/api/cf/asset", params={"kind": "char", "source": "danbooru", "key": "1", "which": "thumb"})
    assert r.status_code == 307
    assert r.headers["location"] == "http://host/preview/miku.jpg"


# ============================================================================
# 主题 2：anima char asset 端到端（local_image_path 的 anima 分支）。
# anima characters 表 DDL（与 tests/test_cf_anima_db.py 一致）。
# ============================================================================

_ANIMA_CHAR_DDL = """
CREATE TABLE characters (
    character TEXT, copyright TEXT, name TEXT, trigger TEXT, core_tags TEXT,
    count INTEGER, url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT,
    image_version INTEGER
);
"""


def _anima_app(tmp_path, monkeypatch):
    """叠加 anima characters.db 到 _app 基线上。"""
    app = _app(tmp_path, monkeypatch)
    anima_db_path = tmp_path / "cf/anima_characters.db"
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_CHARACTERS_DB", anima_db_path)
    c = sqlite3.connect(anima_db_path)
    c.executescript(_ANIMA_CHAR_DDL)
    c.execute(
        "INSERT INTO characters(character,copyright,name,trigger,core_tags,count,url,thumbname,imgname,search_blob) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "2b_(nier_automata)",
            "nier_automata",
            "2B",
            "2b (nier automata)",
            "1girl",
            500,
            "https://blobs.animadex.net/posts/2b",
            "2b (nier automata), nier automata.webp",
            "2b (nier automata), nier automata.png",
            "2b nier",
        ),
    )
    c.commit(); c.close()
    deps.get_anima_character_db.cache_clear()
    return app


def test_anima_char_asset_local_hit(tmp_path, monkeypatch):
    # anima char + which=thumb → 本地 ANIMA_DIR/characters/<thumbname> 命中。
    client = TestClient(_anima_app(tmp_path, monkeypatch))
    char_dir = tmp_path / "cf" / "anima" / "characters"
    char_dir.mkdir(parents=True)
    thumbname = "2b (nier automata), nier automata.webp"
    (char_dir / thumbname).write_bytes(b"WEBPDATA")
    r = client.get("/api/cf/asset", params={
        "kind": "char", "source": "anima", "key": "2b_(nier_automata)", "which": "thumb"})
    assert r.status_code == 200
    assert r.content == b"WEBPDATA"


def test_anima_char_asset_fallback_redirect(tmp_path, monkeypatch):
    # 本地不命中 → 307 回退到 row["url"]。
    client = TestClient(_anima_app(tmp_path, monkeypatch), follow_redirects=False)
    r = client.get("/api/cf/asset", params={
        "kind": "char", "source": "anima", "key": "2b_(nier_automata)", "which": "thumb"})
    assert r.status_code == 307
    assert r.headers["location"] == "https://blobs.animadex.net/posts/2b"
