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


# 健壮性 M7+M8：upload_artist_image 的大小 + 魔数校验，与角色端点对称。
import io
from PIL import Image


def _png_bytes():
    b = io.BytesIO(); Image.new("RGB", (20, 20)).save(b, format="PNG"); return b.getvalue()


def test_artist_image_upload_validates_size_and_magic(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    from backend.characterfinder.upload_validate import MAX_UPLOAD_BYTES

    # 正常 PNG 仍 200（不回归）
    r_ok = client.post("/api/cf/artist/image", params={"source": "danbooru", "key": "1"},
                       files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")})
    assert r_ok.status_code == 200
    assert r_ok.json()["image_override"].endswith(".png")

    # 超大 → 413
    huge = b"\x00" * (MAX_UPLOAD_BYTES + 1)
    r_big = client.post("/api/cf/artist/image", params={"source": "danbooru", "key": "1"},
                        files={"file": ("big.png", io.BytesIO(huge), "image/png")})
    assert r_big.status_code == 413

    # 非图片 → 400
    r_bad = client.post("/api/cf/artist/image", params={"source": "danbooru", "key": "1"},
                        files={"file": ("fake.png", io.BytesIO(b"not an image"), "image/png")})
    assert r_bad.status_code == 400


# ============================================================================
# 主题 3 M10：艺术家 5 联动 smoke（tag/reclassify/save/image/favorite）。
# 复用 danbooru artist fixture（_app 已建 artists.db 含 ebifurya id=1），
# 本地 cover 放 ARTIST_COVERS_DIR（paths.ARTIST_COVERS_DIR 在 _app 中未 patch，
# 这里补 monkeypatch），_FakeTagger monkeypatch routes_artists.get_tagger。
# ============================================================================


class _FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "weird thing": 0.4}


def _artist_overlay_app(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.characterfinder.paths.ARTIST_COVERS_DIR", tmp_path / "cf" / "artist_covers")
    monkeypatch.setattr("backend.api.routes_artists.get_tagger", lambda model="wd14": _FakeTagger())
    return app


def test_artist_tag_writes_overlay(tmp_path, monkeypatch):
    # tag：本地 cover → 反推 → overlay categories + 权威 tag 仍锁定。
    client = TestClient(_artist_overlay_app(tmp_path, monkeypatch))
    (tmp_path / "cf" / "artist_covers").mkdir()
    # local_image_path 用 row.image_url_1 的 slug（_slug 取 Path(url).name = "1.jpg"）
    (tmp_path / "cf" / "artist_covers" / "1.jpg").write_bytes(_png_bytes())
    r = client.post("/api/cf/artist/tag", params={"source": "danbooru", "key": "1"},
                    json={"model": "wd14", "gen_th": 0.35, "char_th": 0.9, "use_char": True})
    assert r.status_code == 200
    d = r.json()
    assert "long hair" in d["categories"]["head"]["tags"]
    assert "dress" in d["categories"]["clothing"]["tags"]
    # 画师 tag 仍在 locked_tags
    assert "ebifurya" in d["locked_tags"]
    # 反向锁定：overlay 分类不渗入 locked_tags
    assert "long hair" not in d["locked_tags"]


def test_artist_save_and_favorite(tmp_path, monkeypatch):
    # save + favorite：overlay 持久化 + 收藏 toggle。
    client = TestClient(_artist_overlay_app(tmp_path, monkeypatch))
    r = client.put("/api/cf/artist", params={"source": "danbooru", "key": "1"},
                   json={"categories": {"head": {"tags": ["x"], "phrase": "", "user_edited": True}},
                         "extras": {"tags": [], "phrase": "", "user_edited": False}, "custom_tags": ["y"]})
    assert r.status_code == 200
    again = client.get("/api/cf/artist", params={"source": "danbooru", "key": "1"}).json()
    assert again["categories"]["head"]["tags"] == ["x"]
    assert again["custom_tags"] == ["y"]
    # favorite toggle
    rf = client.post("/api/cf/artist/favorite", params={"source": "danbooru", "key": "1"})
    assert rf.json()["favorite"] is True


def test_artist_reclassify_and_image(tmp_path, monkeypatch):
    # reclassify + image：existing 保留 + 上传替换图。
    client = TestClient(_artist_overlay_app(tmp_path, monkeypatch))
    (tmp_path / "cf" / "artist_covers").mkdir()
    (tmp_path / "cf" / "artist_covers" / "1.jpg").write_bytes(_png_bytes())
    # 先 tag 产生 raw_tags
    client.post("/api/cf/artist/tag", params={"source": "danbooru", "key": "1"},
                json={"model": "wd14", "gen_th": 0.35, "char_th": 0.9, "use_char": True})
    # reclassify keep head
    r = client.post("/api/cf/artist/reclassify", params={"source": "danbooru", "key": "1"},
                    json={"keep": {"head": ["custom"]}})
    assert r.status_code == 200
    assert r.json()["categories"]["head"]["tags"] == ["custom"]
    # image 上传
    ri = client.post("/api/cf/artist/image", params={"source": "danbooru", "key": "1"},
                     files={"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")})
    assert ri.status_code == 200
    assert ri.json()["image_override"].endswith(".png")

