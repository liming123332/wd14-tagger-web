"""SPA 回退测试：前端子路由（/upload、/gallery、/batch/:id）直接访问或刷新时，
应由后端回退到 index.html，而非返回 404。

根因：backend/main.py 用 ``app.mount("/", StaticFiles(..., html=True))`` 托管前端，
``html=True`` 仅对「目录」返回 index.html，对磁盘上不存在的路径仍抛 404。
"""
from fastapi.testclient import TestClient

from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.IMAGES_DIR", tmp_path / "imgs")
    monkeypatch.setattr("backend.config.settings.MODELS_DIR", tmp_path / "models")
    deps.get_storage.cache_clear()
    return create_app()


def test_root_serves_index(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"].lower()


def test_spa_subroute_falls_back_to_index(tmp_path, monkeypatch):
    """前端子路由应回退到 index.html，而非 404。"""
    client = TestClient(_app(tmp_path, monkeypatch))
    for path in ("/upload", "/gallery", "/batch/abc-123"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} 应回退到 index.html，实得 {r.status_code}"
        assert "text/html" in r.headers["content-type"].lower(), f"{path} 应返回 html"


def test_real_static_asset_still_served(tmp_path, monkeypatch):
    """真实静态资源（favicon.svg）仍由 StaticFiles 正常返回。"""
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/favicon.svg")
    assert r.status_code == 200


def test_api_route_not_swallowed(tmp_path, monkeypatch):
    """API 路由不受 SPA 回退影响：返回 JSON 而非被吞成 html。"""
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/images")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"].lower()


def test_unknown_api_path_still_404(tmp_path, monkeypatch):
    """未知的 /api 路径仍应 404，不被回退成 index.html。"""
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
