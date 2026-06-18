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
