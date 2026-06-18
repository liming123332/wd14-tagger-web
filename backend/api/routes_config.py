import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/rules")
def get_rules():
    return yaml.safe_load(settings.TAG_RULES_PATH.read_text(encoding="utf-8"))


class QualityPayload(BaseModel):
    tags: list[str]


@router.put("/quality")
def put_quality(payload: QualityPayload):
    settings.QUALITY_TEMPLATE_PATH.write_text(
        yaml.safe_dump({"tags": payload.tags}, allow_unicode=True), encoding="utf-8")
    return {"tags": payload.tags}


@router.get("/quality")
def get_quality():
    return yaml.safe_load(settings.QUALITY_TEMPLATE_PATH.read_text(encoding="utf-8"))
