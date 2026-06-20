from pathlib import Path
from backend.tasks.pathtag import expand_images


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
