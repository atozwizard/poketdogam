#!/usr/bin/env bash
set -euo pipefail

node --check app/ui/app.js
uv run --extra vision python -m unittest discover -s tests -v
uv run --extra vision python scripts/build_local_dex/validate_dex.py \
  data/dex.sqlite \
  --fixtures fixtures/ocr/korean_cards.jsonl
uv run --extra vision python scripts/validate_visual_benchmark.py \
  data/vision/benchmark.json
uv run --extra vision python scripts/validate_field_benchmark.py
