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
