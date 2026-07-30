#!/usr/bin/env bash
set -euo pipefail

node --check app/ui/app.js
node --check app/ui/camera-quality.js
node --test tests/ui_camera_quality.test.cjs
uv run --extra vision python -m unittest discover -s tests -v
uv run --extra vision python scripts/build_local_dex/validate_dex.py \
  data/dex.sqlite \
  --fixtures fixtures/ocr/korean_cards.jsonl
uv run python scripts/build_local_dex/artifacts.py
uv run --extra vision python scripts/validate_visual_benchmark.py \
  data/vision/benchmark.json
uv run --extra vision python scripts/validate_field_benchmark.py
