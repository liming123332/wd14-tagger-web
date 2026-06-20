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


def process_one(
    path: Path, tagger, gen_th: float, char_th: float,
    use_char: bool, on_conflict: str,
) -> tuple[str, dict]:
    """处理单张图：读图 → 反推 → 写同名 .txt。返回 (status, sse_event_partial)。
    status ∈ {"ok","skip","error"}；event 已含 type/current/(status|message)，
    done/total 由调用方（_run）在 append 前补全。单张失败不抛出，交由调用方累计。"""
    try:
        with Image.open(path) as pil:
            tags = tagger.tag_image(pil, gen_th, char_th, use_char)
        # tag_image 已做阈值过滤 + _→空格，这里仅按分数降序拼成纯逗号文本（无权重）。
        text = ", ".join(sorted(tags, key=tags.get, reverse=True))
        out = path.with_suffix(".txt")
        if on_conflict == "skip" and out.exists():
            return "skip", {"type": "progress", "current": path.name, "status": "skip"}
        out.write_text(text, encoding="utf-8")
        return "ok", {"type": "progress", "current": path.name, "status": "ok"}
    except Exception as e:
        logger.warning("pathtag %s failed: %r", path, e)
        return "error", {"type": "error", "current": path.name, "message": str(e)}
