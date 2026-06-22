"""封面资产服务：本地优先，未命中回退 CDN（307）。

三层解析顺序：
  1. overlay 替换图（cf_overlay.db + overlay/<safe_key>/）
  2. 本地下载/拷贝图（paths.COVERS_DIR / ARTIST_COVERS_DIR / ANIMA_DIR）
  3. 原始 CDN url（307 RedirectResponse）
  4. 都没有 → 404

Task 9-11 的角色/艺术家详情页 <img src> 统一指向 /api/cf/asset?...，
由本路由解析为本地文件或回退到 CDN，是离线化的关键一环。
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from backend.deps import (
    get_character_db,
    get_artist_db,
    get_anima_character_db,
    get_anima_artist_db,
    get_cf_overlay,
)
from backend.characterfinder import paths
from backend.characterfinder.anima_db import character_thumb_url, artist_thumb_url

router = APIRouter(prefix="/api/cf/asset", tags=["cf-asset"])


def _slug(url: str) -> str:
    return Path(url).name


def local_image_path(kind: str, source: str, key: str, which: str) -> Path | None:
    """根据 kind/source/key/which 在本地文件系统定位图片（不存在不代表路径无效，
    调用方仍需 .exists() 判断）。路径推导失败返回 None。"""
    try:
        if kind == "char" and source in ("danbooru", "e621"):
            row = get_character_db().get_by_id(int(key))
            url = row["image_url"] if row else None
            return paths.COVERS_DIR / _slug(url) if url else None
        if kind == "artist" and source in ("danbooru", "e621"):
            row = get_artist_db().get_by_id(int(key))
            url = (row or {}).get(f"image_url_{which}")
            return paths.ARTIST_COVERS_DIR / _slug(url) if url else None
        if kind == "char" and source == "anima":
            row = get_anima_character_db().get_by_character(key)
            # anima 离线包只携带 webp 缩略图（thumbname）；png 原图（imgname）几乎未带
            # （animadex-data：artists/images 0 张、characters/images 仅 1823/36483）。
            # 且前端 which 命名不统一（char=thumb/image、artist=1/2），旧逻辑只认
            # which=="thumb" → artist 的 1/2 总走 imgname → 本地 png 不存在 → 回退 CDN →
            # 离线全部裂图。统一用 thumbname 命中本地 webp，which 不再区分。
            name = (row or {}).get("thumbname")
            return paths.ANIMA_DIR / "characters" / name if name else None
        if kind == "artist" and source == "anima":
            row = get_anima_artist_db().get_by_artist(key)
            name = (row or {}).get("thumbname")
            return paths.ANIMA_DIR / "artists" / name if name else None
    except Exception:
        return None
    return None


def fallback_url(kind: str, source: str, key: str, which: str) -> str | None:
    """从对应 db 读原始 url 作为 CDN 回退。danbooru/e621 直接返回 image_url；
    anima 返回 db 的 url（posts 页面占位，待后续下载）。"""
    try:
        if kind == "char" and source in ("danbooru", "e621"):
            row = get_character_db().get_by_id(int(key))
            return row["image_url"] if row else None
        if kind == "artist" and source in ("danbooru", "e621"):
            row = get_artist_db().get_by_id(int(key))
            return (row or {}).get(f"image_url_{which}")
        if kind == "char" and source == "anima":
            row = get_anima_character_db().get_by_character(key)
            return row["url"] if row else None
        if kind == "artist" and source == "anima":
            row = get_anima_artist_db().get_by_artist(key)
            return row["url"] if row else None
    except Exception:
        return None
    return None


@router.get("")
def get_asset(kind: str = Query(...), source: str = Query(...),
              key: str = Query(...), which: str = Query("thumb")):
    # 1) overlay 替换图优先
    from backend.characterfinder.paths import entry_key
    ek = entry_key(kind, source, key)
    ov = get_cf_overlay().get(ek)
    if ov and ov.image_override:
        p = get_cf_overlay().image_path(ek, ov.image_override)
        if p.exists():
            return FileResponse(str(p))
    # 2) 本地下载/拷贝图
    p = local_image_path(kind, source, key, which)
    if p and p.exists():
        return FileResponse(str(p))
    # 3) CDN 回退
    url = fallback_url(kind, source, key, which)
    if url:
        return RedirectResponse(url, status_code=307)
    # 4) 都没有
    raise HTTPException(status_code=404, detail="no asset")


def _download_to(url: str, dest: Path) -> int:
    """下载 URL 到 dest（.part 临时文件 + os.replace 原子改名，避免半成品/杀软锁）。
    思路同 scripts/fetch_anima.py 的 download()。"""
    import os
    import urllib.error
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "wd14-portable/1"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            data = r.read()
            f.write(data)
        os.replace(tmp, dest)
        return len(data)
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        if e.code == 404:
            raise HTTPException(status_code=404, detail="服务端暂无此缩略图")
        raise HTTPException(status_code=502, detail=f"下载失败: HTTP {e.code}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"下载失败: {e}")


@router.post("/refresh-thumb")
def refresh_thumb(kind: str = Query(...), source: str = Query(...), key: str = Query(...)):
    """重新从 animadex R2 拉取单个角色/画师的 webp 缩略图到本地（公开 URL，无需 token）。
    仅 anima 源；下载到 paths.ANIMA_DIR/{characters,artists}/<thumbname>，与 local_image_path
    的 anima 落点一致，下次 /api/cf/asset 即命中本地。"""
    if source != "anima":
        raise HTTPException(status_code=400, detail="仅 anima 源支持重新拉取缩略图")
    if kind == "char":
        row = get_anima_character_db().get_by_character(key) or {}
        thumbname = row.get("thumbname")
        url = character_thumb_url(thumbname) if thumbname else None
        dest_dir = paths.ANIMA_DIR / "characters"
    elif kind == "artist":
        row = get_anima_artist_db().get_by_artist(key) or {}
        thumbname = row.get("thumbname")
        url = artist_thumb_url(thumbname) if thumbname else None
        dest_dir = paths.ANIMA_DIR / "artists"
    else:
        raise HTTPException(status_code=400, detail="kind 必须是 char 或 artist")
    if not thumbname or not url:
        raise HTTPException(status_code=404, detail="该条目无缩略图记录")
    n = _download_to(url, dest_dir / thumbname)
    return {"ok": True, "bytes": n, "name": thumbname}
