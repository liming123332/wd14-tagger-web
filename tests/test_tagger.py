import numpy as np
import pytest
from PIL import Image
from backend.tagger.core import WD14Tagger


def _make_tagger_no_load(tmp_path):
    # 跳过 ensure_loaded（不下载模型），仅测预处理
    t = WD14Tagger(tmp_path)
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
            # probs for [long_hair, blue_eyes, dress, rating]
            return [np.array([[0.9, 0.4, 0.1, 0.5]], dtype=np.float32)]

    t.session = FakeSession()
    t.input_name = "x"
    img = Image.new("RGB", (64, 64))
    out = t.tag_image(img, gen_th=0.35, char_th=0.9, use_char=False)
    # 下划线被替换为空格；float32 经 astype(float) 后存在精度差异，使用 approx
    assert set(out.keys()) == {"long hair", "blue eyes"}
    assert out["long hair"] == pytest.approx(0.9, abs=1e-6)
    assert out["blue eyes"] == pytest.approx(0.4, abs=1e-6)


def test_threshold_is_strict(tmp_path):
    # pr == gen_th 时不计入（严格大于），防未来被误改为 >=
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
