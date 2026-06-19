import numpy as np
import pytest
from PIL import Image
from backend.tagger.core import OnnxTagger
from backend.tagger.models_spec import MODEL_SPECS


def _make_tagger_no_load(tmp_path):
    # 跳过 ensure_loaded（不下载模型），仅测预处理
    t = OnnxTagger(MODEL_SPECS["wd14"], tmp_path)
    t.in_h = 448
    t.in_w = 448
    return t


def test_prep_shape_and_bgr(tmp_path):
    t = _make_tagger_no_load(tmp_path)
    img = Image.new("RGB", (1000, 800), color=(10, 20, 30))
    arr = t._prep(img)
    assert arr.shape == (1, 448, 448, 3)
    assert arr.dtype == np.float32
    # RGB(10,20,30) -> BGR 后通道0应为30
    assert arr[0, 0, 0, 0] == 30.0


def test_tag_image_with_mock_session(tmp_path):
    t = _make_tagger_no_load(tmp_path)
    t.tag_names = ["long_hair", "blue_eyes", "dress", "rating_safe"]
    t.general_idx = [0, 1, 2]
    t.char_idx = []
    t.rating_idx = [3]

    class FakeSession:
        def run(self, *_args, **_kw):
            return [np.array([[0.9, 0.4, 0.1, 0.5]], dtype=np.float32)]

    t.session = FakeSession()
    t.input_name = "x"
    img = Image.new("RGB", (64, 64))
    out = t.tag_image(img, gen_th=0.35, char_th=0.9, use_char=False)
    assert set(out.keys()) == {"long hair", "blue eyes"}
    assert out["long hair"] == pytest.approx(0.9, abs=1e-6)
    assert out["blue eyes"] == pytest.approx(0.4, abs=1e-6)


def test_threshold_is_strict(tmp_path):
    # pr == gen_th 时不计入（wd 系严格大于）
    t = _make_tagger_no_load(tmp_path)
    t.tag_names = ["border", "above"]
    t.general_idx = [0, 1]
    t.char_idx = []
    t.rating_idx = []

    class FakeSession:
        def run(self, *_args, **_kw):
            return [np.array([[0.35, 0.36]], dtype=np.float32)]

    t.session = FakeSession()
    t.input_name = "x"
    img = Image.new("RGB", (32, 32))
    out = t.tag_image(img, gen_th=0.35, char_th=0.9, use_char=False)
    assert "border" not in out
    assert out == {"above": pytest.approx(0.36, abs=1e-6)}


def test_ddb_prep_is_rgb_normalized(tmp_path):
    # DDB: 不转 BGR，且 /255 归一化
    t = OnnxTagger(MODEL_SPECS["ddb"], tmp_path)
    t.in_h = 8
    t.in_w = 8
    img = Image.new("RGB", (8, 8), color=(255, 0, 0))
    arr = t._prep(img)
    # 通道0=R=255 -> 1.0；通道1=G=0 -> 0.0（未转 BGR）
    assert arr[0, 0, 0, 0] == pytest.approx(1.0)
    assert arr[0, 0, 0, 1] == pytest.approx(0.0)


def test_ddb_tag_image_single_threshold(tmp_path):
    # DDB 单阈值（>=），无分桶，读 self.tags
    t = OnnxTagger(MODEL_SPECS["ddb"], tmp_path)
    t.in_h = 8
    t.in_w = 8
    t.tags = ["red_background", "blue_sky"]

    class FakeSession:
        def run(self, *_args, **_kw):
            return [np.array([[0.6, 0.4]], dtype=np.float32)]

    t.session = FakeSession()
    t.input_name = "x"
    img = Image.new("RGB", (8, 8))
    out = t.tag_image(img, gen_th=0.4, char_th=0.9, use_char=True)
    # >= 0.4：两个都进；下划线替换空格
    assert out == {"red background": pytest.approx(0.6, abs=1e-6),
                   "blue sky": pytest.approx(0.4, abs=1e-6)}
