from __future__ import annotations
from pydantic import BaseModel, Field


class CategoryData(BaseModel):
    tags: list[str] = Field(default_factory=list)
    phrase: str = ""
    user_edited: bool = False


class ImageInfo(BaseModel):
    original: str
    thumb: str
    width: int = 0
    height: int = 0


class TaggerInfo(BaseModel):
    gen_threshold: float = 0.35
    char_threshold: float = 0.90
    raw_tags: dict[str, float] = Field(default_factory=dict)


class Meta(BaseModel):
    id: str
    source_name: str
    created_at: str
    model: str = "wd14"
    image: ImageInfo
    tagger: TaggerInfo = Field(default_factory=TaggerInfo)
    categories: dict[str, CategoryData] = Field(default_factory=dict)
    extras: CategoryData = Field(default_factory=CategoryData)
    # 用户自定义筛选用标签（不同于反推 prompt，由用户在详情/上传页手动维护）
    tags: list[str] = Field(default_factory=list)


# 顺序与前端 frontend/src/detail-utils.ts 的 buildPrompt 保持一致，
# 使列表项复制的 prompt 与详情页「复制完整 prompt」结果相同。
PROMPT_ORDER = ["quality", "head", "clothing", "view", "action", "scene"]


def build_prompt(meta: Meta) -> str:
    out: list[str] = []
    for k in PROMPT_ORDER:
        cat = meta.categories.get(k)
        if cat:
            out.extend(t for t in cat.tags if t)
    return ", ".join(out)


class PromptboxItem(BaseModel):
    """「提示词收藏」的一条记录：存用户处理过的拆分结果（可手改）+ 原始粘贴文本。
    与图库 Meta 物理隔离（data/promptbox/）。"""
    id: str
    title: str = ""
    raw_prompt: str = ""
    categories: dict[str, list[str]] = Field(default_factory=dict)
    extras: list[str] = Field(default_factory=list)
    image_names: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    # 反推/重分类元数据：老收藏 items.json 无这些字段，靠默认值兼容，无需数据迁移
    model: str = "wd14"
    gen_threshold: float = 0.35
    char_threshold: float = 0.90
    raw_tags: dict[str, float] = Field(default_factory=dict)
