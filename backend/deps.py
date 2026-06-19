from functools import lru_cache
from backend.storage.store import Storage
from backend.classifier.engine import Classifier
from backend.tagger.core import OnnxTagger
from backend.tagger.models_spec import MODEL_SPECS, DEFAULT_MODEL_KEY


@lru_cache
def get_storage() -> Storage:
    return Storage()


@lru_cache
def get_classifier() -> Classifier:
    return Classifier()


# 多模型实例缓存：key -> OnnxTagger/CLTagger。换模型时各自缓存，最多 8 个 ONNX session。
_tagger_cache: dict[str, OnnxTagger] = {}


def get_tagger(model_key: str = DEFAULT_MODEL_KEY) -> OnnxTagger:
    if model_key not in MODEL_SPECS:
        raise ValueError(f"Unknown tagger: {model_key}")
    if model_key not in _tagger_cache:
        _tagger_cache[model_key] = OnnxTagger(MODEL_SPECS[model_key])
    return _tagger_cache[model_key]


def _reset_tagger_cache() -> None:
    """测试隔离：清空多模型实例缓存。"""
    _tagger_cache.clear()
