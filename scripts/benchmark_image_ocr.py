from __future__ import annotations

from pathlib import Path
import argparse
import json
import platform
import subprocess
import tempfile
import time

from app.agents.pokedex_agent.tools.tool_local_dex import LocalDexStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def benchmark(fixture_path: Path, *, limit: int = 30) -> dict[str, object]:
    if platform.system() != "Darwin":
        raise RuntimeError("The synthetic Vision benchmark currently requires macOS.")

    fixtures = [
        json.loads(line)
        for line in fixture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][:limit]
    store = LocalDexStore()
    matched = 0
    latencies = []
    failures = []

    with tempfile.TemporaryDirectory(prefix="poketdogam-ocr-bench-") as temp_dir:
        temp = Path(temp_dir)
        renderer = temp / "render-fixture"
        recognizer = temp / "vision-ocr"
        _compile(PROJECT_ROOT / "scripts/render_ocr_fixture.swift", renderer)
        _compile(PROJECT_ROOT / "scripts/ocr_macos_vision.swift", recognizer)

        for index, fixture in enumerate(fixtures):
            text_path = temp / f"{index}.txt"
            image_path = temp / f"{index}.png"
            text_path.write_text(str(fixture["ocr_text"]), encoding="utf-8")
            subprocess.run([renderer, text_path, image_path], check=True, capture_output=True)
            started = time.perf_counter()
            result = subprocess.run([recognizer, image_path], check=True, capture_output=True)
            latency_ms = (time.perf_counter() - started) * 1000
            latencies.append(latency_ms)
            ocr_text = result.stdout.decode("utf-8", errors="replace").strip()
            candidates = store.match_name(ocr_text, top_k=3)
            candidate_ids = [candidate.pokemon_id for candidate in candidates]
            expected_id = int(fixture["expected_pokemon_id"])
            if expected_id in candidate_ids:
                matched += 1
            else:
                failures.append(
                    {
                        "id": fixture["id"],
                        "expected_pokemon_id": expected_id,
                        "candidate_ids": candidate_ids,
                        "ocr_text": ocr_text,
                    }
                )

    ordered = sorted(latencies)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {
        "benchmark_scope": "synthetic_rendered_images_not_physical_cards",
        "fixture_count": len(fixtures),
        "matched_at_3": matched,
        "ocr_match_recall_at_3": matched / len(fixtures) if fixtures else 0.0,
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95": round(ordered[p95_index], 2) if ordered else 0.0,
        },
        "failures": failures,
    }


def _compile(source: Path, output: Path) -> None:
    subprocess.run(["swiftc", source, "-o", output], check=True, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="fixtures/ocr/korean_cards.jsonl")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    result = benchmark(PROJECT_ROOT / args.fixtures, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
