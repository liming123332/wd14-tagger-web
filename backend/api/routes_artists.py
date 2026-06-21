"""艺术家图鉴 API。结构与 routes_characters 同构，双图 + 画师标签锁定。"""
from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import secrets

# 裁决 B：brief 原文 import 块遗漏了 get_cf_recent，但 get_artist 内调用
# get_cf_recent().add(ek)，缺 import 会 NameError。此处补齐。
from backend.deps import (get_artist_db, get_anima_artist_db, get_cf_overlay,
                          get_cf_artist_favorites, get_cf_recent, get_tagger, get_classifier)
from backend.models import CfOverlay, CategoryData
from backend.characterfinder import paths
from backend.api.routes_cfassets import local_image_path

router = APIRouter(prefix="/api/cf", tags=["cf-artists"])


def _asset(kind, source, key, which):
    return f"/api/cf/asset?kind={kind}&source={source}&key={key}&which={which}"


def _split(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _danbooru_artist(row: dict, fav: bool) -> dict:
    key = str(row["id"])
    return {"entry_key": paths.entry_key("artist", "danbooru", key),
            "source": "danbooru", "name": row.get("display_name") or row["name"],
            "tag": row["tag"], "thumb1_url": _asset("artist", "danbooru", key, "1"),
            "thumb2_url": _asset("artist", "danbooru", key, "2"), "favorite": fav}


def _anima_artist(row: dict, fav: bool) -> dict:
    key = row["artist"]
    return {"entry_key": paths.entry_key("artist", "anima", key), "source": "anima",
            "name": row.get("name"), "tag": row.get("trigger") or row["artist"],
            "thumb1_url": _asset("artist", "anima", key, "1"),
            "thumb2_url": _asset("artist", "anima", key, "2"), "favorite": fav}


@router.get("/artists")
def search_artists(query: str = "", source: str = Query(...),
                   page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    offset = (page - 1) * size
    favs = set(get_cf_artist_favorites().get_all())
    if source == "anima":
        rows, total = get_anima_artist_db().search(query, limit=size, offset=offset)
        items = [_anima_artist(r, paths.entry_key("artist", "anima", r["artist"]) in favs) for r in rows]
    else:
        rows, total = get_artist_db().search(query, limit=size, offset=offset)
        items = [_danbooru_artist(r, paths.entry_key("artist", "danbooru", str(r["id"])) in favs) for r in rows]
    return {"items": items, "total": total}


@router.get("/artist")
def get_artist(source: str = Query(...), key: str = Query(...)):
    if source == "anima":
        row = get_anima_artist_db().get_by_artist(key) or {}
        base = _anima_artist(row, False)
    else:
        row = get_artist_db().get_by_id(int(key))
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        base = _danbooru_artist(row, False)
    ek = base["entry_key"]
    base["favorite"] = get_cf_artist_favorites().is_favorite(ek)
    base["locked_tags"] = list(dict.fromkeys(_split(base.get("tag", ""))))
    ov = get_cf_overlay().get(ek)
    base["categories"] = {k: v.model_dump() for k, v in (ov.categories if ov else {}).items()}
    base["extras"] = (ov.extras.model_dump() if ov else {"tags": [], "phrase": "", "user_edited": False})
    base["custom_tags"] = ov.custom_tags if ov else []
    base["model"] = ov.model if ov else "wd14"
    base["image_override"] = ov.image_override if ov else None
    get_cf_recent().add(ek)
    return base


# ===== 艺术家联动端点（tag/reclassify/save/image/favorite），与角色同构 =====
class ArtistTagParams(BaseModel):
    model: str = "wd14"; gen_th: float = 0.35; char_th: float = 0.9; use_char: bool = True


class ArtistReclassifyRequest(BaseModel):
    keep: dict[str, list[str]] = {}


class ArtistSaveRequest(BaseModel):
    categories: dict[str, dict] = {}
    extras: dict = {}
    custom_tags: list[str] = []


def _load_artist_overlay_or_new(source: str, key: str) -> CfOverlay:
    ek = paths.entry_key("artist", source, key)
    ov = get_cf_overlay().get(ek)
    return ov if ov is not None else CfOverlay(entry_key=ek, kind="artist")


def _artist_current_image(source: str, key: str):
    ek = paths.entry_key("artist", source, key)
    ov = get_cf_overlay().get(ek)
    if ov and ov.image_override:
        return get_cf_overlay().image_path(ek, ov.image_override), True
    p = (local_image_path("artist", source, key, "1")
         or local_image_path("artist", source, key, "2"))
    return p, False


@router.post("/artist/tag")
def tag_artist(source: str, key: str, params: ArtistTagParams):
    img_path, _ = _artist_current_image(source, key)
    if not img_path or not img_path.exists():
        raise HTTPException(status_code=400, detail="no local image to tag (download cover first)")
    try:
        with Image.open(img_path) as pil:
            raw = get_tagger(params.model).tag_image(pil, params.gen_th, params.char_th, params.use_char)
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"bad image: {e}")
    result = get_classifier().classify(raw)
    ov = _load_artist_overlay_or_new(source, key)
    ov.model = params.model; ov.gen_threshold = params.gen_th
    ov.char_threshold = params.char_th; ov.raw_tags = raw
    ov.categories = {k: v for k, v in result.items() if k != "extras"}
    ov.extras = result["extras"]
    get_cf_overlay().upsert(ov)
    return get_artist(source, key)


@router.post("/artist/reclassify")
def reclassify_artist(source: str, key: str, body: ArtistReclassifyRequest):
    ov = get_cf_overlay().get(paths.entry_key("artist", source, key))
    if ov is None or not ov.raw_tags:
        raise HTTPException(status_code=400, detail="no raw_tags; tag first")
    existing = {k: CategoryData(tags=list(t), user_edited=True) for k, t in body.keep.items()}
    result = get_classifier().classify(ov.raw_tags, existing=existing)
    ov.categories = {k: v for k, v in result.items() if k != "extras"}
    ov.extras = result["extras"]
    get_cf_overlay().upsert(ov)
    return get_artist(source, key)


@router.put("/artist")
def save_artist(source: str, key: str, body: ArtistSaveRequest):
    ov = _load_artist_overlay_or_new(source, key)
    ov.categories = {k: CategoryData(**v) for k, v in body.categories.items()}
    ov.extras = CategoryData(**body.extras) if body.extras else CategoryData()
    ov.custom_tags = body.custom_tags
    get_cf_overlay().upsert(ov)
    return get_artist(source, key)


@router.post("/artist/image")
def upload_artist_image(source: str, key: str, file: UploadFile = File(...)):
    ek = paths.entry_key("artist", source, key)
    data = file.file.read()
    ext = "." + (file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "png")
    name = secrets.token_hex(8) + ext
    get_cf_overlay().set_image(ek, name)
    get_cf_overlay().image_path(ek, name).write_bytes(data)
    ov = _load_artist_overlay_or_new(source, key)
    ov.image_override = name
    get_cf_overlay().upsert(ov)
    return {"image_override": name}


@router.post("/artist/favorite")
def toggle_artist_favorite(source: str, key: str):
    ek = paths.entry_key("artist", source, key)
    return {"favorite": get_cf_artist_favorites().toggle(ek)}
