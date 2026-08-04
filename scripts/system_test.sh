#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== system test: quality gate =="
bash scripts/quality_gate.sh

echo "== system test: scoreboard =="
SCOREBOARD="$(mktemp -t poketdogam-scoreboard.XXXXXX)"
trap 'rm -f -- "$SCOREBOARD"' EXIT
uv run python scripts/evaluate_quality_score.py | tee "$SCOREBOARD"

uv run python - "$SCOREBOARD" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text())
print("mvp_engineering_go:", payload.get("mvp_engineering_go"))
print("system_test_authorized:", payload.get("system_test_authorized"))
print("wild_certified:", payload.get("wild_accuracy_certification", {}).get("certified"))
print(
    "product_open_search_certified:",
    payload.get("product_open_search_certification", {}).get("certified"),
)
print("all_species:", payload.get("all_species_coverage", {}).get("score"))
if not payload.get("mvp_engineering_go"):
    raise SystemExit("MVP engineering Go not met")
print("Engineering system-integration entry gate: PASS")
if payload.get("system_test_authorized"):
    print("Full product system authorization: PASS")
else:
    print(
        "Full product system authorization: HOLD "
        "(product open-search and/or physical-field gate below target)"
    )
PY

echo "== system test: API contracts =="
uv run --extra vision python - <<'PY'
from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app())
assert client.get("/health").status_code == 200
assert client.get("/").status_code == 200
ui = client.get("/").text
assert "카드명 영역" in ui
assert 'id="captureButton"' in ui
assert 'id="generationProgress"' in ui
assert 'id="productEvidence"' in ui
scan = client.post("/v1/scan/text", json={"ocr_text": "피카추", "filename": "system.txt"})
assert scan.status_code == 200
assert scan.json()["top_candidates"][0]["pokemon_id"] == 25
search = client.get("/v1/pokedex/search", params={"query": "이상해씨", "limit": 1})
assert search.status_code == 200
health = client.get("/health").json()
evidence = health["visual_recognition"]["recognition_evidence"]
assert evidence["product_open_search"]["generation_hint_used"] is False
assert evidence["generation_aided_lab"]["product_claimable"] is False
assert evidence["field_pilot"]["generation_wide_claimable"] is False
print("API and recognition-evidence contracts: PASS")
PY

echo "system_test.sh complete (execution PASS; release authorization is reported separately)"
