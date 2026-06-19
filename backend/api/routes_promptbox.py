import json
import mimetypes
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError

from backend.deps import get_classifier, get_tagger, get_promptbox_store
from backend.tagger.models_spec import DEFAULT_MODEL_KEY
from backend.models import PROMPT_ORDER

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


# ---- 反推工作区 ----
# 路由须在 /{item_id} 之前注册：否则 GET /workspace/... 的首段会被 /{item_id} 捕获。
# analyze：图落 workspace（不进图库 data/images/），反推+分类后返回，供前端工作台网格展示。
@router.post("/analyze")
def analyze(
    files: list[UploadFile] = File(...),
    model: str = Form(DEFAULT_MODEL_KEY),
    gen_th: float = Form(0.35),
    char_th: float = Form(0.9),
):
    store = get_promptbox_store()
    tagger = get_tagger(model)
    classifier = get_classifier()
    items = []
    for f in files:
        try:
            pil = Image.open(f.file)
            pil.load()
        except (UnidentifiedImageError, OSError) as e:
            raise HTTPException(status_code=400, detail=f"bad image {f.filename}: {e}")
        local_id = store.new_id()
        orig, thumb, w, h = store.save_workspace_image(local_id, pil, f.filename or "img.png")
        raw = tagger.tag_image(pil, gen_th, char_th, True)
        classified = classifier.classify(raw)
        categories = {k: list(classified[k].tags) for k in PROMPT_ORDER}
        extras = list(classified["extras"].tags)
        # raw_prompt 含全部 6 类 + extras，供工作区卡片预览/复制（区别图库 build_prompt 不含 extras）
        all_tags = [t for k in PROMPT_ORDER for t in categories[k]] + extras
        items.append({
            "local_id": local_id, "original": orig, "thumb": thumb,
            "width": w, "height": h, "model": model,
            "categories": categories, "extras": extras,
            "raw_prompt": ", ".join(all_tags),
        })
    return {"items": items}


@router.get("/workspace/{local_id}/image/{name}")
def get_workspace_image(local_id: str, name: str):
    store = get_promptbox_store()
    try:
        p = store.workspace_image_path(local_id, name)
    except ValueError:
        raise HTTPException(status_code=400, detail="bad name")
    if not p.exists():
        raise HTTPException(status_code=404, detail="not found")
    ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    return FileResponse(p, media_type=ctype)


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
