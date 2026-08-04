from __future__ import annotations

from array import array
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import NAMESPACE_URL, uuid5

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.vision.visual_matcher import MODEL_ID
from scripts.build_local_dex.normalize_dex import form_uuid
from scripts.build_local_dex.normalize_pokeapi import _form_name, _url_resource_id


MODEL_SHA256 = "bbbb4c51a55a53905af1daec995ca1aae355046f8839bb8c9f5ce9271394bc40"


def build_visual_index(
    *,
    db_path: Path,
    cache_dir: Path,
    model_path: Path,
    output_path: Path,
    generation: int | None = 1,
    max_workers: int = 10,
    augmentations: int = 4,
) -> dict[str, object]:
    _verify_model(model_path)
    generations = list(range(1, 11)) if generation is None else [generation]
    references: list[dict[str, object]] = []
    for gen in generations:
        references.extend(_reference_records(cache_dir, db_path, generation=gen))
    if not references:
        raise ValueError(f"no visual reference metadata found for generation {generation}")

    with tempfile.TemporaryDirectory(prefix="poketdogam-visual-") as temp_dir:
        temp = Path(temp_dir)
        downloaded = _download_references(references, temp, max_workers=max_workers)
        embedding_rows = _embed_references(
            downloaded,
            model_path,
            generation=generation if generation is not None else 0,
            augmentations=augmentations,
        )

    _persist_embeddings(db_path, embedding_rows, generation_scope=generation)
    _export_android_index(
        db_path,
        output_path,
        generation=generation if generation is not None else 0,
    )

    species_count = len({int(row["pokemon_id"]) for row in embedding_rows})
    form_count = len({str(row["form_id"]) for row in embedding_rows})
    return {
        "model_id": MODEL_ID,
        "model_sha256": MODEL_SHA256,
        "generation": generation,
        "species_count": species_count,
        "form_count": form_count,
        "reference_count": len(embedding_rows),
        "augmentations_per_sprite": augmentations,
        "output_path": str(output_path),
        "policy": "derived numeric embeddings only; source images are temporary and excluded",
    }


def _reference_records(
    cache_dir: Path,
    db_path: Path,
    *,
    generation: int,
) -> list[dict[str, object]]:
    generation_name = f"generation-{_roman(generation)}"
    with closing(sqlite3.connect(db_path)) as conn:
        valid_forms = {
            str(row[0])
            for row in conn.execute(
                """
                select f.form_id
                from pokemon_forms f
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where s.generation = ?
                """,
                (generation,),
            )
        }

    records: list[dict[str, object]] = []
    for species_path in sorted((cache_dir / "pokemon-species").glob("*.json")):
        species = json.loads(species_path.read_text(encoding="utf-8"))
        if (species.get("generation") or {}).get("name") != generation_name:
            continue
        pokemon_id = int(species["id"])
        seen_form_names: set[str] = set()
        for variety in species.get("varieties", []):
            if not isinstance(variety, dict):
                continue
            pokemon_ref = variety.get("pokemon")
            if not isinstance(pokemon_ref, dict):
                continue
            resource_id = _url_resource_id(str(pokemon_ref.get("url") or ""))
            resource_path = (
                cache_dir / "pokemon" / f"{resource_id}.json"
                if variety.get("is_default")
                else cache_dir / "pokemon-varieties" / f"{resource_id}.json"
            )
            if not resource_path.exists():
                continue
            pokemon = json.loads(resource_path.read_text(encoding="utf-8"))
            variety_name = str(pokemon.get("name") or pokemon_ref.get("name") or "")
            if variety.get("is_default"):
                form_name = "base"
            else:
                form_name = _form_name(str(species.get("name") or ""), variety_name)
                if not form_name or form_name in seen_form_names:
                    form_name = f"{form_name or 'variant'}-{resource_id}"
            seen_form_names.add(form_name)
            candidate_form_id = form_uuid(pokemon_id, form_name)
            if candidate_form_id not in valid_forms:
                continue
            # Prefer a single clean official-artwork (or home/sprite) source per form.
            # Extra shiny/home variants diluted Gen7–9 holdout ranking in review follow-up.
            source_urls = _sprite_source_urls(pokemon, include_shiny=False)
            if generation >= 7:
                source_urls = source_urls[:1]
            for source_url in source_urls:
                records.append(
                    {
                        "form_id": candidate_form_id,
                        "pokemon_id": pokemon_id,
                        "form_name": form_name,
                        "source_url": source_url,
                        "generation": generation,
                    }
                )
    return records


def _download_references(
    records: list[dict[str, object]],
    output_dir: Path,
    *,
    max_workers: int,
) -> list[dict[str, object]]:
    def download(record: dict[str, object]) -> dict[str, object]:
        url = str(record["source_url"])
        response = httpx.get(url, timeout=45.0, follow_redirects=True)
        response.raise_for_status()
        output_dir.mkdir(parents=True, exist_ok=True)
        digest = _sha256_text(url)[:16]
        path = output_dir / f"{record['form_id']}-{digest}.png"
        path.write_bytes(response.content)
        return {**record, "path": path}

    downloaded: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download, record) for record in records]
        for future in as_completed(futures):
            downloaded.append(future.result())
    return sorted(downloaded, key=lambda item: (int(item["pokemon_id"]), str(item["form_name"])))


def _embed_references(
    records: list[dict[str, object]],
    model_path: Path,
    *,
    generation: int,
    augmentations: int = 4,
) -> list[dict[str, object]]:
    try:
        import mediapipe as mp
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError as exc:
        raise RuntimeError("Run with `uv run --extra vision` to build visual embeddings") from exc

    options = mp.tasks.vision.ImageEmbedderOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        l2_normalize=True,
        quantize=False,
    )
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, object]] = []
    with mp.tasks.vision.ImageEmbedder.create_from_options(options) as embedder:
        for record in records:
            try:
                with Image.open(record["path"]) as source:
                    variants = _sprite_variants(source.convert("RGBA"), count=max(1, augmentations))
            except OSError:
                continue
            for variant_index, variant in enumerate(variants):
                result = embedder.embed(
                    mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=__import__("numpy").asarray(variant.convert("RGB")),
                    )
                )
                if not result.embeddings:
                    continue
                values = [float(value) for value in result.embeddings[0].embedding]
                norm = math.sqrt(sum(value * value for value in values))
                if norm <= 0:
                    continue
                normalized = array("f", (value / norm for value in values))
                source_url = str(record["source_url"])
                reference_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            f"poketdogam:visual:{MODEL_ID}:{record['form_id']}:"
                            f"{_sha256_text(source_url)}:aug{variant_index}"
                        ),
                    )
                )
                rows.append(
                    {
                        "reference_id": reference_id,
                        "form_id": str(record["form_id"]),
                        "pokemon_id": int(record["pokemon_id"]),
                        "model_id": MODEL_ID,
                        "embedding_blob": normalized.tobytes(),
                        "dimension": len(normalized),
                        "reference_kind": "temporary_source_to_derived_embedding",
                        "source_name": "pokeapi-sprite-metadata",
                        "source_url_sha256": _sha256_text(f"{source_url}:aug{variant_index}"),
                        "generation_scope": int(record.get("generation") or generation),
                        "created_at": built_at,
                    }
                )
    return rows


def _sprite_variants(image, *, count: int) -> list[object]:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    base = image.convert("RGBA")
    variants = [base.convert("RGB")]
    backgrounds = [
        (245, 245, 240),
        (36, 40, 48),
        (176, 150, 120),
        (72, 118, 84),
        (210, 180, 160),
        (120, 160, 200),
        (60, 60, 70),
        (230, 210, 190),
    ]
    for index, background in enumerate(backgrounds):
        if len(variants) >= count:
            break
        canvas = Image.new(
            "RGB",
            (max(base.width * 2, 320), max(base.height * 2, 320)),
            background,
        )
        scale = 0.38 + (index * 0.08)
        width = max(1, int(base.width * scale))
        height = max(1, int(base.height * scale))
        resized = base.resize((width, height), Image.Resampling.LANCZOS)
        angle = (-10 + (index * 3)) if index % 2 else (8 - index)
        rotated = resized.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        left = max(0, (canvas.width - rotated.width) // 2)
        top = max(0, (canvas.height - rotated.height) // 2)
        paste = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        paste.paste(rotated, (left, top), rotated)
        composed = canvas.convert("RGBA")
        composed.alpha_composite(paste)
        tinted = composed.convert("RGB")
        if index % 3 == 1:
            tinted = ImageEnhance.Brightness(tinted).enhance(0.8)
        if index % 3 == 2:
            tinted = ImageEnhance.Contrast(tinted).enhance(1.2).filter(
                ImageFilter.GaussianBlur(0.55)
            )
        variants.append(tinted)
    if len(variants) < count:
        variants.append(ImageEnhance.Brightness(base.convert("RGB")).enhance(0.72))
    if len(variants) < count:
        variants.append(
            ImageEnhance.Contrast(base.convert("RGB"))
            .enhance(1.28)
            .filter(ImageFilter.GaussianBlur(0.7))
        )
    if len(variants) < count:
        mirrored = ImageOps.mirror(base)
        canvas = Image.new(
            "RGB",
            (max(base.width * 2, 320), max(base.height * 2, 320)),
            (40, 44, 52),
        )
        width = max(1, int(base.width * 0.55))
        height = max(1, int(base.height * 0.55))
        resized = mirrored.resize((width, height), Image.Resampling.LANCZOS)
        left = (canvas.width - width) // 2
        top = (canvas.height - height) // 2
        canvas.paste(resized, (left, top), resized)
        variants.append(canvas)
    return variants[:count]


def _persist_embeddings(
    db_path: Path,
    rows: list[dict[str, object]],
    *,
    generation_scope: int | None,
) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("pragma foreign_keys = on")
        conn.execute(
            """
            create table if not exists visual_reference_embeddings (
                reference_id text primary key,
                form_id text not null references pokemon_forms(form_id),
                model_id text not null,
                embedding_blob blob not null,
                dimension integer not null,
                reference_kind text not null,
                source_name text not null,
                source_url_sha256 text not null,
                generation_scope integer not null,
                created_at text not null
            )
            """
        )
        if generation_scope is None or generation_scope == 0:
            conn.execute(
                """
                delete from visual_reference_embeddings
                where model_id = ?
                  and reference_kind = 'temporary_source_to_derived_embedding'
                """,
                (MODEL_ID,),
            )
        else:
            # Only replace temporary in-game derived refs for this generation.
            # Preserve open-license field photo embeddings.
            conn.execute(
                """
                delete from visual_reference_embeddings
                where model_id = ?
                  and generation_scope = ?
                  and reference_kind = 'temporary_source_to_derived_embedding'
                """,
                (MODEL_ID, int(generation_scope)),
            )
        columns = [
            "reference_id",
            "form_id",
            "model_id",
            "embedding_blob",
            "dimension",
            "reference_kind",
            "source_name",
            "source_url_sha256",
            "generation_scope",
            "created_at",
        ]
        conn.executemany(
            f"insert into visual_reference_embeddings ({','.join(columns)}) "
            f"values ({','.join('?' for _ in columns)})",
            [[row[column] for column in columns] for row in rows],
        )
        conn.commit()


def _export_android_index(db_path: Path, output_path: Path, *, generation: int) -> None:
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if generation == 0:
            rows = conn.execute(
                """
                select
                    v.form_id,
                    f.pokemon_id,
                    v.dimension,
                    v.embedding_blob
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                where v.model_id = ?
                order by f.pokemon_id, f.form_name, v.reference_id
                """,
                (MODEL_ID,),
            ).fetchall()
            scope = "all_generations_all_forms"
        else:
            rows = conn.execute(
                """
                select
                    v.form_id,
                    f.pokemon_id,
                    v.dimension,
                    v.embedding_blob
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                where v.model_id = ? and v.generation_scope = ?
                order by f.pokemon_id, f.form_name, v.reference_id
                """,
                (MODEL_ID, generation),
            ).fetchall()
            scope = f"generation_{generation}_all_forms"
    # Collapse to one embedding per form for Android payload size (best = first/clean sprite).
    unique_forms: dict[str, sqlite3.Row] = {}
    for row in rows:
        unique_forms.setdefault(str(row["form_id"]), row)
    collapsed = list(unique_forms.values())
    payload = {
        "schema_version": 1,
        "model_id": MODEL_ID,
        "model_sha256": MODEL_SHA256,
        "scope": scope,
        "reference_count": len(collapsed),
        "items": [
            {
                "form_id": str(row["form_id"]),
                "pokemon_id": int(row["pokemon_id"]),
                "dimension": int(row["dimension"]),
                "embedding_base64": base64.b64encode(row["embedding_blob"]).decode("ascii"),
            }
            for row in collapsed
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _preferred_sprite_url(pokemon: dict[str, object]) -> str:
    urls = _sprite_source_urls(pokemon)
    return urls[0] if urls else ""


def _sprite_source_urls(
    pokemon: dict[str, object],
    *,
    include_shiny: bool = False,
) -> list[str]:
    """Return distinct temporary source URLs (artwork/home/sprite) for embeddings."""
    sprites = pokemon.get("sprites") if isinstance(pokemon.get("sprites"), dict) else {}
    other = sprites.get("other") if isinstance(sprites.get("other"), dict) else {}
    artwork = (
        other.get("official-artwork")
        if isinstance(other.get("official-artwork"), dict)
        else {}
    )
    home = other.get("home") if isinstance(other.get("home"), dict) else {}
    candidates = [
        str(artwork.get("front_default") or ""),
        str(home.get("front_default") or ""),
        str(sprites.get("front_default") or ""),
    ]
    if include_shiny:
        candidates[1:1] = [str(artwork.get("front_shiny") or "")]
    urls: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if url.startswith("https://") and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _verify_model(model_path: Path) -> None:
    if not model_path.exists():
        raise FileNotFoundError(f"visual embedding model missing: {model_path}")
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        raise ValueError(f"visual embedding model checksum mismatch: {digest}")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _roman(value: int) -> str:
    numerals = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix", 10: "x"}
    if value not in numerals:
        raise ValueError(f"unsupported generation: {value}")
    return numerals[value]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/dex.sqlite")
    parser.add_argument("--cache-dir", default="data/raw/pokeapi")
    parser.add_argument("--model-path", default="data/vision/mobilenet_v3_small.tflite")
    parser.add_argument("--output-path", default="data/vision/gen1_visual_index.json")
    parser.add_argument("--generation", type=int, default=1)
    parser.add_argument("--all-generations", action="store_true")
    parser.add_argument("--augmentations", type=int, default=4)
    parser.add_argument("--max-workers", type=int, default=10)
    args = parser.parse_args()
    result = build_visual_index(
        db_path=PROJECT_ROOT / args.db_path,
        cache_dir=PROJECT_ROOT / args.cache_dir,
        model_path=PROJECT_ROOT / args.model_path,
        output_path=PROJECT_ROOT / args.output_path,
        generation=None if args.all_generations else args.generation,
        max_workers=args.max_workers,
        augmentations=args.augmentations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

