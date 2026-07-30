package com.twentyflags.poketdogam

private val typeLabels = mapOf(
    "normal" to "노말",
    "fire" to "불꽃",
    "water" to "물",
    "electric" to "전기",
    "grass" to "풀",
    "ice" to "얼음",
    "fighting" to "격투",
    "poison" to "독",
    "ground" to "땅",
    "flying" to "비행",
    "psychic" to "에스퍼",
    "bug" to "벌레",
    "rock" to "바위",
    "ghost" to "고스트",
    "dragon" to "드래곤",
    "dark" to "악",
    "steel" to "강철",
    "fairy" to "페어리",
)

fun buildNarration(detail: DexDetail): String {
    val form = if (detail.formName == "base") "" else " ${detail.formName} 폼"
    val typeText = detail.types.joinToString("과 ") { typeLabels[it] ?: it }
    val weaknessText = detail.weaknesses
        .take(5)
        .joinToString(", ") { "${typeLabels[it.type] ?: it.type} ${formatMultiplier(it.multiplier)}배" }
        .ifBlank { "확인된 약점 정보 없음" }
    val evolutionText = detail.evolutions
        .take(3)
        .joinToString("; ") {
            val condition = it.triggerValue?.takeIf(String::isNotBlank)?.let { value -> ", 조건은 $value" } ?: ""
            "${it.fromName}에서 ${it.toName}${directionParticle(it.toName)}$condition"
        }
        .ifBlank { "현재 데이터에는 연결된 진화 정보 없음" }
    val bst = detail.stats["합계"]
    return buildString {
        append("${detail.nameKo}$form 정보를 읽는다-로. ")
        if (typeText.isNotBlank()) append("타입은 ${typeText}이다. ")
        append("약점은 ${weaknessText}다. ")
        append("진화 정보는 다음과 같다. ${evolutionText}. ")
        if (bst != null) append("종족값 합계는 ${bst}이다. ")
        append("화면에서 선택한 정확한 폼 기준이다-로.")
    }
}

private fun formatMultiplier(value: Double): String =
    if (value % 1.0 == 0.0) value.toInt().toString() else value.toString()

private fun directionParticle(value: String): String {
    val last = value.lastOrNull() ?: return "으로"
    if (last !in '가'..'힣') return "로"
    val jongseong = (last.code - '가'.code) % 28
    return if (jongseong == 0 || jongseong == 8) "로" else "으로"
}
