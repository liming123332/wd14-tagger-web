import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.deps import get_classifier

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/rules")
def get_rules():
    return yaml.safe_load(settings.TAG_RULES_PATH.read_text(encoding="utf-8"))


# 可写入分类词表的分类（= settings.PRIORITY；quality 来自模板，extras 无规则）
_RULE_CATEGORIES = ["head", "clothing", "view", "action", "scene"]


class CategoryRulePayload(BaseModel):
    tags: list[str]


@router.put("/rules/{category}")
def put_category_rules(category: str, payload: CategoryRulePayload):
    """把 tags 合并进该分类的 exact 词表（去重、小写），并 reload 分类器，
    使下次反推时这些词自动归到此分类。"""
    if category not in _RULE_CATEGORIES:
        raise HTTPException(status_code=400, detail="category not editable")
    data = yaml.safe_load(settings.TAG_RULES_PATH.read_text(encoding="utf-8")) or {}
    cats = data.setdefault("categories", {})
    spec = cats.setdefault(category, {})
    exact = spec.setdefault("exact", [])
    existing = {str(w).lower() for w in exact}
    for t in payload.tags:
        tl = (t or "").strip().lower()
        if tl and tl not in existing:
            exact.append(tl)
            existing.add(tl)
    spec["exact"] = exact
    settings.TAG_RULES_PATH.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    get_classifier().reload()  # 立即生效，无需重启
    return {"category": category, "exact": exact}


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
