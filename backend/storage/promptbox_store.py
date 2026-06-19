from __future__ import annotations
import json
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image

from backend.models import PromptboxItem
from backend.config import settings


class PromptboxStore:
    """提示词收藏存储：items.json 清单 + images/<id>/ 示例图，与图库隔离。
    风格仿 Storage：防目录穿越、原子写（.tmp + replace）。"""

    def __init__(self, data_root: Path | None = None):
        # 运行时读 settings.PROMPTBOX_DIR（而非 def 默认参数绑定）：
        # 默认参数会在模块导入时一次性求值，使测试的 monkeypatch 失效、污染真实
        # data/promptbox/（而该目录会存放用户真实收藏）。运行时读取让测试真正隔离到 tmp。
        self.data_root = Path(data_root) if data_root is not None else settings.PROMPTBOX_DIR
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.images_root = self.data_root / "images"
        self.images_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id() -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{ts}-{secrets.token_hex(2)}"

    def _items_path(self) -> Path:
        return self.data_root / "items.json"

    def _read_all(self) -> list[PromptboxItem]:
        p = self._items_path()
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return [PromptboxItem.model_validate(d) for d in data.get("items", [])]

    def _write_all(self, items: list[PromptboxItem]) -> None:
        p = self._items_path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"items": [it.model_dump() for it in items]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(p)

    def _item_dir(self, item_id: str) -> Path:
        # 防穿越：拒绝空/点/斜杠
        if item_id in ("", ".", "..") or "/" in item_id or "\\" in item_id:
            raise ValueError("bad item id")
        return self.images_root / item_id

    def list_all(self) -> list[PromptboxItem]:
        return self._read_all()

    def get(self, item_id: str) -> PromptboxItem | None:
        for it in self._read_all():
            if it.id == item_id:
                return it
        return None

    def save_image(self, item_id: str, filename: str, data: bytes) -> str:
        d = self._item_dir(item_id)
        d.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower() or ".png"
        name = f"{secrets.token_hex(8)}{ext}"  # token 文件名：防冲突/穿越
        (d / name).write_bytes(data)
        return name

    def remove_image(self, item_id: str, name: str) -> None:
        if "/" in name or "\\" in name:
            raise ValueError("bad image name")
        p = self._item_dir(item_id) / name
        if p.exists():
            p.unlink()

    def create(self, *, title: str, raw_prompt: str, categories: dict[str, list[str]],
               extras: list[str], image_data: list[tuple[str, bytes]],
               model: str = "wd14", gen_threshold: float = 0.35,
               char_threshold: float = 0.90,
               raw_tags: dict[str, float] | None = None) -> PromptboxItem:
        item_id = self.new_id()
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        image_names = [self.save_image(item_id, fn, data) for fn, data in image_data]
        item = PromptboxItem(
            id=item_id, title=title, raw_prompt=raw_prompt,
            categories=categories, extras=extras,
            image_names=image_names, created_at=now, updated_at=now,
            model=model, gen_threshold=gen_threshold,
            char_threshold=char_threshold, raw_tags=raw_tags or {},
        )
        items = self._read_all()
        items.append(item)
        self._write_all(items)
        return item

    def update(self, item_id: str, *, title: str | None = None, raw_prompt: str | None = None,
               categories: dict[str, list[str]] | None = None, extras: list[str] | None = None,
               new_image_data: list[tuple[str, bytes]] | None = None,
               remove_image_names: list[str] | None = None,
               model: str | None = None, gen_threshold: float | None = None,
               char_threshold: float | None = None,
               raw_tags: dict[str, float] | None = None) -> PromptboxItem:
        items = self._read_all()
        for i, it in enumerate(items):
            if it.id == item_id:
                if title is not None:
                    it.title = title
                if raw_prompt is not None:
                    it.raw_prompt = raw_prompt
                if categories is not None:
                    it.categories = categories
                if extras is not None:
                    it.extras = extras
                if model is not None:
                    it.model = model
                if gen_threshold is not None:
                    it.gen_threshold = gen_threshold
                if char_threshold is not None:
                    it.char_threshold = char_threshold
                if raw_tags is not None:
                    it.raw_tags = raw_tags
                for name in (remove_image_names or []):
                    if name in it.image_names:
                        self.remove_image(item_id, name)
                        it.image_names.remove(name)
                for fn, data in (new_image_data or []):
                    it.image_names.append(self.save_image(item_id, fn, data))
                it.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
                self._write_all(items)
                return it
        raise KeyError(item_id)

    def delete(self, item_id: str) -> None:
        items = self._read_all()
        self._write_all([it for it in items if it.id != item_id])
        d = self._item_dir(item_id)
        if d.exists():
            shutil.rmtree(d)

    def image_path(self, item_id: str, name: str) -> Path:
        if "/" in name or "\\" in name:
            raise ValueError("bad image name")
        return self._item_dir(item_id) / name

    # ---- 反推工作区（临时图，与收藏示例图/图库均隔离）----
    # 提示词收藏页「上传反推」专用：图只落 workspace/<local_id>/，不进图库 data/images/，
    # 也不计入收藏 items.json。用户「另存为收藏」时才决定是否升级为正式示例图。

    def workspace_root(self) -> Path:
        d = self.data_root / "workspace"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _ws_dir(self, local_id: str) -> Path:
        # 防穿越：与 _item_dir 同策略
        if local_id in ("", ".", "..") or "/" in local_id or "\\" in local_id:
            raise ValueError("bad workspace id")
        return self.workspace_root() / local_id

    @staticmethod
    def _ext_for(source_name: str) -> str:
        low = source_name.lower()
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            if low.endswith(ext):
                return ext
        return ".png"

    def save_workspace_image(self, local_id: str, pil: Image.Image,
                             source_name: str) -> tuple[str, str, int, int]:
        """存原图 + 缩略图到 workspace/<local_id>/，返回 (original_name, thumb_name, w, h)。
        缩略图逻辑与 Storage._make_thumb 一致（THUMB_MAX_SIZE=400, webp q85）。"""
        d = self._ws_dir(local_id)
        d.mkdir(parents=True, exist_ok=True)
        ext = self._ext_for(source_name)
        original_name = "original" + ext
        pil.save(d / original_name)
        rgb = pil.convert("RGB")
        w, h = rgb.size
        scale = min(1.0, settings.THUMB_MAX_SIZE / max(w, h))
        tw, th = max(1, int(w * scale)), max(1, int(h * scale))
        rgb.resize((tw, th)).save(d / "thumb.webp", format="WEBP", quality=85)
        return original_name, "thumb.webp", w, h

    def workspace_image_path(self, local_id: str, name: str) -> Path:
        if "/" in name or "\\" in name:
            raise ValueError("bad image name")
        return self._ws_dir(local_id) / name
