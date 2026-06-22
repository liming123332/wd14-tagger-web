#!/usr/bin/env python3
"""整合包内置：从 animadex.net 拉取 anima 角色/艺术家数据 + webp 缩略图。

脱离 AnimaDex 程序：本脚本直接调 animadex.net 的 export API（需要 export
token —— 在 animadex.net 登录 → Account → "Offline dataset export" 生成）。
首次运行会提示输入 token 并保存到本地，之后增量更新。

产出（整合包内 data/characterfinder/_anima_source/）：
  animadex.db          CSV ingest 的角色/艺术家库（供 update_anima.py 读取）
  characters/thumbs/   webp 缩略图
  artists/thumbs/
  .import_state.json   增量 version state（下次只拉变化的）
  .token               你的 export token（本地保存，勿外传；失效会自动删除重填）

拉取完成后，由同目录的 update_anima.py 从本 source 重建整合包的
anima_characters.db / anima_artists.db / 主库 anima 行 + 增量拷缩略图。

只下缩略图（webp，离线可浏览），不下几十 GB 的原图；不拉 animadex 的
traits/loras/categories/copyrights 等整合包用不到的表。

用法（在整合包根目录，通常由 更新anima数据.bat 调用）：
    runtime\\python.exe wd14-tagger-web\\scripts\\fetch_anima.py
    python fetch_anima.py --token XXX     # 显式指定 token
    python fetch_anima.py --full          # 强制全量（默认：首次全量、之后增量）
    python fetch_anima.py --dry-run       # 只规划不下载
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

# Windows GBK 控制台兜底：强制 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 本脚本位于 <整合包>/wd14-tagger-web/scripts/fetch_anima.py
SCRIPT_DIR = Path(__file__).resolve().parent
WEB_ROOT = SCRIPT_DIR.parent              # wd14-tagger-web
PKG_ROOT = WEB_ROOT.parent                # 整合包根
CF_DIR = WEB_ROOT / "data" / "characterfinder"
SOURCE_DIR = CF_DIR / "_anima_source"     # 内部拉取产物目录
CHAR_THUMB_DIR = SOURCE_DIR / "characters" / "thumbs"
ARTIST_THUMB_DIR = SOURCE_DIR / "artists" / "thumbs"
SOURCE_DB = SOURCE_DIR / "animadex.db"
STATE_PATH = SOURCE_DIR / ".import_state.json"
TOKEN_PATH = SOURCE_DIR / ".token"

SITE = "https://animadex.net"
USER_AGENT = "wd14-portable-anima-fetch/1"

# 与 animadex.db.sanitize_filename 完全一致：缩略图文件名由此派生，必须和
# 服务端实际文件名一致，否则 update_anima.py 按文件名找缩略图会落空。
ILLEGAL_FS_CHARS = '<>:"/\\|?*'


def sanitize_filename(name: str) -> str:
    cleaned = ''.join('_' if c in ILLEGAL_FS_CHARS else c for c in name)
    return cleaned.rstrip(' .') or 'unnamed'


def _cap_word(word: str) -> str:
    for i, ch in enumerate(word):
        if ch.isalpha():
            return word[:i] + ch.upper() + word[i + 1:]
    return word


def titlecase(text: str) -> str:
    return ' '.join(_cap_word(w) for w in text.split(' '))


def _enc(name: str) -> str:
    """URL 编码文件名（空格→%20，括号保留），匹配 animadex 服务端 R2 URL。"""
    return quote(name, safe='()')


# ---- HTTP 工具 ------------------------------------------------------------

def _get(url, headers=None, timeout=60):
    req = urllib.request.Request(
        url, headers={'User-Agent': USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def get_json(url, headers=None):
    status, body = _get(url, headers)
    return status, json.loads(body.decode('utf-8'))


def download(url, dest: Path) -> int:
    """下载到 .part 临时文件再原子改名。返回字节数。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
        data = r.read()
        f.write(data)
    os.replace(tmp, dest)
    return len(data)


# ---- token ----------------------------------------------------------------

def get_token(arg_token: str | None) -> str:
    """优先级：--token 参数 > ANIMADEX_IMPORT_TOKEN 环境变量 > .token 文件 >
    交互输入（首次）。"""
    if arg_token:
        return arg_token
    env = os.environ.get("ANIMADEX_IMPORT_TOKEN")
    if env:
        return env
    if TOKEN_PATH.exists():
        t = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if t:
            return t
    # 首次：交互输入并保存
    print("=" * 56)
    print("首次使用：需要 animadex.net 的 export token")
    print("  获取：登录 animadex.net → Account → Offline dataset export")
    print("        → Generate token，复制粘贴到下方")
    print("=" * 56)
    t = input("请粘贴 token：").strip()
    if not t:
        sys.exit("未输入 token，已取消。")
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(t, encoding="utf-8")
    print(f"已保存 token 到 {TOKEN_PATH.name}（下次自动读取，失效会提示重填）\n")
    return t


# ---- manifest -------------------------------------------------------------

def fetch_manifest(token: str, want_full: bool):
    """返回 (manifest, did_full)。处理 48h 全量锁（自动回退增量）与 401/503。"""
    base = SITE + '/api/export/manifest'
    url = base + ('?full=1' if want_full else '')
    headers = {'X-Export-Token': token}
    try:
        status, data = get_json(url, headers)
    except urllib.error.HTTPError as e:
        if e.code == 429 and want_full:
            info = json.loads(e.read().decode('utf-8') or '{}')
            hrs = round((info.get('retry_after_secs') or 0) / 3600, 1)
            print(f"  ! 全量下载被锁定（每 48h 一次，剩余 ~{hrs}h），自动改用增量。")
            status, data = get_json(base, headers)
            return data, False
        if e.code == 401:
            # token 失效：删本地 .token，下次重新提示输入
            TOKEN_PATH.unlink(missing_ok=True)
            sys.exit("token 被拒绝（401）。请到 animadex.net 重新生成 export token，"
                     "再运行本脚本。")
        if e.code == 503:
            sys.exit("animadex.net 尚未发布目录导出（503），请稍后再试。")
        raise
    return data, want_full


# ---- CSV 行解析（派生字段，与 animadex.db.parse_*_row 一致）---------------

def parse_character(row: dict) -> dict | None:
    character = (row.get('character') or '').strip()
    if not character:
        return None
    copyright_ = (row.get('copyright') or '').strip()
    trigger = (row.get('trigger') or '').strip()
    core = (row.get('core_tags') or '').strip()
    # trigger 形如 "hatsune miku, vocaloid"：逗号前是名字、后是版权
    if ', ' in trigger:
        nm, cp = trigger.split(', ', 1)
    else:
        nm, cp = trigger, ''
    name = titlecase(nm) if nm else titlecase(character.replace('_', ' '))
    copyright_name = (titlecase(cp) if cp
                      else titlecase(copyright_.replace('_', ' ')))
    try:
        count = int(row.get('count') or 0)
    except ValueError:
        count = 0
    stem = sanitize_filename(trigger)
    return {
        'character': character, 'copyright': copyright_, 'name': name,
        'name_lower': name.lower(), 'copyright_name': copyright_name,
        'trigger': trigger, 'core_tags': core, 'count': count,
        'url': (row.get('url') or '').strip(),
        'imgname': stem + '.png', 'thumbname': stem + '.webp',
        'search_blob': ' '.join((character, copyright_, trigger, core)).lower(),
    }


def parse_artist(row: dict) -> dict | None:
    artist = (row.get('artist') or '').strip()
    if not artist:
        return None
    trigger = (row.get('trigger') or '').strip() or artist.replace('_', ' ')
    name = titlecase(trigger)
    try:
        count = int(row.get('count') or 0)
    except ValueError:
        count = 0
    stem = sanitize_filename(trigger)
    return {
        'artist': artist, 'name': name, 'name_lower': name.lower(),
        'trigger': trigger, 'count': count,
        'url': (row.get('url') or '').strip(),
        'imgname': stem + '.png', 'thumbname': stem + '.webp',
        'search_blob': ' '.join((artist, trigger)).lower(),
    }


# ---- source DB（精简 schema：只 characters/artists，供 update_anima.py 读）-

SOURCE_SCHEMA = """
DROP TABLE IF EXISTS characters;
CREATE TABLE characters (
    character TEXT PRIMARY KEY, copyright TEXT, name TEXT, name_lower TEXT,
    copyright_name TEXT, trigger TEXT, core_tags TEXT, count INTEGER DEFAULT 0,
    url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT
);
DROP TABLE IF EXISTS artists;
CREATE TABLE artists (
    artist TEXT PRIMARY KEY, name TEXT, name_lower TEXT, trigger TEXT,
    count INTEGER DEFAULT 0, url TEXT, score REAL, imgname TEXT, thumbname TEXT,
    search_blob TEXT
);
"""

_CHAR_COLS = ("character,copyright,name,name_lower,copyright_name,trigger,"
              "core_tags,count,url,imgname,thumbname,search_blob")
_ARTIST_COLS = ("artist,name,name_lower,trigger,count,url,imgname,thumbname,"
                "search_blob")


def build_source_db(chars_csv: Path, artists_csv: Path) -> tuple[int, int]:
    """CSV → source animadex.db。每次 DROP+CREATE 重建（schema 演进时自动套用最新
    结构，避免老库缺列——曾因 artists 缺 score 导致 update_anima 崩）；INSERT 全量行。
    增量优化只在缩略图下载层（见 plan_thumbs）。"""
    conn = sqlite3.connect(str(SOURCE_DB))
    conn.executescript(SOURCE_SCHEMA)  # DROP IF EXISTS + CREATE：表结构始终最新

    with open(chars_csv, encoding='utf-8', newline='') as f:
        crows = [r for r in (parse_character(x) for x in csv.DictReader(f)) if r]
    conn.executemany(
        f"INSERT INTO characters({_CHAR_COLS}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r['character'], r['copyright'], r['name'], r['name_lower'],
          r['copyright_name'], r['trigger'], r['core_tags'], r['count'],
          r['url'], r['imgname'], r['thumbname'], r['search_blob']) for r in crows])

    with open(artists_csv, encoding='utf-8', newline='') as f:
        arows = [r for r in (parse_artist(x) for x in csv.DictReader(f)) if r]
    conn.executemany(
        f"INSERT INTO artists({_ARTIST_COLS}) VALUES(?,?,?,?,?,?,?,?,?)",
        [(r['artist'], r['name'], r['name_lower'], r['trigger'], r['count'],
          r['url'], r['imgname'], r['thumbname'], r['search_blob']) for r in arows])

    conn.commit()
    conn.close()
    return len(crows), len(arows)


# ---- 增量规划 -------------------------------------------------------------

def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
    return {'version': None, 'chars': {}, 'artists': {}}


def plan_thumbs(rows, key_col, thumb_prefix, thumb_dir, idx_map, st_map, full):
    """对比 manifest 的 per-row version 与本地 state，只规划需要（重新）下载的
    缩略图。返回 (jobs, new_versions)。"""
    jobs, new_versions = [], {}
    for r in rows:
        slug = r[key_col]
        ver = idx_map.get(slug, 0)
        new_versions[slug] = ver
        # 全量模式，或该行 version 变了，才在下载范围
        if not (full or ver != st_map.get(slug)):
            continue
        dest = thumb_dir / r['thumbname']   # thumbname = sanitize_filename(trigger).webp
        if not dest.exists() or ver != st_map.get(slug):
            jobs.append((f"{thumb_prefix}/{_enc(r['thumbname'])}", dest))
    return jobs, new_versions


# ---- main -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="从 animadex.net 拉取 anima 数据到整合包")
    ap.add_argument('--token', default=None, help='export token（默认读 .token/环境/交互）')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--full', action='store_true', help='强制全量（默认首次全量、之后增量）')
    g.add_argument('--delta', action='store_true', help='强制增量')
    ap.add_argument('--concurrency', type=int, default=8, help='缩略图并发下载数')
    ap.add_argument('--dry-run', action='store_true', help='只规划，不下载不入库')
    args = ap.parse_args()

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    CHAR_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    ARTIST_THUMB_DIR.mkdir(parents=True, exist_ok=True)

    token = get_token(args.token)

    state = _load_state()
    want_full = args.full or (not args.delta and state.get('version') is None)

    print("=" * 56)
    print("  Anima 数据拉取  ←  animadex.net")
    print("=" * 56)
    print(f"联系 {SITE} …")
    man, did_full = fetch_manifest(token, want_full)
    r2 = man['r2_base'].rstrip('/')
    pref = {k: f"{r2}/{v}" for k, v in man['prefixes'].items()}
    print(f"目录版本 {man['version']}  ·  模式：{'全量' if did_full else '增量'}")

    # CSV 落到 source/import/
    imp = SOURCE_DIR / "import"
    imp.mkdir(parents=True, exist_ok=True)
    chars_csv, artists_csv = imp / 'characters.csv', imp / 'artists.csv'
    download(man['csv']['characters'], chars_csv)
    download(man['csv']['artists'], artists_csv)
    _, idx = get_json(man['index_url'])   # per-row version 索引

    with open(chars_csv, encoding='utf-8', newline='') as f:
        char_rows = [r for r in (parse_character(x) for x in csv.DictReader(f)) if r]
    with open(artists_csv, encoding='utf-8', newline='') as f:
        artist_rows = [r for r in (parse_artist(x) for x in csv.DictReader(f)) if r]

    cjobs, cver = plan_thumbs(char_rows, 'character', pref['char_thumb'],
                              CHAR_THUMB_DIR, idx.get('chars', {}),
                              state.get('chars', {}), did_full)
    ajobs, aver = plan_thumbs(artist_rows, 'artist', pref['artist_thumb'],
                              ARTIST_THUMB_DIR, idx.get('artists', {}),
                              state.get('artists', {}), did_full)
    jobs = cjobs + ajobs

    print(f"  角色：{len(char_rows):,} 行 · 待下载 {len(cjobs):,} 缩略图")
    print(f"  艺术家：{len(artist_rows):,} 行 · 待下载 {len(ajobs):,} 缩略图")
    print(f"  总下载：{len(jobs):,}")
    if jobs:
        print(f"  例：{jobs[0][0]}")

    if args.dry_run:
        print("\ndry-run，未下载/入库。")
        return 0

    # 并发下载缩略图；容忍单个 404（新行可能暂无缩略图）
    done = fail = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(download, url, dest): url for url, dest in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
                done += 1
            except urllib.error.HTTPError as e:
                fail += 1
                if e.code != 404:
                    print(f"  ! {futs[fut]} -> HTTP {e.code}")
            except Exception as e:                       # noqa: BLE001
                fail += 1
                print(f"  ! {futs[fut]} -> {e}")
            if i % 500 == 0 or i == len(jobs):
                print(f"  已下载 {done:,}/{len(jobs):,}（{fail} 跳过/失败）")

    # CSV → source DB（全量重建）
    nc, na = build_source_db(chars_csv, artists_csv)
    print(f"已入库 source animadex.db：{nc:,} 角色，{na:,} 艺术家")

    # 保存增量 state（下次只拉变化的）
    state = {'version': man['version'], 'chars': cver, 'artists': aver}
    STATE_PATH.write_text(json.dumps(state), encoding='utf-8')

    print(f"\n拉取完成。token/数据已存 {SOURCE_DIR.name}/。")
    print("接下来由 update_anima.py 重建整合包库（本 bat 会自动继续）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
