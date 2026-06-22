from functools import lru_cache
from backend.storage.store import Storage
from backend.classifier.engine import Classifier
from backend.tagger.core import OnnxTagger
from backend.tagger.models_spec import MODEL_SPECS, DEFAULT_MODEL_KEY


@lru_cache
def get_storage() -> Storage:
    return Storage()


@lru_cache
def get_promptbox_store():
    from backend.storage.promptbox_store import PromptboxStore
    return PromptboxStore()


@lru_cache
def get_classifier() -> Classifier:
    return Classifier()


# 多模型实例缓存：key -> OnnxTagger/CLTagger。换模型时各自缓存，最多 8 个 ONNX session。
# 类型注解去掉 OnnxTagger：cl_tagger 现经此入口返回 CLTagger（见 get_tagger 工厂分支）。
_tagger_cache: dict = {}


def get_tagger(model_key: str = DEFAULT_MODEL_KEY):
    if model_key not in MODEL_SPECS:
        raise ValueError(f"Unknown tagger: {model_key}")
    if model_key not in _tagger_cache:
        spec = MODEL_SPECS[model_key]
        if spec.prep == "cl":
            from backend.tagger.cl_tagger import CLTagger  # 延迟 import 避免循环/加载开销
            _tagger_cache[model_key] = CLTagger(spec)
        elif spec.prep == "cl_v2":
            from backend.tagger.cl_tagger_v2 import CLTaggerV2
            _tagger_cache[model_key] = CLTaggerV2(spec)
        else:
            _tagger_cache[model_key] = OnnxTagger(spec)
    return _tagger_cache[model_key]


def _reset_tagger_cache() -> None:
    """测试隔离：清空多模型实例缓存。"""
    _tagger_cache.clear()


def _release_taggers() -> list[str]:
    """运行期卸载：close 所有已加载的 ONNX session（释放 RAM/GPU 显存 + 文件句柄），
    清空多模型缓存并强制 GC。返回被释放的 model key 列表。
    不删任何模型文件——下次 get_tagger() 会重新 lazy-load。
    区别于 _reset_tagger_cache：后者仅 clear（测试隔离用），不 close session、不 GC，
    无法释放 onnxruntime 占用的显存。"""
    import gc
    released: list[str] = []
    for key, t in list(_tagger_cache.items()):
        s = getattr(t, "session", None)
        if s is not None:
            try:
                s.close()  # onnxruntime InferenceSession.close() 释放显存/文件句柄
            except Exception:
                pass
        released.append(key)
    _tagger_cache.clear()
    gc.collect()  # 兜底：强制回收已无引用的 session 对象
    return released


# === 翻译模型（Hy-MT2，GGUF + llama-cpp-python 进程内推理）===
# 单例管理：get_translator 懒加载，release_translator 卸载释放显存（不删文件）。
# 与 tagger 的 _tagger_cache 不同：翻译模型全局唯一（不分 key），用模块级变量管理。
_translator_singleton = None


def get_translator():
    global _translator_singleton
    if _translator_singleton is None:
        from backend.translate.translator import HyTranslator
        _translator_singleton = HyTranslator()
    return _translator_singleton


def release_translator() -> None:
    """卸载翻译模型 Llama 实例（显存/RAM），清单例；下次 get_translator 重新 lazy-load。不删 GGUF。"""
    global _translator_singleton
    if _translator_singleton is not None:
        _translator_singleton.unload()
        _translator_singleton = None


# === Character Finder ===
@lru_cache
def get_character_db():
    from backend.characterfinder.character_db import CharacterDB
    return CharacterDB()


@lru_cache
def get_artist_db():
    from backend.characterfinder.artist_db import ArtistDB
    return ArtistDB()


@lru_cache
def get_anima_character_db():
    from backend.characterfinder.anima_db import AnimaCharacterDB
    return AnimaCharacterDB()


@lru_cache
def get_anima_artist_db():
    from backend.characterfinder.anima_db import AnimaArtistDB
    return AnimaArtistDB()


@lru_cache
def get_cf_overlay():
    from backend.storage.cf_overlay import CfOverlayStore
    from backend.config import settings
    return CfOverlayStore(settings.CF_OVERLAY_DB, settings.CF_OVERLAY_DIR)


@lru_cache
def get_cf_favorites():
    from backend.characterfinder.favorites import FavoritesDB
    return FavoritesDB()


@lru_cache
def get_cf_artist_favorites():
    from backend.characterfinder.favorites import ArtistFavoritesDB
    return ArtistFavoritesDB()


@lru_cache
def get_cf_recent():
    from backend.characterfinder.favorites import SearchHistoryDB
    return SearchHistoryDB()
