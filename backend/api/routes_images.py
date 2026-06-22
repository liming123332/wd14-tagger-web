import mimetypes
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from backend.deps import get_storage

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("")
def upload_images(files: list[UploadFile] = File(...), tags: list[str] = Form(default_factory=list)):
    storage = get_storage()
    # 先全部解码验证，避免部分失败时已写盘的孤儿文件
    decoded = []
    for f in files:
        try:
            pil = Image.open(f.file)
            pil.load()
        except (UnidentifiedImageError, OSError) as e:
            raise HTTPException(status_code=400, detail=f"bad image {f.filename}: {e}")
        decoded.append((pil, f.filename or "upload.png"))
    ids = [storage.save_upload(pil, name, tags) for pil, name in decoded]
    return {"ids": ids}


@router.get("/{mid}/file/{name}")
def get_file(mid: str, name: str):
    storage = get_storage()
    try:
        p = storage.file_path(mid, name)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad file name")
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(p, media_type=ctype)


from pydantic import BaseModel
from backend.deps import get_classifier, get_tagger
from backend.tagger.models_spec import DEFAULT_MODEL_KEY


class TagParams(BaseModel):
    gen_th: float = 0.35
    char_th: float = 0.9
    use_char: bool = True
    model: str = DEFAULT_MODEL_KEY


@router.post("/{mid}/tag")
def tag_image(mid: str, params: TagParams):
    storage = get_storage()
    try:
        meta = storage.get_meta(mid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="image not found")
    img_path = storage.file_path(mid, meta.image.original)
    try:
        with Image.open(img_path) as pil:
            raw = get_tagger(params.model).tag_image(pil, params.gen_th, params.char_th, params.use_char)
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"bad image {mid}: {e}")
    meta.tagger.gen_threshold = params.gen_th
    meta.tagger.char_threshold = params.char_th
    meta.tagger.raw_tags = raw
    meta.model = params.model
    result = get_classifier().classify(raw)
    meta.categories = {k: v for k, v in result.items() if k != "extras"}
    meta.extras = result["extras"]
    storage.save_meta(mid, meta)
    return meta.model_dump()


@router.post("/{mid}/reclassify")
def reclassify(mid: str):
    storage = get_storage()
    try:
        meta = storage.get_meta(mid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="image not found")
    existing = dict(meta.categories)
    existing["extras"] = meta.extras
    result = get_classifier().classify(meta.tagger.raw_tags, existing=existing)
    meta.categories = {k: v for k, v in result.items() if k != "extras"}
    meta.extras = result["extras"]
    storage.save_meta(mid, meta)
    return meta.model_dump()


from backend.models import Meta


@router.get("")
def list_images(
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=200),
    date: str | None = Query(None, min_length=8, max_length=8),
    random: bool = Query(False),
    tags: list[str] = Query(default_factory=list),
    prompt: list[str] = Query(default_factory=list),
):
    return get_storage().list_images(page, size, date=date, random=random, tags=tags, prompt=prompt)


# 必须声明在 /{mid} 之前：FastAPI 按注册顺序匹配，否则 GET /tags 会命中
# get_meta_endpoint(mid="tags") 返回 404。
@router.get("/tags")
def list_all_tags():
    return get_storage().all_tags()


@router.get("/{mid}")
def get_meta_endpoint(mid: str):
    storage = get_storage()
    try:
        return storage.get_meta(mid).model_dump()
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="image not found")


@router.put("/{mid}")
def save_meta_endpoint(mid: str, meta: Meta):
    storage = get_storage()
    try:
        d = storage.image_dir(mid)
    except ValueError:
        raise HTTPException(status_code=404, detail="image not found")
    if not d.exists():
        raise HTTPException(status_code=404, detail="image not found")
    meta = meta.model_copy(update={"id": mid})
    storage.save_meta(mid, meta)
    return storage.get_meta(mid).model_dump()


@router.post("/{mid}/replace")
def replace_image_endpoint(mid: str, file: UploadFile = File(...)):
    """替换某图库图片的原图+缩略图，保留 meta 标签/收藏（不自动反推）。
    旧标签与新图可能不符，前端提示用户可手动「重新反推」。"""
    storage = get_storage()
    try:
        storage.get_meta(mid)  # 校验存在性 + mid 合法性
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="image not found")
    try:
        pil = Image.open(file.file)
        pil.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"bad image: {e}")
    meta = storage.replace_image(mid, pil, file.filename or "replace.png")
    return meta.model_dump()


@router.delete("/{mid}")
def delete_image(mid: str):
    try:
        get_storage().delete(mid)
    except ValueError:
        raise HTTPException(status_code=404, detail="image not found")
    return {"ok": True}
