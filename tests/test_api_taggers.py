from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps
from backend.tagger import models_spec


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps._reset_tagger_cache()
    return create_app()


def _seed_wd14(tmp_path):
    root = tmp_path / "models"
    d = root / models_spec.MODEL_SPECS["wd14"].folder
    d.mkdir(parents=True)
    for name in models_spec.MODEL_SPECS["wd14"].files:
        (d / name).write_text("x")


def test_list_taggers_returns_ten(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/taggers")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 10
    assert {x["key"] for x in data} == set(models_spec.MODEL_SPECS.keys())
    assert any(x["key"] == "cl_tagger" for x in data)
    assert any(x["key"] == "cl_tagger_v2" for x in data)


def test_list_taggers_downloaded_flag(tmp_path, monkeypatch):
    _seed_wd14(tmp_path)
    client = TestClient(_app(tmp_path, monkeypatch))
    data = client.get("/api/taggers").json()
    by_key = {x["key"]: x for x in data}
    assert by_key["wd14"]["downloaded"] is True
    assert by_key["e621"]["downloaded"] is False
    assert by_key["wd14"]["label"] == "WD14"


def test_download_unknown_key_404(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/taggers/nope/download")
    assert r.status_code == 404


def test_download_triggers_ensure_loaded(tmp_path, monkeypatch):
    # 避免真下载：patch OnnxTagger.ensure_loaded 为 no-op，并预置假文件使
    # is_downloaded 返回 True。
    _seed_wd14(tmp_path)
    calls = {"n": 0}

    def fake_ensure_loaded(self):
        calls["n"] += 1

    monkeypatch.setattr("backend.tagger.core.OnnxTagger.ensure_loaded", fake_ensure_loaded)
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/taggers/wd14/download")
    assert r.status_code == 200
    assert r.json() == {"key": "wd14", "downloaded": True}
    assert calls["n"] == 1


def test_download_failure_returns_500(tmp_path, monkeypatch):
    def boom(self):
        raise RuntimeError("network down")

    monkeypatch.setattr("backend.tagger.core.OnnxTagger.ensure_loaded", boom)
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/taggers/e621/download")
    assert r.status_code == 500
