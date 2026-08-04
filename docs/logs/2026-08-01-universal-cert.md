# 2026-08-01 Universal recognition certification

## Scope expansion (collector president request)

1. Generations **1–9** (1025 species) for recognition corpus/certification.
2. Authorized media: in-game derived embeddings, user screenshots, plush,
   figures/goods, stickers, cards, fan-page photography.
3. Product UI still ships **zero official media files**; sprites/artwork are
   temporary build inputs → numeric embeddings only.
4. Scan default searches **all generations** via generation-scoped merge.

## Pipeline changes

- `scripts/benchmark_universal_recognition.py`
- `scripts/collect_open_field_photos.py --all-generations --allow-screenshots`
- `scripts/evaluate_quality_score.py` reads `universal_recognition_cert.json`
- `app/vision/visual_matcher.py` all-gen merge ranking
- Contribution ingest accepts Gen1–9 + sticker/goods/screenshot kinds

## Gates

| Requirement | Target |
|---|---|
| Species in derived corpus | 1025 |
| Recognizable samples | ≥1025 |
| Media kinds | ≥4 |
| Generation-scoped transform Top-3 | ≥90% |
| Score | ≥95 |

Open all-generation flat search remains a harder diagnostic and is reported
separately from certification.
