from __future__ import annotations
import asyncio
import logging
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path

from PIL import Image

from backend import deps

logger = logging.getLogger(__name__)

MAX_JOBS = 16


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


@dataclass
class PathTagState:
    job_id: str
    total: int
    done: int = 0
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    finished: bool = False
    events: list[dict] = field(default_factory=list)
    waiters: list[asyncio.Event] = field(default_factory=list)


class PathTagQueue:
    """异步批量路径打标队列。结构对齐 backend/tasks/queue.py 的 BatchQueue。"""

    def __init__(self):
        self._jobs: "OrderedDict[str, PathTagState]" = OrderedDict()

    def submit(self, path: str, model: str, gen_th: float, char_th: float,
               use_char: bool, recursive: bool, on_conflict: str) -> tuple[str, int]:
        images = expand_images(path, recursive)
        job_id = secrets.token_hex(8)
        state = PathTagState(job_id=job_id, total=len(images))
        self._jobs[job_id] = state
        while len(self._jobs) > MAX_JOBS:
            self._jobs.popitem(last=False)
        asyncio.create_task(self._run(state, images, model, gen_th, char_th,
                                      use_char, on_conflict))
        return job_id, len(images)

    async def _run(self, state, images, model, gen_th, char_th, use_char, on_conflict):
        tagger = deps.get_tagger(model)
        for p in images:
            status, partial = await asyncio.to_thread(
                process_one, p, tagger, gen_th, char_th, use_char, on_conflict)
            if status == "ok":
                state.ok += 1
            elif status == "skip":
                state.skipped += 1
            else:
                state.failed += 1
            evt = dict(partial)
            if evt.get("type") == "progress":
                evt["done"] = state.done + 1
                evt["total"] = state.total
            state.events.append(evt)
            state.done += 1
            for w in state.waiters:
                w.set()
            state.waiters.clear()
        state.finished = True
        state.events.append({"type": "done", "done": state.done, "total": state.total,
                             "ok": state.ok, "skipped": state.skipped, "errors": state.failed})
        for w in state.waiters:
            w.set()
        state.waiters.clear()

    def state(self, job_id):
        return self._jobs.get(job_id)


_pathtag_queue: "PathTagQueue | None" = None


def get_pathtag_queue() -> PathTagQueue:
    global _pathtag_queue
    if _pathtag_queue is None:
        _pathtag_queue = PathTagQueue()
    return _pathtag_queue
