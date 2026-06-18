from __future__ import annotations
import yaml
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api import routes_config


def _validate_config() -> None:
    # 启动校验词表格式
    data = yaml.safe_load(settings.TAG_RULES_PATH.read_text(encoding="utf-8"))
    if "categories" not in data or "priority" not in data:
        raise RuntimeError("tag_rules.yaml missing 'categories' or 'priority'")
    if not Path(settings.QUALITY_TEMPLATE_PATH).exists():
        raise RuntimeError("quality_template.yaml missing")


def create_app() -> FastAPI:
    import mimetypes
    mimetypes.add_type("image/webp", ".webp")
    _validate_config()
    app = FastAPI(title="WD14 Tagger Web")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(routes_config.router)
    from backend.api import routes_images
    app.include_router(routes_images.router)
    return app


app = create_app()
