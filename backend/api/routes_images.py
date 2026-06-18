import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from backend.deps import get_storage

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("")
def upload_images(files: list[UploadFile] = File(...)):
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
    ids = [storage.save_upload(pil, name) for pil, name in decoded]
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


class TagParams(BaseModel):
    gen_th: float = 0.35
    char_th: float = 0.9
    use_char: bool = True


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
            raw = get_tagger().tag_image(pil, params.gen_th, params.char_th, params.use_char)
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"bad image {mid}: {e}")
    meta.tagger.gen_threshold = params.gen_th
    meta.tagger.char_threshold = params.char_th
    meta.tagger.raw_tags = raw
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
