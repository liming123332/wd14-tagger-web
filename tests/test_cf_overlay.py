import pytest
from backend.models import CategoryData, CfOverlay
from backend.storage.cf_overlay import CfOverlayStore


def test_upsert_and_get(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    ov = CfOverlay(entry_key="char:danbooru:1", kind="char",
                   categories={"head": CategoryData(tags=["long hair"])},
                   extras=CategoryData(), model="wd14")
    saved = s.upsert(ov)
    assert saved.created_at and saved.updated_at
    again = s.get("char:danbooru:1")
    assert again is not None
    assert again.categories["head"].tags == ["long hair"]


def test_get_missing_returns_none(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    assert s.get("char:danbooru:9") is None


def test_set_image_and_path_guard(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.set_image("char:danbooru:1", "orig.png")
    p = s.image_path("char:danbooru:1", "orig.png")
    assert p.parent.exists()
    with pytest.raises(ValueError):
        s.image_path("char:danbooru:1", "../evil.png")


def test_delete(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.upsert(CfOverlay(entry_key="char:danbooru:1", kind="char", extras=CategoryData()))
    s.delete("char:danbooru:1")
    assert s.get("char:danbooru:1") is None
