from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # wd14-tagger-web/

DATA_DIR = ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
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
