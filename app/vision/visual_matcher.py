from __future__ import annotations

from array import array
from contextlib import closing
from io import BytesIO
from pathlib import Path
import math
import sqlite3
from threading import Lock

from app.agents.pokedex_agent.tools.tool_local_dex import resolve_project_path
from app.config.settings import get_settings
from app.schemas.domain import ScanCandidate


MODEL_ID = "mediapipe-mobilenet-v3-small-float32"


class VisualDexMatcher:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        model_path: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.db_path = resolve_project_path(str(db_path or settings.dex_sqlite_path))
        self.model_path = resolve_project_path(
            str(model_path or settings.visual_embedding_model_path)
        )
        self._embedder = None
        self._lock = Lock()

    def is_available(self) -> bool:
        if not self.db_path.exists() or not self.model_path.exists():
            return False
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                row = conn.execute(
                    "select count(*) from visual_reference_embeddings where model_id = ?",
                    (MODEL_ID,),
                ).fetchone()
            return bool(row and int(row[0]) > 0)
        except sqlite3.Error:
            return False

    def reference_count(self) -> int:
        if not self.is_available():
            return 0
        with closing(sqlite3.connect(self.db_path)) as conn:
            return int(
                conn.execute(
                    "select count(*) from visual_reference_embeddings where model_id = ?",
                    (MODEL_ID,),
                ).fetchone()[0]
            )

    def match(self, image_bytes: bytes, *, top_k: int = 5) -> list[ScanCandidate]:
        if not image_bytes or not self.is_available():
            return []
        try:
            ranked = self._rank_rows(image_bytes, top_k=top_k)
        except (ImportError, RuntimeError, ValueError, OSError):
            return []
        return self._candidates_from_ranked(ranked)

    def match_with_diagnostics(
        self,
        image_bytes: bytes,
        *,
        top_k: int = 5,
    ) -> tuple[list[ScanCandidate], list[dict[str, object]]]:
        if not image_bytes or not self.is_available():
            return [], []
        ranked = self._rank_rows(image_bytes, top_k=top_k)
        return self._candidates_from_ranked(ranked), self._raw_rank_payload(ranked)

    def _candidates_from_ranked(
        self,
        ranked: list[tuple[float, sqlite3.Row]],
    ) -> list[ScanCandidate]:
        candidates: list[ScanCandidate] = []
        for similarity, row in ranked:
            confidence = _calibrate_similarity(similarity)
            if confidence < 0.08:
                continue
            candidates.append(
                ScanCandidate(
                    form_id=str(row["form_id"]),
                    pokemon_id=int(row["pokemon_id"]),
                    name_ko=str(row["name_ko"]),
                    name_en=str(row["name_en"]) if row["name_en"] else None,
                    form_name=str(row["form_name"]),
                    types=[
                        str(item)
                        for item in (row["type1"], row["type2"])
                        if item is not None and str(item)
                    ],
                    confidence=confidence,
                    visual_confidence=confidence,
                    matched_alias="derived_visual_embedding",
                    match_reason="visual_embedding",
                    evidence_sources=["visual_embedding"],
                )
            )
        return candidates

    def raw_rank(self, image_bytes: bytes, *, top_k: int = 5) -> list[dict[str, object]]:
        if not image_bytes or not self.is_available():
            return []
        ranked = self._rank_rows(image_bytes, top_k=top_k)
        return self._raw_rank_payload(ranked)

    def _raw_rank_payload(
        self,
        ranked: list[tuple[float, sqlite3.Row]],
    ) -> list[dict[str, object]]:
        return [
            {
                "form_id": str(row["form_id"]),
                "pokemon_id": int(row["pokemon_id"]),
                "similarity": round(float(similarity), 6),
            }
            for similarity, row in ranked
        ]

    def _rank_rows(
        self,
        image_bytes: bytes,
        *,
        top_k: int,
    ) -> list[tuple[float, sqlite3.Row]]:
        queries = self._embed_views(image_bytes)
        if not queries:
            return []
        rows = self._reference_rows()
        best_by_form: dict[str, tuple[float, sqlite3.Row]] = {}
        for row in rows:
            reference = array("f")
            reference.frombytes(row["embedding_blob"])
            compatible_queries = [query for query in queries if len(reference) == len(query)]
            if not compatible_queries:
                continue
            similarity = max(
                sum(a * b for a, b in zip(query, reference))
                for query in compatible_queries
            )
            current = best_by_form.get(str(row["form_id"]))
            if current is None or similarity > current[0]:
                best_by_form[str(row["form_id"])] = (similarity, row)
        return sorted(
            best_by_form.values(),
            key=lambda pair: -pair[0],
        )[: max(1, top_k)]

    def _embed_views(
        self,
        image_bytes: bytes,
        *,
        include_grid: bool = False,
    ) -> list[list[float]]:
        try:
            import mediapipe as mp
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            raise ImportError("Install the vision extra to enable visual matching") from exc

        with Image.open(BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            views = [rgb, *_center_square_views(rgb)]
            if include_grid:
                views.extend(_grid_square_views(rgb))

        embeddings: list[list[float]] = []
        with self._lock:
            if self._embedder is None:
                options = mp.tasks.vision.ImageEmbedderOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    l2_normalize=True,
                    quantize=False,
                )
                self._embedder = mp.tasks.vision.ImageEmbedder.create_from_options(options)
            for view in views:
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.asarray(view),
                )
                result = self._embedder.embed(mp_image)
                if not result.embeddings:
                    continue
                values = [float(item) for item in result.embeddings[0].embedding]
                norm = math.sqrt(sum(value * value for value in values))
                if norm > 0:
                    embeddings.append([value / norm for value in values])
        return embeddings

    def _reference_rows(self) -> list[sqlite3.Row]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                """
                select
                    v.form_id,
                    v.embedding_blob,
                    f.pokemon_id,
                    f.form_name,
                    f.type1,
                    f.type2,
                    s.name_ko,
                    s.name_en
                from visual_reference_embeddings v
                join pokemon_forms f on f.form_id = v.form_id
                join pokemon_species s on s.pokemon_id = f.pokemon_id
                where v.model_id = ? and s.generation = 1
                """,
                (MODEL_ID,),
            ).fetchall()

    def _embed(self, image_bytes: bytes) -> list[float]:
        embeddings = self._embed_views(image_bytes)
        return embeddings[0] if embeddings else []


def _center_square_views(image) -> list[object]:
    size = min(image.width, image.height)
    views: list[object] = []
    for fraction in (0.68, 0.56):
        side = max(1, int(size * fraction))
        left = max(0, (image.width - side) // 2)
        top = max(0, (image.height - side) // 2)
        views.append(image.crop((left, top, left + side, top + side)))
    return views


def _grid_square_views(image) -> list[object]:
    views: list[object] = []
    shortest = min(image.width, image.height)
    seen_boxes: set[tuple[int, int, int, int]] = set()
    for fraction in (0.50, 0.32):
        side = max(1, int(shortest * fraction))
        max_left = max(0, image.width - side)
        max_top = max(0, image.height - side)
        for top_ratio in (0.0, 0.5, 1.0):
            for left_ratio in (0.0, 0.5, 1.0):
                left = int(max_left * left_ratio)
                top = int(max_top * top_ratio)
                box = (left, top, left + side, top + side)
                if box not in seen_boxes:
                    seen_boxes.add(box)
                    views.append(image.crop(box))
    return views


def _calibrate_similarity(similarity: float) -> float:
    return round(min(1.0, max(0.0, (similarity - 0.35) / 0.6)), 4)


_VISUAL_MATCHER: VisualDexMatcher | None = None


def get_visual_matcher() -> VisualDexMatcher:
    global _VISUAL_MATCHER
    if _VISUAL_MATCHER is None:
        _VISUAL_MATCHER = VisualDexMatcher()
    return _VISUAL_MATCHER


def visual_runtime_status() -> dict[str, object]:
    matcher = get_visual_matcher()
    return {
        "engine": MODEL_ID,
        "available": matcher.is_available(),
        "reference_count": matcher.reference_count(),
        "scope": "generation_1_all_forms",
    }
