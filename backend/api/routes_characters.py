"""角色图鉴 API：搜索/详情（权威+overlay 合并），权威标签锁定。

- 权威字段来自 characters.db（danbooru/e621）或 anima_characters.db（anima）。
  trigger + core_tags 经 _split_tags 合并去重保序后作为 locked_tags，禁止编辑。
- overlay 层（cf_overlay.db）保存用户反推/编辑/换图，物理隔离，缺失时给默认值。
- 字段映射/合并规则见 task-9-brief；以下两处按控制器裁决修正自 brief 原文：
  * search_characters 的 anima 分支用 db.search(copyright=series or None, ...)
    （anima_db 真实参数名是 ``copyright``，不是 brief 写的 ``copyright_filter``）。
  * list_series 的 anima 分支：anima_db.list_copyrights() 返回 list[dict]，每项
    形如 {"copyright": str, "n": int}；danbooru 分支的 get_character_db().list_series()
    返回 list[tuple[str,int]]，二者形态不同，故分别处理。
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import secrets
from urllib.parse import quote

# 裁决 C（Task 11）：将 favorites/recent/random 追加端点需要的依赖合并进此顶部
# import 块（避免 brief 写的中部重复 import 块）。原 Task 9/10 已含 char 侧依赖，
# Task 11 追加 artist 侧：get_cf_artist_favorites / get_artist_db / get_anima_artist_db。
from backend.deps import (
    get_character_db,
    get_anima_character_db,
    get_cf_overlay,
    get_cf_favorites,
    get_cf_artist_favorites,
    get_cf_recent,
    get_tagger,
    get_classifier,
    get_artist_db,
    get_anima_artist_db,
)
from backend.models import CfOverlay, CategoryData
from backend.characterfinder import paths
from backend.characterfinder.upload_validate import validate_image_bytes, MAX_UPLOAD_BYTES
from backend.api.routes_cfassets import local_image_path

router = APIRouter(prefix="/api/cf", tags=["cf-characters"])


def _asset_url(kind: str, source: str, key: str, which: str) -> str:
    # key 来自权威数据，可能含 & # = 等字符（如组合画师 "a & b"）。
    # 必须 URL 编码，否则会截断查询字符串（前端列表 cfAssetUrl 已编码，
    # 详情页用的是后端拼的此 URL，故在此编码）。kind/source/which 为枚举值，无需编码。
    return f"/api/cf/asset?kind={kind}&source={source}&key={quote(key, safe='')}&which={which}"


def _split_tags(text: str) -> list[str]:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _danbooru_item(row: dict, favorite: bool) -> dict:
    key = str(row["id"])
    return {
        "entry_key": paths.entry_key("char", "danbooru", key),
        "source": row.get("source") or "danbooru",
        "name": row["name"], "series": row.get("series"),
        "trigger": row["name"], "core_tags": row.get("tags") or "",
        "thumb_url": _asset_url("char", "danbooru", key, "thumb"),
        "image_url": _asset_url("char", "danbooru", key, "image"),
        "favorite": favorite,
    }


def _anima_item(row: dict, favorite: bool) -> dict:
    key = row.get("character")
    return {
        "entry_key": paths.entry_key("char", "anima", key),
        "source": "anima", "name": row.get("name"),
        "series": row.get("copyright"),
        "trigger": row.get("trigger") or "", "core_tags": row.get("core_tags") or "",
        "thumb_url": _asset_url("char", "anima", key, "thumb"),
        "image_url": _asset_url("char", "anima", key, "image"),
        "favorite": favorite,
    }


@router.get("/characters")
def search_characters(query: str = "", source: str = Query(...),
                      series: str = "", page: int = Query(1, ge=1),
                      size: int = Query(50, ge=1, le=200)):
    offset = (page - 1) * size
    favs = set(get_cf_favorites().get_all())
    if source == "anima":
        # 裁决 B：anima_db.search 参数名是 ``copyright``，不是 ``copyright_filter``。
        rows, total = get_anima_character_db().search(
            query, copyright=series or None, limit=size, offset=offset,
        )
        items = [_anima_item(r, paths.entry_key("char", "anima", r["character"]) in favs)
                 for r in rows]
    else:  # danbooru / e621 都在 characters.db
        rows, total = get_character_db().search(
            query, series_filter=series or None,
            source_filter=source, limit=size, offset=offset,
        )
        items = [_danbooru_item(r, paths.entry_key("char", "danbooru", str(r["id"])) in favs)
                 for r in rows]
    return {"items": items, "total": total}


@router.get("/characters/series")
def list_series(source: str = Query(...)):
    if source == "anima":
        # 裁决 C：list_copyrights() 返回 list[dict]，每项 {"copyright": str, "n": int}。
        return [{"series": d["copyright"], "count": d["n"]}
                for d in get_anima_character_db().list_copyrights()]
    # danbooru 分支：list_series() 返回 list[tuple[str, int]]，直接解包。
    return [{"series": s, "count": n} for s, n in get_character_db().list_series()]


@router.get("/character")
def get_character(source: str = Query(...), key: str = Query(...)):
    # 权威字段
    if source == "anima":
        row = get_anima_character_db().get_by_character(key)
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        base = _anima_item(row, False)
    else:
        row = get_character_db().get_by_id(int(key))
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        base = _danbooru_item(row, False)
    ek = base["entry_key"]
    base["favorite"] = get_cf_favorites().is_favorite(ek)
    # 锁定标签 = trigger 词 + core_tags 词，去重保序
    locked: list[str] = []
    if base["trigger"]:
        locked += _split_tags(base["trigger"])
    locked += _split_tags(base["core_tags"])
    base["locked_tags"] = list(dict.fromkeys(locked))
    # overlay 合并：无 overlay 时给与 CategoryData 默认一致的值
    ov = get_cf_overlay().get(ek)
    base["categories"] = {k: v.model_dump() for k, v in (ov.categories if ov else {}).items()}
    base["extras"] = (ov.extras if ov else None).model_dump() if ov else {
        "tags": [], "phrase": "", "user_edited": False,
    }
    base["custom_tags"] = ov.custom_tags if ov else []
    base["model"] = ov.model if ov else "wd14"
    base["gen_threshold"] = ov.gen_threshold if ov else 0.35
    base["char_threshold"] = ov.char_threshold if ov else 0.9
    base["image_override"] = ov.image_override if ov else None
    # 记录最近查看
    get_cf_recent().add(ek)
    return base


class TagParams(BaseModel):
    model: str = "wd14"; gen_th: float = 0.35; char_th: float = 0.9; use_char: bool = True


class ReclassifyRequest(BaseModel):
    keep: dict[str, list[str]] = {}


class SaveRequest(BaseModel):
    categories: dict[str, dict] = {}
    extras: dict = {}
    custom_tags: list[str] = []


def _load_overlay_or_new(source: str, key: str) -> CfOverlay:
    ek = paths.entry_key("char", source, key)
    ov = get_cf_overlay().get(ek)
    if ov is None:
        ov = CfOverlay(entry_key=ek, kind="char")
    return ov


def _current_image_path(source: str, key: str):
    ov = get_cf_overlay().get(paths.entry_key("char", source, key))
    if ov and ov.image_override:
        return get_cf_overlay().image_path(ov.entry_key, ov.image_override), True
    p = local_image_path("char", source, key, "image") or local_image_path("char", source, key, "thumb")
    return p, False


@router.post("/character/tag")
def tag_character(source: str, key: str, params: TagParams):
    img_path, _ = _current_image_path(source, key)
    if not img_path or not img_path.exists():
        raise HTTPException(status_code=400, detail="no local image to tag (download cover first)")
    try:
        with Image.open(img_path) as pil:
            raw = get_tagger(params.model).tag_image(pil, params.gen_th, params.char_th, params.use_char)
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail=f"bad image: {e}")
    result = get_classifier().classify(raw)
    ov = _load_overlay_or_new(source, key)
    ov.model = params.model; ov.gen_threshold = params.gen_th
    ov.char_threshold = params.char_th; ov.raw_tags = raw
    ov.categories = {k: v for k, v in result.items() if k != "extras"}
    ov.extras = result["extras"]
    get_cf_overlay().upsert(ov)
    return get_character(source, key)


@router.post("/character/reclassify")
def reclassify_character(source: str, key: str, body: ReclassifyRequest):
    ov = get_cf_overlay().get(paths.entry_key("char", source, key))
    if ov is None or not ov.raw_tags:
        raise HTTPException(status_code=400, detail="no raw_tags; tag first")
    existing = {k: CategoryData(tags=list(t), user_edited=True) for k, t in body.keep.items()}
    result = get_classifier().classify(ov.raw_tags, existing=existing)
    ov.categories = {k: v for k, v in result.items() if k != "extras"}
    ov.extras = result["extras"]
    get_cf_overlay().upsert(ov)
    return get_character(source, key)


@router.put("/character")
def save_character(source: str, key: str, body: SaveRequest):
    ov = _load_overlay_or_new(source, key)
    ov.categories = {k: CategoryData(**v) for k, v in body.categories.items()}
    ov.extras = CategoryData(**body.extras) if body.extras else CategoryData()
    ov.custom_tags = body.custom_tags
    get_cf_overlay().upsert(ov)
    return get_character(source, key)


@router.post("/character/image")
def upload_character_image(source: str, key: str, file: UploadFile = File(...)):
    ek = paths.entry_key("char", source, key)
    data = file.file.read()
    # 健壮性：先校验大小 + 魔数（M7+M8），坏图/超大文件不落盘（避免孤儿）。
    validate_image_bytes(data)
    ext = "." + (file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "png")
    name = secrets.token_hex(8) + ext
    get_cf_overlay().set_image(ek, name)
    get_cf_overlay().image_path(ek, name).write_bytes(data)
    ov = _load_overlay_or_new(source, key)
    ov.image_override = name
    get_cf_overlay().upsert(ov)
    return {"image_override": name}


@router.post("/character/favorite")
def toggle_favorite(source: str, key: str):
    ek = paths.entry_key("char", source, key)
    return {"favorite": get_cf_favorites().toggle(ek)}


# ============================================================================
# Task 11：共享 /api/cf 前缀的收藏/最近/随机端点（char + artist 统一入口）。
# 追加到 routes_characters.py 末尾，而非 routes_artists.py，避免与 artist 路由
# 同前缀注册冲突；deps import 已合并进顶部（裁决 C）。
# ============================================================================


def _resolve_item(entry_key: str) -> dict | None:
    """从 entry_key 反查权威 db 取回基础信息（带 favorite=True）。找不到返回 None。"""
    try:
        k, src, key = paths.parse_entry_key(entry_key)
    except ValueError:
        return None
    if k == "char":
        row = (get_anima_character_db().get_by_character(key) if src == "anima"
               else get_character_db().get_by_id(int(key)))
        if not row:
            return None
        return _anima_item(row, True) if src == "anima" else _danbooru_item(row, True)
    # artist：lazy import 规避模块顶层循环导入
    from backend.api.routes_artists import _anima_artist, _danbooru_artist
    row = (get_anima_artist_db().get_by_artist(key) if src == "anima"
           else get_artist_db().get_by_id(int(key)))
    if not row:
        return None
    return _anima_artist(row, True) if src == "anima" else _danbooru_artist(row, True)


def _resolve_items(keys: list[str]) -> list[dict]:
    out = []
    for ek in keys:
        item = _resolve_item(ek)
        if item is not None:
            out.append(item)
    return out


# 裁决 D（Task 11）：brief 原文用 Query(regex=...)，FastAPI/pydantic v2 中 regex=
# 已 deprecated，改用 pattern=。
@router.get("/favorites")
def list_favorites(kind: str = Query("char", pattern="^(char|artist)$")):
    store = get_cf_favorites() if kind == "char" else get_cf_artist_favorites()
    keys = [ek for ek in store.get_all() if ek.startswith(f"{kind}:")]
    return {"items": _resolve_items(keys)}


@router.get("/recent")
def list_recent(kind: str = Query("char", pattern="^(char|artist)$"),
                limit: int = Query(50, le=200)):
    keys = [ek for ek in get_cf_recent().get_all() if ek.startswith(f"{kind}:")]
    return {"items": _resolve_items(keys[:limit])}


@router.get("/random")
def random_cf(type: str = Query("characters"), source: str = Query("danbooru"),
              size: int = Query(24, ge=1, le=200)):
    # 真随机：db.random(size) 用 ORDER BY RANDOM()。旧实现 db.search("", limit=size)
    # 固定 ORDER BY rank/count ASC 取前 N，「再抽一页」永远返回同一批——已修。
    if type == "artists":
        db = get_anima_artist_db() if source == "anima" else get_artist_db()
        rows = db.random(size)
        favs = set(get_cf_artist_favorites().get_all())
        from backend.api.routes_artists import _anima_artist, _danbooru_artist
        items = [_anima_artist(r, paths.entry_key("artist", source, r["artist"]) in favs) if source == "anima"
                 else _danbooru_artist(r, paths.entry_key("artist", "danbooru", str(r["id"])) in favs) for r in rows]
    else:
        db = get_anima_character_db() if source == "anima" else get_character_db()
        rows = db.random(size)
        favs = set(get_cf_favorites().get_all())
        items = [_anima_item(r, paths.entry_key("char", source, r["character"]) in favs) if source == "anima"
                 else _danbooru_item(r, paths.entry_key("char", "danbooru", str(r["id"])) in favs) for r in rows]
    return {"items": items}
