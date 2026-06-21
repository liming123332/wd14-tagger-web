"""图库倒排索引（纯内存，无 I/O）。

由 ``backend/storage/store.py:Storage`` 持有并驱动：首次查询时全量扫盘构建，
之后 save_upload/save_meta/delete 增量维护。详见 store.py。
"""
from __future__ import annotations

from bisect import bisect_left, insort
from dataclasses import dataclass, field


@dataclass
class ImageIndex:
    """categories 标签 + 用户标签的双倒排索引。

    - ``all_ids``：升序（id 是 ``YYYYMMDD-HHMMSS-xxxx`` 时间戳字典序），供 bisect 与翻页。
    - ``cat_inv``：``categories``/``extras`` 反推标签（小写）→ {mid}，prompt 搜索主索引。
      与 ``backend.models.build_prompt`` 同源（PROMPT_ORDER + extras）。
    - ``user_inv``：``meta.tags`` 用户手动分类标签（小写）→ {mid}，tags 过滤 + all_tags 统计源。
    - ``cat_fwd``/``user_fwd``：mid → 标签集合，用于增量 update 时拿旧值清倒排（免读旧文件）。
    """

    all_ids: list[str] = field(default_factory=list)
    id_set: set[str] = field(default_factory=set)
    cat_inv: dict[str, set[str]] = field(default_factory=dict)
    cat_fwd: dict[str, set[str]] = field(default_factory=dict)
    user_inv: dict[str, set[str]] = field(default_factory=dict)
    user_fwd: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ImageIndex":
        return cls()

    # -- 增删改 -----------------------------------------------------------
    def add(self, mid: str, cat_tags: set[str], user_tags: set[str]) -> None:
        """幂等加入：若 mid 已在，先按旧标签清理再重写（等价于 update）。"""
        if mid in self.id_set:
            self.remove(mid)
        insort(self.all_ids, mid)
        self.id_set.add(mid)
        cats = {t.lower() for t in cat_tags if t}
        users = {t.lower() for t in user_tags if t}
        self.cat_fwd[mid] = cats
        self.user_fwd[mid] = users
        for t in cats:
            self.cat_inv.setdefault(t, set()).add(mid)
        for t in users:
            self.user_inv.setdefault(t, set()).add(mid)

    def update(self, mid: str, cat_tags: set[str], user_tags: set[str]) -> None:
        """语义同 add（幂等重写）。独立命名只为调用点表意。"""
        self.add(mid, cat_tags, user_tags)

    def remove(self, mid: str) -> None:
        """从索引移除 mid（含倒排清理）。未知 mid 是 no-op。"""
        if mid not in self.id_set:
            return
        i = bisect_left(self.all_ids, mid)
        if i < len(self.all_ids) and self.all_ids[i] == mid:
            del self.all_ids[i]
        self.id_set.discard(mid)
        for t in self.cat_fwd.pop(mid, ()):  # type: ignore[arg-type]
            s = self.cat_inv.get(t)
            if s is not None:
                s.discard(mid)
                if not s:
                    del self.cat_inv[t]
        for t in self.user_fwd.pop(mid, ()):  # type: ignore[arg-type]
            s = self.user_inv.get(t)
            if s is not None:
                s.discard(mid)
                if not s:
                    del self.user_inv[t]

    # -- 查询辅助 ---------------------------------------------------------
    def date_slice(self, prefix: str) -> list[str]:
        """返回 id 前缀匹配 prefix 的子集（升序），用 bisect 取连续段，O(log n)。"""
        if not prefix:
            return list(self.all_ids)
        lo = bisect_left(self.all_ids, prefix)
        # prefix 的上界：同长度下逐位取最大，使 bisect 落在最后一个 startswith(prefix) 之后
        hi_prefix = prefix[:-1] + chr(ord(prefix[-1]) + 1)
        hi = bisect_left(self.all_ids, hi_prefix)
        return self.all_ids[lo:hi]

    def user_tag_counts(self) -> dict[str, int]:
        """每个用户标签命中的图片数（供 all_tags 下拉「tag (n)」）。"""
        return {t: len(s) for t, s in self.user_inv.items()}
