import io, time
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


class FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "smile": 0.6}


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    deps.get_classifier.cache_clear()
    monkeypatch.setattr(deps, "get_tagger", lambda: FakeTagger())
    return create_app()


def _png():
    buf = io.BytesIO(); Image.new("RGB", (20, 20)).save(buf, format="PNG"); buf.seek(0); return buf


def test_batch_runs_all(tmp_path, monkeypatch):
    # 用 with 保持 app lifespan/portal 活跃，使后台 asyncio.create_task 得以持续调度
    with TestClient(_app(tmp_path, monkeypatch)) as client:
        ids = client.post("/api/images", files=[
            ("files", ("a.png", _png(), "image/png")),
            ("files", ("b.png", _png(), "image/png")),
        ]).json()["ids"]
        r = client.post("/api/batch/tag", json={"ids": ids, "gen_th": 0.35, "char_th": 0.9})
        batch_id = r.json()["batch_id"]

        # 轮询 status 直到完成
        for _ in range(50):
            s = client.get(f"/api/batch/{batch_id}/status").json()
            if s["done"]:
                break
            time.sleep(0.05)
        assert s["done"] is True
        assert s["total"] == 2
        assert s["ok"] == 2
        # 验证已落库
        meta = client.get(f"/api/images/{ids[0]}").json()
        assert "long hair" in meta["categories"]["head"]["tags"]
