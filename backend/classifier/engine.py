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
        # 规则词统一小写，保证大小写不敏感匹配
        for spec in self.categories.values():
            for k in ("exact", "suffix", "contains"):
                if isinstance(spec.get(k), list):
                    spec[k] = [str(w).lower() for w in spec[k]]
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

        # 5 个内容类：受保护则保留，否则用新桶（按分数降序）
        for cat in self.priority:
            ex = existing.get(cat)
            if ex is not None and ex.user_edited:
                result[cat] = ex.model_copy()
            else:
                ordered = sorted(buckets[cat], key=lambda t: raw_tags.get(t, 0.0), reverse=True)
                result[cat] = CategoryData(tags=ordered)

        # extras：始终重算（按分数降序）
        ordered_extras = sorted(unmatched, key=lambda t: raw_tags.get(t, 0.0), reverse=True)
        result["extras"] = CategoryData(tags=ordered_extras)

        # 为非 user_edited 类生成 phrase（按反推分数降序）
        for key, cat in result.items():
            if not cat.user_edited:
                cat.phrase = tags_to_phrase(cat.tags, raw_tags)
        return result

    def split(self, text: str) -> dict[str, list[str]]:
        """把一段提示词文本按当前词表拆到 6 大类 + extras。
        与 classify 的区别：quality 改为「按匹配」（只收实际出现的质量词），
        不无条件填充模板；结果无分数、无 phrase，保留原始大小写与出现顺序。"""
        tokens = [t.strip() for t in (text or "").replace("\n", ",").split(",") if t.strip()]
        buckets: dict[str, list[str]] = {k: [] for k in self.priority}
        quality_out: list[str] = []
        extras: list[str] = []
        quality_set = {q.lower() for q in self.quality_tags}

        for tok in tokens:
            t = tok.lower()
            if t in quality_set:
                quality_out.append(tok)
                continue
            placed = False
            for cat in self.priority:
                if self._match(t, self.categories.get(cat, {})):
                    buckets[cat].append(tok)
                    placed = True
                    break
            if not placed:
                extras.append(tok)

        result: dict[str, list[str]] = {"quality": quality_out}
        result.update(buckets)
        result["extras"] = extras
        return result
