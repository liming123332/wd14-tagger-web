from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # wd14-tagger-web/

DATA_DIR = ROOT / "data"
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
