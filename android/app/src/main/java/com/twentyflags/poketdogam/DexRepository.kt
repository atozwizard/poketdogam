package com.twentyflags.poketdogam

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.io.FileOutputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.text.Normalizer
import org.json.JSONObject

data class DexCandidate(
    val formId: String,
    val pokemonId: Int,
    val nameKo: String,
    val formName: String,
    val types: List<String>,
    val confidence: Double = 0.0,
    val ocrConfidence: Double? = null,
    val visualConfidence: Double? = null,
    val evidence: List<String> = emptyList(),
)

data class TypeMatchup(
    val type: String,
    val multiplier: Double,
)

data class EvolutionSummary(
    val fromName: String,
    val toName: String,
    val triggerValue: String?,
)

data class DexDetail(
    val formId: String,
    val pokemonId: Int,
    val nameKo: String,
    val nameEn: String,
    val formName: String,
    val types: List<String>,
    val generation: Int,
    val recordStatus: String,
    val stats: Map<String, Int>,
    val weaknesses: List<TypeMatchup>,
    val evolutions: List<EvolutionSummary>,
)

class DexRepository(private val context: Context) {
    private val assetIntegrity = AssetIntegrity(context)
    private val database: SQLiteDatabase by lazy {
        val directory = File(context.filesDir, "dex").apply { mkdirs() }
        val target = File(directory, "dex.sqlite")
        val expectedHash = assetIntegrity.expectedSha256("dex.sqlite")
        if (!assetIntegrity.fileMatches("dex.sqlite", target)) {
            val temporary = File(directory, ".dex.sqlite.tmp")
            context.assets.open("dex.sqlite").use { source ->
                FileOutputStream(temporary).use { output ->
                    source.copyTo(output)
                    output.fd.sync()
                }
            }
            check(assetIntegrity.sha256(temporary) == expectedHash) { "Bundled Dex checksum mismatch" }
            try {
                Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING,
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,
                )
            }
        }
        SQLiteDatabase.openDatabase(target.path, null, SQLiteDatabase.OPEN_READONLY)
    }

    fun match(rawText: String, limit: Int = 5): List<DexCandidate> {
        val normalized = normalize(rawText)
        if (normalized.isBlank()) return emptyList()
        val tokens = normalized.chunkedWindowCandidates().ifEmpty { listOf(normalized) }
        val placeholders = tokens.joinToString(",") { "?" }
        val sql = """
            select distinct f.form_id, f.pokemon_id, s.name_ko, f.form_name, f.type1, f.type2,
                case
                    when a.alias_norm = ? then 100
                    when instr(?, a.alias_norm) > 0 then 90
                    else 70
                end as score
            from name_aliases a
            join pokemon_forms f on f.form_id = a.form_id
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            where a.alias_norm = ? or instr(?, a.alias_norm) > 0
                or a.alias_norm in ($placeholders)
            order by score desc, length(a.alias_norm) desc,
                case when f.form_name = 'base' then 0 else 1 end,
                f.pokemon_id, f.form_id
            limit ?
        """.trimIndent()
        val args = mutableListOf(normalized, normalized, normalized, normalized)
        args += tokens
        args += limit.toString()
        return database.rawQuery(sql, args.toTypedArray()).use { cursor ->
            buildList {
                while (cursor.moveToNext()) {
                    val score = cursor.getInt(6) / 100.0
                    add(
                        DexCandidate(
                            formId = cursor.getString(0),
                            pokemonId = cursor.getInt(1),
                            nameKo = cursor.getString(2),
                            formName = cursor.getString(3),
                            types = listOfNotNull(cursor.getString(4), cursor.getString(5)),
                            confidence = score,
                            ocrConfidence = score,
                            evidence = listOf("OCR"),
                        )
                    )
                }
            }
        }
    }

    fun candidate(formId: String, visualConfidence: Double): DexCandidate? {
        val sql = """
            select f.form_id, f.pokemon_id, s.name_ko, f.form_name, f.type1, f.type2
            from pokemon_forms f
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            where f.form_id = ?
        """.trimIndent()
        return database.rawQuery(sql, arrayOf(formId)).use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            DexCandidate(
                formId = cursor.getString(0),
                pokemonId = cursor.getInt(1),
                nameKo = cursor.getString(2),
                formName = cursor.getString(3),
                types = listOfNotNull(cursor.getString(4), cursor.getString(5)),
                confidence = visualConfidence,
                visualConfidence = visualConfidence,
                evidence = listOf("이미지"),
            )
        }
    }

    fun fuse(
        ocrCandidates: List<DexCandidate>,
        visualCandidates: List<DexCandidate>,
        limit: Int = 3,
    ): List<DexCandidate> {
        return CandidateRanker.fuse(ocrCandidates, visualCandidates, limit)
    }

    fun detail(formId: String): DexDetail? {
        val sql = """
            select f.form_id, f.pokemon_id, s.name_ko, s.name_en, f.form_name, f.type1, f.type2,
                s.generation, f.record_status, st.hp, st.attack, st.defense, st.sp_attack,
                st.sp_defense, st.speed, st.bst
            from pokemon_forms f
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            left join pokemon_stats st on st.form_id = f.form_id
            where f.form_id = ?
        """.trimIndent()
        return database.rawQuery(sql, arrayOf(formId)).use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            val types = listOfNotNull(cursor.getString(5), cursor.getString(6))
            DexDetail(
                formId = cursor.getString(0),
                pokemonId = cursor.getInt(1),
                nameKo = cursor.getString(2),
                nameEn = cursor.getString(3),
                formName = cursor.getString(4),
                types = types,
                generation = cursor.getInt(7),
                recordStatus = cursor.getString(8),
                stats = mapOf(
                    "HP" to cursor.getInt(9),
                    "공격" to cursor.getInt(10),
                    "방어" to cursor.getInt(11),
                    "특수공격" to cursor.getInt(12),
                    "특수방어" to cursor.getInt(13),
                    "스피드" to cursor.getInt(14),
                    "합계" to cursor.getInt(15),
                ),
                weaknesses = typeMatchups(types).filter { it.multiplier > 1.0 },
                evolutions = evolutions(formId),
            )
        }
    }

    private fun typeMatchups(defenseTypes: List<String>): List<TypeMatchup> {
        if (defenseTypes.isEmpty()) return emptyList()
        val multipliers = mutableMapOf<String, Double>()
        defenseTypes.forEach { defenseType ->
            database.rawQuery(
                "select attack_type, multiplier from type_chart where defense_type = ?",
                arrayOf(defenseType),
            ).use { cursor ->
                while (cursor.moveToNext()) {
                    val attackType = cursor.getString(0)
                    multipliers[attackType] =
                        (multipliers[attackType] ?: 1.0) * cursor.getDouble(1)
                }
            }
        }
        return multipliers
            .map { TypeMatchup(it.key, it.value) }
            .sortedWith(compareByDescending<TypeMatchup> { it.multiplier }.thenBy { it.type })
    }

    private fun evolutions(formId: String): List<EvolutionSummary> {
        val sql = """
            select source_species.name_ko, target_species.name_ko, e.trigger_value, e.condition_json
            from evolution_rules e
            join pokemon_forms source_form on source_form.form_id = e.from_form_id
            join pokemon_species source_species on source_species.pokemon_id = source_form.pokemon_id
            join pokemon_forms target_form on target_form.form_id = e.to_form_id
            join pokemon_species target_species on target_species.pokemon_id = target_form.pokemon_id
            where e.from_form_id = ? or e.to_form_id = ?
            order by source_species.pokemon_id, target_species.pokemon_id
        """.trimIndent()
        return database.rawQuery(sql, arrayOf(formId, formId)).use { cursor ->
            buildList {
                while (cursor.moveToNext()) {
                    add(
                        EvolutionSummary(
                            fromName = cursor.getString(0),
                            toName = cursor.getString(1),
                            triggerValue = evolutionCondition(
                                cursor.getString(2),
                                cursor.getString(3),
                            ),
                        )
                    )
                }
            }
        }
    }

    private fun evolutionCondition(triggerValue: String?, conditionJson: String?): String {
        val condition = runCatching { JSONObject(conditionJson ?: "{}") }.getOrDefault(JSONObject())
        val parts = buildList {
            condition.optString("region").takeIf { it.isNotBlank() }?.let {
                add("${regionLabels[it] ?: it.replace('-', ' ')} 지역")
            }
            condition.optString("item").takeIf { it.isNotBlank() }?.let {
                add("${itemLabels[it] ?: it.replace('-', ' ')} 사용")
            }
            condition.optString("held_item").takeIf { it.isNotBlank() }?.let {
                add("${itemLabels[it] ?: it.replace('-', ' ')} 지니기")
            }
            condition.optInt("min_level").takeIf { it > 0 }?.let { add("레벨 $it 이상") }
            condition.optInt("min_happiness").takeIf { it > 0 }?.let { add("친밀도 $it 이상") }
        }
        if (parts.isNotEmpty()) return parts.take(3).joinToString(", ")
        return when (triggerValue) {
            "level-up" -> "레벨업"
            "trade" -> "통신교환"
            "use-item" -> "진화 도구 사용"
            in itemLabels -> "${itemLabels[triggerValue]} 사용"
            else -> triggerValue?.replace('-', ' ').orEmpty()
        }
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value.lowercase(), Normalizer.Form.NFKC)
            .replace(Regex("[^0-9a-z가-힣ぁ-んァ-ン一-龯]"), "")

    private fun String.chunkedWindowCandidates(): List<String> =
        (2..minOf(length, 12))
            .flatMap { size -> windowed(size) }
            .distinct()
            .take(120)
}

private val itemLabels = mapOf(
    "thunder-stone" to "천둥의돌",
    "fire-stone" to "불꽃의돌",
    "water-stone" to "물의돌",
    "leaf-stone" to "리프의돌",
    "moon-stone" to "달의돌",
    "sun-stone" to "태양의돌",
    "shiny-stone" to "빛의돌",
    "dusk-stone" to "어둠의돌",
    "dawn-stone" to "각성의돌",
    "ice-stone" to "얼음의돌",
    "kings-rock" to "왕의징표석",
    "metal-coat" to "금속코트",
)

private val regionLabels = mapOf(
    "alola" to "알로라",
    "galar" to "가라르",
    "hisui" to "히스이",
    "paldea" to "팔데아",
)
