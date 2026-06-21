from fastapi.testclient import TestClient
from backend.main import create_app


def test_cf_routes_registered():
    # 不带真实 db 也能注册（懒连接）
    app = create_app()
    client = TestClient(app)
    # /api/cf/characters 缺 source 参数应返回 422（证明路由已注册）
    assert client.get("/api/cf/characters").status_code == 422
