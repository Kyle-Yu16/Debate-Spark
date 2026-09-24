package com.debatespark.mobile

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores all user data on-device. The API key is AES-GCM encrypted with Android Keystore. */
class LocalStore(context: Context) {
    private val preferences = context.getSharedPreferences("debate_spark_local", Context.MODE_PRIVATE)
    private val keyAlias = "debate_spark_api_key"

    fun config(): ApiConfig = ApiConfig(
        apiKey = decrypt(preferences.getString("api_key", "") ?: ""),
        baseUrl = preferences.getString("base_url", "") ?: "",
        model = preferences.getString("model", "") ?: ""
    )

    fun saveConfig(config: ApiConfig) {
        preferences.edit()
            .putString("api_key", encrypt(config.apiKey))
            .putString("base_url", config.baseUrl.trim())
            .putString("model", config.model.trim())
            .apply()
    }

    fun projects(): List<DebateProject> = runCatching {
        val array = JSONArray(preferences.getString("projects", "[]"))
        List(array.length()) { DebateProject.fromJson(array.getJSONObject(it)) }.sortedByDescending { it.updatedAt }
    }.getOrDefault(emptyList())

    fun saveProjects(projects: List<DebateProject>) {
        val array = JSONArray().apply { projects.forEach { put(it.toJson()) } }
        preferences.edit().putString("projects", array.toString()).apply()
    }

    private fun secretKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build())
        }.generateKey()
    }

    private fun encrypt(value: String): String {
        if (value.isBlank()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, secretKey()) }
        val payload = cipher.iv + cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        return Base64.encodeToString(payload, Base64.NO_WRAP)
    }

    private fun decrypt(value: String): String = runCatching {
        if (value.isBlank()) return ""
        val payload = Base64.decode(value, Base64.NO_WRAP)
        val iv = payload.copyOfRange(0, 12)
        val ciphertext = payload.copyOfRange(12, payload.size)
        Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, iv))
        }.doFinal(ciphertext).toString(StandardCharsets.UTF_8)
    }.getOrDefault("")
}
