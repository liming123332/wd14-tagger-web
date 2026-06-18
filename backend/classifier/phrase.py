from __future__ import annotations


def tags_to_phrase(tags: list[str], scores: dict[str, float] | None = None) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tags:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        ordered.append(t)
    if scores:
        ordered.sort(key=lambda t: scores.get(t, 0.0), reverse=True)
    return " ".join(ordered)


def apply_phrase(phrase: str) -> list[str]:
    phrase = (phrase or "").strip()
    if not phrase:
        return []
    if "," in phrase:
        parts = [p.strip() for p in phrase.split(",")]
    else:
        parts = phrase.split()
    return [p for p in parts if p]
