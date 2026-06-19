from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

# 下载源移植自 tagger_prompt/scripts/tagger_prompt.py 的 _MODEL_DOWNLOADS。
_HF = "https://huggingface.co"


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    folder: str
    files: dict[str, str]  # 文件名 -> 下载 URL
    prep: str              # "bgr_wd" | "ddb"
    tag_source: str        # "csv" | "txt"


def _wd(key: str, label: str, folder: str, repo: str) -> ModelSpec:
    base = f"{_HF}/SmilingWolf/{repo}/resolve/main"
    return ModelSpec(
        key=key, label=label, folder=folder,
        files={"model.onnx": f"{base}/model.onnx",
               "selected_tags.csv": f"{base}/selected_tags.csv"},
        prep="bgr_wd", tag_source="csv",
    )


MODEL_SPECS: dict[str, ModelSpec] = {
    "wd14":       _wd("wd14", "WD14", "wd14", "wd-v1-4-convnext-tagger-v2"),
    "wd3":        _wd("wd3", "WD3", "wd_swinv2_v3", "wd-swinv2-tagger-v3"),
    "wd_vit_v3":  _wd("wd_vit_v3", "WD ViT v3", "wd_vit_v3", "wd-vit-tagger-v3"),
    "wd_eva_v3":  _wd("wd_eva_v3", "WD EVA v3", "wd_eva_v3", "wd-eva02-large-tagger-v3"),
    "wd_conv_v3": _wd("wd_conv_v3", "WD Conv v3", "wd_conv_v3", "wd-convnext-tagger-v3"),
    "ddb": ModelSpec(
        key="ddb", label="DDB", folder="deepdanbooru",
        files={"model.onnx": f"{_HF}/chinoll/deepdanbooru/resolve/main/deepdanbooru.onnx",
               "tags.txt": f"{_HF}/chinoll/deepdanbooru/resolve/main/tags.txt"},
        prep="ddb", tag_source="txt",
    ),
    "e621": _wd("e621", "E621", "e621", "silveroxides/Z3D-E621-Convnext"),
}

DEFAULT_MODEL_KEY = "wd14"


def is_downloaded(key: str, models_root: Path) -> bool:
    """该 key 的全部 files 是否都存在于 models_root/<folder>。"""
    spec = MODEL_SPECS[key]  # 未知 key 抛 KeyError
    d = Path(models_root) / spec.folder
    return all((d / name).exists() for name in spec.files)
