import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend import deps
from backend.main import create_app


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    return create_app()


@pytest.fixture(autouse=True)
def _clear_dep_caches():
    # 清空 deps 单例缓存，保证每个测试用各自 monkeypatch 的 IMAGES_DIR
    deps.get_storage.cache_clear()
    deps.get_classifier.cache_clear()
    deps._reset_tagger_cache()
    yield


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (40, 60), (5, 6, 7)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_upload_image(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/images", files={"files": ("a.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    ids = r.json()["ids"]
    assert len(ids) == 1
    assert "-" in ids[0]


def test_get_file(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    ids = client.post("/api/images", files={"files": ("a.png", _png_bytes(), "image/png")}).json()["ids"]
    r = client.get(f"/api/images/{ids[0]}/file/thumb.webp")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image")


def test_upload_bad_image_returns_400(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/images", files={"files": ("bad.png", io.BytesIO(b"not an image"), "image/png")})
    assert r.status_code == 400


def test_get_missing_file_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    ids = client.post("/api/images", files={"files": ("a.png", _png_bytes(), "image/png")}).json()["ids"]
    r = client.get(f"/api/images/{ids[0]}/file/nope.png")
    assert r.status_code == 404
