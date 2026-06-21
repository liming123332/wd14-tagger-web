from backend.characterfinder import paths


def test_db_paths():
    assert paths.CHARACTERS_DB.name == "characters.db"
    assert paths.ARTISTS_DB.name == "artists.db"
    assert paths.ANIMA_CHARACTERS_DB.name == "anima_characters.db"
    assert paths.ANIMA_ARTISTS_DB.name == "anima_artists.db"
    assert paths.DANBOORU_TAGS_CSV.name == "danbooru_tags.csv"


def test_entry_key_roundtrip():
    k = paths.entry_key("char", "anima", "001_(darling_in_the_franxx)")
    assert k == "char:anima:001_(darling_in_the_franxx)"
    assert paths.parse_entry_key(k) == ("char", "anima", "001_(darling_in_the_franxx)")


def test_parse_entry_key_rejects_bad():
    import pytest
    with pytest.raises(ValueError):
        paths.parse_entry_key("bogus")
