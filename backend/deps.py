from functools import lru_cache
from backend.storage.store import Storage
from backend.classifier.engine import Classifier
from backend.tagger.core import WD14Tagger


@lru_cache
def get_storage() -> Storage:
    return Storage()


@lru_cache
def get_classifier() -> Classifier:
    return Classifier()


@lru_cache
def get_tagger() -> WD14Tagger:
    return WD14Tagger()
