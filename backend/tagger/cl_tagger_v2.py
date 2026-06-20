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

logger = logging.getLogger(__name__)


class CLTaggerV2:
    """cl_tagger_v2（cella110n/cl_tagger_v2，SigLIP2-so400m-patch14-384 编码器）反推。
    与 v1（CLTagger）的三处本质差异：
      1. 预处理（SigLIP2 準拠）：RGB→resize 384×384（BICUBIC，不 pad 不裁剪）→/255→CHW
         →mean/std(0.5) 归一化。保持 RGB（不转 BGR），区别于 v1 的 pad 正方形+448+BGR；
      2. 权重外部数据：model.onnx + model.onnx.data，onnxruntime 加载 model.onnx 时自动
         读取同目录 .data（两文件必须同目录）；
      3. 词表 model_vocabulary.json（{tag_to_idx, idx_to_tag, tag_to_category, categories}），
         6 类 General/Quality/Rating/Character/Copyright/Meta。输出 General/Copyright/Character/Meta，
         排除 Rating（评分无用）与 Quality（交 Classifier 的 quality_template）。
    阈值：v2 文档推荐单阈值 0.55 运营（probs >= thr），不区分角色阈值（区别于 v1 的 gen/char 双阈值）。
    对外接口与其它 tagger 一致，返回 {tag: score}，供 Classifier 统一分类。"""

    def __init__(self, spec: ModelSpec, models_root: Path = settings.MODELS_DIR):
        self.spec = spec
        self.model_dir = Path(models_root) / spec.folder
        self.session = None
        self.input_name = None
        self.in_size = 384  # siglip2-so400m-patch14-384 固定 384×384
        self.names: list[str] = []
        self.general_idx: list[int] = []
        self.character_idx: list[int] = []
        self.copyright_idx: list[int] = []
        self.meta_idx: list[int] = []

    def ensure_loaded(self) -> None:
        if self.session is not None:
            return
        self._download()
        self._load()

    def _download(self) -> None:
        # 逻辑同 OnnxTagger/CLTagger（逐文件 skip 已有、.part 原子写、Content-Length 校验）。
        # 注：cl_tagger_v2 是 gated 模型，hf-mirror 无法直接下载；用户需手动下载 3 文件放入 model_dir。
        self.model_dir.mkdir(parents=True, exist_ok=True)
        for name, url in self.spec.files.items():
            dst = self.model_dir / name
            if dst.exists():
                continue
            tmp = dst.with_suffix(dst.suffix + ".part")
            try:
                with urllib.request.urlopen(url) as resp:
                    expected = resp.headers.get("Content-Length")
                    with tmp.open("wb") as f:
                        shutil.copyfileobj(resp, f)
                if expected is not None and str(tmp.stat().st_size) != expected:
                    raise IOError(f"{name} 下载不完整：期望 {expected}，实际 {tmp.stat().st_size}")
                tmp.replace(dst)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise

    def _load(self) -> None:
        import onnxruntime as ort
        from onnxruntime import InferenceSession

        onnx_path = self.model_dir / "model.onnx"
        vocab_path = self.model_dir / "model_vocabulary.json"
        if not onnx_path.exists():
            raise FileNotFoundError(f"model.onnx missing in {self.model_dir}")
        if not vocab_path.exists():
            raise FileNotFoundError(f"model_vocabulary.json missing in {self.model_dir}")

        providers = ["CPUExecutionProvider"]
        try:
            if "CUDAExecutionProvider" in set(ort.get_available_providers()):
                providers.insert(0, "CUDAExecutionProvider")
        except Exception:
            pass
        # onnxruntime 自动加载同目录 model.onnx.data（外部权重）
        self.session = InferenceSession(str(onnx_path), providers=providers)
        logger.info("%s ONNX providers: %s", self.spec.key, self.session.get_providers())
        self.input_name = self.session.get_inputs()[0].name

        with vocab_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        idx_to_tag = {int(k): v for k, v in data["idx_to_tag"].items()}
        tag_to_category = data["tag_to_category"]

        self.names = [None] * (max(idx_to_tag) + 1)
        buckets = {
            "General": self.general_idx, "Character": self.character_idx,
            "Copyright": self.copyright_idx, "Meta": self.meta_idx,
        }
        self.general_idx.clear(); self.character_idx.clear()
        self.copyright_idx.clear(); self.meta_idx.clear()
        for idx, tag in idx_to_tag.items():
            while idx >= len(self.names):
                self.names.append(None)
            self.names[idx] = tag
            cat = tag_to_category.get(tag, "")
            if cat in buckets:
                buckets[cat].append(idx)

    def _prep(self, pil_image: Image.Image) -> np.ndarray:
        # SigLIP2：RGB→resize 384×384（BICUBIC，不 pad）→/255→mean=std=0.5 归一化→CHW（保持 RGB）
        im = pil_image.convert("RGB").resize((self.in_size, self.in_size), Image.BICUBIC)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)  # HWC→CHW
        mean = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(3, 1, 1)
        std = np.array([0.5, 0.5, 0.5], dtype=np.float32).reshape(3, 1, 1)
        arr = (arr - mean) / std
        return arr[None, ...].astype(np.float32)

    def tag_image(self, pil_image, gen_th: float = 0.55,
                  char_th: float = 0.55, use_char: bool = True) -> dict[str, float]:
        # v2 单阈值运营（文档推荐 0.55，probs >= thr）：General/Copyright/Character/Meta 统一用 gen_th。
        # char_th 参数仅为接口一致保留，v2 不区分角色阈值（区别于 v1 的 char_th 0.6）。
        self.ensure_loaded()
        x = self._prep(pil_image)
        outputs = self.session.run(None, {self.input_name: x})[0]
        probs = 1.0 / (1.0 + np.exp(-np.clip(outputs[0], -30, 30)))  # logits→stable sigmoid
        out: dict[str, float] = {}
        buckets = [self.general_idx, self.copyright_idx, self.meta_idx]
        if use_char:
            buckets.append(self.character_idx)
        for bucket in buckets:
            for i in bucket:
                if i < len(self.names) and self.names[i] is not None:
                    pr = float(probs[i])
                    if pr >= gen_th:
                        out[self.names[i].replace("_", " ")] = pr
        return out
