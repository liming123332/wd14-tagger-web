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


def test_workspace_save_and_path(tmp_path):
    from PIL import Image
    s = PromptboxStore(tmp_path)
    pil = Image.new("RGB", (40, 60))
    orig, thumb, w, h = s.save_workspace_image("ws-1", pil, "a.png")
    assert orig == "original.png"
    assert thumb == "thumb.webp"
    assert (w, h) == (40, 60)
    assert s.workspace_image_path("ws-1", orig).exists()
    assert s.workspace_image_path("ws-1", thumb).exists()
    # 缩略图是 webp
    assert s.workspace_image_path("ws-1", thumb).suffix == ".webp"


def test_workspace_traversal_guard(tmp_path):
    from PIL import Image
    s = PromptboxStore(tmp_path)
    with pytest.raises(ValueError):
        s.workspace_image_path("..", "x.png")
    with pytest.raises(ValueError):
        s.workspace_image_path("ok", "../evil.png")
    with pytest.raises(ValueError):
        s.save_workspace_image("..", Image.new("RGB", (2, 2)), "a.png")


def test_create_persists_tagger_fields(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t", raw_prompt="x", categories={}, extras=[],
                  image_data=[], model="wd3", gen_threshold=0.4,
                  char_threshold=0.6, raw_tags={"a": 0.9})
    again = s.get(it.id)
    assert again.model == "wd3"
    assert again.gen_threshold == 0.4
    assert again.char_threshold == 0.6
    assert again.raw_tags == {"a": 0.9}


def test_update_tagger_fields(tmp_path):
    s = PromptboxStore(tmp_path)
    it = s.create(title="t", raw_prompt="x", categories={}, extras=[], image_data=[])
    s.update(it.id, model="wd3", raw_tags={"b": 0.8}, gen_threshold=0.5)
    again = s.get(it.id)
    assert again.model == "wd3"
    assert again.raw_tags == {"b": 0.8}
    assert again.gen_threshold == 0.5
