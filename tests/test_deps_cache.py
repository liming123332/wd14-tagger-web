import pytest
from backend import deps
from backend.tagger.core import OnnxTagger


def test_get_tagger_returns_onnx_tagger():
    deps._reset_tagger_cache()
    t = deps.get_tagger("wd14")
    assert isinstance(t, OnnxTagger)


def test_get_tagger_caches_per_key():
    deps._reset_tagger_cache()
    a = deps.get_tagger("wd14")
    b = deps.get_tagger("wd14")
    assert a is b  # 同 key 同实例


def test_get_tagger_different_keys_different_instances():
    deps._reset_tagger_cache()
    a = deps.get_tagger("wd14")
    b = deps.get_tagger("e621")
    assert a is not b
    assert a.spec.key == "wd14"
    assert b.spec.key == "e621"


def test_get_tagger_unknown_key_raises():
    deps._reset_tagger_cache()
    with pytest.raises(ValueError):
        deps.get_tagger("nope")


def test_reset_clears_cache():
    deps._reset_tagger_cache()
    a = deps.get_tagger("wd14")
    deps._reset_tagger_cache()
    b = deps.get_tagger("wd14")
    assert a is not b  # 重置后是新实例


def test_get_tagger_cl_returns_cl_tagger():
    deps._reset_tagger_cache()
    from backend.tagger.cl_tagger import CLTagger
    t = deps.get_tagger("cl_tagger")
    assert isinstance(t, CLTagger)


def test_get_tagger_wd_still_onnx_tagger():
    # 加 cl 分支后，wd 系仍返回 OnnxTagger（回归保护）
    deps._reset_tagger_cache()
    from backend.tagger.core import OnnxTagger
    assert isinstance(deps.get_tagger("wd14"), OnnxTagger)
    assert isinstance(deps.get_tagger("e621"), OnnxTagger)


def test_cf_factories_cached():
    from backend import deps
    deps.get_character_db.cache_clear()
    deps.get_artist_db.cache_clear()
    deps.get_anima_character_db.cache_clear()
    deps.get_anima_artist_db.cache_clear()
    deps.get_cf_overlay.cache_clear()
    a = deps.get_character_db(); b = deps.get_character_db()
    assert a is b
    assert deps.get_cf_overlay() is deps.get_cf_overlay()
