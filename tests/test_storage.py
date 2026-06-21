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


def test_image_dir_rejects_traversal(tmp_path):
    s = Storage(tmp_path)
    for bad in ["..", ".", "", "a/b", "a\\b"]:
        with pytest.raises(ValueError):
            s.image_dir(bad)
    # 合法 id 正常返回
    assert s.image_dir("20260101-000000-abcd").name == "20260101-000000-abcd"


def _write_meta_directly(root, mid, *, tags=None, user_tags=None):
    """手建图片目录 + meta.json（list_images 只读 meta.json，不依赖图文件）；
    用可控 id 前缀，便于按日期/标签筛选测试。
    tags=反推 prompt 标签（写入 categories.head）；user_tags=用户自定义筛选用标签（meta.tags）。"""
    from pathlib import Path
    from backend.models import Meta, ImageInfo, TaggerInfo, CategoryData
    d = Path(root) / mid
    d.mkdir(parents=True, exist_ok=True)
    cats = {"head": CategoryData(tags=tags or [], phrase=", ".join(tags or []))} if tags else {}
    m = Meta(
        id=mid,
        source_name=f"{mid}.png",
        created_at="2026-06-19T12:00:00+08:00",
        model="wd14",
        image=ImageInfo(original="original.png", thumb="thumb.webp", width=100, height=100),
        tagger=TaggerInfo(),
        categories=cats,
        tags=list(user_tags or []),
    )
    (d / "meta.json").write_text(m.model_dump_json(indent=2), encoding="utf-8")
    return mid


def test_list_images_filters_by_date(tmp_path):
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260618-120000-aaaa")
    _write_meta_directly(tmp_path, "20260619-120000-bbbb", tags=["long hair"])
    _write_meta_directly(tmp_path, "20260619-130000-cccc")
    res = s.list_images(date="20260619")
    ids = [it["id"] for it in res["items"]]
    assert ids == ["20260619-130000-cccc", "20260619-120000-bbbb"]  # 仅当天，倒序
    assert res["total"] == 2


def test_list_images_random_returns_subset(tmp_path):
    s = Storage(tmp_path)
    for i in range(10):
        _write_meta_directly(tmp_path, f"20260619-1200{i:02d}-{i:04x}")
    res = s.list_images(size=5, random=True)
    ids = [it["id"] for it in res["items"]]
    assert len(ids) == 5
    assert len(set(ids)) == 5  # 无重复
    assert res["total"] == 10  # 全库总数不受 random 影响


def test_list_images_includes_prompt_and_original(tmp_path):
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260619-120000-dddd", tags=["long hair", "blue eyes"])
    res = s.list_images()
    it = res["items"][0]
    assert it["original"] == "original.png"
    assert it["prompt"] == "long hair, blue eyes"


def test_list_images_filters_by_tags_intersection(tmp_path):
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260619-100000-0001", user_tags=["a", "b"])
    _write_meta_directly(tmp_path, "20260619-100000-0002", user_tags=["a"])
    _write_meta_directly(tmp_path, "20260619-100000-0003", user_tags=["b", "c"])
    _write_meta_directly(tmp_path, "20260619-100000-0004", user_tags=[])
    # 单标签 a：含 a 的 0001、0002（顺序按 id 倒序）
    r = s.list_images(tags=["a"])
    assert [it["id"] for it in r["items"]] == ["20260619-100000-0002", "20260619-100000-0001"]
    assert r["total"] == 2
    # 多标签交集 a,b：仅 0001
    r2 = s.list_images(tags=["a", "b"])
    assert [it["id"] for it in r2["items"]] == ["20260619-100000-0001"]
    assert r2["total"] == 1


def test_all_tags_counts_dedup(tmp_path):
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260619-100000-0001", user_tags=["fav", "test"])
    _write_meta_directly(tmp_path, "20260619-100000-0002", user_tags=["fav"])
    _write_meta_directly(tmp_path, "20260619-100000-0003", user_tags=["fav", "test"])
    counts = s.all_tags()
    assert counts == {"fav": 3, "test": 2}


def test_save_upload_persists_tags(tmp_path):
    s = Storage(tmp_path)
    src = tmp_path / "in.png"
    _img(src)
    mid = s.save_upload(Image.open(src), "in.png", tags=["x", "y"])
    meta = s.get_meta(mid)
    assert meta.tags == ["x", "y"]
    # list_images item 携带 tags
    item = s.list_images()["items"][0]
    assert item["tags"] == ["x", "y"]


def test_list_images_filters_by_prompt(tmp_path):
    # build_prompt 取 categories 的 tags；_write_meta_directly 的 tags 写入 categories["head"]
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260619-100000-0001", tags=["long hair", "blue eyes"])
    _write_meta_directly(tmp_path, "20260619-100000-0002", tags=["long hair"])
    _write_meta_directly(tmp_path, "20260619-100000-0003", tags=["short hair"])
    # 单词：含 "long hair" 的 0001、0002
    r = s.list_images(prompt=["long hair"])
    assert sorted(i["id"] for i in r["items"]) == ["20260619-100000-0001", "20260619-100000-0002"]
    assert r["total"] == 2
    # 交集 "long hair" + "blue eyes"：仅 0001
    r2 = s.list_images(prompt=["long hair", "blue eyes"])
    assert [i["id"] for i in r2["items"]] == ["20260619-100000-0001"]
    assert r2["total"] == 1
    # 子串匹配：所有含 "hair" 的
    r3 = s.list_images(prompt=["hair"])
    assert r3["total"] == 3


def test_list_images_prompt_combines_with_tags(tmp_path):
    # date + tags + prompt 三者 AND
    s = Storage(tmp_path)
    _write_meta_directly(tmp_path, "20260619-100000-0001", tags=["long hair"], user_tags=["fav"])
    _write_meta_directly(tmp_path, "20260619-100000-0002", tags=["long hair"])  # 无 user tag
    # prompt=long hair 且 tags=fav：仅 0001
    r = s.list_images(prompt=["long hair"], tags=["fav"])
    assert [i["id"] for i in r["items"]] == ["20260619-100000-0001"]


def test_list_images_no_filter_skips_full_scan(tmp_path, monkeypatch):
    # 无过滤翻页：过滤阶段不读 meta，只 items 构造读 size 张（旧实现会读全部 N 张）
    s = Storage(tmp_path)
    for i in range(20):
        _write_meta_directly(tmp_path, f"20260619-1000{i:02d}-{i:04x}")
    calls = {"n": 0}
    orig = s.get_meta

    def counting(mid):
        calls["n"] += 1
        return orig(mid)

    monkeypatch.setattr(s, "get_meta", counting)
    res = s.list_images(page=1, size=5)
    assert res["total"] == 20
    assert len(res["items"]) == 5
    assert calls["n"] == 5  # 只读切片的 5 张，不扫全 20 张


def test_prompt_substring_skips_full_scan(tmp_path, monkeypatch):
    # 子串兜底走词表（cat_inv.keys()），不读图文件；只 items 构造读 size 张
    s = Storage(tmp_path)
    for i in range(20):
        _write_meta_directly(tmp_path, f"20260619-1000{i:02d}-{i:04x}", tags=[f"tag {i}"])
    calls = {"n": 0}
    orig = s.get_meta

    def counting(mid):
        calls["n"] += 1
        return orig(mid)

    monkeypatch.setattr(s, "get_meta", counting)
    res = s.list_images(prompt=["tag"], size=5)  # "tag" 子串命中全部 20 张
    assert res["total"] == 20
    assert calls["n"] == 5  # 过滤走词表不读盘，只读切片 5 张
