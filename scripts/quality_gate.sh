#!/usr/bin/env bash
set -euo pipefail

node --check app/ui/app.js
uv run python -m unittest discover -s tests -v
uv run python scripts/build_local_dex/validate_dex.py \
  data/dex.sqlite \
  --fixtures fixtures/ocr/korean_cards.jsonl
