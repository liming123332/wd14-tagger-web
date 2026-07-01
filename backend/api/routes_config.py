import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings, runtime
from backend.deps import get_classifier, _release_taggers
from backend.characterfinder import paths

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


# ===== Anima 数据更新 token（设置页配置，fetch_anima.py 读取）=====
def _mask_token(t: str) -> str:
    """token 掩码预览：前2 + *** + 后3（过短则全掩）。绝不返回明文。"""
    return (t[:2] + "***" + t[-3:]) if len(t) > 6 else "***"


class AnimaTokenPayload(BaseModel):
    token: str


@router.get("/anima-token")
def get_anima_token():
    """animadex export token 配置状态。token 文件 = paths.ANIMA_TOKEN_PATH
    （fetch_anima.py 读取的 .token），设置页写入。"""
    p = paths.ANIMA_TOKEN_PATH
    if not p.exists():
        return {"configured": False, "preview": None}
    t = p.read_text(encoding="utf-8").strip()
    if not t:
        return {"configured": False, "preview": None}
    return {"configured": True, "preview": _mask_token(t)}


@router.post("/anima-token")
def set_anima_token(payload: AnimaTokenPayload):
    """保存 animadex export token 到本地 .token（fetch_anima.py 读取，不外传）。"""
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token 不能为空")
    p = paths.ANIMA_TOKEN_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token, encoding="utf-8")
    return {"configured": True, "preview": _mask_token(token)}


# ===== 反推设备（force_cpu 开关，设置页切换、立即生效）=====
class DevicePayload(BaseModel):
    force_cpu: bool


@router.get("/device")
def get_device():
    """反推设备偏好：force_cpu=True 时反推（打标）强制走 CPU，否则自动探测 GPU。"""
    return {"force_cpu": runtime.get_force_cpu()}


@router.put("/device")
def put_device(payload: DevicePayload):
    """设置反推设备偏好并立即生效：写偏好 + 卸载已加载的 ONNX session，
    下次反推 _load() 时按新 force_cpu 重建 InferenceSession（无需重启）。"""
    runtime.set_force_cpu(payload.force_cpu)
    released = _release_taggers()  # 立即生效：释放已加载 session，下次反推按新设备重载
    return {"force_cpu": payload.force_cpu, "released": released}
