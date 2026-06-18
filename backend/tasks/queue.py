from __future__ import annotations
import asyncio
import logging
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field

from PIL import Image

from backend import deps

logger = logging.getLogger(__name__)

MAX_BATCHES = 16


@dataclass
class BatchState:
    batch_id: str
    total: int
    done: int = 0
    ok: int = 0
    failed: int = 0
    finished: bool = False
    events: list[dict] = field(default_factory=list)
    waiters: list[asyncio.Event] = field(default_factory=list)


class BatchQueue:
    def __init__(self):
        self._batches: "OrderedDict[str, BatchState]" = OrderedDict()

    def submit(self, ids: list[str], gen_th: float, char_th: float) -> str:
        batch_id = secrets.token_hex(8)
        state = BatchState(batch_id=batch_id, total=len(ids))
        self._batches[batch_id] = state
        while len(self._batches) > MAX_BATCHES:
            self._batches.popitem(last=False)  # 删最旧，保留最近 N 个
        asyncio.create_task(self._run(state, ids, gen_th, char_th))
        return batch_id

    async def _run(self, state, ids, gen_th, char_th):
        storage = deps.get_storage()
        clf = deps.get_classifier()
        tagger = deps.get_tagger()
        for mid in ids:
            try:
                meta = storage.get_meta(mid)
                with Image.open(storage.file_path(mid, meta.image.original)) as pil:
                    raw = await asyncio.to_thread(tagger.tag_image, pil, gen_th, char_th, True)
                meta.tagger.gen_threshold = gen_th
                meta.tagger.char_threshold = char_th
                meta.tagger.raw_tags = raw
                result = clf.classify(raw)
                meta.categories = {k: v for k, v in result.items() if k != "extras"}
                meta.extras = result["extras"]
                storage.save_meta(mid, meta)
                state.ok += 1
                evt = {"type": "progress", "done": state.done + 1, "total": state.total,
                       "current": meta.source_name, "id": mid, "status": "ok"}
            except Exception as e:
                logger.warning("batch item %s failed: %r", mid, e)
                state.failed += 1
                evt = {"type": "error", "id": mid, "message": str(e)}
            state.events.append(evt)
            state.done += 1
            for w in state.waiters:
                w.set()
            state.waiters.clear()
        state.finished = True
        state.events.append({"type": "done", "ok": state.ok, "failed": state.failed})
        for w in state.waiters:
            w.set()
        state.waiters.clear()

    def status(self, batch_id):
        s = self._batches.get(batch_id)
        if s is None:
            return {"done": True, "total": 0, "ok": 0, "failed": 0}
        return {"done": s.finished, "total": s.total, "ok": s.ok, "failed": s.failed}

    def state(self, batch_id):
        return self._batches.get(batch_id)


_queue = None
def get_queue():
    global _queue
    if _queue is None:
        _queue = BatchQueue()
    return _queue
