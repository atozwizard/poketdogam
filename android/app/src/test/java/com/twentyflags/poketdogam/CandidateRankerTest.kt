package com.twentyflags.poketdogam

import org.junit.Assert.assertEquals
import org.junit.Test

class CandidateRankerTest {
    @Test
    fun equalOcrScoresPreferBaseForm() {
        val special = candidate("special", "rock-star", 1.0)
        val base = candidate("base", "base", 1.0)

        val ranked = CandidateRanker.fuse(listOf(special, base), emptyList())

        assertEquals("base", ranked.first().formId)
    }

    @Test
    fun strongVisualEvidenceCanBeatWeakOcr() {
        val wrong = candidate("wrong", "base", 0.6)
        val visual = candidate("visual", "base", 0.95).copy(
            ocrConfidence = null,
            visualConfidence = 0.95,
            evidence = listOf("이미지"),
        )

        val ranked = CandidateRanker.fuse(listOf(wrong), listOf(visual))

        assertEquals("visual", ranked.first().formId)
        assertEquals(listOf("이미지"), ranked.first().evidence)
    }

    private fun candidate(formId: String, formName: String, score: Double) = DexCandidate(
        formId = formId,
        pokemonId = 25,
        nameKo = "피카츄",
        formName = formName,
        types = listOf("electric"),
        confidence = score,
        ocrConfidence = score,
        evidence = listOf("OCR"),
    )
}
