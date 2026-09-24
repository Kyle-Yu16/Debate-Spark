package com.debatespark.mobile

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

data class UiState(
    val config: ApiConfig = ApiConfig(),
    val projects: List<DebateProject> = emptyList(),
    val loading: Boolean = false,
    val message: String? = null
)

class DebateViewModel(application: Application) : AndroidViewModel(application) {
    private val store = LocalStore(application)
    private val client = OpenAiClient()
    var state by mutableStateOf(UiState(config = store.config(), projects = store.projects()))
        private set

    fun saveConfig(config: ApiConfig) {
        store.saveConfig(config)
        state = state.copy(config = config, message = "连接配置已安全保存在本机。")
    }

    fun testConnection(done: (Boolean) -> Unit) = runModelCall(done) {
        client.complete(state.config, "你是连接测试助手。只回复：连接成功", "请确认服务可用。")
    }

    fun addProject(topic: String, stance: String): DebateProject {
        val project = DebateProject(topic = topic.trim(), stance = stance)
        persist(listOf(project) + state.projects)
        return project
    }

    fun deleteProject(id: String) = persist(state.projects.filterNot { it.id == id })

    fun prepare(project: DebateProject) = runModelCall { result ->
        val prompt = """
            辩题：${project.topic}
            用户持方：${project.stance}

            请完成一份可直接用于中文辩论训练的备赛简报。你需要先完成辩题拆解，再构建正反双方最强论证；不能制造稻草人，不能捏造数据、论文、机构或链接。资料不足时明确标注“待核验”。

            用 Markdown 输出，且严格包含以下一级标题：
            # 辩题拆解
            # 双方全景
            # ${project.stance}方论证
            # 攻防问题树
            # 自由辩论弹药
            # 待核验材料

            每个论点要写明判断标准、逻辑链、适用边界与对方可能攻击。表达要短、具体、可口头使用。
        """.trimIndent()
        val system = "你是观点火花的备赛编排器。先有严谨论证，再追求表达；不把相关命题偷换成原辩题，不用华丽措辞掩盖论证缺口。"
        val updated = project.copy(preparation = client.complete(state.config, system, prompt), updatedAt = System.currentTimeMillis())
        replace(updated)
    }

    fun debate(project: DebateProject, userText: String) = runModelCall { result ->
        val userTurn = DebateTurn(role = "user", content = userText.trim())
        val history = (project.turns + userTurn).takeLast(10).joinToString("\n") {
            if (it.role == "user") "用户：${it.content}" else "Agent：${it.content}"
        }
        val agentStance = if (project.stance == "正方") "反方" else "正方"
        val prompt = """
            辩题：${project.topic}
            用户持${project.stance}，你持$agentStance。当前是自由辩论。
            备赛材料（只可作为内部依据，不得说“证据卡/S1/E1”）：
            ${project.preparation.ifBlank { "尚未生成备赛材料；只能就概念和逻辑交锋，不得伪造事实。" }}

            最近发言：
            $history

            只输出本轮口头发言，120—190 个汉字。先回应对方最关键的一点，再推进一个更有力的质疑或标准争夺。不要逐点罗列；不要使用“请回答”“请比较”“请说明”等命令式结尾。若提及事实材料，直接说出来源类型、内容及其限制；没有可靠材料则降低断言强度。
        """.trimIndent()
        val system = "你是一位严谨、自然、有攻击性的中文辩手。紧扣原辩题，绝不偷换论题；每轮只抓一个关键争点，不重复已说过的话。"
        val response = client.complete(state.config, system, prompt)
        replace(project.copy(turns = project.turns + userTurn + DebateTurn(role = "agent", content = response), updatedAt = System.currentTimeMillis()))
    }

    fun clearMessage() { state = state.copy(message = null) }

    private fun replace(project: DebateProject) = persist(state.projects.map { if (it.id == project.id) project else it })
    private fun persist(projects: List<DebateProject>) { store.saveProjects(projects); state = state.copy(projects = projects.sortedByDescending { it.updatedAt }) }

    private fun runModelCall(done: (Boolean) -> Unit = {}, action: suspend (String) -> Unit) {
        if (!state.config.ready) { state = state.copy(message = "请先完成模型连接设置。"); done(false); return }
        state = state.copy(loading = true, message = null)
        viewModelScope.launch {
            runCatching { action("") }.onSuccess { done(true) }.onFailure {
                state = state.copy(message = it.message ?: "请求失败，请检查网络和接口设置。")
                done(false)
            }
            state = state.copy(loading = false)
        }
    }
}
