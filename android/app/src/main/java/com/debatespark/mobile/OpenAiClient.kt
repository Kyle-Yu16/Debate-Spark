package com.debatespark.mobile

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class OpenAiClient {
    private val client = OkHttpClient.Builder().callTimeout(90, TimeUnit.SECONDS).build()

    suspend fun complete(config: ApiConfig, system: String, user: String): String = withContext(Dispatchers.IO) {
        require(config.ready) { "请先在设置中填写 API Key、Base URL 与模型名称。" }
        val endpoint = config.baseUrl.trimEnd('/').let {
            if (it.endsWith("/chat/completions")) it else "$it/chat/completions"
        }
        val messages = JSONArray()
            .put(JSONObject().put("role", "system").put("content", system))
            .put(JSONObject().put("role", "user").put("content", user))
        val body = JSONObject().put("model", config.model).put("messages", messages).put("temperature", 0.7)
        val request = Request.Builder().url(endpoint)
            .header("Authorization", "Bearer ${config.apiKey}")
            .header("Content-Type", "application/json")
            .post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
        client.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IllegalStateException("模型服务返回 ${response.code}：${errorMessage(raw)}")
            val content = JSONObject(raw).optJSONArray("choices")?.optJSONObject(0)
                ?.optJSONObject("message")?.optString("content").orEmpty()
            if (content.isBlank()) throw IllegalStateException("模型服务未返回可用内容。")
            content
        }
    }

    private fun errorMessage(raw: String): String = runCatching {
        JSONObject(raw).optJSONObject("error")?.optString("message") ?: raw.take(180)
    }.getOrDefault(raw.take(180))
}
