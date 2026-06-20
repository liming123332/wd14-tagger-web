from pathlib import Path
from PIL import Image as PILImage

from backend.tasks.pathtag import expand_images, process_one


# ---- Task 1: expand_images ----

def test_expand_images_non_recursive_only_top_level(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.png").write_bytes(b"x")
    result = expand_images(str(tmp_path), recursive=False)
    assert [p.name for p in result] == ["a.png", "b.jpg"]


def test_expand_images_recursive_includes_subdirs(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.png").write_bytes(b"x")
    names = [p.name for p in expand_images(str(tmp_path), recursive=True)]
    assert "a.png" in names and "c.png" in names


def test_expand_images_filters_non_image(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "data.json").write_text("{}")
    assert [p.name for p in expand_images(str(tmp_path))] == ["a.png"]


def test_expand_images_empty_dir(tmp_path):
    assert expand_images(str(tmp_path)) == []


# ---- Task 2: process_one ----

def _make_img(path: Path) -> None:
    """造一张真能被 PIL 打开的 8x8 图（process_one 内部会 Image.open）。"""
    PILImage.new("RGB", (8, 8), (255, 0, 0)).save(path)


class FakeTagger:
    """不调真 ONNX，直接回预设标签 dict（模拟 tag_image 返回）。"""
    def __init__(self, mapping: dict[str, float]):
        self.mapping = mapping

    def tag_image(self, pil, gen_th=0.55, char_th=0.55, use_char=True):
        return dict(self.mapping)


def test_process_one_writes_sorted_txt(tmp_path):
    img = tmp_path / "a.png"
    _make_img(img)
    tagger = FakeTagger({"1girl": 0.9, "solo": 0.5, "long_hair": 0.7})
    status, evt = process_one(img, tagger, 0.55, 0.55, True, "overwrite")
    assert status == "ok"
    assert evt == {"type": "progress", "current": "a.png", "status": "ok"}
    # 按分数降序：0.9 > 0.7 > 0.5
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "1girl, long_hair, solo"


def test_process_one_skip_existing(tmp_path):
    img = tmp_path / "a.png"
    _make_img(img)
    (tmp_path / "a.txt").write_text("handwritten", encoding="utf-8")
    status, _ = process_one(img, FakeTagger({"1girl": 0.9}), 0.55, 0.55, True, "skip")
    assert status == "skip"
    # 跳过：原内容保留
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "handwritten"


def test_process_one_overwrite_existing(tmp_path):
    img = tmp_path / "a.png"
    _make_img(img)
    (tmp_path / "a.txt").write_text("old", encoding="utf-8")
    status, _ = process_one(img, FakeTagger({"1girl": 0.9}), 0.55, 0.55, True, "overwrite")
    assert status == "ok"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "1girl"


def test_process_one_bad_image_returns_error(tmp_path):
    bad = tmp_path / "a.png"
    bad.write_bytes(b"not an image")
    status, evt = process_one(bad, FakeTagger({}), 0.55, 0.55, True, "overwrite")
    assert status == "error"
    assert evt["type"] == "error" and evt["current"] == "a.png"
