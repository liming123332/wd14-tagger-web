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


def test_get_nonexistent_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.get("/api/images/99999999-000000-0000").status_code == 404


def test_get_bad_mid_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    # ".." 命中 storage 的 traversal guard (ValueError)，应统一转 404 而非 500
    assert client.get("/api/images/..").status_code in (404, 405)


def test_put_nonexistent_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    meta = {"id": "99999999-000000-0000", "source_name": "x", "created_at": "2026-01-01T00:00:00+08:00",
            "image": {"original": "original.png", "thumb": "thumb.webp", "width": 1, "height": 1}}
    assert client.put("/api/images/99999999-000000-0000", json=meta).status_code == 404


def test_put_unifies_id_with_path(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    mid = _upload(client)
    meta = client.get(f"/api/images/{mid}").json()
    meta["id"] = "WRONG-ID"  # body id 与路径不一致
    r = client.put(f"/api/images/{mid}", json=meta)
    assert r.status_code == 200
    # 路径权威：存盘后 id 应被统一为路径 mid
    assert client.get(f"/api/images/{mid}").json()["id"] == mid


def test_delete_bad_mid_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.delete("/api/images/..").status_code in (404, 405)


def test_list_invalid_pagination_422(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.get("/api/images?page=0").status_code == 422
    assert client.get("/api/images?size=0").status_code == 422
