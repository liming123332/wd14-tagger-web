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
