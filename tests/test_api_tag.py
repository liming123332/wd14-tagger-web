import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


class FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "indoors": 0.5, "unknown thing": 0.4}


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    deps.get_classifier.cache_clear()
    # 注意：patch routes_images 模块的 get_tagger 名字（from-import 绑定在此），
    # 而非 deps.get_tagger，否则真实 WD14 模型会被触发下载。
    monkeypatch.setattr("backend.api.routes_images.get_tagger", lambda: FakeTagger())
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


def test_reclassify_after_quality_change(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]
    client.post(f"/api/images/{mid}/tag", json={"gen_th": 0.35, "char_th": 0.9})
    r = client.post(f"/api/images/{mid}/reclassify")
    assert r.status_code == 200
    assert "long hair" in r.json()["categories"]["head"]["tags"]
