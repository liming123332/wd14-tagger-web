from __future__ import annotations
from pathlib import Path
import csv
import shutil
import urllib.request

from backend.config import settings

import logging

logger = logging.getLogger(__name__)


class WD14Tagger:
    """WD14 ONNX 反推。移植自参考项目 taggers_core.py，接收 PIL Image。"""

    def __init__(self, models_root: Path = settings.MODELS_DIR):
        self.model_dir = Path(models_root) / "wd14"
        self.session = None
        self.input_name = None
        self.in_h = 448
        self.in_w = 448
        self.tag_names: list[str] = []
        self.rating_idx: list[int] = []
        self.general_idx: list[int] = []
        self.char_idx: list[int] = []

    def ensure_loaded(self) -> None:
        if self.session is not None:
            return
        if not self.model_dir.exists():
            self._download()
        self._load()

    def _download(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        for url, name in [(settings.WD14_MODEL_URL, "model.onnx"),
                          (settings.WD14_CSV_URL, "selected_tags.csv")]:
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
        import onnxruntime as ort
        from onnxruntime import InferenceSession

        onnx_path = self.model_dir / "model.onnx"
        csv_path = self.model_dir / "selected_tags.csv"
        if not onnx_path.exists() or not csv_path.exists():
            raise FileNotFoundError(f"WD14 model files missing in {self.model_dir}")

        providers = ["CPUExecutionProvider"]
        try:
            if "CUDAExecutionProvider" in set(ort.get_available_providers()):
                providers.insert(0, "CUDAExecutionProvider")
        except Exception:
            pass

        self.session = InferenceSession(str(onnx_path), providers=providers)
        logger.info("WD14 ONNX providers: %s", self.session.get_providers())
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        if len(shape) == 4:
            _, h, w, _ = shape
            if isinstance(h, int) and isinstance(w, int):
                self.in_h, self.in_w = h, w

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
        arr = arr[:, :, ::-1]  # RGB -> BGR
        return arr[None, ...]

    def tag_image(self, pil_image, gen_th: float = 0.35,
                  char_th: float = 0.90, use_char: bool = True) -> dict[str, float]:
        self.ensure_loaded()
        x = self._prep(pil_image)
        probs = self.session.run(None, {self.input_name: x})[0][0].astype(float)
        out: dict[str, float] = {}
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
