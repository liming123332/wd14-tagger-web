import pytest
from backend.classifier.engine import Classifier
from backend.models import CategoryData


@pytest.fixture
def clf(tmp_path, monkeypatch):
    # 用临时词表，避免依赖真实配置
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        """
priority: [head, clothing, view, action, scene]
categories:
  head:
    suffix: [hair, eyes]
    exact: [glasses]
  clothing:
    suffix: [dress, shirt]
  view:
    exact: [close-up]
  action:
    exact: [sitting, smile]
    suffix: [pose]
  scene:
    exact: [indoors]
quality_template:
  tags: [masterpiece, best quality]
""".strip(),
        encoding="utf-8",
    )
    quality = tmp_path / "quality.yaml"
    quality.write_text("tags: [masterpiece, best quality]\n", encoding="utf-8")
    return Classifier(rules_path=rules, quality_path=quality)


def test_classify_assigns_by_priority(clf):
    raw = {"long hair": 0.9, "blue eyes": 0.8, "dress": 0.7, "sitting": 0.6, "indoors": 0.5, "close-up": 0.4}
    res = clf.classify(raw)
    assert "long hair" in res["head"].tags
    assert "blue eyes" in res["head"].tags
    assert res["clothing"].tags == ["dress"]
    assert res["action"].tags == ["sitting"]
    assert res["scene"].tags == ["indoors"]
    assert res["view"].tags == ["close-up"]


def test_classify_quality_from_template(clf):
    res = clf.classify({})
    assert res["quality"].tags == ["masterpiece", "best quality"]


def test_classify_extras_catches_unknown(clf):
    res = clf.classify({"something weird": 0.6, "another tag": 0.5})
    assert set(res["extras"].tags) == {"something weird", "another tag"}
    for key in ["head", "clothing", "view", "action", "scene"]:
        assert res[key].tags == []


def test_classify_phrase_generated(clf):
    raw = {"long hair": 0.9, "blue eyes": 0.8}
    res = clf.classify(raw)
    assert res["head"].phrase == "blue eyes long hair"  # 按分数降序


def test_reclassify_skips_user_edited(clf):
    existing = {
        "head": CategoryData(tags=["custom"], phrase="custom", user_edited=True),
        "clothing": CategoryData(tags=["dress"], phrase="dress"),
    }
    raw = {"long hair": 0.9, "dress": 0.7, "blue eyes": 0.8}
    res = clf.classify(raw, existing=existing)
    assert res["head"].tags == ["custom"]  # 被保护，未覆盖
    assert res["head"].user_edited is True
    assert "dress" in res["clothing"].tags  # 未保护，重算


def test_reclassify_extras_always_recalculated(clf):
    existing = {"extras": CategoryData(tags=["stale unknown"], user_edited=False)}
    raw = {"long hair": 0.9, "mystery tag": 0.6}
    res = clf.classify(raw, existing=existing)
    assert "mystery tag" in res["extras"].tags
    assert "stale unknown" not in res["extras"].tags


def test_quality_protected_when_user_edited(clf):
    existing = {"quality": CategoryData(tags=["my quality"], phrase="my quality", user_edited=True)}
    res = clf.classify({}, existing=existing)
    assert res["quality"].tags == ["my quality"]
