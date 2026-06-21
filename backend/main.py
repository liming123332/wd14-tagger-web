from __future__ import annotations
import yaml
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.api import routes_config


def _validate_config() -> None:
    # 启动校验词表格式
    data = yaml.safe_load(settings.TAG_RULES_PATH.read_text(encoding="utf-8"))
    if "categories" not in data or "priority" not in data:
        raise RuntimeError("tag_rules.yaml missing 'categories' or 'priority'")
    if not Path(settings.QUALITY_TEMPLATE_PATH).exists():
        raise RuntimeError("quality_template.yaml missing")


class SpaStaticFiles(StaticFiles):
    """单页应用静态托管：磁盘上不存在的非 API 路径回退到 index.html，
    以支持 /upload、/gallery、/batch/:id 等前端路由的直接访问与刷新。
    /api 前缀的未知路径保持原 404 语义，不被吞成 html。
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404 and not path.startswith("api"):
                return FileResponse(str(Path(self.directory) / "index.html"))
            raise


def create_app() -> FastAPI:
    import mimetypes
    mimetypes.add_type("image/webp", ".webp")
    _validate_config()
    app = FastAPI(title="WD14 Tagger Web")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(routes_config.router)
    from backend.api import routes_images
    from backend.api import routes_batch
    from backend.api import routes_taggers
    from backend.api import routes_promptbox
    from backend.api import routes_pathtag
    app.include_router(routes_images.router)
    app.include_router(routes_batch.router)
    app.include_router(routes_taggers.router)
    app.include_router(routes_promptbox.router)
    app.include_router(routes_pathtag.router)
    from backend.api import routes_cfassets
    app.include_router(routes_cfassets.router)
    from backend.api import routes_characters
    app.include_router(routes_characters.router)
    # 裁决 A（Task 11）：cfassets/characters 已在上方注册（Task 8/9），此处只新增
    # routes_artists。不重复 include 同一 router，避免路由重复注册。
    from backend.api import routes_artists
    app.include_router(routes_artists.router)
    # 生产：托管前端构建产物（mount "/" 必须在所有 /api 路由 include 之后，避免拦截 API）
    dist = settings.ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", SpaStaticFiles(directory=str(dist), html=True), name="frontend")
    return app


app = create_app()
