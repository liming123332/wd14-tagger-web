"""测试 PUT /api/config/rules/{category}：合并词到 exact 词表 + reload 分类器。
用 tmp_path + monkeypatch 隔离，绝不触碰真实 tag_rules.yaml。"""
import shutil
import pytest
import yaml
from fastapi import HTTPException


@pytest.fixture
def isolated_rules(tmp_path, monkeypatch):
    from backend.config import settings
    dst = tmp_path / "tag_rules.yaml"
    shutil.copy(settings.TAG_RULES_PATH, dst)
    monkeypatch.setattr(settings, "TAG_RULES_PATH", dst)
    return dst


def test_put_category_rules_merges_dedup_lower(isolated_rules, monkeypatch):
    from backend.api import routes_config as rc
    from backend.classifier.engine import Classifier
    stub = Classifier(rules_path=isolated_rules)
    monkeypatch.setattr(rc, "get_classifier", lambda: stub)

    rc.put_category_rules("head", rc.CategoryRulePayload(tags=["Long Hair", "long hair", "elf ears"]))
    data = yaml.safe_load(isolated_rules.read_text(encoding="utf-8"))
    exact = data["categories"]["head"]["exact"]
    # 去重 + 小写
    assert "long hair" in exact
    assert "elf ears" in exact
    assert exact.count("long hair") == 1
    # priority 等其它结构未破坏
    assert data["priority"] == ["head", "clothing", "view", "action", "scene"]
    # reload 后分类器把新词归到 head（而非 extras）
    res = stub.classify({"long hair": 0.9, "elf ears": 0.8})
    assert "long hair" in res["head"].tags
    assert "elf ears" in res["head"].tags


def test_put_category_rules_preserves_other_categories(isolated_rules, monkeypatch):
    from backend.api import routes_config as rc
    from backend.classifier.engine import Classifier
    stub = Classifier(rules_path=isolated_rules)
    monkeypatch.setattr(rc, "get_classifier", lambda: stub)

    before = yaml.safe_load(isolated_rules.read_text(encoding="utf-8"))
    rc.put_category_rules("scene", rc.CategoryRulePayload(tags=["waterfall"]))
    after = yaml.safe_load(isolated_rules.read_text(encoding="utf-8"))
    # 其它分类不受影响
    assert after["categories"]["head"] == before["categories"]["head"]
    assert "waterfall" in after["categories"]["scene"]["exact"]


def test_put_category_rules_rejects_extras(isolated_rules, monkeypatch):
    from backend.api import routes_config as rc
    with pytest.raises(HTTPException):
        rc.put_category_rules("extras", rc.CategoryRulePayload(tags=["x"]))
    with pytest.raises(HTTPException):
        rc.put_category_rules("quality", rc.CategoryRulePayload(tags=["x"]))


def test_put_category_rules_reload_takes_effect_immediately(isolated_rules, monkeypatch):
    from backend.api import routes_config as rc
    from backend.classifier.engine import Classifier
    stub = Classifier(rules_path=isolated_rules)
    monkeypatch.setattr(rc, "get_classifier", lambda: stub)

    # 写入前 customword 会落到 extras
    before = stub.classify({"customword": 0.9})
    assert "customword" in before["extras"].tags
    rc.put_category_rules("action", rc.CategoryRulePayload(tags=["customword"]))
    # reload 后归到 action
    after = stub.classify({"customword": 0.9})
    assert "customword" in after["action"].tags
    assert "customword" not in after["extras"].tags
