package com.twentyflags.poketdogam

import android.content.Context
import java.io.File
import java.security.MessageDigest
import org.json.JSONObject

class AssetIntegrity(private val context: Context) {
    private val metadata: JSONObject by lazy {
        context.assets.open("dex.meta.json").bufferedReader().use { reader ->
            JSONObject(reader.readText())
        }
    }
    private val verifiedAssets = mutableSetOf<String>()

    fun expectedSha256(name: String): String =
        metadata.getJSONObject("artifacts")
            .getJSONObject(name)
            .getString("sha256")

    fun readVerified(name: String): ByteArray {
        val bytes = context.assets.open(name).use { it.readBytes() }
        check(sha256(bytes) == expectedSha256(name)) { "Bundled $name checksum mismatch" }
        synchronized(verifiedAssets) { verifiedAssets += name }
        return bytes
    }

    fun requireVerified(name: String) {
        if (synchronized(verifiedAssets) { name in verifiedAssets }) return
        readVerified(name)
    }

    fun fileMatches(name: String, file: File): Boolean =
        file.exists() && sha256(file) == expectedSha256(name)

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().toHex()
    }

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).toHex()

    private fun ByteArray.toHex(): String =
        joinToString("") { byte -> "%02x".format(byte) }
}
