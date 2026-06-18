import yaml
from fastapi.testclient import TestClient
from backend.main import create_app


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.storage.store.settings.IMAGES_DIR", tmp_path / "imgs")
    return create_app()


def test_get_rules(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/config/rules")
    assert r.status_code == 200
    data = r.json()
    assert "priority" in data
    assert "head" in data["categories"]


def test_put_quality(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.put("/api/config/quality", json={"tags": ["a", "b"]})
    assert r.status_code == 200
    assert r.json()["tags"] == ["a", "b"]
    # 持久化
    r2 = client.get("/api/config/quality")
    assert r2.json()["tags"] == ["a", "b"]
