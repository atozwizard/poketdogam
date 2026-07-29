# Run: python app/agents/pokedex_agent/rag/analyze_query.py
from __future__ import annotations

from dataclasses import dataclass, field
import re


FACET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("weakness", re.compile(r"약점|약하|불리|weak", re.I)),
    ("resistance", re.compile(r"저항|반감|무효|버티|resist", re.I)),
    ("evolution", re.compile(r"진화|evol", re.I)),
    ("stats", re.compile(r"종족값|스탯|능력치|stats?", re.I)),
    ("type", re.compile(r"타입|type", re.I)),
    ("profile", re.compile(r"알려|정보|뭐야|누구", re.I)),
]

FOLLOWUP_RE = re.compile(r"^(그럼|그\s*포켓몬|걔|그건|또|그리고|그럼요|약점은|저항은|진화는)", re.I)


@dataclass(slots=True)
class QueryAnalysis:
    raw: str
    normalized: str
    facet: str = "profile"
    is_followup: bool = False
    compare: bool = False
    search_queries: list[str] = field(default_factory=list)


def analyze_query(text: str) -> QueryAnalysis:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    facet = "profile"
    for name, pattern in FACET_PATTERNS:
        if pattern.search(normalized):
            facet = name
            break
    compare = " vs " in normalized.lower() or "대" in normalized and "비교" in normalized
    queries = [normalized]
    if facet != "profile":
        queries.append(f"{normalized} {facet}")
    return QueryAnalysis(
        raw=text,
        normalized=normalized,
        facet=facet,
        is_followup=bool(FOLLOWUP_RE.search(normalized)),
        compare=compare,
        search_queries=queries[:3],
    )


def main() -> None:
    print(analyze_query("그럼 약점은?"))


if __name__ == "__main__":
    main()
