from __future__ import annotations
import logging
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image
import random as _random  # 别名避开下方 random 形参

from backend.models import Meta, ImageInfo, TaggerInfo, build_prompt
from backend.config import settings

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, data_root: Path = settings.IMAGES_DIR):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)

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

    def _meta_path(self, mid: str) -> Path:
        return self.image_dir(mid) / "meta.json"

    def get_meta(self, mid: str) -> Meta:
        return Meta.model_validate_json(self._meta_path(mid).read_text(encoding="utf-8"))

    def save_meta(self, mid: str, meta: Meta) -> None:
        self._meta_path(mid).write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def list_images(self, page: int = 1, size: int = 24, date: str | None = None, random: bool = False, tags: list[str] | None = None, prompt: list[str] | None = None) -> dict:
        ids = sorted([p.name for p in self.data_root.iterdir() if p.is_dir()], reverse=True)
        if date:  # date 形如 "20260619"，按 id 前缀过滤
            ids = [i for i in ids if i.startswith(date)]
        if tags or prompt:
            # tags 交集 + prompt 交集：都需读 meta，合并到同一循环避免重复读盘。
            # date + tags + prompt 三者 AND。放在切片前，保证 total/分页基于筛选结果。
            wanted_tags = set(tags or [])
            words = [w.strip().lower() for w in (prompt or []) if w and w.strip()]
            filtered = []
            for mid in ids:
                try:
                    m = self.get_meta(mid)
                except Exception as e:
                    logger.warning("skipping image dir %s: %s", mid, e)
                    continue
                if wanted_tags and not wanted_tags.issubset(set(m.tags)):
                    continue
                if words and not all(w in build_prompt(m).lower() for w in words):
                    continue
                filtered.append(mid)
            ids = filtered
        total = len(ids)
        if random:
            _random.shuffle(ids)
            slice_ids = ids[:size]  # 随机模式只取一页，无分页
        else:
            start = (page - 1) * size
            slice_ids = ids[start:start + size]
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
        供图库筛选下拉显示「tag (n)」。"""
        counts: dict[str, int] = {}
        for p in self.data_root.iterdir():
            if not p.is_dir():
                continue
            try:
                m = self.get_meta(p.name)
            except Exception as e:
                logger.warning("skipping image dir %s: %s", p.name, e)
                continue
            for t in set(m.tags):
                counts[t] = counts.get(t, 0) + 1
        return counts

    def delete(self, mid: str) -> None:
        d = self.image_dir(mid)
        if d.exists():
            shutil.rmtree(d)

    def file_path(self, mid: str, name: str) -> Path:
        # 防目录穿越
        if "/" in name or "\\" in name:
            raise ValueError("bad file name")
        return self.image_dir(mid) / name
