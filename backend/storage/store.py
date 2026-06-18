from __future__ import annotations
import logging
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image

from backend.models import Meta, ImageInfo, TaggerInfo
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

    def save_upload(self, pil: Image.Image, source_name: str) -> str:
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
        )
        self.save_meta(mid, meta)
        return mid

    def _meta_path(self, mid: str) -> Path:
        return self.image_dir(mid) / "meta.json"

    def get_meta(self, mid: str) -> Meta:
        return Meta.model_validate_json(self._meta_path(mid).read_text(encoding="utf-8"))

    def save_meta(self, mid: str, meta: Meta) -> None:
        self._meta_path(mid).write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def list_images(self, page: int = 1, size: int = 24) -> dict:
        ids = sorted([p.name for p in self.data_root.iterdir() if p.is_dir()], reverse=True)
        total = len(ids)
        start = (page - 1) * size
        slice_ids = ids[start:start + size]
        items = []
        for mid in slice_ids:
            try:
                m = self.get_meta(mid)
                items.append({"id": mid, "source_name": m.source_name,
                              "thumb": m.image.thumb, "width": m.image.width, "height": m.image.height})
            except Exception as e:
                logger.warning("skipping image dir %s: %s", mid, e)
                continue
        return {"items": items, "total": total, "page": page, "size": size}

    def delete(self, mid: str) -> None:
        d = self.image_dir(mid)
        if d.exists():
            shutil.rmtree(d)

    def file_path(self, mid: str, name: str) -> Path:
        # 防目录穿越
        if "/" in name or "\\" in name:
            raise ValueError("bad file name")
        return self.image_dir(mid) / name
