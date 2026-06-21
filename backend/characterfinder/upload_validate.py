"""上传图片校验：大小上限 + 魔数合法性。

供 routes_characters.upload_character_image 与 routes_artists.upload_artist_image
共用，避免坏图/超大文件落盘成孤儿（最终审查 Minor M7+M8 的增强清理）。

设计：
- 先校验大小（10MB），超限直接 413，文件不落盘。
- 用 PIL.Image.open + verify 校验图片头（覆盖 PNG/JPEG/WebP/GIF/BMP/TIFF 等
  PIL 支持的格式）。非合法图片 → 400。
- 校验通过后调用方才 set_image / write_bytes / upsert，保证坏数据不落盘。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

# 10 MB 上限。两端点共用。
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def validate_image_bytes(data: bytes, *, max_bytes: Optional[int] = None) -> None:
    """校验上传字节流：大小 + 魔数（PIL 能否识别为合法图片）。

    失败抛 HTTPException：
    - 413 "image too large"：超过 max_bytes（默认 MAX_UPLOAD_BYTES）。
    - 400 "invalid image"：PIL 无法识别（非图片/损坏/空）。

    成功返回 None。调用方应在 set_image / write_bytes 之前调用本函数。
    """
    limit = max_bytes if max_bytes is not None else MAX_UPLOAD_BYTES
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="image too large")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()  # 解码头校验，不加载像素
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"invalid image: {e}")
