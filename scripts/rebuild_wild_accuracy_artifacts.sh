#!/usr/bin/env bash
# Rebuild wild-accuracy artifacts after new field photos are reviewed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv run python scripts/export_field_coverage_gap.py
uv run python scripts/review_field_photo_manifest.py --reuse-existing-license-review || \
  uv run python scripts/review_field_photo_manifest.py
uv run --extra vision python scripts/build_physical_field_index.py
uv run python - <<'PY'
from pathlib import Path
from scripts.build_local_dex.artifacts import attach_artifact_manifest
root = Path('.').resolve()
attach_artifact_manifest(
    root / 'data' / 'dex.meta.json',
    {
        'dex.sqlite': root / 'data' / 'dex.sqlite',
        'gen1_visual_index.json': root / 'data' / 'vision' / 'gen1_visual_index.json',
        'mobilenet_v3_small.tflite': root / 'data' / 'vision' / 'mobilenet_v3_small.tflite',
    },
)
print('artifact manifest refreshed')
PY
uv run --extra vision python scripts/benchmark_field_loo_physical.py
uv run --extra vision python scripts/benchmark_field_photos.py
uv run python scripts/evaluate_quality_score.py | tee /tmp/poketdogam-wild-progress.json
python3 - <<'PY'
import json
from pathlib import Path
d=json.loads(Path('/tmp/poketdogam-wild-progress.json').read_text())
wild=d['wild_accuracy_certification']
print('wild_score', wild['score'], 'certified', wild['certified'])
print('coverage_gap', wild['coverage_gap'])
print('loo', wild.get('loo_physical_recall_at_3'))
print('mvp', d['mvp_engineering_go'])
PY
