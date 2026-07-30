package com.twentyflags.poketdogam

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.util.Base64
import androidx.core.graphics.scale
import androidx.exifinterface.media.ExifInterface
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedder
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import kotlin.math.sqrt
import org.json.JSONObject

private data class VisualReference(
    val formId: String,
    val embedding: FloatArray,
)

class VisualMatcher(
    private val context: Context,
    private val repository: DexRepository,
) : AutoCloseable {
    private val assetIntegrity = AssetIntegrity(context)
    private val references: List<VisualReference> by lazy { loadReferences() }
    private var embedderInstance: ImageEmbedder? = null
    private fun getEmbedder(): ImageEmbedder {
        embedderInstance?.let { return it }
        assetIntegrity.requireVerified("mobilenet_v3_small.tflite")
        val baseOptions = BaseOptions.builder()
            .setModelAssetPath("mobilenet_v3_small.tflite")
            .build()
        val options = ImageEmbedder.ImageEmbedderOptions.builder()
            .setBaseOptions(baseOptions)
            .setL2Normalize(true)
            .setQuantize(false)
            .build()
        return ImageEmbedder.createFromOptions(context, options).also { embedderInstance = it }
    }

    fun match(imageFile: File, limit: Int = 5): List<DexCandidate> {
        val decoded = BitmapFactory.decodeFile(imageFile.path) ?: return emptyList()
        val oriented = orientBitmap(decoded, imageFile)
        val bitmap = downscaleForEmbedding(oriented).also {
            if (it !== oriented) oriented.recycle()
        }
        val views = imageViews(bitmap)
        val queries = try {
            views.mapNotNull { view ->
                val mpImage = BitmapImageBuilder(view).build()
                try {
                    getEmbedder().embed(mpImage)
                        .embeddingResult()
                        .embeddings()
                        .firstOrNull()
                        ?.floatEmbedding()
                } finally {
                    mpImage.close()
                }
            }
        } finally {
            views.filter { it !== bitmap }.forEach(Bitmap::recycle)
            bitmap.recycle()
        }
        val normalizedQueries = queries.mapNotNull { query ->
            val norm = l2Norm(query)
            if (norm == 0.0) null else FloatArray(query.size) { query[it] / norm.toFloat() }
        }
        if (normalizedQueries.isEmpty()) return emptyList()

        val bestByForm = mutableMapOf<String, Double>()
        references.forEach { reference ->
            val compatible = normalizedQueries.filter {
                reference.embedding.size == it.size
            }
            if (compatible.isNotEmpty()) {
                val score = compatible.maxOf { query ->
                    var dot = 0.0
                    for (index in query.indices) {
                        dot += query[index] * reference.embedding[index]
                    }
                    calibrate(dot)
                }
                if (score > (bestByForm[reference.formId] ?: Double.NEGATIVE_INFINITY)) {
                    bestByForm[reference.formId] = score
                }
            }
        }
        return bestByForm.entries
            .sortedByDescending { it.value }
            .filter { it.value >= 0.08 }
            .take(limit)
            .mapNotNull { (formId, score) -> repository.candidate(formId, score) }
    }

    override fun close() {
        embedderInstance?.close()
        embedderInstance = null
    }

    private fun loadReferences(): List<VisualReference> {
        val payload = JSONObject(
            String(
                assetIntegrity.readVerified("gen1_visual_index.json"),
                StandardCharsets.UTF_8,
            )
        )
        require(payload.getString("scope") == "generation_1_all_forms")
        val items = payload.getJSONArray("items")
        return buildList {
            for (index in 0 until items.length()) {
                val item = items.getJSONObject(index)
                val bytes = Base64.decode(item.getString("embedding_base64"), Base64.DEFAULT)
                val floats = ByteBuffer.wrap(bytes)
                    .order(ByteOrder.LITTLE_ENDIAN)
                    .asFloatBuffer()
                val embedding = FloatArray(floats.remaining())
                floats.get(embedding)
                add(VisualReference(item.getString("form_id"), embedding))
            }
        }.also {
            require(it.size == payload.getInt("reference_count"))
        }
    }

    private fun l2Norm(values: FloatArray): Double =
        sqrt(values.sumOf { value -> value.toDouble() * value.toDouble() })

    private fun imageViews(bitmap: Bitmap): List<Bitmap> = buildList {
        add(bitmap)
        val shortest = minOf(bitmap.width, bitmap.height)
        listOf(0.68, 0.56).forEach { fraction ->
            val side = (shortest * fraction).toInt().coerceAtLeast(1)
            val left = ((bitmap.width - side) / 2).coerceAtLeast(0)
            val top = ((bitmap.height - side) / 2).coerceAtLeast(0)
            add(Bitmap.createBitmap(bitmap, left, top, side, side))
        }
        listOf(0.50, 0.32).forEach { fraction ->
            val side = (shortest * fraction).toInt().coerceAtLeast(1)
            val maxLeft = (bitmap.width - side).coerceAtLeast(0)
            val maxTop = (bitmap.height - side).coerceAtLeast(0)
            listOf(0.0, 0.5, 1.0).forEach { topRatio ->
                listOf(0.0, 0.5, 1.0).forEach { leftRatio ->
                    val left = (maxLeft * leftRatio).toInt()
                    val top = (maxTop * topRatio).toInt()
                    add(Bitmap.createBitmap(bitmap, left, top, side, side))
                }
            }
        }
    }

    private fun downscaleForEmbedding(bitmap: Bitmap): Bitmap {
        val longest = maxOf(bitmap.width, bitmap.height)
        if (longest <= 1024) return bitmap
        val scale = 1024.0 / longest
        return bitmap.scale(
            (bitmap.width * scale).toInt().coerceAtLeast(1),
            (bitmap.height * scale).toInt().coerceAtLeast(1),
        )
    }

    private fun orientBitmap(bitmap: Bitmap, imageFile: File): Bitmap {
        val orientation = runCatching {
            ExifInterface(imageFile).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.preScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.preScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.preScale(-1f, 1f)
                matrix.postRotate(270f)
            }
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.preScale(-1f, 1f)
                matrix.postRotate(90f)
            }
            else -> return bitmap
        }
        return Bitmap.createBitmap(
            bitmap,
            0,
            0,
            bitmap.width,
            bitmap.height,
            matrix,
            true,
        ).also {
            if (it !== bitmap) bitmap.recycle()
        }
    }

    private fun calibrate(similarity: Double): Double =
        ((similarity + 1.0) / 2.0).coerceIn(0.0, 1.0)
}
