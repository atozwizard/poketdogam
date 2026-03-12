#!/usr/bin/env python3
"""
요청 반영 메모(반드시 유지):
1) 목표가 `요구역량 추론 + 그래프 + VectorDB 근거추적`이면, 다중 산출물(5개)이 더 정합적이다.
2) 단일 파일이 I/O가 적어 보통 5~15% 내외로 조금 더 빠를 수 있다.
3) 단순 키워드 빈도만 필요하면 1개 파일이 적합하고,
   근거 청크/품질지표/관계형 추론이 필요하면 분리 산출물이 적합하다.
4) 운영 관점에서는 디렉토리 분리 관리가 권장된다.
   - outputs/word_freq
   - outputs/chunks
   - outputs/metrics
   - outputs/debug
   - outputs/specs
5) 기본 전략은 `기본 1개 파일 생성`, `--debug일 때만 분리 산출물 생성`이다.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

DEFAULT_WORD_FREQ_DIR = Path("app/agents/service_agent/data/outputs/word_freq")
DEFAULT_OUTPUT_ROOT = Path("app/agents/service_agent/data/outputs")


@dataclass
class CleaningConfig:
    max_chunk_chars: int = 420
    duplicate_similarity: float = 0.93
    min_token_len: int = 2
    keep_short_tokens: set[str] = field(default_factory=lambda: {"ai", "llm"})
    stopwords: set[str] = field(
        default_factory=lambda: {
            "the",
            "and",
            "or",
            "to",
            "of",
            "in",
            "for",
            "with",
            "on",
            "at",
            "a",
            "an",
            "is",
            "are",
            "be",
            "by",
            "as",
            "we",
            "our",
            "you",
            "your",
            "from",
            "more",
            "new",
            "about",
            "use",
            "now",
            "us",
            "learn",
            "try",
            "contact",
            "products",
            "solutions",
            "resources",
            "company",
            "support",
            "pricing",
            "apps",
            "blog",
            "events",
            "customers",
            "careers",
            "partners",
            "newsroom",
            "documentation",
            "privacy",
            "terms",
            "cookies",
            "allow",
            "decline",
        }
    )
    nav_line_patterns: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: (
            re.compile(
                r"^(products|solutions|resources|company|support|documentation)\s*$",
                re.I,
            ),
            re.compile(r"^(learn more|try now|try demo|contact sales|contact us)\s*$", re.I),
            re.compile(r"^(privacy policy|terms of use|subscribe to our newsletter)\s*$", re.I),
            re.compile(r"^title:\s*", re.I),
            re.compile(r"^description:\s*", re.I),
        )
    )
    synonym_map: dict[str, str] = field(
        default_factory=lambda: {
            "models": "model",
            "llms": "llm",
            "apis": "api",
            "responses": "response",
            "workflows": "workflow",
            "deployments": "deployment",
            "benchmarks": "benchmark",
            "improvements": "improvement",
            "services": "service",
            "tasks": "task",
        }
    )
    keyword_pattern: re.Pattern[str] = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|[가-힣]+|\d+[A-Za-z]*")


class TextCleaner:
    def __init__(self, config: CleaningConfig | None = None) -> None:
        self.cfg = config or CleaningConfig()

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\u00a0", " ")
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _line_signature(line: str) -> str:
        signature = line.lower().strip()
        signature = re.sub(r"[^a-z0-9가-힣 ]+", "", signature)
        signature = re.sub(r"\s+", " ", signature)
        return signature

    def _is_navigation_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if len(stripped) <= 2:
            return True
        return any(p.search(stripped) for p in self.cfg.nav_line_patterns)

    def _is_noise_token(self, token: str) -> bool:
        if "�" in token:
            return True
        if token.count("?") >= 1 and len(token) > 2:
            return True
        if re.search(r"[A-Za-z][가-힣]|[가-힣][A-Za-z]", token):
            return True
        if re.search(r"[^\w가-힣-]", token):
            return True
        return False

    def _near_duplicate(self, line: str, seen_signatures: list[str]) -> bool:
        sig = self._line_signature(line)
        for prev in seen_signatures[-40:]:
            if sig == prev:
                return True
            ratio = SequenceMatcher(None, sig, prev).ratio()
            if ratio >= self.cfg.duplicate_similarity:
                return True
        return False

    def _normalize_token(self, token: str) -> str:
        token = token.lower()
        return self.cfg.synonym_map.get(token, token)

    def _extract_tokens(self, text: str) -> list[str]:
        return self.cfg.keyword_pattern.findall(text)

    def clean(self, raw_text: str) -> dict:
        raw_lines = [self._normalize_unicode(x) for x in raw_text.splitlines()]
        raw_lines = [x for x in raw_lines if x]
        total_lines = len(raw_lines)

        kept_lines: list[str] = []
        seen_signatures: list[str] = []
        nav_removed = 0
        dup_removed = 0

        for line in raw_lines:
            if self._is_navigation_line(line):
                nav_removed += 1
                continue
            if self._near_duplicate(line, seen_signatures):
                dup_removed += 1
                continue
            kept_lines.append(line)
            seen_signatures.append(self._line_signature(line))

        cleaned_text = " ".join(kept_lines)
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        raw_tokens = self._extract_tokens(cleaned_text)
        total_tokens = len(raw_tokens)

        keyword_counter: Counter[str] = Counter()
        numeric_specs: Counter[str] = Counter()
        noise_tokens = 0
        dropped_stopword = 0
        dropped_short = 0

        for token in raw_tokens:
            if self._is_noise_token(token):
                noise_tokens += 1
                continue

            norm = self._normalize_token(token)

            if norm.isdigit():
                continue

            if re.fullmatch(r"\d+[a-zA-Z]+", norm):
                numeric_specs[norm] += 1
                continue

            if len(norm) < self.cfg.min_token_len and norm not in self.cfg.keep_short_tokens:
                dropped_short += 1
                continue

            if norm in self.cfg.stopwords:
                dropped_stopword += 1
                continue

            keyword_counter[norm] += 1

        chunks = self._make_chunks(cleaned_text, self.cfg.max_chunk_chars)

        nav_ratio = nav_removed / total_lines if total_lines else 0.0
        dup_ratio = dup_removed / total_lines if total_lines else 0.0
        noise_ratio = noise_tokens / total_tokens if total_tokens else 0.0

        return {
            "cleaned_text": cleaned_text,
            "cleaned_lines": kept_lines,
            "chunks": chunks,
            "keyword_freq": keyword_counter,
            "numeric_specs": numeric_specs,
            "stats": {
                "line_count_raw": total_lines,
                "line_count_kept": len(kept_lines),
                "line_removed_navigation": nav_removed,
                "line_removed_duplicate": dup_removed,
                "token_count_raw": total_tokens,
                "token_dropped_noise": noise_tokens,
                "token_dropped_stopword": dropped_stopword,
                "token_dropped_short": dropped_short,
                "keyword_count_unique": len(keyword_counter),
                "chunk_count": len(chunks),
                "nav_ratio": round(nav_ratio, 4),
                "dup_ratio": round(dup_ratio, 4),
                "noise_ratio": round(noise_ratio, 4),
            },
        }

    @staticmethod
    def _sentence_split(text: str) -> list[str]:
        if not text:
            return []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _make_chunks(self, text: str, max_chars: int) -> list[dict]:
        sentences = self._sentence_split(text)
        if not sentences:
            return []

        chunks: list[dict] = []
        buffer: list[str] = []
        idx = 1

        def flush() -> None:
            nonlocal idx
            if not buffer:
                return
            chunk_text = " ".join(buffer).strip()
            chunks.append(
                {
                    "chunk_id": f"ch{idx}",
                    "text": chunk_text,
                    "char_len": len(chunk_text),
                }
            )
            idx += 1
            buffer.clear()

        current_len = 0
        for sent in sentences:
            sent_len = len(sent) + 1
            if current_len + sent_len > max_chars and buffer:
                flush()
                current_len = 0
            buffer.append(sent)
            current_len += sent_len
        flush()
        return chunks


def _write_wordfreq_txt(counter: Counter[str], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{word}\t{count}" for word, count in counter.most_common()]
    output_file.write_text("\n".join(lines), encoding="utf-8")


def _write_debug_outputs(result: dict, input_path: Path, output_root: Path) -> None:
    stem = input_path.stem

    dirs = {
        "word_freq": output_root / "word_freq",
        "chunks": output_root / "chunks",
        "metrics": output_root / "metrics",
        "debug": output_root / "debug",
        "specs": output_root / "specs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    _write_wordfreq_txt(result["keyword_freq"], dirs["word_freq"] / f"{stem}-wordfreq.txt")
    (dirs["chunks"] / f"{stem}-chunks.json").write_text(
        json.dumps(result["chunks"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dirs["metrics"] / f"{stem}-stats.json").write_text(
        json.dumps(result["stats"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (dirs["debug"] / f"{stem}-cleaned.txt").write_text(result["cleaned_text"], encoding="utf-8")
    (dirs["specs"] / f"{stem}-numeric-specs.json").write_text(
        json.dumps(result["numeric_specs"].most_common(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HybridRAG 텍스트 정제 및 wordfreq 생성")
    parser.add_argument("--input", required=True, help="원본 파싱 텍스트 파일 경로")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_WORD_FREQ_DIR),
        help="기본 출력 디렉토리(wordfreq 1개 파일 저장)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="디버그 모드: outputs 하위 디렉토리로 분리 산출물 생성",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="디버그 모드 분리 출력 루트 디렉토리",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    cleaner = TextCleaner()

    raw = input_path.read_text(encoding="utf-8", errors="ignore")
    result = cleaner.clean(raw)

    if args.debug:
        output_root = Path(args.output_root)
        _write_debug_outputs(result, input_path, output_root)
        out_summary = {
            "mode": "debug",
            "output_root": str(output_root),
            "generated_dirs": ["word_freq", "chunks", "metrics", "debug", "specs"],
        }
    else:
        out_dir = Path(args.out_dir)
        output_file = out_dir / f"{input_path.stem}-wordfreq.txt"
        _write_wordfreq_txt(result["keyword_freq"], output_file)
        out_summary = {"mode": "single", "output_file": str(output_file)}

    print(
        json.dumps(
            {
                "input": str(input_path),
                **out_summary,
                "stats": result["stats"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
