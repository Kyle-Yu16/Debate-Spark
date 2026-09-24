package com.debatespark.mobile

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class ApiConfig(val apiKey: String = "", val baseUrl: String = "", val model: String = "") {
    val ready get() = apiKey.isNotBlank() && baseUrl.isNotBlank() && model.isNotBlank()
}

data class DebateTurn(
    val id: String = UUID.randomUUID().toString(),
    val role: String,
    val content: String,
    val createdAt: Long = System.currentTimeMillis()
) {
    fun toJson() = JSONObject().apply {
        put("id", id); put("role", role); put("content", content); put("createdAt", createdAt)
    }

    companion object {
        fun fromJson(json: JSONObject) = DebateTurn(
            json.optString("id", UUID.randomUUID().toString()),
            json.optString("role"), json.optString("content"), json.optLong("createdAt")
        )
    }
}

data class DebateProject(
    val id: String = UUID.randomUUID().toString(),
    val topic: String,
    val stance: String,
    val createdAt: Long = System.currentTimeMillis(),
    val preparation: String = "",
    val updatedAt: Long = createdAt,
    val turns: List<DebateTurn> = emptyList()
) {
    fun toJson() = JSONObject().apply {
        put("id", id); put("topic", topic); put("stance", stance); put("createdAt", createdAt)
        put("preparation", preparation); put("updatedAt", updatedAt)
        put("turns", JSONArray().apply { turns.forEach { put(it.toJson()) } })
    }

    companion object {
        fun fromJson(json: JSONObject): DebateProject {
            val turns = json.optJSONArray("turns") ?: JSONArray()
            return DebateProject(
                id = json.optString("id", UUID.randomUUID().toString()),
                topic = json.optString("topic"), stance = json.optString("stance", "正方"),
                createdAt = json.optLong("createdAt", System.currentTimeMillis()),
                preparation = json.optString("preparation"),
                updatedAt = json.optLong("updatedAt", System.currentTimeMillis()),
                turns = List(turns.length()) { DebateTurn.fromJson(turns.getJSONObject(it)) }
            )
        }
    }
}
