import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.tasks.pathtag import get_pathtag_queue
from backend.tagger.models_spec import MODEL_SPECS

router = APIRouter(prefix="/api/pathtag", tags=["pathtag"])


class PathTagRequest(BaseModel):
    path: str
    model: str = "cl_tagger_v2"
    gen_th: float = 0.55
    char_th: float = 0.55
    use_char: bool = True
    recursive: bool = False
    on_conflict: str = "overwrite"


@router.post("/start")
async def start_pathtag(req: PathTagRequest):
    if req.model not in MODEL_SPECS:
        raise HTTPException(status_code=400, detail="unknown tagger")
    if req.on_conflict not in ("overwrite", "skip"):
        raise HTTPException(status_code=400, detail="on_conflict must be overwrite or skip")
    if not Path(req.path).is_dir():
        raise HTTPException(status_code=400, detail="path not found or not a directory")
    job_id, total = get_pathtag_queue().submit(
        req.path, req.model, req.gen_th, req.char_th,
        req.use_char, req.recursive, req.on_conflict)
    return {"job_id": job_id, "total": total}


@router.get("/{job_id}/events")
async def pathtag_events(job_id: str):
    state = get_pathtag_queue().state(job_id)
    if state is None:
        return StreamingResponse(
            iter(["data: " + json.dumps(
                {"type": "done", "done": 0, "total": 0, "ok": 0, "skipped": 0, "errors": 0}
            ) + "\n\n"]),
            media_type="text/event-stream",
        )

    async def gen():
        idx = 0
        while True:
            while idx < len(state.events):
                yield "data: " + json.dumps(state.events[idx]) + "\n\n"
                if state.events[idx].get("type") == "done":
                    return
                idx += 1
            if state.finished and idx >= len(state.events):
                return
            ev = asyncio.Event()
            state.waiters.append(ev)
            await ev.wait()

    return StreamingResponse(gen(), media_type="text/event-stream")
