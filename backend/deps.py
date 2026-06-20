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
