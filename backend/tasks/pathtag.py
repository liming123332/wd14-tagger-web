from __future__ import annotations
import logging
from glob import glob
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def _supported_extensions() -> set[str]:
    """PIL 能打开的图片扩展名集合（带点号、小写）。对齐 mikazuki interrogator.py 取法。"""
    return {e.lower() for e, f in Image.registered_extensions().items() if f in Image.OPEN}


def expand_images(path: str, recursive: bool = False) -> list[Path]:
    """把文件夹路径展开成按文件名排序的图片列表。
    recursive=False：仅直接子文件（path/*）；True：含子目录（path/**/*）。"""
    base = Path(path)
    pattern = f"{base}/**/*" if recursive else f"{base}/*"
    exts = _supported_extensions()
    paths = [
        Path(p) for p in glob(str(pattern), recursive=recursive)
        if Path(p).suffix.lower() in exts
    ]
    return sorted(paths, key=lambda p: p.name)
