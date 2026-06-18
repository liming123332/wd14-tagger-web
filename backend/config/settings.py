from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # wd14-tagger-web/

DATA_DIR = ROOT / "data"
IMAGES_DIR = DATA_DIR / "images"
MODELS_DIR = ROOT / "models"
CONFIG_DIR = ROOT / "backend" / "config"
TAG_RULES_PATH = CONFIG_DIR / "tag_rules.yaml"
QUALITY_TEMPLATE_PATH = CONFIG_DIR / "quality_template.yaml"

DEFAULT_GEN_THRESHOLD = 0.35
DEFAULT_CHAR_THRESHOLD = 0.90
THUMB_MAX_SIZE = 400

CATEGORY_KEYS = ["quality", "head", "clothing", "view", "action", "scene"]
PRIORITY = ["head", "clothing", "view", "action", "scene"]
PROMPT_ORDER = ["quality", "head", "clothing", "view", "action", "scene"]

WD14_MODEL_URL = "https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2/resolve/main/model.onnx"
WD14_CSV_URL = "https://huggingface.co/SmilingWolf/wd-v1-4-convnext-tagger-v2/resolve/main/selected_tags.csv"

ALL_DISPLAY_KEYS = ["quality", "head", "clothing", "view", "action", "scene", "extras"]
