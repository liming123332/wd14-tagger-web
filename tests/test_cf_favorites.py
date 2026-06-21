from backend.characterfinder.favorites import FavoritesDB, ArtistFavoritesDB, SearchHistoryDB


def test_favorites_toggle(tmp_path):
    f = FavoritesDB(tmp_path / "fav.json")
    assert f.is_favorite("char:danbooru:1") is False
    assert f.toggle("char:danbooru:1") is True
    assert f.is_favorite("char:danbooru:1") is True
    assert "char:danbooru:1" in f.get_all()
    assert f.toggle("char:danbooru:1") is False
    assert f.is_favorite("char:danbooru:1") is False


def test_artist_favorites_toggle(tmp_path):
    f = ArtistFavoritesDB(tmp_path / "afav.json")
    assert f.toggle("artist:danbooru:1") is True
    assert f.is_favorite("artist:danbooru:1") is True


def test_search_history_dedup_and_order(tmp_path):
    h = SearchHistoryDB(tmp_path / "recent.json")
    h.add("char:anima:a"); h.add("char:anima:b"); h.add("char:anima:a")
    all_ = h.get_all()
    assert all_[0] == "char:anima:a"  # 最近在前
    assert len(all_) == 2  # 去重


def test_search_history_truncation(tmp_path):
    h = SearchHistoryDB(tmp_path / "recent.json")
    for i in range(105):
        h.add(f"k:{i}")
    all_ = h.get_all()
    assert len(all_) == 100
    assert all_[0] == "k:104"          # 最新在前
    assert "k:0" not in all_            # 最早 5 项被丢弃
