from backend.models import Meta, CategoryData, ImageInfo, TaggerInfo


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
