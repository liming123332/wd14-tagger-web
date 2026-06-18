import pytest
from PIL import Image
from backend.storage.store import Storage


def _img(path):
    Image.new("RGB", (50, 70), (1, 2, 3)).save(path)


def test_save_upload_creates_files_and_meta(tmp_path):
    s = Storage(tmp_path)
    src = tmp_path / "in.png"
    _img(src)
    img = Image.open(src)
    mid = s.save_upload(img, "in.png")
    d = s.image_dir(mid)
    assert (d / "original.png").exists()
    assert (d / "thumb.webp").exists()
    meta = s.get_meta(mid)
    assert meta.source_name == "in.png"
    assert meta.image.width == 50
    assert meta.image.height == 70
    assert meta.id == mid


def test_new_id_format(tmp_path):
    s = Storage(tmp_path)
    i = s.new_id()
    parts = i.split("-")
    assert len(parts) == 3 and len(parts[2]) == 4


def test_list_images_pagination(tmp_path):
    s = Storage(tmp_path)
    for n in range(3):
        src = tmp_path / f"{n}.png"
        _img(src)
        s.save_upload(Image.open(src), f"{n}.png")
    res = s.list_images(page=1, size=2)
    assert res["total"] == 3
    assert len(res["items"]) == 2
    # id 为零填充时间戳，降序即"最新优先"
    assert res["items"][0]["id"] > res["items"][1]["id"]
    res2 = s.list_images(page=2, size=2)
    assert len(res2["items"]) == 1


def test_delete_removes_dir(tmp_path):
    s = Storage(tmp_path)
    src = tmp_path / "x.png"
    _img(src)
    mid = s.save_upload(Image.open(src), "x.png")
    s.delete(mid)
    assert not s.image_dir(mid).exists()


def test_save_and_reload_meta(tmp_path):
    from backend.models import CategoryData
    s = Storage(tmp_path)
    src = tmp_path / "x.png"
    _img(src)
    mid = s.save_upload(Image.open(src), "x.png")
    meta = s.get_meta(mid)
    meta.categories["head"] = CategoryData(tags=["long hair"], phrase="long hair")
    s.save_meta(mid, meta)
    again = s.get_meta(mid)
    assert again.categories["head"].tags == ["long hair"]


def test_file_path_rejects_traversal(tmp_path):
    s = Storage(tmp_path)
    mid = "20260101-000000-abcd"
    # 含路径分隔符应被拒绝
    with pytest.raises(ValueError):
        s.file_path(mid, "../evil.png")
    with pytest.raises(ValueError):
        s.file_path(mid, "sub\\x.png")
    # 合法文件名返回镜像目录内的路径
    p = s.file_path(mid, "thumb.webp")
    assert p.name == "thumb.webp"
