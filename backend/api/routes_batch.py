import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.tasks.queue import get_queue
from backend.tagger.models_spec import DEFAULT_MODEL_KEY

router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchRequest(BaseModel):
    ids: list[str]
    gen_th: float = 0.35
    char_th: float = 0.9
    model: str = DEFAULT_MODEL_KEY


@router.post("/tag")
async def submit_batch(req: BatchRequest):
    if not req.ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")
    bid = get_queue().submit(req.ids, req.gen_th, req.char_th, req.model)
    return {"batch_id": bid}


@router.get("/{batch_id}/status")
def batch_status(batch_id: str):
    return get_queue().status(batch_id)


@router.get("/{batch_id}/events")
async def batch_events(batch_id: str):
    state = get_queue().state(batch_id)
    if state is None:
        return StreamingResponse(iter(["data: " + json.dumps({"type": "done", "ok": 0, "failed": 0}) + "\n\n"]),
                                 media_type="text/event-stream")

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
