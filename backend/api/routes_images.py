import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from backend.deps import get_storage

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("")
def upload_images(files: list[UploadFile] = File(...)):
    storage = get_storage()
    ids = []
    for f in files:
        try:
            pil = Image.open(f.file)
            pil.load()
        except (UnidentifiedImageError, Exception) as e:
            raise HTTPException(status_code=400, detail=f"bad image {f.filename}: {e}")
        mid = storage.save_upload(pil, f.filename or "upload.png")
        ids.append(mid)
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
    # Windows 的 mimetypes 数据库不含 .webp，会回退到 application/octet-stream，
    # 显式补一个 image/* 类型，保证缩略图等图片资源 content-type 正确。
    ctype, _ = mimetypes.guess_type(str(p))
    if not ctype or not ctype.startswith("image"):
        ctype = "image/webp" if p.suffix.lower() == ".webp" else "application/octet-stream"
    return FileResponse(p, media_type=ctype)
