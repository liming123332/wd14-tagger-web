"""_release_taggers 单元测试。

验证运行期卸载语义：close 所有已加载 ONNX session、清空 _tagger_cache。
不依赖真 onnxruntime（用 fake session），聚焦 Python 侧资源释放逻辑。
"""
import pytest

from backend import deps


class _FakeSession:
    def __init__(self, raises: bool = False):
        self.closed = False
        self._raises = raises

    def close(self):
        if self._raises:
            raise RuntimeError("boom")
        self.closed = True


class _FakeTagger:
    def __init__(self, session=None):
        self.session = session


@pytest.fixture(autouse=True)
def _clean_cache():
    """_tagger_cache 是模块级单例，测试间隔离。"""
    deps._tagger_cache.clear()
    yield
    deps._tagger_cache.clear()


def test_release_closes_all_sessions_and_clears_cache():
    s1, s2 = _FakeSession(), _FakeSession()
    deps._tagger_cache["wd14"] = _FakeTagger(s1)
    deps._tagger_cache["cl_tagger_v2"] = _FakeTagger(s2)

    released = deps._release_taggers()

    assert set(released) == {"wd14", "cl_tagger_v2"}
    assert s1.closed and s2.closed
    assert deps._tagger_cache == {}


def test_release_skips_tagger_without_session():
    # session 为 None（getattr 返回 None）——仅清缓存，不调 close、不抛
    deps._tagger_cache["x"] = _FakeTagger(session=None)
    assert deps._release_taggers() == ["x"]
    assert deps._tagger_cache == {}


def test_release_tolerates_close_error():
    # session.close 抛异常时不应中断其余释放（_release_taggers 内 try/except）
    deps._tagger_cache["x"] = _FakeTagger(_FakeSession(raises=True))
    assert deps._release_taggers() == ["x"]
    assert deps._tagger_cache == {}


def test_release_empty_cache_is_noop():
    assert deps._release_taggers() == []
