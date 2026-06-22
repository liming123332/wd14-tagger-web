from __future__ import annotations
import json
import logging
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image
import random as _random  # 别名避开下方 random 形参

from backend.models import Meta, ImageInfo, TaggerInfo, build_prompt, PROMPT_ORDER
from backend.config import settings
from backend.storage.index import ImageIndex

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, data_root: Path = settings.IMAGES_DIR):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        # 倒排索引：懒构建（首次 list_images/all_tags 触发），save_* 增量维护。
        # None = 尚未构建；测试用 _write_meta_directly 绕过 save_* 直接落盘的数据，
        # 靠首次查询的全量 rebuild 进入索引。
        self._index: ImageIndex | None = None

    @staticmethod
    def new_id() -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{ts}-{secrets.token_hex(2)}"

    def image_dir(self, mid: str) -> Path:
        # 防 mid 穿越（不依赖路由规范化）：拒绝空/点/斜杠，并校验 resolve 后仍在 data_root 内
        if mid in ("", ".", "..") or "/" in mid or "\\" in mid:
            raise ValueError("bad image id")
        root = self.data_root.resolve()
        resolved = (root / mid).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("bad image id")
        return self.data_root / mid

    def _ext_for(self, source_name: str) -> str:
        low = source_name.lower()
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
            if low.endswith(ext):
                return ext
        return ".png"

    def _make_thumb(self, pil: Image.Image, dst: Path) -> tuple[int, int]:
        pil = pil.convert("RGB")
        w, h = pil.size
        scale = min(1.0, settings.THUMB_MAX_SIZE / max(w, h))
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        pil.resize((tw, th)).save(dst, format="WEBP", quality=85)
        return w, h

    def save_upload(self, pil: Image.Image, source_name: str, tags: list[str] | None = None) -> str:
        mid = self.new_id()
        d = self.image_dir(mid)
        d.mkdir(parents=True, exist_ok=True)
        ext = self._ext_for(source_name)
        original_name = "original" + ext
        pil.save(d / original_name)
        w, h = self._make_thumb(pil, d / "thumb.webp")
        meta = Meta(
            id=mid,
            source_name=source_name,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            model="wd14",
            image=ImageInfo(original=original_name, thumb="thumb.webp", width=w, height=h),
            tagger=TaggerInfo(),
            tags=list(tags or []),
        )
        self.save_meta(mid, meta)
        return mid

    def replace_image(self, mid: str, pil: Image.Image, source_name: str) -> Meta:
        """覆盖某 mid 的原图 + 缩略图，仅更新 meta.image（尺寸/文件名），保留
        tags/categories/source_name/tagger 等——换图不自动反推（与各详情页「替换图片」一致）。
        mid 非法抛 ValueError；meta 不存在抛 FileNotFoundError（路由转 404）。"""
        d = self.image_dir(mid)
        meta = self.get_meta(mid)
        ext = self._ext_for(source_name)
        new_original = "original" + ext
        if meta.image.original and meta.image.original != new_original:
            (d / meta.image.original).unlink(missing_ok=True)  # ext 变化删旧原图防残留
        pil.save(d / new_original)
        w, h = self._make_thumb(pil, d / "thumb.webp")  # 覆盖缩略图
        meta.image = ImageInfo(original=new_original, thumb="thumb.webp", width=w, height=h)
        self.save_meta(mid, meta)
        return meta

    def _meta_path(self, mid: str) -> Path:
        return self.image_dir(mid) / "meta.json"

    def get_meta(self, mid: str) -> Meta:
        return Meta.model_validate_json(self._meta_path(mid).read_text(encoding="utf-8"))

    def save_meta(self, mid: str, meta: Meta) -> None:
        # 先写文件、再更索引：崩溃时以文件为准，下次重启全量 rebuild 自愈
        self._meta_path(mid).write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        if self._index is not None:
            self._index.update(mid, self._extract_cat_tags(meta), set(meta.tags))

    def list_images(self, page: int = 1, size: int = 24, date: str | None = None, random: bool = False, tags: list[str] | None = None, prompt: list[str] | None = None) -> dict:
        idx = self._touch_index()
        wanted_tags = {t.strip().lower() for t in (tags or []) if t and t.strip()}
        words = [w.strip().lower() for w in (prompt or []) if w and w.strip()]

        # date + tags + prompt 三者 AND，结果作为候选集；None 表示全集。
        candidate: set[str] | None = None

        if date:  # date 形如 "20260619"，按 id 前缀过滤（bisect 取连续段）
            candidate = set(idx.date_slice(date))

        if wanted_tags:
            # m.tags 交集：任一标签无命中即整体为空
            tag_sets: list[set[str]] = []
            for t in wanted_tags:
                s = idx.user_inv.get(t)
                if not s:
                    return {"items": [], "total": 0, "page": page, "size": size}
                tag_sets.append(s)
            tag_and = set.intersection(*tag_sets)
            candidate = tag_and if candidate is None else candidate & tag_and

        if words:
            # prompt 交集：精确优先（词==标签），无精确命中再扫词表做子串兜底
            word_sets: list[set[str]] = []
            for w in words:
                exact = idx.cat_inv.get(w)
                if exact is not None:
                    word_sets.append(set(exact))
                else:
                    matched: set[str] = set()
                    for tag in idx.cat_inv:  # 扫词表（~数千），不扫图
                        if w in tag:
                            matched |= idx.cat_inv[tag]
                    word_sets.append(matched)
            prompt_and = set.intersection(*word_sets) if word_sets else set()
            candidate = prompt_and if candidate is None else candidate & prompt_and

        # 转降序（id 倒序 = 最新优先）。all_ids 升序，全集走 reversed 免排序。
        if candidate is None:
            ordered = list(reversed(idx.all_ids))
        else:
            ordered = sorted(candidate, reverse=True)

        total = len(ordered)
        if random:
            _random.shuffle(ordered)
            slice_ids = ordered[:size]  # 随机模式只取一页，无分页
        else:
            start = (page - 1) * size
            slice_ids = ordered[start:start + size]
        items = []
        for mid in slice_ids:
            try:
                m = self.get_meta(mid)
                items.append({"id": mid, "source_name": m.source_name,
                              "thumb": m.image.thumb, "original": m.image.original,
                              "width": m.image.width, "height": m.image.height,
                              "prompt": build_prompt(m), "tags": m.tags})
            except Exception as e:
                logger.warning("skipping image dir %s: %s", mid, e)
                continue
        return {"items": items, "total": total, "page": page, "size": size}

    def all_tags(self) -> dict[str, int]:
        """全库统计每个用户标签出现的图片数（一张图同一标签只计一次），
        供图库筛选下拉显示「tag (n)」。从倒排索引出，免全量读盘。"""
        return self._touch_index().user_tag_counts()

    def delete(self, mid: str) -> None:
        if self._index is not None:
            self._index.remove(mid)
        d = self.image_dir(mid)
        if d.exists():
            shutil.rmtree(d)

    # -- 倒排索引 --------------------------------------------------------
    def _touch_index(self) -> ImageIndex:
        """首次访问懒构建；后续直接复用。"""
        if self._index is None:
            self.rebuild_index()
        assert self._index is not None
        return self._index

    def rebuild_index(self, force: bool = False) -> None:
        """全量扫盘重建索引。force=True 时即使已存在也重建（脏数据自愈）。
        走 json.loads 只取 categories/extras/tags 三字段，不经 pydantic，万图量级亚秒。"""
        if self._index is not None and not force:
            return
        idx = ImageIndex.empty()
        for p in self.data_root.iterdir():
            if not p.is_dir():
                continue
            mid = p.name
            try:
                raw = json.loads((p / "meta.json").read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("skipping image dir %s during index rebuild: %s", mid, e)
                continue
            cat_tags = self._cat_tags_from_raw(raw)
            user_tags = {t for t in (raw.get("tags") or []) if t}
            idx.add(mid, cat_tags, user_tags)
        self._index = idx

    def _extract_cat_tags(self, meta: Meta) -> set[str]:
        """从 Meta 提取 prompt 标签集合，与 build_prompt 同源（PROMPT_ORDER + extras）。"""
        tags: set[str] = set()
        for k in PROMPT_ORDER:
            cat = meta.categories.get(k)
            if cat:
                tags.update(t for t in cat.tags if t)
        tags.update(t for t in meta.extras.tags if t)
        return tags

    @staticmethod
    def _cat_tags_from_raw(raw: dict) -> set[str]:
        """rebuild 时从 raw dict 提取 prompt 标签，与 _extract_cat_tags / build_prompt 同源。"""
        tags: set[str] = set()
        cats = raw.get("categories") or {}
        for k in PROMPT_ORDER:
            c = cats.get(k)
            if c:
                tags.update(t for t in (c.get("tags") or []) if t)
        extras = raw.get("extras") or {}
        tags.update(t for t in (extras.get("tags") or []) if t)
        return tags

    def file_path(self, mid: str, name: str) -> Path:
        # 防目录穿越
        if "/" in name or "\\" in name:
            raise ValueError("bad file name")
        return self.image_dir(mid) / name
