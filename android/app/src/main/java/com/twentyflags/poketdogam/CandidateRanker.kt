package com.twentyflags.poketdogam

object CandidateRanker {
    fun fuse(
        ocrCandidates: List<DexCandidate>,
        visualCandidates: List<DexCandidate>,
        limit: Int = 3,
    ): List<DexCandidate> {
        if (ocrCandidates.isEmpty() && visualCandidates.isEmpty()) return emptyList()
        val topOcr = ocrCandidates.firstOrNull()?.confidence ?: 0.0
        val (ocrWeight, visualWeight) = when {
            ocrCandidates.isEmpty() -> 0.0 to 1.0
            visualCandidates.isEmpty() -> 1.0 to 0.0
            topOcr >= 0.9 -> 0.75 to 0.25
            topOcr >= 0.72 -> 0.55 to 0.45
            else -> 0.35 to 0.65
        }
        val ocrByForm = ocrCandidates.associateBy { it.formId }
        val visualByForm = visualCandidates.associateBy { it.formId }
        return (ocrByForm.keys + visualByForm.keys)
            .mapNotNull { formId ->
                val ocr = ocrByForm[formId]
                val visual = visualByForm[formId]
                val base = ocr ?: visual ?: return@mapNotNull null
                val ocrScore = ocr?.confidence
                val visualScore = visual?.confidence
                base.copy(
                    confidence = (ocrWeight * (ocrScore ?: 0.0) +
                        visualWeight * (visualScore ?: 0.0)).coerceIn(0.0, 1.0),
                    ocrConfidence = ocrScore,
                    visualConfidence = visualScore,
                    evidence = buildList {
                        if (ocrScore != null) add("OCR")
                        if (visualScore != null) add("이미지")
                    },
                )
            }
            .sortedWith(
                compareByDescending<DexCandidate> { it.confidence }
                    .thenByDescending { it.ocrConfidence ?: 0.0 }
                    .thenByDescending { it.visualConfidence ?: 0.0 }
                    .thenBy { it.formName != "base" }
                    .thenBy { it.pokemonId }
                    .thenBy { it.formId }
            )
            .take(limit.coerceAtLeast(1))
    }
}
