from backend.config import settings


def test_cf_paths_under_data_dir():
    assert settings.CF_DIR == settings.DATA_DIR / "characterfinder"
    assert settings.CF_COVERS_DIR == settings.CF_DIR / "covers"
    assert settings.CF_ARTIST_COVERS_DIR == settings.CF_DIR / "artist_covers"
    assert settings.CF_ANIMA_DIR == settings.CF_DIR / "anima"
    assert settings.CF_OVERLAY_DIR == settings.CF_DIR / "overlay"
    assert settings.CF_OVERLAY_DB == settings.CF_DIR / "cf_overlay.db"
    assert settings.CF_FAVORITES_PATH == settings.CF_DIR / "favorites.json"
    assert settings.CF_RECENT_PATH == settings.CF_DIR / "recent_viewed.json"


def test_cf_source_dirs_and_download_tunables():
    assert settings.SDCF_SOURCE_DIR.name == "sd-character-finder"
    assert settings.ANIMADEX_SOURCE_DIR.name == "animadex-data"
    assert settings.CF_DOWNLOAD_CONCURRENCY >= 1
    assert settings.CF_DOWNLOAD_RETRIES >= 1
