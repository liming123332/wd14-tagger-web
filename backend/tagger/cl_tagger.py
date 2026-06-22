from __future__ import annotations
from pathlib import Path
import json
import shutil
import urllib.request
import logging

import numpy as np
from PIL import Image

from backend.config import settings
from backend.tagger.models_spec import ModelSpec
from backend.tagger._onnx_providers import select_providers

logger = logging.getLogger(__name__)


class CLTagger:
    """cl_tagger（cella110n/cl_tagger）反推。移植自 mikazuki/tagger/interrogators/cl.py。
    与 wd/ddb 系的三处本质差异：
      1. 预处理：RGB→pad 正方形→BICUBIC 448→/255→CHW→BGR→mean/std(0.5) 归一化；
      2. 后处理：模型输出是 logits，需 stable_sigmoid；
      3. 标签：tag_mapping.json（兼容 {idx_to_tag,tag_to_category} 与 dict-of-dicts 两格式），
         按 Rating/General/Character/Copyright/Artist/Meta/Quality/Model 8 类分桶。
    对外接口与 OnnxTagger.tag_image 完全一致，返回 {tag: score}，供 Classifier 统一分类。"""

    def __init__(self, spec: ModelSpec, models_root: Path = settings.MODELS_DIR):
        self.spec = spec
        self.model_dir = Path(models_root) / spec.folder
        self.session = None
        self.input_name = None
        self.in_size = 448  # cl 固定 448×448
        self.names: list[str] = []
        self.rating_idx: list[int] = []
        self.general_idx: list[int] = []
        self.character_idx: list[int] = []
        self.copyright_idx: list[int] = []
        self.artist_idx: list[int] = []
        self.meta_idx: list[int] = []
        self.quality_idx: list[int] = []
        self.model_idx: list[int] = []

    def ensure_loaded(self) -> None:
        if self.session is not None:
            return
        self._download()
        self._load()

    def _download(self) -> None:
        # 逐文件下载 + 进度，逻辑集中在 _download_util.download_files（三类 tagger 共用）。
        from backend.tagger._download_util import download_files
        download_files(self.spec, self.model_dir, self.spec.key)

    def _load(self) -> None:
        from onnxruntime import InferenceSession

        onnx_path = self.model_dir / "model.onnx"
        mapping_path = self.model_dir / "tag_mapping.json"
        if not onnx_path.exists():
            raise FileNotFoundError(f"model.onnx missing in {self.model_dir}")
        if not mapping_path.exists():
            raise FileNotFoundError(f"tag_mapping.json missing in {self.model_dir}")

        self.session = InferenceSession(str(onnx_path), providers=select_providers())
        logger.info("%s ONNX providers: %s", self.spec.key, self.session.get_providers())
        self.input_name = self.session.get_inputs()[0].name

        with mapping_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容两种 tag_mapping.json 格式
        if isinstance(data, dict) and "idx_to_tag" in data:
            idx_to_tag = {int(k): v for k, v in data["idx_to_tag"].items()}
            tag_to_category = data["tag_to_category"]
        else:
            int_keys = {int(k): v for k, v in data.items()}
            idx_to_tag = {idx: d["tag"] for idx, d in int_keys.items()}
            tag_to_category = {d["tag"]: d["category"] for d in int_keys.values()}

        self.names = [None] * (max(idx_to_tag) + 1)
        buckets = {
            "Rating": self.rating_idx, "General": self.general_idx,
            "Character": self.character_idx, "Copyright": self.copyright_idx,
            "Artist": self.artist_idx, "Meta": self.meta_idx,
            "Quality": self.quality_idx, "Model": self.model_idx,
        }
        self.rating_idx.clear(); self.general_idx.clear(); self.character_idx.clear()
        self.copyright_idx.clear(); self.artist_idx.clear(); self.meta_idx.clear()
        self.quality_idx.clear(); self.model_idx.clear()
        for idx, tag in idx_to_tag.items():
            while idx >= len(self.names):
                self.names.append(None)
            self.names[idx] = tag
            cat = tag_to_category.get(tag, "")
            if cat in buckets:
                buckets[cat].append(idx)

    def _prep(self, pil_image: Image.Image) -> np.ndarray:
        im = pil_image.convert("RGB")
        w, h = im.size
        if w != h:
            # pad 正方形（白底居中）
            size = max(w, h)
            bg = Image.new("RGB", (size, size), (255, 255, 255))
            bg.paste(im, ((size - w) // 2, (size - h) // 2))
            im = bg
        im = im.resize((self.in_size, self.in_size), Image.BICUBIC)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[::-1, :, :]  # HWC→CHW + RGB→BGR
        mean = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(3, 1, 1)
        std = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(3, 1, 1)
        arr = (arr - mean) / std
        return arr[None, ...].astype(np.float32)

    def tag_image(self, pil_image, gen_th: float = 0.35,
                  char_th: float = 0.60, use_char: bool = True) -> dict[str, float]:
        self.ensure_loaded()
        x = self._prep(pil_image)
        outputs = self.session.run(None, {self.input_name: x})[0]
        # 输出是 logits → stable_sigmoid
        probs = 1.0 / (1.0 + np.exp(-np.clip(outputs[0], -30, 30)))
        out: dict[str, float] = {}
        # general/copyright/artist/meta 用 gen_th（严格 >）；character 用 char_th。
        # char_th 默认 0.60 = cl_tagger 的「角色名称识别阈值」（移植自 mikazuki
        # character_threshold=0.6），区别于 wd 系的 0.90：cl 专门训练了角色/版权识别，
        # 阈值更低以保留更多角色名。UI 上该阈值标注「仅 cl_tagger 生效」（Task 8）。
        # rating/model 默认不要；quality 交给 Classifier 的 quality_template 统一处理。
        for bucket in (self.general_idx, self.copyright_idx, self.artist_idx, self.meta_idx):
            for i in bucket:
                if i < len(self.names) and self.names[i] is not None:
                    pr = float(probs[i])
                    if pr > gen_th:
                        out[self.names[i].replace("_", " ")] = pr
        if use_char:
            for i in self.character_idx:
                if i < len(self.names) and self.names[i] is not None:
                    pr = float(probs[i])
                    if pr > char_th:
                        out[self.names[i].replace("_", " ")] = pr
        return out
