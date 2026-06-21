import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps
from backend.models import CfOverlay, CategoryData


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


def test_get_detail_with_overlay(tmp_path, monkeypatch):
    # 覆盖 routes_characters.get_character 的 overlay 合并分支：
    # categories 序列化、extras 双重三元、custom_tags/model/gen_threshold/
    # char_threshold/image_override 取自 overlay 的分支，同时确认 locked_tags 不被 overlay 篡改。
    client = TestClient(_app(tmp_path, monkeypatch))
    # _app 已对 get_cf_overlay 做 cache_clear，此处拿到的 store 连的是 tmp 路径下的 db
    store = deps.get_cf_overlay()
    ov = CfOverlay(
        entry_key="char:danbooru:1",
        kind="char",
        custom_tags=["artist:x"],
        categories={"角色": CategoryData(tags=["hatsune_miku"], phrase="vocaloid", user_edited=True)},
        extras=CategoryData(tags=["1girl", "solo"], phrase="", user_edited=False),
        model="wd14",
        gen_threshold=0.5,
        char_threshold=0.95,
    )
    store.upsert(ov)
    r = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"})
    assert r.status_code == 200
    d = r.json()
    # custom_tags 走 ov.custom_tags 分支（非默认 []）
    assert "artist:x" in d["custom_tags"]
    # categories 走 {k: v.model_dump() ...} 序列化分支（非默认 {}，且 value 是 dict）
    assert d["categories"] != {}
    assert all(isinstance(v, dict) for v in d["categories"].values())
    assert d["categories"]["角色"]["tags"] == ["hatsune_miku"]
    assert d["categories"]["角色"]["user_edited"] is True
    # extras 走 ov.extras.model_dump() 分支（非默认 {"tags":[],"phrase":"","user_edited":False}）
    assert isinstance(d["extras"], dict)
    assert d["extras"]["tags"] == ["1girl", "solo"]
    # 阈值与 model 取自 overlay
    assert d["model"] == "wd14"
    assert d["gen_threshold"] == 0.5
    assert d["char_threshold"] == 0.95
    # 关键：overlay 不改 locked_tags，权威 trigger/core_tags 仍生效
    assert "miku" in d["locked_tags"]
