import numpy as np
import pytest
from PIL import Image
from backend.tagger.cl_tagger import CLTagger
from backend.tagger.models_spec import MODEL_SPECS


def _make(tmp_path):
    t = CLTagger(MODEL_SPECS["cl_tagger"], tmp_path)
    return t


def test_cl_prep_shape_and_normalize(tmp_path):
    t = _make(tmp_path)
    # 非正方形 100x60 → pad 正方形 → BICUBIC 448；输出 NCHW
    img = Image.new("RGB", (100, 60), color=(128, 128, 128))
    arr = t._prep(img)
    assert arr.shape == (1, 3, 448, 448)
    # 灰色：(128/255 - 0.5)/0.5 ≈ 0.00392。
    # 取中心区域像素：100x60 经白底 pad 后居中，角点落在白底（=1.0），
    # 中心才反映灰色输入值。
    val = (128 / 255.0 - 0.5) / 0.5
    assert arr[0, 0, 224, 224] == pytest.approx(val, abs=1e-2)


def test_cl_prep_bgr_channel_swap(tmp_path):
    t = _make(tmp_path)
    # 纯红 (255,0,0)：/255→(1,0,0)；BGR 反转后通道0=B=0、通道2=R=1
    img = Image.new("RGB", (448, 448), color=(255, 0, 0))
    arr = t._prep(img)
    assert arr[0, 0, 0, 0] == pytest.approx((0 - 0.5) / 0.5)
    assert arr[0, 2, 0, 0] == pytest.approx((1 - 0.5) / 0.5)


def test_cl_tag_image_sigmoid_and_buckets(tmp_path):
    t = _make(tmp_path)
    t.names = ["long_hair", "char_a", "rating_safe", "qual_high", "meta_x", "vocaloid"]
    t.general_idx = [0]
    t.character_idx = [1]
    t.rating_idx = [2]
    t.quality_idx = [3]
    t.meta_idx = [4]
    t.copyright_idx = [5]

    class FakeSession:
        def run(self, *_a, **_k):
            # logits → stable_sigmoid
            # sigmoid(2)≈0.88, sigmoid(0.5)≈0.62, sigmoid(9)≈1.0, sigmoid(8)≈0.9995,
            # sigmoid(-2)≈0.12, sigmoid(3)≈0.95
            return [np.array([[2.0, 0.5, 9.0, 8.0, -2.0, 3.0]], dtype=np.float32)]

    t.session = FakeSession()
    t.input_name = "x"
    img = Image.new("RGB", (64, 64))
    out = t.tag_image(img, gen_th=0.35, char_th=0.9, use_char=True)
    # general long_hair 0.88 > 0.35 ✓（下划线替换空格）
    assert "long hair" in out
    assert out["long hair"] == pytest.approx(1 / (1 + np.exp(-2.0)), abs=1e-5)
    # copyright vocaloid 0.95 > 0.35 ✓
    assert "vocaloid" in out
    # character char_a 0.62 < char_th 0.9 ✗
    assert "char a" not in out
    # rating/quality 即便高也丢弃（rating/model 默认不要；quality 交给 Classifier 模板）
    assert "rating safe" not in out
    assert "qual high" not in out
    # meta meta_x 0.12 < 0.35 ✗
    assert "meta x" not in out


def test_cl_tag_image_no_char(tmp_path):
    t = _make(tmp_path)
    t.names = ["a", "char_b"]
    t.general_idx = [0]
    t.character_idx = [1]

    class FakeSession:
        def run(self, *_a, **_k):
            return [np.array([[1.0, 5.0]], dtype=np.float32)]  # char 0.99 但 use_char=False

    t.session = FakeSession()
    t.input_name = "x"
    out = t.tag_image(Image.new("RGB", (32, 32)), gen_th=0.35, char_th=0.9, use_char=False)
    assert out == {"a": pytest.approx(1 / (1 + np.exp(-1.0)), abs=1e-5)}
