package com.twentyflags.poketdogam

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.text.Normalizer

data class DexCandidate(
    val formId: String,
    val pokemonId: Int,
    val nameKo: String,
    val formName: String,
    val types: List<String>,
)

data class DexDetail(
    val pokemonId: Int,
    val nameKo: String,
    val nameEn: String,
    val formName: String,
    val types: List<String>,
    val generation: Int,
    val stats: Map<String, Int>,
)

class DexRepository(private val context: Context) {
    private val database: SQLiteDatabase by lazy {
        val directory = File(context.filesDir, "dex").apply { mkdirs() }
        val target = File(directory, "dex.sqlite")
        if (!target.exists()) {
            context.assets.open("dex.sqlite").use { source ->
                target.outputStream().use(source::copyTo)
            }
        }
        SQLiteDatabase.openDatabase(target.path, null, SQLiteDatabase.OPEN_READONLY)
    }

    fun match(rawText: String, limit: Int = 3): List<DexCandidate> {
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
            order by score desc, length(a.alias_norm) desc, f.pokemon_id
            limit ?
        """.trimIndent()
        val args = mutableListOf(normalized, normalized, normalized, normalized)
        args += tokens
        args += limit.toString()
        return database.rawQuery(sql, args.toTypedArray()).use { cursor ->
            buildList {
                while (cursor.moveToNext()) {
                    add(
                        DexCandidate(
                            formId = cursor.getString(0),
                            pokemonId = cursor.getInt(1),
                            nameKo = cursor.getString(2),
                            formName = cursor.getString(3),
                            types = listOfNotNull(cursor.getString(4), cursor.getString(5)),
                        )
                    )
                }
            }
        }
    }

    fun detail(formId: String): DexDetail? {
        val sql = """
            select f.pokemon_id, s.name_ko, s.name_en, f.form_name, f.type1, f.type2, s.generation,
                st.hp, st.attack, st.defense, st.sp_attack, st.sp_defense, st.speed, st.bst
            from pokemon_forms f
            join pokemon_species s on s.pokemon_id = f.pokemon_id
            left join pokemon_stats st on st.form_id = f.form_id
            where f.form_id = ?
        """.trimIndent()
        return database.rawQuery(sql, arrayOf(formId)).use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            DexDetail(
                pokemonId = cursor.getInt(0),
                nameKo = cursor.getString(1),
                nameEn = cursor.getString(2),
                formName = cursor.getString(3),
                types = listOfNotNull(cursor.getString(4), cursor.getString(5)),
                generation = cursor.getInt(6),
                stats = mapOf(
                    "HP" to cursor.getInt(7),
                    "공격" to cursor.getInt(8),
                    "방어" to cursor.getInt(9),
                    "특수공격" to cursor.getInt(10),
                    "특수방어" to cursor.getInt(11),
                    "스피드" to cursor.getInt(12),
                    "합계" to cursor.getInt(13),
                ),
            )
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
