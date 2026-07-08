from __future__ import annotations
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # wd14-tagger-web/

# 数据目录（data/）可外置到其他硬盘或 NAS。解析优先级（高→低）：
#   1) 环境变量 WD14_DATA_DIR（运维硬覆盖，盖过页面配置）
#   2) 页面配置文件 ROOT/data_dir.json（设置页写入）
#   3) 默认 ROOT/data
# 任一级缺失/损坏都安全降级到下一级。DATA_DIR 在启动时求值一次，
# 改页面配置后需重启后端生效（所有派生路径随新进程重新求值）。
DATA_DIR_PREF_PATH = ROOT / "data_dir.json"


def _resolve_data_dir() -> tuple[Path, str]:
    """返回 (data_dir, source)。source ∈ {'env','page','default'}，描述当前
    运行实例 DATA_DIR 的来源（启动时锁定，改配置后需重启才变）。"""
    env = os.environ.get("WD14_DATA_DIR", "").strip().strip('"').strip("'")
    if env:
        return Path(env), "env"
    configured = read_configured_data_dir()
    if configured:
        return Path(configured), "page"
    return ROOT / "data", "default"


def read_configured_data_dir() -> str | None:
    """实时读取页面配置文件里的路径值（未配置/损坏 → None）。

    GET 接口用它返回最新 configured（PUT/DELETE 后立即反映），区别于启动时
    锁定的 DATA_DIR / DATA_DIR_SOURCE。
    """
    try:
        pref = json.loads(DATA_DIR_PREF_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if isinstance(pref, dict):
        p = str(pref.get("path") or "").strip().strip('"').strip("'")
        return p or None
    return None


DATA_DIR, DATA_DIR_SOURCE = _resolve_data_dir()
IMAGES_DIR = DATA_DIR / "images"
PROMPTBOX_DIR = DATA_DIR / "promptbox"
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
MODELS_DIR = ROOT / "models"
CONFIG_DIR = ROOT / "backend" / "config"
TAG_RULES_PATH = CONFIG_DIR / "tag_rules.yaml"
QUALITY_TEMPLATE_PATH = CONFIG_DIR / "quality_template.yaml"

# general-tag / character-tag confidence thresholds for WD14
DEFAULT_GEN_THRESHOLD = 0.35
DEFAULT_CHAR_THRESHOLD = 0.90
THUMB_MAX_SIZE = 400  # thumbnail longest edge in px

# All 6 categories shown in the UI (includes quality). For DISPLAY only —
# do NOT index tag_rules.yaml `categories` with this list, since `quality`
# has no rule block (it comes from quality_template.yaml instead).
CATEGORY_KEYS = ["quality", "head", "clothing", "view", "action", "scene"]
# Order in which a tag is matched against rule blocks (quality excluded —
# it's never matched, only template-filled). The engine iterates this list.
PRIORITY = ["head", "clothing", "view", "action", "scene"]
# Order categories are concatenated when building the final prompt string.
PROMPT_ORDER = ["quality", "head", "clothing", "view", "action", "scene"]

WD14_MODEL_URL = "https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2/resolve/main/model.onnx"
WD14_CSV_URL = "https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2/resolve/main/selected_tags.csv"

ALL_DISPLAY_KEYS = ["quality", "head", "clothing", "view", "action", "scene", "extras"]
