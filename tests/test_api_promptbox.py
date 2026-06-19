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


class _FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "indoors": 0.5, "unknown thing": 0.4}


def test_analyze_endpoint(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    monkeypatch.setattr("backend.api.routes_promptbox.get_tagger",
                        lambda model="wd14": _FakeTagger())
    r = client.post("/api/promptbox/analyze",
                    data={"model": "wd14", "gen_th": "0.35", "char_th": "0.9"},
                    files=[("files", ("a.png", _png(), "image/png"))])
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["local_id"]
    assert it["model"] == "wd14"
    assert "long hair" in it["categories"]["head"]
    assert "dress" in it["categories"]["clothing"]
    assert "unknown thing" in it["extras"]
    assert "long hair" in it["raw_prompt"]
    # 工作区缩略图可访问
    assert client.get(
        f"/api/promptbox/workspace/{it['local_id']}/image/{it['thumb']}"
    ).status_code == 200


def test_workspace_image_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    assert client.get(
        "/api/promptbox/workspace/nope/image/thumb.webp"
    ).status_code == 404


def _tag_app(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.api.routes_promptbox.get_tagger",
                        lambda model="wd14": _FakeTagger())
    return app


def test_tag_endpoint_classifies(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }, files=[("files", ("a.png", _png(), "image/png"))]).json()
    r = client.post(f"/api/promptbox/{item['id']}/tag",
                    json={"gen_th": 0.35, "char_th": 0.9})
    assert r.status_code == 200
    d = r.json()
    assert "long hair" in d["categories"]["head"]
    assert "dress" in d["categories"]["clothing"]
    assert "unknown thing" in d["extras"]
    assert d["model"] == "wd14"
    assert d["raw_tags"]["long hair"] == 0.9


def test_tag_endpoint_no_image_returns_400(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }).json()
    assert client.post(f"/api/promptbox/{item['id']}/tag",
                       json={"gen_th": 0.35, "char_th": 0.9}).status_code == 400


def test_reclassify_endpoint_keeps_user_edited(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }, files=[("files", ("a.png", _png(), "image/png"))]).json()
    client.post(f"/api/promptbox/{item['id']}/tag", json={"gen_th": 0.35, "char_th": 0.9})
    r = client.post(f"/api/promptbox/{item['id']}/reclassify",
                    json={"keep": {"head": ["my custom tag"]}})
    assert r.status_code == 200
    assert r.json()["categories"]["head"] == ["my custom tag"]


def test_reclassify_without_raw_tags_returns_400(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
    }).json()
    assert client.post(f"/api/promptbox/{item['id']}/reclassify",
                       json={"keep": {}}).status_code == 400


def test_tag_unknown_returns_404(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    assert client.post("/api/promptbox/nope/tag",
                       json={"gen_th": 0.35, "char_th": 0.9}).status_code == 404


def test_create_persists_tagger_form_fields(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    item = client.post("/api/promptbox", data={
        "title": "t", "raw_prompt": "x", "categories": "{}", "extras": "[]",
        "model": "wd3", "gen_threshold": "0.4", "char_threshold": "0.6",
        "raw_tags": '{"a": 0.9}',
    }).json()
    assert item["model"] == "wd3"
    assert item["gen_threshold"] == 0.4
    assert item["raw_tags"]["a"] == 0.9
