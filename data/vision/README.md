# Visual embedding assets

- Runtime model: MediaPipe recommended MobileNetV3 Small image embedder.
- Model SHA-256: `bbbb4c51a55a53905af1daec995ca1aae355046f8839bb8c9f5ce9271394bc40`.
- PoC scope: every Generation 1 species and form available in the normalized Dex.
- Reference media is downloaded only into a temporary build directory and is not
  included in the database, web runtime, Android assets, or Git.
- The committed index contains numeric embeddings, form IDs, model metadata, and
  hashed source URLs only.
- Runtime matching downsizes the input to at most 1024px and embeds the full
  frame, two centered square crops (68% and 56%), and eighteen position crops
  (50% and 32% on a 3x3 grid), then keeps the best score per form. Android also
  honors JPEG EXIF orientation before embedding.
- `benchmark.json` records a 238-form/714-query transformed holdout. Form
  recall@3 is 93.70% overall and at least 92.86% in every committed scenario.
  Run `uv run --extra vision python scripts/benchmark_visual_recognition.py` to
  regenerate it; temporary source and transformed images are discarded.
- The benchmark is a regression gate for indirect reference transforms, not a
  field-accuracy claim for physical toys, cards, or user camera samples.
- These derived embeddings remain restricted to noncommercial PoC evaluation.
  Product distribution requires the formal license and legal review gates.

## Open-license field pilot

The field pilot intentionally keeps raw photographs outside Git and application
assets. `collect_open_field_photos.py` searches Openverse for photographs with
licenses that permit modification, downloads bounded image files, removes EXIF
and embedded metadata, and rejects ambiguous labels. Openverse itself warns that
indexed license data must be independently verified, so
`review_field_photo_manifest.py` checks each original landing page for the
declared license URL and requires a human label/privacy review.

```bash
uv run --extra vision python scripts/collect_open_field_photos.py \
  --species-search --max-downloads 600 --max-per-species 8
uv run python scripts/review_field_photo_manifest.py \
  --reject 'SOURCE_ID=visual or privacy rejection reason'
uv run --extra vision python scripts/benchmark_field_photos.py
uv run --extra vision python scripts/benchmark_field_prototype_split.py
uv run --extra vision python scripts/validate_field_benchmark.py
```

Committed evidence, without the photographs:

- `field_collection.json`: 69 downloaded candidates; 68 license-verified and
  privacy-reviewed samples; 9 species, 5 creators; 67 figures/toys and 1 card.
- `field_attribution.json`: source page, creator, license, expected species, and
  object type for every eligible sample.
- `field_benchmark.json`: current 21-view product path. Fused species recall@3
  is 16.18% (11/68); raw visual recall@3 is 17.65% (12/68).
- `field_prototype_experiment.json`: deterministic 34-train/34-test,
  benchmark-only 21-crop prototype experiment. Recall@3 improves from 17.65%
  with indirect references to 79.41% with field prototypes, but only two test
  samples are creator-independent.

The result exposes an artwork-to-photograph domain gap; lowering the confidence
threshold cannot fix the ranking errors. The 90% Generation 1 claim remains
blocked until the benchmark covers all 151 species, at least 30 independent
creators, at least 453 samples, and a creator-disjoint test split. Cards retain
their separate 30-sample alpha and 100-sample MVP gates.

Sources:

- Openverse API: https://api.openverse.org/
- Openverse license-verification warning:
  https://docs.openverse.org/api/reference/made_with_ov.html
- Wikimedia Commons image metadata API:
  https://www.mediawiki.org/wiki/API:Imageinfo/en
