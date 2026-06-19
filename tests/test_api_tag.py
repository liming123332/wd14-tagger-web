import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


class FakeTagger:
    def __init__(self, key="wd14"):
        self.key = key

    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "indoors": 0.5, "unknown thing": 0.4}


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    deps.get_classifier.cache_clear()
    deps._reset_tagger_cache()
    # patch routes_images 模块的 get_tagger 名字（from-import 绑定在此），
    # 接收 model 参数返回 FakeTagger，避免触发真实模型下载。
    monkeypatch.setattr("backend.api.routes_images.get_tagger", lambda model="wd14": FakeTagger(model))
    return create_app()


def _png():
    buf = io.BytesIO(); Image.new("RGB", (20, 20)).save(buf, format="PNG"); buf.seek(0); return buf


def test_tag_endpoint_classifies(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]
    r = client.post(f"/api/images/{mid}/tag", json={"gen_th": 0.35, "char_th": 0.9})
    assert r.status_code == 200
    meta = r.json()
    assert "long hair" in meta["categories"]["head"]["tags"]
    assert "dress" in meta["categories"]["clothing"]["tags"]
    assert "indoors" in meta["categories"]["scene"]["tags"]
    assert "unknown thing" in meta["extras"]["tags"]
    assert meta["categories"]["quality"]["tags"]  # 非空
    assert "long hair" in meta["tagger"]["raw_tags"]
    assert meta["model"] == "wd14"  # 默认 model 落库


def test_tag_endpoint_passes_model(tmp_path, monkeypatch):
    captured = {}

    def fake_get_tagger(model="wd14"):
        captured["model"] = model
        return FakeTagger(model)

    app = _app(tmp_path, monkeypatch)  # 先建 app（内部 patch 默认 lambda）
    # 覆盖为捕获 model 的版本（monkeypatch 后注册先生效）
    monkeypatch.setattr("backend.api.routes_images.get_tagger", fake_get_tagger)
    client = TestClient(app)
    mid = client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]
    meta = client.post(f"/api/images/{mid}/tag", json={"gen_th": 0.35, "char_th": 0.9, "model": "wd3"}).json()
    assert meta["model"] == "wd3"
    assert captured["model"] == "wd3"


def test_reclassify_after_quality_change(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]
    client.post(f"/api/images/{mid}/tag", json={"gen_th": 0.35, "char_th": 0.9})
    r = client.post(f"/api/images/{mid}/reclassify")
    assert r.status_code == 200
    assert "long hair" in r.json()["categories"]["head"]["tags"]


def test_tag_unknown_mid_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/images/nope/tag", json={"gen_th": 0.35, "char_th": 0.9})
    assert r.status_code == 404


def test_reclassify_preserves_user_edited(tmp_path, monkeypatch):
    from backend.models import CategoryData
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]
    client.post(f"/api/images/{mid}/tag", json={"gen_th": 0.35, "char_th": 0.9})
    storage = deps.get_storage()
    meta = storage.get_meta(mid)
    meta.categories["head"] = CategoryData(tags=["custom edited"], phrase="custom edited", user_edited=True)
    storage.save_meta(mid, meta)
    r = client.post(f"/api/images/{mid}/reclassify")
    assert r.status_code == 200
    assert r.json()["categories"]["head"]["tags"] == ["custom edited"]
