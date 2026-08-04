# Visual embedding assets

- Runtime model: MediaPipe recommended MobileNetV3 Small image embedder.
- Model SHA-256: `bbbb4c51a55a53905af1daec995ca1aae355046f8839bb8c9f5ce9271394bc40`.
- PoC scope: base species across Generations 1–9. The committed generation
  indexes currently contain 4,969 derived reference embeddings for 1,025
  numbered species.
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
- Universal benchmark evidence has two different search modes. Generation-aided
  laboratory search reaches Top-3 91.80%, while the product-equivalent flat
  all-generation search reaches 69.63%. Only the latter may certify the default
  product path.
- The current benchmark evaluates one media kind, `in_game_transform`. The seven
  authorized corpus labels describe what the collection pipeline can accept;
  they are not seven evaluated accuracy domains.
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
  --species-search --allow-fan-pages --license-type all \
  --max-downloads 600 --max-per-species 8 --max-per-creator 8
uv run python scripts/review_field_photo_manifest.py \
  --reject 'SOURCE_ID=visual or privacy rejection reason'
uv run --extra vision python scripts/benchmark_field_photos.py
uv run --extra vision python scripts/benchmark_field_prototype_split.py
uv run --extra vision python scripts/validate_field_benchmark.py
```

Fan-page / collector photography is in scope when `--allow-fan-pages` is set:
Openverse queries include shelf/haul/collection terms, multi-species shelf
photos may take a primary species label from the title, and soft person/art
filters are relaxed only for that fan context. Child/cosplay terms still reject.
License and privacy review remain mandatory before `benchmark_eligible=true`.

Committed evidence, without the photographs:

- `field_collection.json`: open-license candidates after fan-page expansion;
  91 license-verified and privacy-reviewed samples; 28 species, 20 creators.
- `field_attribution.json`: source page, creator, license, expected species, and
  object type for every eligible sample.
- `field_benchmark.json`: current product-path field recall (regenerate with
  `rebuild_wild_accuracy_artifacts.sh`).
- `field_prototype_experiment.json`: deterministic train/test prototype split.
- `field_coverage_gap.json`: remaining gaps vs 151 species / 30 creators / 453
  samples (currently 123 species / 10 creators / 362 samples).
- `field_loo_physical_experiment.json`: 91-sample LOO physical-prototype upper
  bound for already covered species (Top-3 69.23%); it is not a field gate.

The product-path field benchmark is fused Top-3 9.89%. It exposes an
artwork-to-photograph domain gap; lowering the confidence threshold cannot fix
the ranking errors. The 90% Generation 1 claim remains
blocked until the benchmark covers all 151 species, at least 30 independent
creators, at least 453 samples, and a creator-disjoint test split. Cards retain
their separate 30-sample alpha and 100-sample MVP gates.

Sources:

- Openverse API: https://api.openverse.org/
- Openverse license-verification warning:
  https://docs.openverse.org/api/reference/made_with_ov.html
- Wikimedia Commons image metadata API:
  https://www.mediawiki.org/wiki/API:Imageinfo/en
