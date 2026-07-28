# Run: python app/agents/pokedex_agent/matching.py
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣ぁ-ゟァ-ヿ一-龯éÉ]+")
_KEEP_RE = re.compile(r"[^0-9a-z가-힣ぁ-ゟァ-ヿ一-龯]+")


@dataclass(frozen=True, slots=True)
class AliasMatch:
    form_id: str
    score: float
    matched_alias: str
    matched_variant: str
    reason: str


def normalize_match_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("é", "e")
    normalized = normalized.replace("pokemon", "포켓몬")
    normalized = _KEEP_RE.sub("", normalized)
    return normalized


def iter_query_variants(text: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()
    raw_parts = [text, *text.splitlines(), *_TOKEN_RE.findall(text)]

    for part in raw_parts:
        norm = normalize_match_text(part)
        if len(norm) < 2 or norm in seen:
            continue
        seen.add(norm)
        variants.append(norm)

    return variants


def similarity_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        shorter = min(len(left), len(right))
        longer = max(len(left), len(right))
        return max(0.88, shorter / longer)
    sequence_score = SequenceMatcher(None, left, right).ratio()
    edit_score = 1.0 - (_levenshtein(left, right) / max(len(left), len(right)))
    return max(sequence_score, edit_score)


def rank_aliases(
    raw_text: str,
    aliases: list[dict[str, str]],
    *,
    top_k: int = 3,
    threshold: float = 0.72,
) -> list[AliasMatch]:
    variants = iter_query_variants(raw_text)
    if not variants:
        return []

    best_by_form: dict[str, AliasMatch] = {}
    for alias in aliases:
        form_id = alias["form_id"]
        alias_text = alias["alias_text"]
        alias_norm = alias["alias_norm"]
        if not alias_norm:
            continue

        best_score = 0.0
        best_variant = ""
        best_reason = "fuzzy"
        for variant in variants:
            if variant == alias_norm:
                score = 1.0
                reason = "exact"
            elif alias_norm in variant:
                score = 0.96
                reason = "alias_in_ocr"
            elif variant in alias_norm and len(variant) >= 3:
                score = 0.9
                reason = "ocr_in_alias"
            else:
                score = similarity_score(variant, alias_norm)
                reason = "fuzzy"

            if score > best_score:
                best_score = score
                best_variant = variant
                best_reason = reason

        if best_score < threshold:
            continue

        current = best_by_form.get(form_id)
        if current is None or best_score > current.score:
            best_by_form[form_id] = AliasMatch(
                form_id=form_id,
                score=round(best_score, 4),
                matched_alias=alias_text,
                matched_variant=best_variant,
                reason=best_reason,
            )

    return sorted(best_by_form.values(), key=lambda item: item.score, reverse=True)[:top_k]


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def main() -> None:
    aliases = [
        {"form_id": "demo", "alias_text": "피카츄", "alias_norm": normalize_match_text("피카츄")},
    ]
    print(rank_aliases("피카추 HP 60", aliases))


if __name__ == "__main__":
    main()
