# Character Finder 整合 — P1 后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 wd14-tagger-web 后端接入 sd-character-finder 的角色/艺术家数据，提供搜索、详情、反推（落 overlay）、编辑、换图、收藏、最近、随机 API，权威标签锁定不可改。

**Architecture:** 权威层（复制 sdcf 的 sqlite db，只读）+ Overlay 层（新增 `cf_overlay.db`，存用户反推/编辑/换图）。数据访问层从 sdcf `wildcard_creator/` 原样移植（纯 stdlib sqlite3），仅改默认 db 路径。API 仿现有 `routes_images`/`routes_promptbox` 风格，复用 `get_tagger`/`get_classifier`。

**Tech Stack:** Python 3、FastAPI、sqlite3（stdlib）、pydantic v2、pytest（现有测试体系）、Pillow。

## 分阶段说明
本 plan 仅覆盖 **P1 后端**（独立可测，pytest 全绿即交付可用 API）。P2 前端、P3 随机/收藏 UI、P4 脚本将在 P1 完成后基于真实接口各写一份 plan。

## Global Constraints
- 数据根目录 `data/characterfinder/`（`settings.CF_DIR`），所有 cf 数据落此，与图库 `data/images/`、提示词盒 `data/promptbox/` 物理隔离。
- 权威标签（角色 `trigger`/`core_tags`、画师 `tag`）只读；后端 `tag`/`PUT` 必须以权威为准，忽略前端改写锁定字段的请求。
- entry_key 复合格式：`{kind}:{source}:{key}`，`kind∈{char,artist}`，`source∈{danbooru,e621,anima}`，danbooru/e621 用自增 id，anima 用 `character`/`artist` 文本主键。
- 存储须防目录穿越、原子写（`.tmp` + `replace`），风格仿 `backend/storage/promptbox_store.py`。
- 不新增运行时重依赖；仅脚本侧加 `requests`（P4 处理，P1 不涉及）。
- 测试用 `_app(tmp_path, monkeypatch)` helper 隔离到 tmp，`cache_clear` deps，不得污染真实 `data/`。

## File Structure（P1 涉及）
- Create `backend/characterfinder/__init__.py` — 包初始化
- Create `backend/characterfinder/paths.py` — cf 数据路径集中管理
- Create `backend/characterfinder/character_db.py` — 移植自 sdcf `CharacterDB`
- Create `backend/characterfinder/artist_db.py` — 移植自 sdcf `ArtistDB`
- Create `backend/characterfinder/anima_db.py` — 移植自 sdcf `AnimaCharacterDB`/`AnimaArtistDB`
- Create `backend/characterfinder/favorites.py` — 移植 `FavoritesDB`/`ArtistFavoritesDB`/`SearchHistoryDB`
- Create `backend/storage/cf_overlay.py` — Overlay 存储（sqlite）
- Modify `backend/models.py` — 新增 `CfOverlay` pydantic model
- Modify `backend/config/settings.py` — 新增 `CF_*` 路径常量
- Modify `backend/deps.py` — 新增 cf 工厂注入
- Create `backend/api/routes_cfassets.py` — 封面资产服务
- Create `backend/api/routes_characters.py` — 角色 API
- Create `backend/api/routes_artists.py` — 艺术家 API
- Modify `backend/main.py` — 注册 3 个新 router
- Create `tests/test_cf_*.py` — 各 task 对应测试

---

### Task 1: settings 配置项

**Files:**
- Modify: `backend/config/settings.py`（在 `PROMPTBOX_DIR` 一行之后新增）

**Interfaces:**
- Produces: `settings.CF_DIR`、`CF_COVERS_DIR`、`CF_ARTIST_COVERS_DIR`、`CF_ANIMA_DIR`、`CF_OVERLAY_DIR`、`CF_OVERLAY_DB`、`CF_FAVORITES_PATH`、`CF_RECENT_PATH`、`SDCF_SOURCE_DIR`、`ANIMADEX_SOURCE_DIR`、`CF_DOWNLOAD_CONCURRENCY`、`CF_DOWNLOAD_RETRIES`

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_config.py`:
```python
from backend.config import settings


def test_cf_paths_under_data_dir():
    assert settings.CF_DIR == settings.DATA_DIR / "characterfinder"
    assert settings.CF_COVERS_DIR == settings.CF_DIR / "covers"
    assert settings.CF_ARTIST_COVERS_DIR == settings.CF_DIR / "artist_covers"
    assert settings.CF_ANIMA_DIR == settings.CF_DIR / "anima"
    assert settings.CF_OVERLAY_DIR == settings.CF_DIR / "overlay"
    assert settings.CF_OVERLAY_DB == settings.CF_DIR / "cf_overlay.db"
    assert settings.CF_FAVORITES_PATH == settings.CF_DIR / "favorites.json"
    assert settings.CF_RECENT_PATH == settings.CF_DIR / "recent_viewed.json"


def test_cf_source_dirs_and_download_tunables():
    assert settings.SDCF_SOURCE_DIR.name == "sd-character-finder"
    assert settings.ANIMADEX_SOURCE_DIR.name == "animadex-data"
    assert settings.CF_DOWNLOAD_CONCURRENCY >= 1
    assert settings.CF_DOWNLOAD_RETRIES >= 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_config.py -v`
Expected: FAIL（`AttributeError: CF_DIR`）

- [ ] **Step 3: 实现**

在 `backend/config/settings.py` 的 `PROMPTBOX_DIR = DATA_DIR / "promptbox"` 之后追加：
```python
# === Character Finder（整合自 sd-character-finder）===
CF_DIR = DATA_DIR / "characterfinder"
CF_COVERS_DIR = CF_DIR / "covers"
CF_ARTIST_COVERS_DIR = CF_DIR / "artist_covers"
CF_ANIMA_DIR = CF_DIR / "anima"
CF_OVERLAY_DIR = CF_DIR / "overlay"
CF_OVERLAY_DB = CF_DIR / "cf_overlay.db"
CF_FAVORITES_PATH = CF_DIR / "favorites.json"
CF_RECENT_PATH = CF_DIR / "recent_viewed.json"
# 同步源（db 来自 sdcf，anima 图片来自 animadex-data）；默认指向同级目录
SDCF_SOURCE_DIR = ROOT.parent / "sd-character-finder"
ANIMADEX_SOURCE_DIR = ROOT.parent / "animadex-data"
CF_DOWNLOAD_CONCURRENCY = 16
CF_DOWNLOAD_RETRIES = 3
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/config/settings.py tests/test_cf_config.py
git commit -m "feat(cf): add characterfinder path config"
```

---

### Task 2: characterfinder 包骨架 + paths.py

**Files:**
- Create: `backend/characterfinder/__init__.py`、`backend/characterfinder/paths.py`

**Interfaces:**
- Consumes: `settings.CF_*`（Task 1）
- Produces: `paths.CHARACTERS_DB`、`ARTISTS_DB`、`ANIMA_CHARACTERS_DB`、`ANIMA_ARTISTS_DB`、`DANBOORU_TAGS_CSV`、`COVERS_DIR`、`ARTIST_COVERS_DIR`、`ANIMA_DIR`、`OVERLAY_DB`、`OVERLAY_DIR`、`entry_key(kind, source, key)`、`parse_entry_key`

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_paths.py`:
```python
from backend.characterfinder import paths


def test_db_paths():
    assert paths.CHARACTERS_DB.name == "characters.db"
    assert paths.ARTISTS_DB.name == "artists.db"
    assert paths.ANIMA_CHARACTERS_DB.name == "anima_characters.db"
    assert paths.ANIMA_ARTISTS_DB.name == "anima_artists.db"
    assert paths.DANBOORU_TAGS_CSV.name == "danbooru_tags.csv"


def test_entry_key_roundtrip():
    k = paths.entry_key("char", "anima", "001_(darling_in_the_franxx)")
    assert k == "char:anima:001_(darling_in_the_franxx)"
    assert paths.parse_entry_key(k) == ("char", "anima", "001_(darling_in_the_franxx)")


def test_parse_entry_key_rejects_bad():
    import pytest
    with pytest.raises(ValueError):
        paths.parse_entry_key("bogus")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_paths.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`backend/characterfinder/__init__.py`（空文件，标记为包）：
```python
```

`backend/characterfinder/paths.py`:
```python
"""Character Finder 数据路径与 entry_key 编解码。"""
from __future__ import annotations
from backend.config import settings

CHARACTERS_DB = settings.CF_DIR / "characters.db"
ARTISTS_DB = settings.CF_DIR / "artists.db"
ANIMA_CHARACTERS_DB = settings.CF_DIR / "anima_characters.db"
ANIMA_ARTISTS_DB = settings.CF_DIR / "anima_artists.db"
DANBOORU_TAGS_CSV = settings.CF_DIR / "danbooru_tags.csv"
COVERS_DIR = settings.CF_COVERS_DIR
ARTIST_COVERS_DIR = settings.CF_ARTIST_COVERS_DIR
ANIMA_DIR = settings.CF_ANIMA_DIR
OVERLAY_DB = settings.CF_OVERLAY_DB
OVERLAY_DIR = settings.CF_OVERLAY_DIR


def entry_key(kind: str, source: str, key: str) -> str:
    """kind∈{char,artist}, source∈{danbooru,e621,anima}, key=库主键。"""
    if kind not in ("char", "artist"):
        raise ValueError(f"bad kind {kind!r}")
    if source not in ("danbooru", "e621", "anima"):
        raise ValueError(f"bad source {source!r}")
    if not key:
        raise ValueError("empty key")
    return f"{kind}:{source}:{key}"


def parse_entry_key(ek: str) -> tuple[str, str, str]:
    parts = ek.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"bad entry_key {ek!r}")
    kind, source, key = parts
    if kind not in ("char", "artist") or source not in ("danbooru", "e621", "anima") or not key:
        raise ValueError(f"bad entry_key {ek!r}")
    return kind, source, key
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_paths.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/characterfinder/__init__.py backend/characterfinder/paths.py tests/test_cf_paths.py
git commit -m "feat(cf): add characterfinder package and paths"
```

---

### Task 3: 移植数据访问层 CharacterDB / ArtistDB

**Files:**
- Create: `backend/characterfinder/character_db.py`、`backend/characterfinder/artist_db.py`
- 源文件（复制自）：`../sd-character-finder/wildcard_creator/character_db.py`、`artist_db.py`
- Test: `tests/test_cf_db.py`

**Interfaces:**
- Consumes: `paths.CHARACTERS_DB`、`paths.ARTISTS_DB`（Task 2）
- Produces: `CharacterDB(db_path)` 含 `.search(query, series_filter, source_filter, limit, offset) -> (list[dict], int)`、`.get(name)`、`.list_series()`、`.count_by_source(source)`、`.count()`；`ArtistDB(db_path)` 含 `.search(...)`、`.get_by_name(name)`、`.list_series()` 等（保留 sdcf 原签名）

**移植改动点**（两个文件相同处理）：
1. 复制 sdcf 对应文件全文到 `backend/characterfinder/`。
2. 将 `_DEFAULT_DB = Path(__file__).parent.parent / "data" / "characters.db"` 改为：
   ```python
   from backend.characterfinder import paths
   _DEFAULT_DB = paths.CHARACTERS_DB   # artist_db.py 用 paths.ARTISTS_DB
   ```
3. 单例函数 `get_character_db()`/`get_artist_db()` **删除**（改由 `backend/deps.py` 统一注入，避免两套单例）。即移除文件末尾的 `_db_instance`、`get_character_db`、`@atexit.register` 段。
4. 其余（连接管理、`_migrate`、`search`/`get` 等）原样保留。

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_db.py`:
```python
import sqlite3
import pytest
from backend.characterfinder.character_db import CharacterDB
from backend.characterfinder.artist_db import ArtistDB

# characters.db 的 DDL（与 sdcf scrape_characters.py 一致）
CHAR_DDL = """
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, series TEXT,
    tags TEXT NOT NULL, image_url TEXT, rank INTEGER UNIQUE,
    danbooru_tag TEXT, source TEXT DEFAULT 'danbooru'
);
"""
ARTIST_DDL = """
CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tag TEXT NOT NULL,
    display_name TEXT NOT NULL, image_url_1 TEXT, image_url_2 TEXT,
    ref_count INTEGER DEFAULT 0, source TEXT DEFAULT 'danbooru', rank INTEGER
);
"""


def _char_db(tmp_path):
    p = tmp_path / "characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    c.execute("INSERT INTO characters(name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?)",
              ("hatsune miku", "vocaloid", "hatsune miku, vocaloid, 1girl, long hair", "http://x/miku.jpg", 1, "danbooru"))
    c.execute("INSERT INTO characters(name,series,tags,image_url,rank,source) VALUES(?,?,?,?,?,?)",
              ("saber", "fate", "saber, fate/stay night, 1girl", "http://x/saber.jpg", 2, "danbooru"))
    c.commit(); c.close()
    return CharacterDB(p)


def test_search_and_get(tmp_path):
    db = _char_db(tmp_path)
    rows, total = db.search("miku")
    assert total == 1 and rows[0]["name"] == "hatsune miku"
    got = db.get("hatsune miku")
    assert got is not None and "1girl" in got["tags"]


def test_list_series(tmp_path):
    db = _char_db(tmp_path)
    series = db.list_series()
    names = [s[0] for s in series]
    assert "vocaloid" in names and "fate" in names


def test_count_by_source(tmp_path):
    db = _char_db(tmp_path)
    assert db.count_by_source("danbooru") == 2
    assert db.count_by_source("e621") == 0


def test_artist_get_by_name(tmp_path):
    p = tmp_path / "artists.db"
    c = sqlite3.connect(p); c.executescript(ARTIST_DDL)
    c.execute("INSERT INTO artists(name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(?,?,?,?,?,?,?)",
              ("ebifurya", "ebifurya", "ebifurya", "http://x/1.jpg", "http://x/2.jpg", 1, "danbooru"))
    c.commit(); c.close()
    adb = ArtistDB(p)
    a = adb.get_by_name("ebifurya")
    assert a is not None and a["tag"] == "ebifurya"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_db.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现（移植）**

```bash
cp ../sd-character-finder/wildcard_creator/character_db.py backend/characterfinder/character_db.py
cp ../sd-character-finder/wildcard_creator/artist_db.py backend/characterfinder/artist_db.py
```
然后按上述「移植改动点」编辑两个文件：改 `_DEFAULT_DB` 指向 `paths`、删除单例与 atexit 段。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/characterfinder/character_db.py backend/characterfinder/artist_db.py tests/test_cf_db.py
git commit -m "feat(cf): port CharacterDB and ArtistDB from sdcf"
```

---

### Task 4: 移植 AnimaCharacterDB / AnimaArtistDB

**Files:**
- Create: `backend/characterfinder/anima_db.py`
- 源文件：`../sd-character-finder/wildcard_creator/anima_db.py`
- Test: `tests/test_cf_anima_db.py`

**Interfaces:**
- Consumes: `paths.ANIMA_CHARACTERS_DB`、`paths.ANIMA_ARTISTS_DB`
- Produces: `AnimaCharacterDB(db_path)` 含 `.search(query, copyright_filter, limit, offset) -> (list[dict], int)`、`.get_by_character(key)`、`.list_copyrights()`、`.count()`；`AnimaArtistDB(db_path)` 含 `.search(...)`、`.get_by_artist(key)`、`.count()`

**移植改动点**：
1. 复制 sdcf `anima_db.py` 全文到 `backend/characterfinder/anima_db.py`。
2. 把两个类的 `_DEFAULT_DB`（或等价默认路径）改为分别指向 `paths.ANIMA_CHARACTERS_DB`、`paths.ANIMA_ARTISTS_DB`。
3. 删除模块级单例函数（如 `get_anima_character_db`），统一由 deps 注入。
4. 其余原样保留。

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_anima_db.py`:
```python
import sqlite3
from backend.characterfinder.anima_db import AnimaCharacterDB, AnimaArtistDB

CHAR_DDL = """
CREATE TABLE characters (
    character TEXT, copyright TEXT, name TEXT, trigger TEXT, core_tags TEXT,
    count INTEGER, url TEXT, imgname TEXT, thumbname TEXT, search_blob TEXT,
    image_version INTEGER
);
CREATE INDEX idx_char_search ON characters(search_blob);
"""
ARTIST_DDL = """
CREATE TABLE artists (
    artist TEXT, name TEXT, name_lower TEXT, trigger TEXT, count INTEGER,
    url TEXT, imgname TEXT, thumbname TEXT, score REAL, search_blob TEXT,
    image_version INTEGER
);
"""


def _achar(tmp_path):
    p = tmp_path / "anima_characters.db"
    c = sqlite3.connect(p); c.executescript(CHAR_DDL)
    c.execute("INSERT INTO characters(character,copyright,name,trigger,core_tags,count,thumbname,imgname,search_blob) VALUES(?,?,?,?,?,?,?,?,?)",
              ("001_(darling_in_the_franxx)", "darling_in_the_franxx", "001 (Darling In The Franxx)",
               "001 (darling in the franxx), darling in the franxx", "1girl, blue skin", 111,
               "001 (darling in the franxx), darling in the franxx.webp", "001 (darling in the franxx), darling in the franxx.png",
               "001 darling_in_the_franxx"))
    c.commit(); c.close()
    return AnimaCharacterDB(p)


def test_search_and_get_by_character(tmp_path):
    db = _achar(tmp_path)
    rows, total = db.search("001")
    assert total == 1 and "darling" in rows[0]["copyright"]
    got = db.get_by_character("001_(darling_in_the_franxx)")
    assert got is not None and got["thumbname"].endswith(".webp")


def test_list_copyrights(tmp_path):
    db = _achar(tmp_path)
    cops = db.list_copyrights()
    assert any("darling" in c[0] for c in cops)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_anima_db.py -v`
Expected: FAIL

- [ ] **Step 3: 实现（移植）**

```bash
cp ../sd-character-finder/wildcard_creator/anima_db.py backend/characterfinder/anima_db.py
```
按「移植改动点」改默认路径、删单例。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_anima_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/characterfinder/anima_db.py tests/test_cf_anima_db.py
git commit -m "feat(cf): port AnimaCharacterDB/AnimaArtistDB from sdcf"
```

---

### Task 5: 移植 FavoritesDB / ArtistFavoritesDB / SearchHistoryDB

**Files:**
- Create: `backend/characterfinder/favorites.py`
- 源文件：`../sd-character-finder/wildcard_creator/favorites.py`、`artist_favorites.py`、`search_history.py`
- Test: `tests/test_cf_favorites.py`

**Interfaces:**
- Consumes: `paths.entry_key`（生成收藏项 id）、`settings.CF_FAVORITES_PATH`、`settings.CF_RECENT_PATH`
- Produces: `FavoritesDB(json_path)` 含 `.get_all() -> list[str]`、`.is_favorite(entry_key) -> bool`、`.toggle(entry_key) -> bool`（返回收藏后状态）；`ArtistFavoritesDB` 同构；`SearchHistoryDB(json_path)` 含 `.get_all() -> list[str]`、`.add(entry_key)`（最近在前、去重、截断上限 100）

**移植改动点**：sdcf 原实现以角色 id（int）为收藏 key；本仓库改用 entry_key（str）。三个类复制后：
1. 合并到单一文件 `backend/characterfinder/favorites.py`（或保留三个 import）。推荐合并，减少文件数。
2. `FavoritesDB.__init__` 接受 `json_path` 参数（默认 `settings.CF_FAVORITES_PATH`，运行时读，非默认参数绑定——同 `PromptboxStore` 做法）。
3. 把内部存取的 id 类型保持为 str（entry_key 即 str），`is_favorite`/`toggle` 参数名改为 `entry_key`。
4. `SearchHistoryDB.add` 上限改为 100（与 sdcf 一致）。
5. 删除模块级单例（`get_favorites_db` 等），由 deps 注入。

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_favorites.py`:
```python
from backend.characterfinder.favorites import FavoritesDB, ArtistFavoritesDB, SearchHistoryDB


def test_favorites_toggle(tmp_path):
    f = FavoritesDB(tmp_path / "fav.json")
    assert f.is_favorite("char:danbooru:1") is False
    assert f.toggle("char:danbooru:1") is True
    assert f.is_favorite("char:danbooru:1") is True
    assert "char:danbooru:1" in f.get_all()
    assert f.toggle("char:danbooru:1") is False
    assert f.is_favorite("char:danbooru:1") is False


def test_artist_favorites_toggle(tmp_path):
    f = ArtistFavoritesDB(tmp_path / "afav.json")
    assert f.toggle("artist:danbooru:1") is True
    assert f.is_favorite("artist:danbooru:1") is True


def test_search_history_dedup_and_order(tmp_path):
    h = SearchHistoryDB(tmp_path / "recent.json")
    h.add("char:anima:a"); h.add("char:anima:b"); h.add("char:anima:a")
    all_ = h.get_all()
    assert all_[0] == "char:anima:a"  # 最近在前
    assert len(all_) == 2  # 去重
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_favorites.py -v`
Expected: FAIL

- [ ] **Step 3: 实现（移植 + 合并）**

复制 sdcf 三个文件，合并入 `backend/characterfinder/favorites.py`，按「移植改动点」调整（key 改 str、构造接受路径、删单例）。若 sdcf 原文件逻辑复杂，最小可工作实现如下（若移植版更完整则优先移植版）：
```python
"""角色/艺术家收藏与最近查看（json 持久化，key 为 entry_key）。"""
from __future__ import annotations
import json
from pathlib import Path
from backend.config import settings


class _JsonSetStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            return []

    def _save(self, items: list[str]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


class FavoritesDB(_JsonSetStore):
    def __init__(self, path: Path | None = None):
        super().__init__(path if path is not None else settings.CF_FAVORITES_PATH)

    def get_all(self) -> list[str]:
        return self._load()

    def is_favorite(self, entry_key: str) -> bool:
        return entry_key in self._load()

    def toggle(self, entry_key: str) -> bool:
        items = self._load()
        if entry_key in items:
            items.remove(entry_key); self._save(items); return False
        items.append(entry_key); self._save(items); return True


class ArtistFavoritesDB(FavoritesDB):
    pass  # 结构同 FavoritesDB，独立文件以便前端分类展示


class SearchHistoryDB(_JsonSetStore):
    MAX = 100

    def __init__(self, path: Path | None = None):
        super().__init__(path if path is not None else settings.CF_RECENT_PATH)

    def get_all(self) -> list[str]:
        return self._load()

    def add(self, entry_key: str) -> None:
        items = self._load()
        if entry_key in items:
            items.remove(entry_key)
        items.insert(0, entry_key)
        del items[self.MAX:]
        self._save(items)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_favorites.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/characterfinder/favorites.py tests/test_cf_favorites.py
git commit -m "feat(cf): port favorites/recent (entry_key based)"
```

---

### Task 6: CfOverlay model + cf_overlay 存储

**Files:**
- Modify: `backend/models.py`（新增 `CfOverlay`）
- Create: `backend/storage/cf_overlay.py`
- Test: `tests/test_cf_overlay.py`

**Interfaces:**
- Consumes: `settings.CF_OVERLAY_DB`、`settings.CF_OVERLAY_DIR`、`backend.models.CategoryData`、`paths.entry_key`/`parse_entry_key`
- Produces: `CfOverlay`（pydantic：`entry_key, kind, custom_tags:list[str], categories:dict[str,CategoryData], extras:CategoryData, image_override:str|None, model, gen_threshold, char_threshold, raw_tags:dict[str,float], created_at, updated_at`）；`CfOverlayStore` 含 `.get(entry_key) -> CfOverlay|None`、`.upsert(overlay) -> CfOverlay`、`.set_image(entry_key, filename)`、`.image_path(entry_key, filename) -> Path`、`.delete(entry_key)`

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_overlay.py`:
```python
import pytest
from backend.models import CategoryData, CfOverlay
from backend.storage.cf_overlay import CfOverlayStore


def test_upsert_and_get(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    ov = CfOverlay(entry_key="char:danbooru:1", kind="char",
                   categories={"head": CategoryData(tags=["long hair"])},
                   extras=CategoryData(), model="wd14")
    saved = s.upsert(ov)
    assert saved.created_at and saved.updated_at
    again = s.get("char:danbooru:1")
    assert again is not None
    assert again.categories["head"].tags == ["long hair"]


def test_get_missing_returns_none(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    assert s.get("char:danbooru:9") is None


def test_set_image_and_path_guard(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.set_image("char:danbooru:1", "orig.png")
    p = s.image_path("char:danbooru:1", "orig.png")
    assert p.parent.exists()
    with pytest.raises(ValueError):
        s.image_path("char:danbooru:1", "../evil.png")


def test_delete(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.upsert(CfOverlay(entry_key="char:danbooru:1", kind="char", extras=CategoryData()))
    s.delete("char:danbooru:1")
    assert s.get("char:danbooru:1") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_overlay.py -v`
Expected: FAIL（`CfOverlay`/`CfOverlayStore` 不存在）

- [ ] **Step 3: 实现 model**

在 `backend/models.py` 末尾追加：
```python
class CfOverlay(BaseModel):
    """角色/艺术家条目的用户层数据（反推结果/编辑/换图），与权威 db 物理隔离。"""
    entry_key: str
    kind: str  # 'char' | 'artist'
    custom_tags: list[str] = Field(default_factory=list)
    categories: dict[str, CategoryData] = Field(default_factory=dict)
    extras: CategoryData = Field(default_factory=CategoryData)
    image_override: str | None = None  # 替换图文件名（存 overlay/<safe>/）
    model: str = "wd14"
    gen_threshold: float = 0.35
    char_threshold: float = 0.90
    raw_tags: dict[str, float] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
```

- [ ] **Step 4: 实现 store**

`backend/storage/cf_overlay.py`:
```python
"""Overlay 存储：cf_overlay.db（sqlite）+ overlay/<safe_key>/ 替换图。"""
from __future__ import annotations
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from backend.models import CfOverlay, CategoryData


def _safe_name(entry_key: str) -> str:
    # 文件系统安全：把 entry_key 中的路径分隔/非法字符替换为 _
    return re.sub(r"[^A-Za-z0-9_.-]", "_", entry_key)


class CfOverlayStore:
    def __init__(self, db_path: Path, overlay_dir: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.overlay_dir = Path(overlay_dir)
        self.overlay_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """CREATE TABLE IF NOT EXISTS overlay (
                entry_key TEXT PRIMARY KEY, kind TEXT NOT NULL,
                custom_tags TEXT, categories TEXT, extras TEXT,
                image_override TEXT, model TEXT,
                gen_threshold REAL, char_threshold REAL,
                raw_tags TEXT, created_at TEXT, updated_at TEXT);
            """
        )
        self._conn.commit()

    def _dir_for(self, entry_key: str) -> Path:
        if "/" in entry_key or "\\" in entry_key:
            raise ValueError("bad entry_key")
        return self.overlay_dir / _safe_name(entry_key)

    def image_path(self, entry_key: str, filename: str) -> Path:
        if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
            raise ValueError("bad image name")
        return self._dir_for(entry_key) / filename

    def set_image(self, entry_key: str, filename: str) -> None:
        self._dir_for(entry_key).mkdir(parents=True, exist_ok=True)

    def _row_to(self, r: sqlite3.Row) -> CfOverlay:
        return CfOverlay(
            entry_key=r["entry_key"], kind=r["kind"],
            custom_tags=json.loads(r["custom_tags"] or "[]"),
            categories={k: CategoryData(**v) for k, v in json.loads(r["categories"] or "{}").items()},
            extras=CategoryData(**(json.loads(r["extras"] or "null") or {})),
            image_override=r["image_override"], model=r["model"],
            gen_threshold=r["gen_threshold"], char_threshold=r["char_threshold"],
            raw_tags=json.loads(r["raw_tags"] or "{}"),
            created_at=r["created_at"] or "", updated_at=r["updated_at"] or "",
        )

    def get(self, entry_key: str) -> CfOverlay | None:
        r = self._conn.execute("SELECT * FROM overlay WHERE entry_key=?", (entry_key,)).fetchone()
        return self._row_to(r) if r else None

    def upsert(self, ov: CfOverlay) -> CfOverlay:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        existing = self.get(ov.entry_key)
        ov.created_at = existing.created_at or now if existing else now
        ov.updated_at = now
        with self._lock:
            self._conn.execute(
                """INSERT INTO overlay(entry_key,kind,custom_tags,categories,extras,image_override,
                      model,gen_threshold,char_threshold,raw_tags,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(entry_key) DO UPDATE SET
                      kind=excluded.kind, custom_tags=excluded.custom_tags,
                      categories=excluded.categories, extras=excluded.extras,
                      image_override=excluded.image_override, model=excluded.model,
                      gen_threshold=excluded.gen_threshold, char_threshold=excluded.char_threshold,
                      raw_tags=excluded.raw_tags, updated_at=excluded.updated_at""",
                (ov.entry_key, ov.kind, json.dumps(ov.custom_tags, ensure_ascii=False),
                 json.dumps({k: v.model_dump() for k, v in ov.categories.items()}, ensure_ascii=False),
                 json.dumps(ov.extras.model_dump(), ensure_ascii=False), ov.image_override,
                 ov.model, ov.gen_threshold, ov.char_threshold,
                 json.dumps(ov.raw_tags), ov.created_at, ov.updated_at),
            )
            self._conn.commit()
        return ov

    def delete(self, entry_key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM overlay WHERE entry_key=?", (entry_key,))
            self._conn.commit()
        import shutil
        d = self._dir_for(entry_key)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_overlay.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/models.py backend/storage/cf_overlay.py tests/test_cf_overlay.py
git commit -m "feat(cf): add CfOverlay model and overlay store"
```

---

### Task 7: deps 注入

**Files:**
- Modify: `backend/deps.py`
- Test: `tests/test_deps_cache.py`（已有文件，追加用例）

**Interfaces:**
- Consumes: Task 3/4/5/6 的类
- Produces: `get_character_db()`、`get_artist_db()`、`get_anima_character_db()`、`get_anima_artist_db()`、`get_cf_overlay()`、`get_cf_favorites()`、`get_cf_artist_favorites()`、`get_cf_recent()`（均 `@lru_cache`）

- [ ] **Step 1: 写失败测试**

在 `tests/test_deps_cache.py` 末尾追加：
```python
def test_cf_factories_cached():
    from backend import deps
    deps.get_character_db.cache_clear()
    deps.get_artist_db.cache_clear()
    deps.get_anima_character_db.cache_clear()
    deps.get_anima_artist_db.cache_clear()
    deps.get_cf_overlay.cache_clear()
    a = deps.get_character_db(); b = deps.get_character_db()
    assert a is b
    assert deps.get_cf_overlay() is deps.get_cf_overlay()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_deps_cache.py::test_cf_factories_cached -v`
Expected: FAIL（`get_character_db` 不存在）

- [ ] **Step 3: 实现**

在 `backend/deps.py` 末尾追加：
```python
# === Character Finder ===
@lru_cache
def get_character_db():
    from backend.characterfinder.character_db import CharacterDB
    return CharacterDB()

@lru_cache
def get_artist_db():
    from backend.characterfinder.artist_db import ArtistDB
    return ArtistDB()

@lru_cache
def get_anima_character_db():
    from backend.characterfinder.anima_db import AnimaCharacterDB
    return AnimaCharacterDB()

@lru_cache
def get_anima_artist_db():
    from backend.characterfinder.anima_db import AnimaArtistDB
    return AnimaArtistDB()

@lru_cache
def get_cf_overlay():
    from backend.storage.cf_overlay import CfOverlayStore
    from backend.config import settings
    return CfOverlayStore(settings.CF_OVERLAY_DB, settings.CF_OVERLAY_DIR)

@lru_cache
def get_cf_favorites():
    from backend.characterfinder.favorites import FavoritesDB
    return FavoritesDB()

@lru_cache
def get_cf_artist_favorites():
    from backend.characterfinder.favorites import ArtistFavoritesDB
    return ArtistFavoritesDB()

@lru_cache
def get_cf_recent():
    from backend.characterfinder.favorites import SearchHistoryDB
    return SearchHistoryDB()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_deps_cache.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/deps.py tests/test_deps_cache.py
git commit -m "feat(cf): wire cf factories into deps"
```

---

### Task 8: 封面资产服务 routes_cfassets

**Files:**
- Create: `backend/api/routes_cfassets.py`
- Test: `tests/test_cf_assets.py`

**Interfaces:**
- Consumes: `paths`（本地图目录）、`get_cf_overlay`（替换图优先）
- Produces: `GET /api/cf/asset?kind=&source=&key=&which=` → 本地替换图 > 本地下载/拷贝图 > 302 到原始 CDN url；`GET /api/cf/asset/overlay/{entry_key}/{filename}` → 替换图文件

**本地图定位规则**（封装为模块内函数 `local_image_path(kind, source, key, which) -> Path|None`）：
- `char` + `danbooru/e621`：根据 db 的 `image_url` 推导 slug（`Path(url).name`），查 `paths.COVERS_DIR / slug`
- `artist` + `danbooru/e621`：`which∈{1,2}` 对应 `image_url_1/2` → `paths.ARTIST_COVERS_DIR / slug`
- `char` + `anima`：`which=thumb`→`thumbname`，`which=image`→`imgname`，查 `paths.ANIMA_DIR / "characters" / <文件名>`
- `artist` + `anima`：`paths.ANIMA_DIR / "artists" / <文件名>`

**CDN url 回退**（`fallback_url(kind, source, key, which) -> str|None`）：从对应 db 读 `image_url`/`image_url_1`/`thumbname`→animadex 的 url 规则。danbooru/e621 直接返回 db 的 image_url；anima 返回 db 的 `url`（posts 页面，仅作占位，标注待下载）。

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_assets.py`:
```python
import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps
from backend.characterfinder import paths


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.characterfinder.paths.CHARACTERS_DB", tmp_path / "cf/characters.db")
    monkeypatch.setattr("backend.characterfinder.paths.COVERS_DIR", tmp_path / "cf/covers")
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_DIR", tmp_path / "cf/anima")
    for f in (deps.get_character_db, deps.get_artist_db, deps.get_anima_character_db,
              deps.get_anima_artist_db, deps.get_cf_overlay):
        f.cache_clear()
    # 建小 characters.db
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/characters.db")
    c.executescript("CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')")
    c.execute("INSERT INTO characters(id,name,image_url,source) VALUES(1,'miku','http://host/preview/miku.jpg','danbooru')")
    c.commit(); c.close()
    return create_app()


def test_local_cover_served(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    (tmp_path / "cf" / "covers").mkdir()
    (tmp_path / "cf" / "covers" / "miku.jpg").write_bytes(b"JPGDATA")
    r = client.get("/api/cf/asset", params={"kind": "char", "source": "danbooru", "key": "1", "which": "thumb"})
    assert r.status_code == 200 and r.content == b"JPGDATA"


def test_missing_falls_back_to_cdn(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/asset", params={"kind": "char", "source": "danbooru", "key": "1", "which": "thumb"})
    assert r.status_code == 307
    assert r.headers["location"] == "http://host/preview/miku.jpg"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_assets.py -v`
Expected: FAIL（路由不存在）

- [ ] **Step 3: 实现**

`backend/api/routes_cfassets.py`:
```python
"""封面资产服务：本地优先，未命中回退 CDN（307）。"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse

from backend.deps import get_character_db, get_artist_db, get_anima_character_db, get_anima_artist_db, get_cf_overlay
from backend.characterfinder import paths

router = APIRouter(prefix="/api/cf/asset", tags=["cf-asset"])


def _slug(url: str) -> str:
    return Path(url).name


def local_image_path(kind: str, source: str, key: str, which: str) -> Path | None:
    try:
        if kind == "char" and source in ("danbooru", "e621"):
            row = get_character_db().get_by_id(int(key)) if hasattr(get_character_db(), "get_by_id") else None
            url = row["image_url"] if row else None
            return paths.COVERS_DIR / _slug(url) if url else None
        if kind == "artist" and source in ("danbooru", "e621"):
            row = get_artist_db().get_by_id(int(key)) if hasattr(get_artist_db(), "get_by_id") else None
            url = (row or {}).get(f"image_url_{which}")
            return paths.ARTIST_COVERS_DIR / _slug(url) if url else None
        if kind == "char" and source == "anima":
            row = get_anima_character_db().get_by_character(key)
            name = (row or {}).get("thumbname" if which == "thumb" else "imgname")
            return paths.ANIMA_DIR / "characters" / name if name else None
        if kind == "artist" and source == "anima":
            row = get_anima_artist_db().get_by_artist(key)
            name = (row or {}).get("thumbname" if which == "thumb" else "imgname")
            return paths.ANIMA_DIR / "artists" / name if name else None
    except Exception:
        return None
    return None


def fallback_url(kind: str, source: str, key: str, which: str) -> str | None:
    try:
        if kind == "char" and source in ("danbooru", "e621"):
            row = get_character_db().get_by_id(int(key)) if hasattr(get_character_db(), "get_by_id") else None
            return row["image_url"] if row else None
        if kind == "artist" and source in ("danbooru", "e621"):
            row = get_artist_db().get_by_id(int(key)) if hasattr(get_artist_db(), "get_by_id") else None
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
    raise HTTPException(status_code=404, detail="no asset")
```

> **注意**：sdcf `CharacterDB`/`ArtistDB` 移植后可能没有 `get_by_id` 方法（原只有 `get(name)`/`get_by_name`）。**实现时先在 `character_db.py`/`artist_db.py` 各补一个 `get_by_id(id: int)` 方法**（`SELECT ... WHERE id=?`），并在 Task 3/4 的测试里补一条断言。若已在 Task 3 补上则此处直接可用。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_assets.py -v`
Expected: PASS（若 `get_by_id` 缺失，先补方法再跑）

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes_cfassets.py tests/test_cf_assets.py backend/characterfinder/character_db.py backend/characterfinder/artist_db.py
git commit -m "feat(cf): add cover asset service (local-first, cdn fallback)"
```

---

### Task 9: 角色只读 API routes_characters

**Files:**
- Create: `backend/api/routes_characters.py`
- Test: `tests/test_cf_characters.py`

**Interfaces:**
- Consumes: `get_character_db`/`get_anima_character_db`/`get_cf_favorites`/`paths.entry_key`
- Produces:
  - `GET /api/cf/characters?query=&source=&series=&page=1&size=50` → `{items:[{entry_key,source,name,series,trigger,core_tags,thumb_url,image_url,favorite}], total}`
  - `GET /api/cf/characters/series?source=` → `[{series,count}]`
  - `GET /api/cf/character?source=&key=` → 权威字段 + overlay 合并（含 `locked_tags`、`categories`、`extras`、`custom_tags`、`favorite`、`recent` 记录）

**字段映射**：
- danbooru/e621 角色：`trigger=name`、`core_tags=tags`（来自 characters.db 的 tags 列）；`locked_tags = [trigger] + core_tags 拆词`
- anima 角色：`trigger`、`core_tags` 直接取列；`locked_tags = [trigger] + core_tags 拆词`
- `thumb_url`/`image_url` 由前端拼 `/api/cf/asset?kind=char&source=&key=&which=thumb|image`（后端只返回 entry_key，前端组装；或后端直接返回拼好的 url——本任务后端返回拼好的 url 字符串，降低前端复杂度）

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_characters.py`:
```python
import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.config.settings.CF_FAVORITES_PATH", tmp_path / "cf/fav.json")
    monkeypatch.setattr("backend.config.settings.CF_RECENT_PATH", tmp_path / "cf/recent.json")
    monkeypatch.setattr("backend.characterfinder.paths.CHARACTERS_DB", tmp_path / "cf/characters.db")
    monkeypatch.setattr("backend.characterfinder.paths.ANIMA_CHARACTERS_DB", tmp_path / "cf/anima_characters.db")
    for f in (deps.get_character_db, deps.get_anima_character_db, deps.get_cf_overlay,
              deps.get_cf_favorites, deps.get_cf_recent):
        f.cache_clear()
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/characters.db")
    c.executescript("CREATE TABLE characters(id INTEGER PRIMARY KEY, name TEXT, series TEXT, tags TEXT, image_url TEXT, rank INTEGER, danbooru_tag TEXT, source TEXT DEFAULT 'danbooru')")
    c.execute("INSERT INTO characters(id,name,series,tags,image_url,rank,source) VALUES(1,'miku','vocaloid','miku, vocaloid, 1girl','http://x/miku.jpg',1,'danbooru')")
    c.commit(); c.close()
    return create_app()


def test_search_returns_entry_shape(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/characters", params={"query": "miku", "source": "danbooru"})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 1
    it = d["items"][0]
    assert it["entry_key"] == "char:danbooru:1"
    assert it["name"] == "miku"
    assert "/api/cf/asset" in it["thumb_url"]


def test_get_detail_includes_locked_tags(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"})
    assert r.status_code == 200
    d = r.json()
    assert "miku" in d["locked_tags"]  # trigger 进锁定标签
    assert d["categories"] == {}  # 无 overlay 时为空


def test_series_endpoint(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/characters/series", params={"source": "danbooru"})
    assert r.status_code == 200
    assert any(s["series"] == "vocaloid" for s in r.json())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_characters.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/api/routes_characters.py`:
```python
"""角色图鉴 API：搜索/详情（权威+overlay 合并），权威标签锁定。"""
from fastapi import APIRouter, Query
from backend.deps import (get_character_db, get_anima_character_db,
                          get_cf_overlay, get_cf_favorites, get_cf_recent)
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
        rows, total = get_anima_character_db().search(query, copyright_filter=series or None,
                                                       limit=size, offset=offset)
        items = [_anima_item(r, paths.entry_key("char", "anima", r["character"]) in favs) for r in rows]
    else:  # danbooru / e621 都在 characters.db
        rows, total = get_character_db().search(query, series_filter=series or None,
                                                 source_filter=source, limit=size, offset=offset)
        items = [_danbooru_item(r, paths.entry_key("char", "danbooru", str(r["id"])) in favs) for r in rows]
    return {"items": items, "total": total}


@router.get("/characters/series")
def list_series(source: str = Query(...)):
    if source == "anima":
        return [{"series": c, "count": n} for c, n in get_anima_character_db().list_copyrights()]
    return [{"series": s, "count": n} for s, n in get_character_db().list_series()]


@router.get("/character")
def get_character(source: str = Query(...), key: str = Query(...)):
    # 权威
    if source == "anima":
        row = get_anima_character_db().get_by_character(key) or {}
        base = _anima_item(row, False)
    else:
        row = get_character_db().get_by_id(int(key))
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="not found")
        base = _danbooru_item(row, False)
    ek = base["entry_key"]
    base["favorite"] = get_cf_favorites().is_favorite(ek)
    # 锁定标签 = trigger 词 + core_tags 词
    locked = []
    if base["trigger"]:
        locked += _split_tags(base["trigger"])
    locked += _split_tags(base["core_tags"])
    base["locked_tags"] = list(dict.fromkeys(locked))  # 去重保序
    # overlay 合并
    ov = get_cf_overlay().get(ek)
    base["categories"] = {k: v.model_dump() for k, v in (ov.categories if ov else {}).items()}
    base["extras"] = (ov.extras if ov else None).model_dump() if ov else {"tags": [], "phrase": "", "user_edited": False}
    base["custom_tags"] = ov.custom_tags if ov else []
    base["model"] = ov.model if ov else "wd14"
    base["gen_threshold"] = ov.gen_threshold if ov else 0.35
    base["char_threshold"] = ov.char_threshold if ov else 0.9
    base["image_override"] = ov.image_override if ov else None
    # 记录最近查看
    get_cf_recent().add(ek)
    return base
```

> **注意 `get_character_db().search` 的 `source_filter` 参数**：sdcf 原签名是 `source_filter: str = "both"`。若传 `"danbooru"`/`"e621"` 会按 source 列过滤。保持原签名，Task 3 移植时勿改。`get_by_id` 在 Task 8 已补。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_characters.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes_characters.py tests/test_cf_characters.py
git commit -m "feat(cf): add character search/detail api"
```

---

### Task 10: 角色 overlay 联动（tag/reclassify/save/image/favorite）

**Files:**
- Modify: `backend/api/routes_characters.py`（追加端点）
- Test: `tests/test_cf_characters.py`（追加用例）

**Interfaces:**
- Consumes: `get_tagger`/`get_classifier`/`get_cf_overlay`/`local_image_path`（Task 8）
- Produces：
  - `POST /api/cf/character/tag?source=&key=` body `{model,gen_th,char_th,use_char}` → 对当前图跑 tagger，结果落 overlay，返回合并详情
  - `POST /api/cf/character/reclassify?source=&key=` body `{keep:dict[str,list[str]]}` → 用 raw_tags 重分类
  - `PUT /api/cf/character?source=&key=` body `{categories,extras,custom_tags}` → 存 overlay（**不接收 locked_tags**）
  - `POST /api/cf/character/image?source=&key=` 上传替换图 → 存 overlay，返回新 image_override
  - `POST /api/cf/character/favorite?source=&key=` → toggle，返回 `{favorite:bool}`

**锁定语义**：tag/reclassify 只写 overlay 的 categories/extras，绝不触碰权威 trigger/core_tags；save 忽略请求体中的任何锁定字段。

- [ ] **Step 1: 写失败测试**

在 `tests/test_cf_characters.py` 追加：
```python
import io
from PIL import Image


def _png():
    b = io.BytesIO(); Image.new("RGB", (20, 20)).save(b, format="PNG"); b.seek(0); return b


class _FakeTagger:
    def tag_image(self, pil, gen_th=0.35, char_th=0.9, use_char=True):
        return {"long hair": 0.9, "dress": 0.7, "weird thing": 0.4}


def _tag_app(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.api.routes_characters.get_tagger", lambda model="wd14": _FakeTagger())
    return app


def test_tag_writes_overlay(tmp_path, monkeypatch):
    client = TestClient(_tag_app(tmp_path, monkeypatch))
    # 先放一张本地封面供反推读取
    (tmp_path / "cf" / "covers").mkdir()
    (tmp_path / "cf" / "covers" / "miku.jpg").write_bytes(_png().read())
    r = client.post("/api/cf/character/tag", params={"source": "danbooru", "key": "1"},
                    json={"model": "wd14", "gen_th": 0.35, "char_th": 0.9, "use_char": True})
    assert r.status_code == 200
    d = r.json()
    assert "long hair" in d["categories"]["head"]["tags"]
    assert "dress" in d["categories"]["clothing"]["tags"]
    assert "weird thing" in d["extras"]["tags"]
    # 权威 trigger 仍在锁定标签
    assert "miku" in d["locked_tags"]


def test_save_persists_categories(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.put("/api/cf/character", params={"source": "danbooru", "key": "1"},
                   json={"categories": {"head": {"tags": ["my tag"], "phrase": "", "user_edited": True}},
                         "extras": {"tags": [], "phrase": "", "user_edited": False}, "custom_tags": ["fav"]})
    assert r.status_code == 200
    again = client.get("/api/cf/character", params={"source": "danbooru", "key": "1"}).json()
    assert again["categories"]["head"]["tags"] == ["my tag"]
    assert again["custom_tags"] == ["fav"]


def test_favorite_toggle(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.post("/api/cf/character/favorite", params={"source": "danbooru", "key": "1"})
    assert r.json()["favorite"] is True
    r2 = client.post("/api/cf/character/favorite", params={"source": "danbooru", "key": "1"})
    assert r2.json()["favorite"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_characters.py -k "tag_writes or save_persists or favorite_toggle" -v`
Expected: FAIL（端点不存在）

- [ ] **Step 3: 实现**

在 `backend/api/routes_characters.py` 追加（顶部 import 补 `UploadFile, File, HTTPException`、`get_tagger, get_classifier`、`CfOverlay, CategoryData`、`Image`、`local_image_path`、`secrets`）：
```python
from fastapi import HTTPException, UploadFile, File
from fastapi import Form
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import secrets

from backend.deps import get_tagger, get_classifier
from backend.models import CfOverlay, CategoryData, PROMPT_ORDER
from backend.api.routes_cfassets import local_image_path


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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_characters.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/api/routes_characters.py tests/test_cf_characters.py
git commit -m "feat(cf): add tag/reclassify/save/image/favorite for characters"
```

---

### Task 11: 艺术家 API routes_artists + 收藏/最近/随机 + main.py 注册

**Files:**
- Create: `backend/api/routes_artists.py`
- Modify: `backend/main.py`（注册 3 个 router）
- Test: `tests/test_cf_artists.py`、`tests/test_cf_integration.py`

**Interfaces:**
- Consumes: `get_artist_db`/`get_anima_artist_db`/`get_cf_artist_favorites`/`get_cf_overlay`/`get_cf_recent`
- Produces：
  - `GET /api/cf/artists?query=&source=&page=&size=`、`/api/cf/artist?source=&key=`（含双图 thumb1_url/thumb2_url、locked_tags=[画师 tag]）、`POST /api/cf/artist/tag|reclassify|image|favorite`、`PUT /api/cf/artist`
  - `GET /api/cf/favorites?kind=char|artist` → `[{entry_key,...}]`（解析 entry_key 取回基础信息）
  - `GET /api/cf/recent?kind=char|artist&limit=` → 最近查看
  - `GET /api/cf/random?type=characters|artists&source=&size=24` → 随机 item 列表（复用 search 的 item 形状）

- [ ] **Step 1: 写失败测试**

Create `tests/test_cf_artists.py`:
```python
import sqlite3
from fastapi.testclient import TestClient
from backend.main import create_app
from backend import deps


def _app(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.config.settings.CF_DIR", tmp_path / "cf")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DB", tmp_path / "cf/cf_overlay.db")
    monkeypatch.setattr("backend.config.settings.CF_OVERLAY_DIR", tmp_path / "cf/overlay")
    monkeypatch.setattr("backend.config.settings.CF_FAVORITES_PATH", tmp_path / "cf/fav.json")
    monkeypatch.setattr("backend.config.settings.CF_RECENT_PATH", tmp_path / "cf/recent.json")
    monkeypatch.setattr("backend.characterfinder.paths.ARTISTS_DB", tmp_path / "cf/artists.db")
    for f in (deps.get_artist_db, deps.get_cf_overlay, deps.get_cf_artist_favorites, deps.get_cf_recent):
        f.cache_clear()
    (tmp_path / "cf").mkdir()
    c = sqlite3.connect(tmp_path / "cf/artists.db")
    c.executescript("CREATE TABLE artists(id INTEGER PRIMARY KEY, name TEXT, tag TEXT, display_name TEXT, image_url_1 TEXT, image_url_2 TEXT, ref_count INTEGER, source TEXT DEFAULT 'danbooru', rank INTEGER)")
    c.execute("INSERT INTO artists(id,name,tag,display_name,image_url_1,image_url_2,rank,source) VALUES(1,'ebifurya','ebifurya','ebifurya','http://x/1.jpg','http://x/2.jpg',1,'danbooru')")
    c.commit(); c.close()
    return create_app()


def test_artist_search_and_detail(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/artists", params={"query": "ebi", "source": "danbooru"})
    assert r.json()["total"] == 1
    it = r.json()["items"][0]
    assert it["entry_key"] == "artist:danbooru:1"
    d = client.get("/api/cf/artist", params={"source": "danbooru", "key": "1"}).json()
    assert "ebifurya" in d["locked_tags"]
    assert "/api/cf/asset" in d["thumb1_url"]


def test_random(tmp_path, monkeypatch):
    client = TestClient(_app(tmp_path, monkeypatch))
    r = client.get("/api/cf/random", params={"type": "artists", "source": "danbooru", "size": 5})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cf_artists.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 routes_artists.py**

仿 `routes_characters.py` 结构。关键差异：item 多 `tag`/`thumb1_url`/`thumb2_url`，`locked_tags=[tag]`，`which` 用 `1`/`2`。`tag/reclassify/save/image/favorite` 同构（kind="artist"，favorite 用 `get_cf_artist_favorites`）。`get_by_id` 用 Task 8 在 `artist_db.py` 补的同名方法。

```python
"""艺术家图鉴 API。结构与 routes_characters 同构，双图 + 画师标签锁定。"""
from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
import secrets

from backend.deps import (get_artist_db, get_anima_artist_db, get_cf_overlay,
                          get_cf_artist_favorites, get_tagger, get_classifier)
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
```

**收藏/最近/随机**（追加到 `routes_characters.py` 末尾，因其共享 `/api/cf` 前缀）：
```python
from backend.deps import (get_cf_favorites, get_cf_artist_favorites, get_cf_recent,
                          get_character_db, get_anima_character_db,
                          get_artist_db, get_anima_artist_db)


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


@router.get("/favorites")
def list_favorites(kind: str = Query("char", regex="^(char|artist)$")):
    store = get_cf_favorites() if kind == "char" else get_cf_artist_favorites()
    keys = [ek for ek in store.get_all() if ek.startswith(f"{kind}:")]
    return {"items": _resolve_items(keys)}


@router.get("/recent")
def list_recent(kind: str = Query("char", regex="^(char|artist)$"), limit: int = Query(50, le=200)):
    keys = [ek for ek in get_cf_recent().get_all() if ek.startswith(f"{kind}:")]
    return {"items": _resolve_items(keys[:limit])}


@router.get("/random")
def random_cf(type: str = Query("characters"), source: str = Query("danbooru"),
              size: int = Query(24, ge=1, le=200)):
    if type == "artists":
        db = get_anima_artist_db() if source == "anima" else get_artist_db()
        rows, _ = db.search("", limit=size, offset=0)
        favs = set(get_cf_artist_favorites().get_all())
        from backend.api.routes_artists import _anima_artist, _danbooru_artist
        items = [_anima_artist(r, paths.entry_key("artist", source, r["artist"]) in favs) if source == "anima"
                 else _danbooru_artist(r, paths.entry_key("artist", "danbooru", str(r["id"])) in favs) for r in rows]
    else:
        db = get_anima_character_db() if source == "anima" else get_character_db()
        rows, _ = db.search("", limit=size, offset=0)
        favs = set(get_cf_favorites().get_all())
        items = [_anima_item(r, paths.entry_key("char", source, r["character"]) in favs) if source == "anima"
                 else _danbooru_item(r, paths.entry_key("char", "danbooru", str(r["id"])) in favs) for r in rows]
    return {"items": items}
```

> 随机性说明：首版用 `search("")` 取前 N，不强求真随机；若 db 支持 `ORDER BY RANDOM()` 可后续优化（P3 前端接入验证够用即可）。

- [ ] **Step 4: 注册到 main.py**

修改 `backend/main.py` 的 `create_app()`，在 `app.include_router(routes_pathtag.router)` 之后追加：
```python
    from backend.api import routes_cfassets, routes_characters, routes_artists
    app.include_router(routes_cfassets.router)
    app.include_router(routes_characters.router)
    app.include_router(routes_artists.router)
```
（仍需在 `app.mount("/", SpaStaticFiles(...))` 之前）

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_cf_artists.py tests/test_cf_characters.py -v`
Expected: PASS

补 `tests/test_cf_integration.py`（防止 mount 顺序破坏 SPA 与 /api）：
```python
from fastapi.testclient import TestClient
from backend.main import create_app


def test_cf_routes_registered():
    # 不带真实 db 也能注册（懒连接）
    app = create_app()
    client = TestClient(app)
    # /api/cf/characters 缺 source 参数应返回 422（证明路由已注册）
    assert client.get("/api/cf/characters").status_code == 422
```

Run: `python -m pytest tests/test_cf_integration.py -v`
Expected: PASS

- [ ] **Step 6: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿（含原有测试）

- [ ] **Step 7: 提交**

```bash
git add backend/api/routes_artists.py backend/api/routes_characters.py backend/main.py tests/test_cf_artists.py tests/test_cf_integration.py
git commit -m "feat(cf): add artists api, favorites/recent/random, register routes"
```

---

## Self-Review 结论

**Spec 覆盖**：P1 后端全部覆盖——数据层移植(T3-5)、overlay(T6)、deps(T7)、资产服务(T8)、角色 API 含联动(T9-10)、艺术家+收藏+最近+随机+注册(T11)。P2 前端、P3 UI、P4 脚本明确留给后续 plan（本 plan 开头声明）。

**Placeholder**：无 TBD/TODO。移植类 task（T3/4）给出精确源文件路径 + 改动点；T5 给完整兜底实现（json 持久化版）。所有「新增」代码均贴全文：T6 的 model+store、T8 的资产服务、T9 的角色只读 API、T10 的角色 5 联动端点、T11 的艺术家只读+5 联动端点、T11 的 `_resolve_item`/`_resolve_items`/favorites/recent/random。无「同上」「复制 Task N」式省略。

**类型一致**：`entry_key`/`parse_entry_key`、`CfOverlay`、`CategoryData`、`get_by_id`、`local_image_path`、`_danbooru_item`/`_anima_item` 等名称跨 task 一致。`get_by_id` 在 Task 8 首次要求补充，Task 9/11 复用。

**已知实现注意**：sdcf 移植类需补 `get_by_id`；`search` 的 `source_filter` 保持 sdcf 原签名；anima key 含特殊字符走 query 参数或前端 `encodeURIComponent`（详情用 query `?source=&key=` 已规避路径问题）。
