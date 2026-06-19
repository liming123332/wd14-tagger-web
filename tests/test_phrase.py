from backend.classifier.phrase import tags_to_phrase, apply_phrase


def test_tags_to_phrase_basic():
    assert tags_to_phrase(["long hair", "blue eyes"]) == "long hair, blue eyes"


def test_tags_to_phrase_dedup():
    assert tags_to_phrase(["long hair", "long hair", "smile"]) == "long hair, smile"


def test_tags_to_phrase_sort_by_score():
    scores = {"long hair": 0.5, "blue eyes": 0.95, "smile": 0.7}
    out = tags_to_phrase(["long hair", "blue eyes", "smile"], scores)
    assert out == "blue eyes, smile, long hair"


def test_tags_to_phrase_empty():
    assert tags_to_phrase([]) == ""


def test_apply_phrase_split_by_comma():
    assert apply_phrase("long hair, blue eyes,smile") == ["long hair", "blue eyes", "smile"]


def test_apply_phrase_split_by_space_when_no_comma():
    assert apply_phrase("long hair blue eyes") == ["long", "hair", "blue", "eyes"]


def test_apply_phrase_empty():
    assert apply_phrase("") == []
