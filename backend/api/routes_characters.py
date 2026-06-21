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
from fastapi import APIRouter, HTTPException, Query

from backend.deps import (
    get_character_db,
    get_anima_character_db,
    get_cf_overlay,
    get_cf_favorites,
    get_cf_recent,
)
from backend.characterfinder import paths

router = APIRouter(prefix="/api/cf", tags=["cf-characters"])


def _asset_url(kind: str, source: str, key: str, which: str) -> str:
    return f"/api/cf/asset?kind={kind}&source={source}&key={key}&which={which}"


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
    key = row["character"]
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
        row = get_anima_character_db().get_by_character(key) or {}
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
