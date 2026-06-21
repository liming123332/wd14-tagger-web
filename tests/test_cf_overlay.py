import time

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


def test_set_image_rejects_traversal_filename(tmp_path):
    # set_image 必须复用 image_path 的穿越校验，不应忽略 filename。
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    with pytest.raises(ValueError):
        s.set_image("char:danbooru:1", "../evil.png")


def test_delete(tmp_path):
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.upsert(CfOverlay(entry_key="char:danbooru:1", kind="char", extras=CategoryData()))
    s.delete("char:danbooru:1")
    assert s.get("char:danbooru:1") is None


def test_delete_is_idempotent_for_bad_key(tmp_path):
    # 异常 entry_key（含路径分隔）不应让 delete 整体抛错；DB 删除已成功。
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    s.upsert(CfOverlay(entry_key="char:danbooru:1", kind="char", extras=CategoryData()))
    # 不抛异常即通过；之前 _dir_for 会抛 ValueError。
    s.delete("../evil")
    assert s.get("char:danbooru:1") is not None  # 该 key 不受影响


def test_upsert_preserves_created_at_on_repeat(tmp_path):
    # 回归保护：同一 entry_key 二次 upsert，created_at 保留不变，updated_at 被刷新。
    s = CfOverlayStore(tmp_path / "ov.db", tmp_path / "ov")
    ov1 = CfOverlay(entry_key="char:danbooru:1", kind="char", extras=CategoryData())
    saved1 = s.upsert(ov1)
    assert saved1.created_at
    assert saved1.updated_at
    # 确保时间戳秒级不同（isoformat timespec="seconds"）。
    time.sleep(1.1)
    ov2 = CfOverlay(entry_key="char:danbooru:1", kind="char",
                    custom_tags=["new"], extras=CategoryData())
    saved2 = s.upsert(ov2)
    assert saved2.created_at == saved1.created_at  # 保留
    assert saved2.updated_at != saved1.updated_at  # 刷新
    assert saved2.custom_tags == ["new"]

