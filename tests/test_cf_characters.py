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


import io
from PIL import Image


def _png():
    b = io.BytesIO(); Image.new("RGB", (20, 20)).save(b, format="PNG"); b.seek(0); return b


class _FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "weird thing": 0.4}


def _tag_app(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    # brief 的 _app 只 patch 了 settings.CF_DIR，未 patch 模块级常量 paths.COVERS_DIR
    # （它在 import 时已绑定到真实 data 目录）。tag 端点经 local_image_path 查封面时
    # 走 paths.COVERS_DIR，故此处必须同步 patch，测试才能找到自放的 miku.jpg。
    monkeypatch.setattr("backend.characterfinder.paths.COVERS_DIR", tmp_path / "cf" / "covers")
    monkeypatch.setattr("backend.api.routes_characters.get_tagger", lambda model="wd14": _FakeTagger())
    return app


def test_tag_writes_overlay(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    # 先放一张本地封面供反推读取
    (tmp_path / "cf" / "covers").mkdir()
    (tmp_path / "cf" / "covers" / "miku.jpg").write_bytes(_png().read())
    r = client.post("/api/cf/character/tag", params={"source": "danbooru", "key": "1"},
                    json={"model": "wd14", "gen_th": 0.35, "char_th": 0.9, "use_char": True})
    assert r.status_code == 200
    d = r.json()
    assert "long hair" in d["categories"]["head"]["tags"]
    assert "dress" in d["categories"]["clothing"]["tags"]
    assert "weird thing" in d["extras"]["tags"]
    # 权威 trigger 仍在锁定标签
    assert "miku" in d["locked_tags"]
    # 反向锁定：overlay 的分类标签不渗入 locked_tags
    assert "long hair" not in d["locked_tags"]


def test_reclassify_keeps_user_edited(tmp_path, monkeypatch):
    # reclassify 的 existing=keep 保留语义：keep 转成 CategoryData(user_edited=True)，
    # classify 会原样保留这些类，其余按 raw_tags 重算。
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    (tmp_path / "cf" / "covers").mkdir()
    (tmp_path / "cf" / "covers" / "miku.jpg").write_bytes(_png().read())
    # 1) 先 tag 产生 raw_tags（_FakeTagger 把 head 算成 "long hair"）
    r = client.post("/api/cf/character/tag", params={"source": "danbooru", "key": "1"},
                    json={"model": "wd14", "gen_th": 0.35, "char_th": 0.9, "use_char": True})
    assert r.status_code == 200
    tagged = r.json()
    assert tagged["categories"]["head"]["tags"] == ["long hair"]  # baseline：当前 head 来自 raw
    # 2) reclassify 带 keep={"head": ["my_custom_head"]}：head 标记 user_edited=True，
    #    classify 原样保留，不被 raw_tags 的 "long hair" 覆盖
    r2 = client.post("/api/cf/character/reclassify", params={"source": "danbooru", "key": "1"},
                     json={"keep": {"head": ["my_custom_head"]}})
    assert r2.status_code == 200
    d = r2.json()
    assert d["categories"]["head"]["tags"] == ["my_custom_head"]  # user_edited 类被保留
    assert d["categories"]["head"]["user_edited"] is True
    # 未 keep 的类仍按 raw_tags 重算（clothing 应仍含 dress）
    assert "dress" in d["categories"]["clothing"]["tags"]
    assert "weird thing" in d["extras"]["tags"]
    # 锁定标签不受 reclassify 影响
    assert "miku" in d["locked_tags"]


def test_image_upload_overrides_path(tmp_path, monkeypatch):
    # image 上传 → overlay 联动：文件写到 overlay 目录，image_override 持久化。
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/cf/character/image", params={"source": "danbooru", "key": "1"},
                    files={"file": ("miku2.png", _png(), "image/png")})
    assert r.status_code == 200
    name = r.json()["image_override"]
    assert isinstance(name, str) and name  # 非空
    assert name.endswith(".png")
    # 详情里 image_override 持久化
    again = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"}).json()
    assert again["image_override"] == name
    # 文件确实落到 overlay 目录（entry_key="char:danbooru:1" → _safe_name "char_danbooru_1"）
    from backend.characterfinder.paths import entry_key
    from backend.storage.cf_overlay import _safe_name
    safe = _safe_name(entry_key("char", "danbooru", "1"))
    written = tmp_path / "cf" / "overlay" / safe / name
    assert written.exists() and written.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_save_persists_categories(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.put("/api/cf/character", params={"source": "danbooru", "key": "1"},
                   json={"categories": {"head": {"tags": ["my tag"], "phrase": "", "user_edited": True}},
                         "extras": {"tags": [], "phrase": "", "user_edited": False}, "custom_tags": ["fav"]})
    assert r.status_code == 200
    again = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"}).json()
    assert again["categories"]["head"]["tags"] == ["my tag"]
    assert again["custom_tags"] == ["fav"]


def test_favorite_toggle(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/cf/character/favorite", params={"source": "danbooru", "key": "1"})
    assert r.json()["favorite"] is True
    r2 = client.post("/api/cf/character/favorite", params={"source": "danbooru", "key": "1"})
    assert r2.json()["favorite"] is False
