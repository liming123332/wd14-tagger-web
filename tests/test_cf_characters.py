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


def test_image_upload_rejects_oversized(tmp_path, monkeypatch):
    # 健壮性 M7：超过 10MB 直接 413，文件不落盘。
    from backend.characterfinder.upload_validate import MAX_UPLOAD_BYTES
    client = TestClient(_app(tmp_path, monkeypatch))
    huge = b"\x00" * (MAX_UPLOAD_BYTES + 1)
    r = client.post("/api/cf/character/image", params={"source": "danbooru", "key": "1"},
                    files={"file": ("big.png", io.BytesIO(huge), "image/png")})
    assert r.status_code == 413
    # overlay 目录无文件落盘
    from backend.characterfinder.paths import entry_key
    from backend.storage.cf_overlay import _safe_name
    safe = _safe_name(entry_key("char", "danbooru", "1"))
    overlay_dir = tmp_path / "cf" / "overlay" / safe
    assert not overlay_dir.exists() or not any(overlay_dir.iterdir())
    # 详情里 image_override 仍为 None（未被污染）
    d = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"}).json()
    assert d["image_override"] is None


def test_image_upload_rejects_non_image(tmp_path, monkeypatch):
    # 健壮性 M8：非合法图片字节（魔数校验失败）→ 400，文件不落盘。
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/cf/character/image", params={"source": "danbooru", "key": "1"},
                    files={"file": ("fake.png", io.BytesIO(b"not an image"), "image/png")})
    assert r.status_code == 400
    # 详情里 image_override 仍为 None
    d = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"}).json()
    assert d["image_override"] is None


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


# ============================================================================
# 主题 2：anima 端到端 + char anima 404 对称（M4+M6+M14）。
# anima characters 表 DDL（与 tests/test_cf_anima_db.py / scripts/import_anima.py 一致）。
# ============================================================================

_ANIMA_CHAR_DDL = """
CREATE TABLE characters (
    character TEXT, copyright TEXT, name TEXT, trigger TEXT, core_tags TEXT,
    count INTEGER, url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT,
    image_version INTEGER
);
CREATE INDEX idx_char_search ON characters(search_blob);
"""


def _anima_char_app(tmp_path, monkeypatch):
    """复用 danbooru _app 的 settings/paths 配置，再叠加 anima characters.db。"""
    app = _app(tmp_path, monkeypatch)
    anima_db_path = tmp_path / "cf/anima_characters.db"
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_CHARACTERS_DB", anima_db_path)
    c = sqlite3.connect(anima_db_path)
    c.executescript(_ANIMA_CHAR_DDL)
    c.execute(
        "INSERT INTO characters(character,copyright,name,trigger,core_tags,count,url,imgname,thumbname,search_blob) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "2b_(nier_automata)",
            "nier_automata",
            "2B (Nier Automata)",
            "2b (nier automata), nier automata",
            "1girl, blindfold",
            500,
            "https://example.com/2b",
            "2b (nier automata), nier automata.png",
            "2b (nier automata), nier automata.webp",
            "2b nier_automata",
        ),
    )
    c.commit(); c.close()
    deps.get_anima_character_db.cache_clear()
    return app


def test_anima_character_search_end_to_end(tmp_path, monkeypatch):
    # M4：anima 角色搜索端到端（HTTP 层）—entry_key 前缀 char:anima:、items 非空。
    client = TestClient(_anima_char_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/characters", params={"query": "2b", "source": "anima"})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    assert len(d["items"]) >= 1
    it = d["items"][0]
    assert it["entry_key"] == "char:anima:2b_(nier_automata)"
    assert it["source"] == "anima"
    assert it["name"] == "2B (Nier Automata)"
    assert it["series"] == "nier_automata"
    # 缩略图 url 指向 asset 路由
    assert "/api/cf/asset" in it["thumb_url"]
    # anima 搜索可用 copyright 系列过滤
    r2 = client.get("/api/cf/characters", params={"query": "2b", "source": "anima", "series": "nier_automata"})
    assert r2.json()["total"] == 1


def test_anima_character_detail_locked_tags(tmp_path, monkeypatch):
    # M6：anima 详情 locked_tags 含 trigger 词。
    client = TestClient(_anima_char_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/character", params={"source": "anima", "key": "2b_(nier_automata)"})
    assert r.status_code == 200
    d = r.json()
    assert d["entry_key"] == "char:anima:2b_(nier_automata)"
    # locked_tags 来自 trigger + core_tags
    assert "2b (nier automata)" in d["locked_tags"]
    assert "nier automata" in d["locked_tags"]
    assert "1girl" in d["locked_tags"]  # core_tags 词
    assert "blindfold" in d["locked_tags"]


def test_anima_character_detail_404_on_missing_key(tmp_path, monkeypatch):
    # M14：anima char 详情 key 不存在 → 404（与 anima artist 404 对称）。
    # 建一个空的 anima characters.db：表存在但无任何行，get_by_character 返回 None。
    app = _app(tmp_path, monkeypatch)
    anima_db_path = tmp_path / "cf/anima_characters.db"
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_CHARACTERS_DB", anima_db_path)
    c = sqlite3.connect(anima_db_path)
    c.executescript(_ANIMA_CHAR_DDL)
    c.commit(); c.close()
    deps.get_anima_character_db.cache_clear()
    client = TestClient(app)
    r = client.get("/api/cf/character", params={"source": "anima", "key": "nonexistent"})
    assert r.status_code == 404


# ============================================================================
# 主题 3 M11：favorites/recent 的 _resolve_item 反查（char-danbooru + artist-anima 两组合）。
# _resolve_item 走 entry_key 解析 → 反查权威 db → 复用 _danbooru_item / _anima_artist。
# ============================================================================

_ANIMA_ARTIST_DDL = """
CREATE TABLE artists (
    artist TEXT, name TEXT, name_lower TEXT, trigger TEXT, count INTEGER,
    url TEXT, imgname TEXT, thumbname TEXT, score REAL, search_blob TEXT,
    image_version INTEGER
);
"""


def _resolve_app(tmp_path, monkeypatch):
    """char danbooru（miku id=1）+ artist anima（ciloranko）双 db 配置。"""
    app = _app(tmp_path, monkeypatch)
    # artist anima db
    anima_artists_db = tmp_path / "cf/anima_artists.db"
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_ARTISTS_DB", anima_artists_db)
    c = sqlite3.connect(anima_artists_db)
    c.executescript(_ANIMA_ARTIST_DDL)
    c.execute(
        "INSERT INTO artists(artist,name,name_lower,trigger,count,url,thumbname,imgname,search_blob) VALUES(?,?,?,?,?,?,?,?,?)",
        ("ciloranko", "Ciloranko", "ciloranko", "ciloranko", 500,
         "https://example.com/c", "ciloranko.webp", "ciloranko.png", "ciloranko"),
    )
    c.commit(); c.close()
    # _app 已 cache_clear char 工厂，这里补 anima artist 工厂
    deps.get_anima_artist_db.cache_clear()
    return app


def test_favorites_resolve_char_danbooru_and_artist_anima(tmp_path, monkeypatch):
    # _resolve_item 的 char-danbooru + artist-anima 两组合：
    # 收藏一个 char（danbooru miku）和一个 artist（anima ciloranko），断言两 kind 各自返回对应 item。
    client = TestClient(_resolve_app(tmp_path, monkeypatch))
    # 收藏 char danbooru
    client.post("/api/cf/character/favorite", params={"source": "danbooru", "key": "1"})
    # 收藏 artist anima
    client.post("/api/cf/artist/favorite", params={"source": "anima", "key": "ciloranko"})
    # favorites?kind=char 返回 miku item（entry_key 前缀 char:）
    rc = client.get("/api/cf/favorites", params={"kind": "char"})
    assert rc.status_code == 200
    char_items = rc.json()["items"]
    assert len(char_items) == 1
    assert char_items[0]["entry_key"] == "char:danbooru:1"
    assert char_items[0]["name"] == "miku"
    assert char_items[0]["favorite"] is True
    # favorites?kind=artist 返回 ciloranko item（entry_key 前缀 artist:）
    ra = client.get("/api/cf/favorites", params={"kind": "artist"})
    assert ra.status_code == 200
    artist_items = ra.json()["items"]
    assert len(artist_items) == 1
    assert artist_items[0]["entry_key"] == "artist:anima:ciloranko"
    assert artist_items[0]["name"] == "Ciloranko"
    assert artist_items[0]["favorite"] is True


def test_recent_resolve_char_danbooru(tmp_path, monkeypatch):
    # _resolve_item 经 recent 反查 char-danbooru：查看详情后 recent 含该 char item。
    client = TestClient(_resolve_app(tmp_path, monkeypatch))
    # 查看详情触发 recent.add
    client.get("/api/cf/character", params={"source": "danbooru", "key": "1"})
    rr = client.get("/api/cf/recent", params={"kind": "char"})
    assert rr.status_code == 200
    items = rr.json()["items"]
    assert len(items) == 1
    assert items[0]["entry_key"] == "char:danbooru:1"
    assert items[0]["name"] == "miku"


# ============================================================================
# 主题 4：/api/cf/random 真随机回归。
# 修前 random_cf 走 db.search("", limit=size) 固定 ORDER BY rank ASC，取前 N 条，
# 导致「再抽一页」永远返回同一批；修后 db.random(size) 用 ORDER BY RANDOM()。
# ============================================================================

def _many_char_app(tmp_path, monkeypatch):
    """50 行 danbooru 角色的最小 app，供随机抽样测试（小样本下两次必然不同）。"""
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.config.settings.CF_FAVORITES_PATH", tmp_path / "cf/fav.json")
    monkeypatch.setattr("backend.config.settings.CF_RECENT_PATH", tmp_path / "cf/recent.json")
    monkeypatch.setattr("backend.characterfinder.paths.CHARACTERS_DB", tmp_path / "cf/characters.db")
    for f in (deps.get_character_db, deps.get_cf_overlay, deps.get_cf_favorites, deps.get_cf_recent):
        f.cache_clear()
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/characters.db")
    c.executescript(
        "CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, "
        "image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')"
    )
    for i in range(50):
        c.execute(
            "INSERT INTO characters(id,name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?,?)",
            (i + 1, f"c{i}", "s", "t", f"http://x/c{i}.jpg", i, "danbooru"),
        )
    c.commit(); c.close()
    return create_app()


def test_random_returns_different_rows_across_calls(tmp_path, monkeypatch):
    # 真随机回归：50 抽 10，两次结果集合不同（概率 ≈1/C(50,10)≈1e-10，不会 flaky）。
    # 修前两次必然完全相同（固定 rank ASC 取前 10）→ 此断言失败。
    client = TestClient(_many_char_app(tmp_path, monkeypatch))
    r1 = client.get("/api/cf/random", params={"type": "characters", "source": "danbooru", "size": 10})
    r2 = client.get("/api/cf/random", params={"type": "characters", "source": "danbooru", "size": 10})
    assert r1.status_code == 200 and r2.status_code == 200
    ids1 = {it["entry_key"] for it in r1.json()["items"]}
    ids2 = {it["entry_key"] for it in r2.json()["items"]}
    assert len(ids1) == 10 and len(ids2) == 10
    assert ids1 != ids2


def test_random_db_method_shuffles(tmp_path):
    # 单元层：CharacterDB.random 多次调用结果会变（直接验证 ORDER BY RANDOM()）。
    from backend.characterfinder.character_db import CharacterDB
    db_path = tmp_path / "characters.db"
    # _migrate 假定 characters 表已存在（它 ALTER ADD COLUMN），故先用原生 sqlite3
    # 建表+插数据，再实例化 DB，避免 _get_conn()→_migrate() 撞 no such table。
    c = sqlite3.connect(db_path)
    c.executescript(
        "CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, "
        "image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')"
    )
    for i in range(40):
        c.execute("INSERT INTO characters(id,name,rank) VALUES(?,?,?)", (i + 1, f"c{i}", i))
    c.commit(); c.close()
    db = CharacterDB(db_path=db_path)
    samples = [tuple(r["id"] for r in db.random(10)) for _ in range(5)]
    # 5 次抽样里至少有一次与第一次不同（全相同概率≈0）
    assert any(s != samples[0] for s in samples[1:])
