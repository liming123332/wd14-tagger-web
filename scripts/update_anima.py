#!/usr/bin/env python3
"""整合包内置：从 source animadex.db 重建整合包的 anima 角色/艺术家库。

默认 source = 整合包内 data/characterfinder/_anima_source/（由 fetch_anima.py
从 animadex.net 拉取产生）；也支持 --animadex-data 指向外部 AnimaDex 程序的
animadex-data/（向后兼容）。

重建 anima_characters.db/anima_artists.db，刷新主库 characters.db/artists.db
的 source='anima' 行（danbooru/e621 不动），增量拷贝 webp 缩略图。幂等可重复。

不会动你的：cf_overlay.db（收藏/编辑）、data/images（上传图）、models、runtime。

用法（通常由 更新anima数据.bat 在 fetch_anima.py 之后自动调用）：
    runtime\\python.exe wd14-tagger-web\\scripts\\update_anima.py
    python update_anima.py --animadex-data D:\\path\\to\\animadex-data
    python update_anima.py --prune          # 顺带清理已删角色的残留收藏
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

# Windows 控制台 GBK 兜底：强制 UTF-8 输出，避免中文/符号打印报错
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 本脚本位于 <整合包>/wd14-tagger-web/scripts/update_anima.py
SCRIPT_DIR = Path(__file__).resolve().parent
WEB_ROOT = SCRIPT_DIR.parent              # wd14-tagger-web
PKG_ROOT = WEB_ROOT.parent                # 整合包根
CF_DIR = WEB_ROOT / "data" / "characterfinder"
ANIMA_DIR = CF_DIR / "anima"

R2_BASE = "https://blobs.animadex.net"


def _r2_thumb_url(prefix: str, thumbname: str) -> str:
    """R2 缩略图 URL（保留文件名里的空格/逗号）。"""
    return f"{R2_BASE}/{prefix}/{quote(thumbname, safe='(),')}" if thumbname else ""


def _titlecase(text: str) -> str:
    def _cap(word: str) -> str:
        for i, ch in enumerate(word):
            if ch.isalpha():
                return word[:i] + ch.upper() + word[i + 1:]
        return word
    return " ".join(_cap(w) for w in text.split(" "))


def find_animadex_data(override: str | None) -> Path | None:
    """定位 animadex-data 目录（需含 animadex.db）。
    优先级：--animadex-data 参数 > ANIMADEX_DATA 环境变量 > 相对/绝对候选路径。"""
    checks: list[Path] = []
    if override:
        checks.append(Path(override))
    env = os.environ.get("ANIMADEX_DATA")
    if env:
        checks.append(Path(env))
    # 相对整合包根反推（适配不同安装位置）+ 本机常见绝对路径兜底
    checks.extend([
        CF_DIR / "_anima_source",              # 整合包内置 fetch_anima.py 产物（默认首选）
        PKG_ROOT.parent / "animadex-data",                    # trae 下整合包：../animadex-data
        PKG_ROOT.parent / "trae" / "wd14" / "animadex-data",  # I 盘根整合包
        PKG_ROOT.parent / "wd14" / "animadex-data",
        Path(r"I:\trae\wd14\animadex-data"),
        Path(r"i:\trae\wd14\animadex-data"),
    ])
    for c in checks:
        if (c / "animadex.db").exists():
            return c.resolve()
    return None


# anima DB schema，与 sd-character-finder/scripts/import_anima.py 保持一致
CHAR_SCHEMA = """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character TEXT NOT NULL UNIQUE,
    copyright TEXT, name TEXT, trigger TEXT NOT NULL, core_tags TEXT,
    count INTEGER DEFAULT 0, url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT
);
CREATE INDEX idx_char_search ON characters(search_blob);
CREATE INDEX idx_char_copyright ON characters(copyright);
CREATE INDEX idx_char_count ON characters(count DESC);
"""

ARTIST_SCHEMA = """
CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL UNIQUE, name TEXT, trigger TEXT NOT NULL,
    count INTEGER DEFAULT 0, url TEXT, score REAL,
    imgname TEXT, thumbname TEXT, search_blob TEXT
);
CREATE INDEX idx_artist_search ON artists(search_blob);
CREATE INDEX idx_artist_count ON artists(count DESC);
CREATE INDEX idx_artist_score ON artists(score DESC);
"""


def rebuild_anima_db(src_db: Path) -> tuple[int, int]:
    """从 animadex.db 全量重建整合包的 anima_characters.db / anima_artists.db（先删后建，幂等）。"""
    src = sqlite3.connect(str(src_db))
    src.row_factory = sqlite3.Row

    char_db = CF_DIR / "anima_characters.db"
    if char_db.exists():
        char_db.unlink()
    dc = sqlite3.connect(str(char_db))
    dc.executescript(CHAR_SCHEMA)
    rows = src.execute(
        "SELECT character, copyright, name, trigger, core_tags, count, url, imgname, thumbname, search_blob "
        "FROM characters"
    ).fetchall()
    dc.executemany(
        "INSERT INTO characters(character,copyright,name,trigger,core_tags,count,url,imgname,thumbname,search_blob) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        [tuple(r) for r in rows],
    )
    dc.commit()
    n_char = len(rows)
    dc.close()

    artist_db = CF_DIR / "anima_artists.db"
    if artist_db.exists():
        artist_db.unlink()
    da = sqlite3.connect(str(artist_db))
    da.executescript(ARTIST_SCHEMA)
    rows = src.execute(
        "SELECT artist, name, trigger, count, url, score, imgname, thumbname, search_blob FROM artists"
    ).fetchall()
    da.executemany(
        "INSERT INTO artists(artist,name,trigger,count,url,score,imgname,thumbname,search_blob) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        [tuple(r) for r in rows],
    )
    da.commit()
    n_artist = len(rows)
    da.close()

    src.close()
    return n_char, n_artist


def refresh_main_anima() -> tuple[int, int]:
    """主库 characters.db/artists.db：DELETE source='anima' 后从 anima DB 重新 INSERT。
    danbooru/e621 行不动；rank 从当前最大值续编。幂等。转换规则与
    sd-character-finder/scripts/import_anima_to_main_db.py 完全一致。"""
    # ----- characters -----
    anima_char = sqlite3.connect(str(CF_DIR / "anima_characters.db"))
    anima_char.row_factory = sqlite3.Row
    main_c = sqlite3.connect(str(CF_DIR / "characters.db"))
    try:  # 老库可能缺 source 列
        main_c.execute("ALTER TABLE characters ADD COLUMN source TEXT DEFAULT 'danbooru'")
        main_c.commit()
    except sqlite3.OperationalError:
        pass
    main_c.execute("DELETE FROM characters WHERE source='anima'")
    next_rank = (main_c.execute("SELECT MAX(rank) FROM characters").fetchone()[0] or 0) + 1
    rows = anima_char.execute(
        "SELECT character, copyright, name, trigger, core_tags, thumbname FROM characters ORDER BY count DESC"
    ).fetchall()
    for row in rows:
        trigger = (row["trigger"] or "").strip()
        core_tags = (row["core_tags"] or "").strip()
        tags = f"{trigger}, {core_tags}" if trigger and core_tags else (trigger or core_tags)
        name = row["name"] or _titlecase(row["character"].replace("_", " "))
        image_url = _r2_thumb_url("Outputs/thumbs", row["thumbname"])
        main_c.execute(
            "INSERT INTO characters(name, series, tags, image_url, rank, danbooru_tag, source) VALUES(?,?,?,?,?,?,'anima')",
            (name, (row["copyright"] or "").strip(), tags, image_url, next_rank, trigger),
        )
        next_rank += 1
    main_c.commit()
    n_char = len(rows)
    main_c.close()
    anima_char.close()

    # ----- artists -----
    anima_art = sqlite3.connect(str(CF_DIR / "anima_artists.db"))
    anima_art.row_factory = sqlite3.Row
    main_a = sqlite3.connect(str(CF_DIR / "artists.db"))
    try:
        main_a.execute("ALTER TABLE artists ADD COLUMN source TEXT DEFAULT 'danbooru'")
        main_a.commit()
    except sqlite3.OperationalError:
        pass
    main_a.execute("DELETE FROM artists WHERE source='anima'")
    next_rank = (main_a.execute("SELECT MAX(rank) FROM artists").fetchone()[0] or 0) + 1
    rows = anima_art.execute(
        "SELECT artist, name, trigger, count, thumbname FROM artists ORDER BY count DESC"
    ).fetchall()
    for row in rows:
        trigger = (row["trigger"] or "").strip()
        artist_key = (row["artist"] or "").strip()
        tag = trigger if trigger.startswith("@") else f"@{trigger}"
        display_name = row["name"] or _titlecase(trigger)
        name = artist_key or trigger.replace(" ", "_")
        image_url_1 = _r2_thumb_url("ArtistOutputs/thumbs", row["thumbname"])
        main_a.execute(
            "INSERT INTO artists(name, tag, display_name, image_url_1, image_url_2, ref_count, source, rank) "
            "VALUES(?,?,?,?,NULL,?,'anima',?)",
            (name, tag, display_name, image_url_1, row["count"] or 0, next_rank),
        )
        next_rank += 1
    main_a.commit()
    n_artist = len(rows)
    main_a.close()
    anima_art.close()
    return n_char, n_artist


def sync_thumbs(src_data: Path) -> tuple[int, int]:
    """animadex-data/{characters,artists}/thumbs → 整合包 anima/{characters,artists}/。
    仅拷贝目标不存在或大小不同的文件（增量，不全量覆盖）；旧图保留不删。"""
    added = [0, 0]
    for i, kind in enumerate(("characters", "artists")):
        s = src_data / kind / "thumbs"
        d = ANIMA_DIR / kind
        if not s.exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        n = 0
        for f in s.iterdir():
            if not f.is_file():
                continue
            dst = d / f.name
            if not dst.exists() or dst.stat().st_size != f.stat().st_size:
                shutil.copy2(f, dst)
                n += 1
        added[i] = n
    return added[0], added[1]


def prune_overlay_orphans(src_db: Path) -> tuple[int, int]:
    """删除 cf_overlay.db 里指向 animadex 已不存在角色/艺术家的记录（孤儿收藏）。
    用 Python 端集合过滤，避免 SQL IN 子句参数超限（3万+ 会超 sqlite 上限）。"""
    ov_db = CF_DIR / "cf_overlay.db"
    if not ov_db.exists():
        return 0, 0
    src = sqlite3.connect(str(src_db))
    src.row_factory = sqlite3.Row
    valid_char = {f"char:anima:{r['character']}" for r in src.execute("SELECT character FROM characters")}
    valid_art = {f"artist:anima:{r['artist']}" for r in src.execute("SELECT artist FROM artists")}
    src.close()

    ov = sqlite3.connect(str(ov_db))
    keys = [r[0] for r in ov.execute(
        "SELECT entry_key FROM overlay WHERE entry_key LIKE 'char:anima:%' OR entry_key LIKE 'artist:anima:%'"
    )]
    char_orphans = [k for k in keys if k.startswith("char:anima:") and k not in valid_char]
    art_orphans = [k for k in keys if k.startswith("artist:anima:") and k not in valid_art]
    for k in char_orphans + art_orphans:
        ov.execute("DELETE FROM overlay WHERE entry_key=?", (k,))
        d = CF_DIR / "overlay" / re.sub(r"[^A-Za-z0-9_.-]", "_", k)  # 与 cf_overlay._safe_name 一致
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    ov.commit()
    ov.close()
    return len(char_orphans), len(art_orphans)


def main() -> int:
    ap = argparse.ArgumentParser(description="从本机 animadex-data 同步 anima 数据到整合包")
    ap.add_argument("--animadex-data", default=None, help="animadex-data 目录路径（默认自动探测）")
    ap.add_argument("--prune", action="store_true", help="顺带清理 animadex 已删角色的残留收藏")
    args = ap.parse_args()

    print("=" * 56)
    print("  Anima 数据同步  →  整合包 data/characterfinder/")
    print("=" * 56)

    src = find_animadex_data(args.animadex_data)
    if not src:
        print("\n[错误] 找不到 animadex-data 目录（需含 animadex.db）。")
        print("  - 先运行 AnimaDex\\import.bat 拉取数据；")
        print("  - 或用 --animadex-data 指定路径；")
        print("  - 或设环境变量 ANIMADEX_DATA。")
        return 1
    src_db = src / "animadex.db"
    print(f"数据源：{src}")
    print(f"整合包：{PKG_ROOT}")

    if not (CF_DIR / "characters.db").exists() or not (CF_DIR / "artists.db").exists():
        print("\n[错误] 主库 characters.db / artists.db 不存在，整合包数据不完整。")
        print("  请用完整的整合包重新部署。")
        return 1

    CF_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] 重建 anima 角色/艺术家库...")
    nc, na = rebuild_anima_db(src_db)
    print(f"  anima_characters.db : {nc:,} 角色")
    print(f"  anima_artists.db    : {na:,} 艺术家")

    print("\n[2/3] 刷新主库 anima 行（DELETE 后重插，danbooru/e621 不动）...")
    mc, ma = refresh_main_anima()
    print(f"  characters.db anima 行 : {mc:,}")
    print(f"  artists.db anima 行    : {ma:,}")

    print("\n[3/3] 增量拷贝 webp 缩略图（仅新增/变化的）...")
    tc, ta = sync_thumbs(src)
    print(f"  anima/characters : 新增/更新 {tc:,} 张")
    print(f"  anima/artists    : 新增/更新 {ta:,} 张")

    if args.prune:
        print("\n[prune] 清理孤儿收藏...")
        oc, oa = prune_overlay_orphans(src_db)
        print(f"  删除角色孤儿 {oc} 条，艺术家孤儿 {oa} 条")
    else:
        print("\n（孤儿收藏已保留；加 --prune 可清理 animadex 已删角色的残留）")

    print("\n完成。请重启整合包后端（关闭启动窗口后重新双击「启动.bat」）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
