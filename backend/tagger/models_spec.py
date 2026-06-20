from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

# 下载源移植自 tagger_prompt/scripts/tagger_prompt.py 的 _MODEL_DOWNLOADS。
_HF = "https://hf-mirror.com"  # 国内镜像：所有模型走 hf-mirror（huggingface.co 的完整镜像）


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    folder: str
    files: dict[str, str]  # 文件名 -> 下载 URL
    prep: str              # "bgr_wd" | "ddb" | "cl"
    tag_source: str        # "csv" | "txt" | "cl_json"


def _wd(key: str, label: str, folder: str, repo: str, owner: str = "SmilingWolf") -> ModelSpec:
    base = f"{_HF}/{owner}/{repo}/resolve/main"
    return ModelSpec(
        key=key, label=label, folder=folder,
        files={"model.onnx": f"{base}/model.onnx",
               "selected_tags.csv": f"{base}/selected_tags.csv"},
        prep="bgr_wd", tag_source="csv",
    )


def _cl() -> ModelSpec:
    # cella110n/cl_tagger：架构异构（pad+BICUBIC+BGR+mean/std 归一化、logits 需 sigmoid、
    # tag_mapping.json 8 类分桶），由独立 CLTagger 类处理（不进 OnnxTagger）。
    base = f"{_HF}/cella110n/cl_tagger/resolve/main/cl_tagger_1_01"
    return ModelSpec(
        key="cl_tagger", label="CL Tagger", folder="cl_tagger",
        files={"model.onnx": f"{base}/model.onnx",
               "tag_mapping.json": f"{base}/tag_mapping.json"},
        prep="cl", tag_source="cl_json",
    )


MODEL_SPECS: dict[str, ModelSpec] = {
    "wd14":       _wd("wd14", "WD14", "wd14", "wd-v1-4-convnext-tagger-v2"),
    "wd3":        _wd("wd3", "WD3", "wd_swinv2_v3", "wd-swinv2-tagger-v3"),
    "wd_vit_v3":  _wd("wd_vit_v3", "WD ViT v3", "wd_vit_v3", "wd-vit-tagger-v3"),
    "wd_vit_large_v3": _wd("wd_vit_large_v3", "WD ViT Large v3", "wd_vit_large_v3", "wd-vit-large-tagger-v3"),
    "wd_eva_v3":  _wd("wd_eva_v3", "WD EVA v3", "wd_eva_v3", "wd-eva02-large-tagger-v3"),
    "wd_conv_v3": _wd("wd_conv_v3", "WD Conv v3", "wd_conv_v3", "wd-convnext-tagger-v3"),
    "ddb": ModelSpec(
        key="ddb", label="DDB", folder="deepdanbooru",
        files={"model.onnx": f"{_HF}/chinoll/deepdanbooru/resolve/main/deepdanbooru.onnx",
               "tags.txt": f"{_HF}/chinoll/deepdanbooru/resolve/main/tags.txt"},
        prep="ddb", tag_source="txt",
    ),
    "e621": _wd("e621", "E621", "e621", "Z3D-E621-Convnext", owner="silveroxides"),
    "cl_tagger": _cl(),
    # cl_tagger_v2（cella110n/cl_tagger_v2，SigLIP2-so400m-patch14-384）：架构异构于 v1，
    # 由独立 CLTaggerV2 类处理（不进 OnnxTagger/CLTagger）。权重为外部数据（model.onnx.data），
    # onnxruntime 加载 model.onnx 时自动读取同目录 .data。gated 模型，需手动下载 3 文件放入 folder。
    # 注意 resolve 路径在仓库 v2_01a/ 子目录下（v2_00 为旧版）。
    "cl_tagger_v2": ModelSpec(
        key="cl_tagger_v2", label="CL Tagger v2", folder="cl_tagger_v2_01a",
        files={"model.onnx": f"{_HF}/cella110n/cl_tagger_v2/resolve/main/v2_01a/model.onnx",
               "model.onnx.data": f"{_HF}/cella110n/cl_tagger_v2/resolve/main/v2_01a/model.onnx.data",
               "model_vocabulary.json": f"{_HF}/cella110n/cl_tagger_v2/resolve/main/v2_01a/model_vocabulary.json"},
        prep="cl_v2", tag_source="cl_v2_json",
    ),
}

DEFAULT_MODEL_KEY = "wd14"


def is_downloaded(key: str, models_root: Path) -> bool:
    """该 key 的全部 files 是否都存在于 models_root/<folder>。"""
    spec = MODEL_SPECS[key]  # 未知 key 抛 KeyError
    d = Path(models_root) / spec.folder
    return all((d / name).exists() for name in spec.files)
