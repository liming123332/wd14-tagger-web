import pytest
from backend.storage.promptbox_store import PromptboxStore


def test_create_and_list(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t1", raw_prompt="long hair, dress",
                  categories={"head": ["long hair"], "clothing": ["dress"]},
                  extras=[], image_data=[])
    assert it.id
    assert it.title == "t1"
    assert s.get(it.id).raw_prompt == "long hair, dress"
    assert len(s.list_all()) == 1


def test_create_with_images(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t", raw_prompt="x", categories={}, extras=[],
                  image_data=[("a.png", b"PNGDATA1"), ("b.jpg", b"PNGDATA2")])
    assert len(it.image_names) == 2
    # 图片落盘到 images/<id>/
    for name in it.image_names:
        assert s.image_path(it.id, name).exists()
        assert s.image_path(it.id, name).read_bytes() in (b"PNGDATA1", b"PNGDATA2")


def test_update_fields_and_images(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t", raw_prompt="x", categories={"head": ["a"]}, extras=[],
                  image_data=[("a.png", b"D1")])
    updated = s.update(it.id, title="t2", categories={"head": ["a", "b"]},
                      new_image_data=[("c.png", b"D2")], remove_image_names=[it.image_names[0]])
    assert updated.title == "t2"
    assert updated.categories == {"head": ["a", "b"]}
    assert len(updated.image_names) == 1  # 删 1 加 1
    # 旧图已删
    assert not tmp_path.joinpath("images", it.id).joinpath(it.image_names[0]).exists()


def test_update_unknown_raises(tmp_path):
    s = PromptboxStore(tmp_path)
    with pytest.raises(KeyError):
        s.update("nope", title="x")


def test_delete_removes_item_and_images(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t", raw_prompt="x", categories={}, extras=[],
                  image_data=[("a.png", b"D")])
    s.delete(it.id)
    assert s.get(it.id) is None
    assert not tmp_path.joinpath("images", it.id).exists()


def test_atomic_write(tmp_path):
    s = PromptboxStore(tmp_path)
    s.create(title="t", raw_prompt="x", categories={}, extras=[], image_data=[])
    # 写后不应残留 .tmp
    assert not tmp_path.joinpath("items.json.tmp").exists()
    assert tmp_path.joinpath("items.json").exists()


def test_traversal_guard(tmp_path):
    s = PromptboxStore(tmp_path)
    with pytest.raises(ValueError):
        s.image_path("..", "x.png")
    with pytest.raises(ValueError):
        s.image_path("ok", "../evil.png")
