# Run: python app/agents/pokedex_agent/rag/embeddings.py
"""Offline hash embeddings (ThinkFlow dense channel substitute / RSLF offline-embed)."""

from __future__ import annotations

import hashlib
import math
import re


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def hash_embed(text: str, *, dim: int = 256) -> list[float]:
    vector = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[idx] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def main() -> None:
    left = hash_embed("피카츄 전기 타입")
    right = hash_embed("피카츄 약점")
    print({"dim": len(left), "cosine": round(cosine(left, right), 4)})


if __name__ == "__main__":
    main()
