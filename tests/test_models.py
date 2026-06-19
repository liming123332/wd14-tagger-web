from backend.models import Meta, CategoryData, ImageInfo, TaggerInfo, PromptboxItem


def test_category_data_defaults():
    c = CategoryData()
    assert c.tags == []
    assert c.phrase == ""
    assert c.user_edited is False


def test_meta_roundtrip():
    m = Meta(
        id="20260618-153012-a1b2",
        source_name="x.png",
        created_at="2026-06-18T15:30:12+08:00",
        model="wd14",
        image=ImageInfo(original="original.png", thumb="thumb.webp", width=100, height=120),
        tagger=TaggerInfo(gen_threshold=0.35, char_threshold=0.90, raw_tags={"long hair": 0.9}),
        categories={"head": CategoryData(tags=["long hair"], phrase="long hair")},
        extras=CategoryData(),
    )
    d = m.model_dump()
    m2 = Meta.model_validate(d)
    assert m2.id == m.id
    assert m2.categories["head"].tags == ["long hair"]
    assert m2.extras.tags == []


def test_promptbox_item_defaults_for_old_data():
    # 老收藏 items.json 无反推/重分类字段：Pydantic 默认值兜底，不报错
    it = PromptboxItem(id="x")
    assert it.model == "wd14"
    assert it.gen_threshold == 0.35
    assert it.char_threshold == 0.90
    assert it.raw_tags == {}


def test_promptbox_item_roundtrip_with_raw_tags():
    it = PromptboxItem(id="x", model="wd3", gen_threshold=0.4,
                       char_threshold=0.6, raw_tags={"long hair": 0.9})
    again = PromptboxItem.model_validate(it.model_dump())
    assert again.model == "wd3"
    assert again.gen_threshold == 0.4
    assert again.char_threshold == 0.6
    assert again.raw_tags["long hair"] == 0.9
