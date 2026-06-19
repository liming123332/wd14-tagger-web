import json
import mimetypes
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.deps import get_classifier, get_promptbox_store

router = APIRouter(prefix="/api/promptbox", tags=["promptbox"])


class SplitRequest(BaseModel):
    text: str


@router.post("/split")
def split_prompt(req: SplitRequest):
    res = get_classifier().split(req.text)
    categories = {k: res[k] for k in ("quality", "head", "clothing", "view", "action", "scene")}
    return {"categories": categories, "extras": res["extras"]}


def _parse_json(val: str | None, default):
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


@router.post("")
def create_item(
    title: str = Form(""),
    raw_prompt: str = Form(""),
    categories: str = Form("{}"),
    extras: str = Form("[]"),
    files: list[UploadFile] = File(default_factory=list),
):
    store = get_promptbox_store()
    image_data = [(f.filename or "img.png", f.file.read()) for f in files]
    item = store.create(
        title=title, raw_prompt=raw_prompt,
        categories=_parse_json(categories, {}), extras=_parse_json(extras, []),
        image_data=image_data,
    )
    return item.model_dump()


@router.get("")
def list_items():
    return [it.model_dump() for it in get_promptbox_store().list_all()]


@router.get("/{item_id}")
def get_item(item_id: str):
    it = get_promptbox_store().get(item_id)
    if it is None:
        raise HTTPException(status_code=404, detail="not found")
    return it.model_dump()


@router.put("/{item_id}")
def update_item(
    item_id: str,
    title: str = Form(None),
    raw_prompt: str = Form(None),
    categories: str = Form(None),
    extras: str = Form(None),
    remove_image_names: str = Form(None),
    files: list[UploadFile] = File(default_factory=list),
):
    store = get_promptbox_store()
    if store.get(item_id) is None:
        raise HTTPException(status_code=404, detail="not found")
    image_data = [(f.filename or "img.png", f.file.read()) for f in files]
    try:
        item = store.update(
            item_id, title=title, raw_prompt=raw_prompt,
            categories=_parse_json(categories, None), extras=_parse_json(extras, None),
            new_image_data=image_data,
            remove_image_names=_parse_json(remove_image_names, None),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")
    return item.model_dump()


@router.delete("/{item_id}")
def delete_item(item_id: str):
    get_promptbox_store().delete(item_id)
    return {"ok": True}


@router.get("/{item_id}/image/{name}")
def get_image(item_id: str, name: str):
    store = get_promptbox_store()
    try:
        p = store.image_path(item_id, name)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad name")
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(p, media_type=ctype)
