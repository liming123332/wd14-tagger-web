import io
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.PROMPTBOX_DIR", tmp_path / "promptbox")
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    deps.get_promptbox_store.cache_clear()
    return create_app()


def _png(name="a.png"):
    buf = io.BytesIO(); Image.new("RGB", (20, 20)).save(buf, format="PNG"); buf.seek(0); return buf


def test_split_endpoint(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/promptbox/split", json={"text": "long hair, dress, weird"})
    assert r.status_code == 200
    data = r.json()
    assert data["categories"]["head"] == ["long hair"]
    assert data["categories"]["clothing"] == ["dress"]
    assert data["extras"] == ["weird"]


def test_create_with_images_then_list(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/promptbox", data={
        "title": "我的收藏", "raw_prompt": "long hair",
        "categories": '{"head": ["long hair"]}', "extras": "[]",
    }, files=[("files", ("a.png", _png(), "image/png"))])
    assert r.status_code == 200
    item = r.json()
    assert item["title"] == "我的收藏"
    assert len(item["image_names"]) == 1
    item_id = item["id"]

    # list 含该条
    lst = client.get("/api/promptbox").json()
    assert any(it["id"] == item_id for it in lst)
    # get 单条
    assert client.get(f"/api/promptbox/{item_id}").json()["id"] == item_id


def test_update_title(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    item_id = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }).json()["id"]
    r = client.put(f"/api/promptbox/{item_id}", data={"title": "t2"})
    assert r.status_code == 200
    assert r.json()["title"] == "t2"


def test_delete(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    item_id = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }).json()["id"]
    assert client.delete(f"/api/promptbox/{item_id}").status_code == 200
    assert client.get(f"/api/promptbox/{item_id}").status_code == 404


def test_get_image(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }, files=[("files", ("a.png", _png(), "image/png"))]).json()
    name = item["image_names"][0]
    r = client.get(f"/api/promptbox/{item['id']}/image/{name}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_get_unknown_returns_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.get("/api/promptbox/nope").status_code == 404
