import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    return create_app()


def _png():
    buf = io.BytesIO(); Image.new("RGB", (20, 20)).save(buf, format="PNG"); buf.seek(0); return buf


def _upload(client):
    return client.post("/api/images", files={"files": ("a.png", _png(), "image/png")}).json()["ids"][0]


def test_list_and_detail(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = _upload(client)
    r = client.get("/api/images")
    assert r.status_code == 200
    assert any(it["id"] == mid for it in r.json()["items"])
    d = client.get(f"/api/images/{mid}")
    assert d.status_code == 200
    assert d.json()["id"] == mid


def test_save_categories(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = _upload(client)
    meta = client.get(f"/api/images/{mid}").json()
    meta["categories"]["head"] = {"tags": ["custom hair"], "phrase": "custom hair", "user_edited": True}
    r = client.put(f"/api/images/{mid}", json=meta)
    assert r.status_code == 200
    assert r.json()["categories"]["head"]["user_edited"] is True
    # 持久化
    assert client.get(f"/api/images/{mid}").json()["categories"]["head"]["tags"] == ["custom hair"]


def test_delete(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = _upload(client)
    r = client.delete(f"/api/images/{mid}")
    assert r.status_code == 200
    assert client.get(f"/api/images/{mid}").status_code == 404
