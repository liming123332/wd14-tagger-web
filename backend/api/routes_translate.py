from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.translate import translator as tr_mod
from backend.deps import get_translator, release_translator

router = APIRouter(prefix="/api/translate", tags=["translate"])


class TranslateReq(BaseModel):
    texts: list[str]
    target: str | None = None  # 缺省译成中文（translator.DEFAULT_TARGET）


@router.get("/status")
def status():
    # 前端首次翻译前查：未下载则触发下载（设置页 + 详情页点翻译自动编排）
    t = get_translator()
    return {"downloaded": tr_mod.is_downloaded(settings.MODELS_DIR), "loaded": t.loaded}


@router.post("/download")
def download():
    # ensure_loaded = 补全缺失文件 + 加载。下载进度由 _download_util._state 驱动，
    # 前端复用 GET /api/taggers/download-progress 轮询 + App.vue 全局浮层（与 tagger 同款）。
    try:
        get_translator().ensure_loaded()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"download failed: {e}")
    return {"downloaded": tr_mod.is_downloaded(settings.MODELS_DIR)}


@router.post("")
def translate(req: TranslateReq):
    # 翻译不落地：每次现译，结果不存库。未下载返回 409，前端编排先下载再重试。
    if not tr_mod.is_downloaded(settings.MODELS_DIR):
        raise HTTPException(status_code=409, detail="translate model not downloaded")
    try:
        t = get_translator()
        results = t.translate(req.texts, target=req.target or tr_mod.DEFAULT_TARGET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"translate failed: {e}")
    return {"results": results}


class ToTagsReq(BaseModel):
    texts: list[str]  # 中文短语（详情页「中文添加标签」用）


@router.post("/to-tags")
def to_tags(req: ToTagsReq):
    # 中文 → 英文 danbooru 标签（反向词典兜底 + Hy-MT2 模型）。详情页中文输入转标准英文 tag。
    # 复用翻译模型：未下载返回 409（与 translate 一致，前端编排先下载再重试）。
    if not tr_mod.is_downloaded(settings.MODELS_DIR):
        raise HTTPException(status_code=409, detail="translate model not downloaded")
    try:
        t = get_translator()
        results = t.translate_to_tags(req.texts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"translate failed: {e}")
    return {"results": results}


@router.post("/unload")
def unload():
    # 释放已加载 Llama（显存/RAM），不删 GGUF；下次翻译重新 lazy-load。
    release_translator()
    return {"released": True}
