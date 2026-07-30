from __future__ import annotations

from dataclasses import dataclass

from app.schemas.domain import ScanCandidate


@dataclass(frozen=True, slots=True)
class FusionWeights:
    ocr: float
    visual: float


def fuse_candidates(
    ocr_candidates: list[ScanCandidate],
    visual_candidates: list[ScanCandidate],
    *,
    top_k: int = 3,
) -> list[ScanCandidate]:
    if not ocr_candidates and not visual_candidates:
        return []

    weights = _weights_for(ocr_candidates)
    merged: dict[str, ScanCandidate] = {}
    ocr_scores = {item.form_id: float(item.confidence) for item in ocr_candidates}
    visual_scores = {item.form_id: float(item.confidence) for item in visual_candidates}
    source_items = [*ocr_candidates, *visual_candidates]

    for item in source_items:
        if item.form_id in merged:
            continue
        ocr_score = ocr_scores.get(item.form_id, 0.0)
        visual_score = visual_scores.get(item.form_id, 0.0)
        if ocr_candidates and visual_candidates:
            confidence = weights.ocr * ocr_score + weights.visual * visual_score
        elif ocr_candidates:
            confidence = ocr_score
        else:
            confidence = visual_score
        evidence = []
        if ocr_score > 0:
            evidence.append("ocr")
        if visual_score > 0:
            evidence.append("visual_embedding")
        merged[item.form_id] = item.model_copy(
            update={
                "confidence": min(1.0, max(0.0, confidence)),
                "ocr_confidence": ocr_score or None,
                "visual_confidence": visual_score or None,
                "evidence_sources": evidence,
                "match_reason": "+".join(evidence) or item.match_reason,
            }
        )

    return sorted(
        merged.values(),
        key=lambda item: (
            -float(item.confidence),
            -float(item.ocr_confidence or 0.0),
            -float(item.visual_confidence or 0.0),
            int(item.pokemon_id or 0),
            item.form_id,
        ),
    )[: max(1, top_k)]


def _weights_for(ocr_candidates: list[ScanCandidate]) -> FusionWeights:
    if not ocr_candidates:
        return FusionWeights(ocr=0.0, visual=1.0)
    top = float(ocr_candidates[0].confidence)
    if top >= 0.9:
        return FusionWeights(ocr=0.75, visual=0.25)
    if top >= 0.72:
        return FusionWeights(ocr=0.55, visual=0.45)
    return FusionWeights(ocr=0.35, visual=0.65)

