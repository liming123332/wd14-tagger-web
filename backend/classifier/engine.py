from __future__ import annotations
from pathlib import Path
import yaml

from backend.models import CategoryData
from backend.classifier.phrase import tags_to_phrase
from backend.config import settings


class Classifier:
    """把扁平的 {tag: score} 反推结果归类到 6 大类 + extras 兜底。"""

    def __init__(self, rules_path: Path = settings.TAG_RULES_PATH,
                 quality_path: Path = settings.QUALITY_TEMPLATE_PATH):
        self.rules_path = Path(rules_path)
        self.quality_path = Path(quality_path)
        self.priority: list[str] = []
        self.categories: dict[str, dict] = {}
        self.quality_tags: list[str] = []
        self.reload()

    def reload(self) -> None:
        data = yaml.safe_load(self.rules_path.read_text(encoding="utf-8"))
        self.priority = data.get("priority", settings.PRIORITY)
        self.categories = data.get("categories", {})
        q = yaml.safe_load(self.quality_path.read_text(encoding="utf-8"))
        self.quality_tags = list(q.get("tags", []))

    @staticmethod
    def _match(tag: str, spec: dict) -> bool:
        for t in spec.get("exact", []):
            if tag == t:
                return True
        for suf in spec.get("suffix", []):
            if tag.endswith(suf):
                return True
        for sub in spec.get("contains", []):
            if sub in tag:
                return True
        return False

    def classify(self, raw_tags: dict[str, float],
                 existing: dict[str, CategoryData] | None = None
                 ) -> dict[str, CategoryData]:
        existing = existing or {}
        result: dict[str, CategoryData] = {}

        # quality：模板填充，除非用户手改过
        q_ex = existing.get("quality")
        if q_ex is not None and q_ex.user_edited:
            result["quality"] = q_ex.model_copy()
        else:
            result["quality"] = CategoryData(tags=list(self.quality_tags))

        # 把标签按 priority 分桶
        buckets: dict[str, list[str]] = {k: [] for k in self.priority}
        unmatched: list[str] = []
        for tag in raw_tags.keys():
            t = tag.strip().lower()
            placed = False
            for cat in self.priority:
                if self._match(t, self.categories.get(cat, {})):
                    buckets[cat].append(tag)
                    placed = True
                    break
            if not placed:
                unmatched.append(tag)

        # 5 个内容类：受保护则保留，否则用新桶
        for cat in self.priority:
            ex = existing.get(cat)
            if ex is not None and ex.user_edited:
                result[cat] = ex.model_copy()
            else:
                result[cat] = CategoryData(tags=buckets[cat])

        # extras：始终重算
        result["extras"] = CategoryData(tags=unmatched)

        # 为非 user_edited 类生成 phrase。
        # tags_to_phrase 内部用 reverse=True（分数从高到低）；这里取负分，
        # 等价于按原始分数从低到高排序——即把置信度最低的标签放在最前面，
        # 让最强匹配留在末尾（与 UI 期望展示顺序一致）。
        neg_scores = {t: -s for t, s in raw_tags.items()}
        for key, cat in result.items():
            if not cat.user_edited:
                cat.phrase = tags_to_phrase(cat.tags, neg_scores)
        return result
