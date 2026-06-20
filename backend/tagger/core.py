from __future__ import annotations
from pathlib import Path
import csv
import shutil
import urllib.request

from backend.config import settings
from backend.tagger.models_spec import ModelSpec
from backend.tagger._onnx_providers import select_providers

import logging

logger = logging.getLogger(__name__)


class OnnxTagger:
    """通用 ONNX 反推。一个类覆盖 7 个模型：6 个 wd 系（BGR/不归一/csv 分桶）
    与 DDB（RGB/归一/txt 无分桶）。差异由 ModelSpec.prep / tag_source 决定。
    移植自参考项目 taggers_core.py，接收 PIL Image。"""

    def __init__(self, spec: ModelSpec, models_root: Path = settings.MODELS_DIR):
        self.spec = spec
        self.model_dir = Path(models_root) / spec.folder
        self.session = None
        self.input_name = None
        self.in_h = 448
        self.in_w = 448
        # wd 系（csv）用 tag_names + general/char/rating 分桶
        self.tag_names: list[str] = []
        self.rating_idx: list[int] = []
        self.general_idx: list[int] = []
        self.char_idx: list[int] = []
        # DDB（txt）用扁平 tags，无分桶
        self.tags: list[str] = []

    def ensure_loaded(self) -> None:
        if self.session is not None:
            return
        # 总是走 _download：它逐文件 skip 已有，可补全此前中断的下载
        # （比"目录不存在才下载"更健壮）。
        self._download()
        self._load()

    def _download(self) -> None:
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
                    raise IOError(
                        f"{name} 下载不完整：期望 {expected} 字节，实际 {tmp.stat().st_size}"
                    )
                tmp.replace(dst)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise

    def _load(self) -> None:
        from onnxruntime import InferenceSession

        onnx_path = self.model_dir / "model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"model.onnx missing in {self.model_dir}")

        self.session = InferenceSession(str(onnx_path), providers=select_providers())
        logger.info("%s ONNX providers: %s", self.spec.key, self.session.get_providers())
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        if len(shape) == 4:
            _, h, w, _ = shape
            if isinstance(h, int) and isinstance(w, int):
                self.in_h, self.in_w = h, w

        if self.spec.tag_source == "txt":
            tags_path = self.model_dir / "tags.txt"
            if not tags_path.exists():
                raise FileNotFoundError(f"tags.txt missing in {self.model_dir}")
            self.tags = [
                line.strip()
                for line in tags_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip()
            ]
        else:  # csv
            csv_path = self.model_dir / "selected_tags.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"selected_tags.csv missing in {self.model_dir}")
            self.tag_names.clear()
            self.general_idx.clear()
            self.char_idx.clear()
            self.rating_idx.clear()
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                rdr = csv.DictReader(f, delimiter=",", quotechar='"')
                for i, row in enumerate(rdr):
                    name = (row.get("name", "") or "").strip()
                    if not name:
                        continue
                    self.tag_names.append(name)
                    cat = row.get("category", "")
                    if cat == "0":
                        self.general_idx.append(i)
                    elif cat == "4":
                        self.char_idx.append(i)
                    elif cat == "9":
                        self.rating_idx.append(i)

    def _prep(self, pil_image):
        import numpy as np
        im = pil_image.convert("RGB").resize((self.in_w, self.in_h))
        arr = np.asarray(im, dtype=np.float32)
        if self.spec.prep == "ddb":
            arr = arr / 255.0        # DDB: RGB 保持，归一化
        else:
            arr = arr[:, :, ::-1]     # wd 系: RGB -> BGR，不归一化
        return arr[None, ...]

    def tag_image(self, pil_image, gen_th: float = 0.35,
                  char_th: float = 0.90, use_char: bool = True) -> dict[str, float]:
        self.ensure_loaded()
        x = self._prep(pil_image)
        probs = self.session.run(None, {self.input_name: x})[0][0].astype(float)
        out: dict[str, float] = {}

        if self.spec.tag_source == "txt":
            # DDB: 单阈值（>=），扁平 tags 无分桶
            for i, pr in enumerate(probs):
                pr = float(pr)
                if pr >= gen_th:
                    tag = (self.tags[i] if i < len(self.tags) else f"tag_{i}").replace("_", " ")
                    out[tag] = pr
            return out

        # wd 系: general + char 双阈值（严格 >）
        for i in self.general_idx:
            pr = float(probs[i])
            if pr > gen_th:
                out[self.tag_names[i].replace("_", " ")] = pr
        if use_char:
            for i in self.char_idx:
                pr = float(probs[i])
                if pr > char_th:
                    out[self.tag_names[i].replace("_", " ")] = pr
        return out
