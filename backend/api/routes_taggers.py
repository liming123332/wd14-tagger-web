from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.tagger import models_spec
from backend.deps import get_tagger, _reset_tagger_cache

router = APIRouter(prefix="/api/taggers", tags=["taggers"])


@router.get("")
def list_taggers():
    root = settings.MODELS_DIR
    return [
        {"key": key, "label": spec.label, "downloaded": models_spec.is_downloaded(key, root)}
        for key, spec in models_spec.MODEL_SPECS.items()
    ]


@router.post("/{key}/download")
def download_tagger(key: str):
    if key not in models_spec.MODEL_SPECS:
        raise HTTPException(status_code=404, detail="unknown tagger")
    try:
        # ensure_loaded 内部 _download 会逐文件补全缺失文件，再加载 session。
        get_tagger(key).ensure_loaded()
    except Exception as e:
        # 失败清缓存，避免残留半成品实例影响后续重试
        _reset_tagger_cache()
        raise HTTPException(status_code=500, detail=f"download failed: {e}")
    return {"key": key, "downloaded": models_spec.is_downloaded(key, settings.MODELS_DIR)}
