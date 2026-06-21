"""ImageIndex 纯内存倒排索引单元测试（不碰文件系统）。"""
from backend.storage.index import ImageIndex


def test_add_and_query_exact_cat():
    idx = ImageIndex.empty()
    idx.add("20260619-100000-0001", {"long hair", "blue eyes"}, {"fav"})
    idx.add("20260619-100000-0002", {"long hair"}, set())
    # 精确命中 cat_inv
    assert idx.cat_inv["long hair"] == {"20260619-100000-0001", "20260619-100000-0002"}
    assert idx.cat_inv["blue eyes"] == {"20260619-100000-0001"}
    # 正向表
    assert idx.cat_fwd["20260619-100000-0001"] == {"long hair", "blue eyes"}


def test_user_inv_independent_from_cat():
    idx = ImageIndex.empty()
    idx.add("m1", {"long hair"}, {"fav", "test"})
    # user 索引独立于 cat 索引：同名字签不串
    assert idx.user_inv["fav"] == {"m1"}
    assert idx.cat_inv.get("fav") is None
    assert idx.cat_inv["long hair"] == {"m1"}
    assert idx.user_inv.get("long hair") is None


def test_add_is_idempotent():
    idx = ImageIndex.empty()
    idx.add("m1", {"a"}, {"x"})
    idx.add("m1", {"a"}, {"x"})  # 重复 add 不应翻倍
    assert idx.all_ids.count("m1") == 1
    assert idx.cat_inv["a"] == {"m1"}
    assert idx.user_inv["x"] == {"m1"}


def test_add_replaces_tags_on_re_add():
    # 再次 add 同 mid 带不同 tags：旧 tag 应从倒排清除
    idx = ImageIndex.empty()
    idx.add("m1", {"a", "b"}, {"x"})
    idx.add("m1", {"b", "c"}, {"y"})
    assert idx.cat_inv.get("a") is None or idx.cat_inv["a"] == set()
    assert idx.cat_inv["b"] == {"m1"}
    assert idx.cat_inv["c"] == {"m1"}
    assert idx.cat_fwd["m1"] == {"b", "c"}
    assert idx.user_fwd["m1"] == {"y"}


def test_remove_clears_inverted_and_forward():
    idx = ImageIndex.empty()
    idx.add("m1", {"a"}, {"x"})
    idx.add("m2", {"a"}, {"x"})
    idx.remove("m1")
    assert "m1" not in idx.id_set
    assert idx.all_ids.count("m1") == 0
    # m1 从倒排清除，m2 仍在
    assert idx.cat_inv["a"] == {"m2"}
    assert idx.user_inv["x"] == {"m2"}
    assert "m1" not in idx.cat_fwd
    assert "m1" not in idx.user_fwd


def test_remove_unknown_is_noop():
    idx = ImageIndex.empty()
    idx.remove("nope")  # 不存在不报错
    assert idx.all_ids == []


def test_update_diff():
    idx = ImageIndex.empty()
    idx.add("m1", {"a", "b"}, {"x"})
    idx.update("m1", {"b", "c"}, {"x", "y"})
    assert idx.cat_fwd["m1"] == {"b", "c"}
    assert idx.user_fwd["m1"] == {"x", "y"}
    assert idx.cat_inv.get("a") in (None, set())
    assert idx.cat_inv["c"] == {"m1"}
    assert idx.user_inv["y"] == {"m1"}


def test_all_ids_ascending():
    idx = ImageIndex.empty()
    for mid in ["20260620-100000-0003", "20260618-100000-0001", "20260619-100000-0002"]:
        idx.add(mid, set(), set())
    # 升序（bisect/date_slice 依赖）
    assert idx.all_ids == ["20260618-100000-0001", "20260619-100000-0002", "20260620-100000-0003"]
    assert idx.id_set == {"20260618-100000-0001", "20260619-100000-0002", "20260620-100000-0003"}


def test_date_slice_prefix_bisect():
    idx = ImageIndex.empty()
    for mid in [
        "20260618-120000-aaaa",
        "20260619-100000-bbbb",
        "20260619-235959-cccc",
        "20260620-000000-dddd",
    ]:
        idx.add(mid, set(), set())
    # date=20260619：该日全部，升序
    got = idx.date_slice("20260619")
    assert got == ["20260619-100000-bbbb", "20260619-235959-cccc"]
    # 无匹配前缀返回空
    assert idx.date_slice("19990101") == []


def test_user_tag_counts():
    idx = ImageIndex.empty()
    idx.add("m1", set(), {"fav", "test"})
    idx.add("m2", set(), {"fav"})
    idx.add("m3", set(), {"fav", "test"})
    assert idx.user_tag_counts() == {"fav": 3, "test": 2}


def test_cat_vocab_for_substring_fallback():
    # 子串兜底需遍历 cat_inv.keys()
    idx = ImageIndex.empty()
    idx.add("m1", {"long hair", "blue eyes"}, set())
    idx.add("m2", {"short hair"}, set())
    vocab = set(idx.cat_inv.keys())
    assert vocab == {"long hair", "blue eyes", "short hair"}
