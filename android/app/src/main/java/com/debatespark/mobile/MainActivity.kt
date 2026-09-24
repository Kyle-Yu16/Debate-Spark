package com.debatespark.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Hub
import androidx.compose.material.icons.outlined.Key
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.Send
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

private val Ink = Color(0xFF242622)
private val Paper = Color(0xFFF8F6F0)
private val Lime = Color(0xFFD8F16A)
private val Purple = Color(0xFF65587D)
private val Pro = Color(0xFFD95D45)
private val Con = Color(0xFF416C78)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { DebateSparkApp() }
    }
}

@Composable
private fun DebateSparkApp(vm: DebateViewModel = viewModel()) {
    var screen by rememberSaveable { mutableStateOf("home") }
    var projectId by rememberSaveable { mutableStateOf<String?>(null) }
    val state = vm.state
    val project = state.projects.firstOrNull { it.id == projectId }
    val snackbars = remember { SnackbarHostState() }
    LaunchedEffect(state.message) { state.message?.let { snackbars.showSnackbar(it); vm.clearMessage() } }
    MaterialTheme(colorScheme = MaterialTheme.colorScheme.copy(primary = Ink, secondary = Purple, background = Paper)) {
        Scaffold(containerColor = Paper, snackbarHost = { SnackbarHost(snackbars) }) { padding ->
            when {
                screen == "settings" -> SettingsScreen(state.config, state.loading, { vm.saveConfig(it) }, { vm.testConnection {} }, { screen = "home" }, Modifier.padding(padding))
                project != null -> ProjectScreen(project, state.loading, { vm.prepare(project) }, { vm.debate(project, it) }, { projectId = null }, Modifier.padding(padding))
                else -> HomeScreen(state.projects, state.loading, { screen = "settings" }, { created -> projectId = created.id }, { vm.addProject(it.first, it.second) }, { vm.deleteProject(it) }, Modifier.padding(padding))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(projects: List<DebateProject>, loading: Boolean, onSettings: () -> Unit, onOpen: (DebateProject) -> Unit, onCreate: (Pair<String, String>) -> DebateProject, onDelete: (String) -> Unit, modifier: Modifier) {
    var showCreate by remember { mutableStateOf(false) }
    Column(modifier.fillMaxSize()) {
        TopAppBar(
            title = { BrandTitle() },
            actions = { IconButton(onClick = onSettings) { Icon(Icons.Outlined.Settings, "设置") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper)
        )
        LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxSize()) {
            item { Hero(onClick = { showCreate = true }) }
            item { Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 14.dp)) { Text("本机辩题库", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); Spacer(Modifier.weight(1f)); Text("${projects.size} 个项目", color = Color.Gray, style = MaterialTheme.typography.labelSmall) } }
            if (projects.isEmpty()) item { EmptyProjects() }
            items(projects, key = { it.id }) { project -> ProjectCard(project, { onOpen(project) }, { onDelete(project.id) }) }
        }
    }
    if (showCreate) CreateProjectDialog(onDismiss = { showCreate = false }, onConfirm = { topic, stance -> onOpen(onCreate(topic to stance)); showCreate = false })
}

@Composable private fun BrandTitle() = Row(verticalAlignment = Alignment.CenterVertically) {
    Box(Modifier.size(31.dp).background(Lime, RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Outlined.AutoAwesome, null, tint = Ink, modifier = Modifier.size(18.dp)) }
    Spacer(Modifier.width(9.dp)); Column { Text("观点火花", fontWeight = FontWeight.Bold); Text("DEBATE SPARK · LOCAL", style = MaterialTheme.typography.labelSmall, color = Color.Gray) }
}

@Composable private fun Hero(onClick: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = Ink), shape = RoundedCornerShape(22.dp)) {
    Column(Modifier.padding(23.dp)) {
        Text("让观点交锋，", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("让思想发光。", color = Lime, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp)); Text("备赛、攻防与复盘，都保存于你的手机。", color = Color(0xFFCFD0C9), style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(20.dp)); Button(onClick = onClick, colors = ButtonDefaults.buttonColors(containerColor = Lime, contentColor = Ink)) { Icon(Icons.Outlined.Add, null); Spacer(Modifier.width(5.dp)); Text("新建辩题") }
    }
}

@Composable private fun EmptyProjects() = Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(17.dp)) { Column(Modifier.fillMaxWidth().padding(30.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(Icons.Outlined.Hub, null, tint = Purple); Spacer(Modifier.height(8.dp)); Text("从一个辩题开始", fontWeight = FontWeight.Bold); Text("准备材料、训练对辩和历史记录均仅保存在本机。", color = Color.Gray, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 5.dp)) } }

@Composable private fun ProjectCard(project: DebateProject, onOpen: () -> Unit, onDelete: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen)) { Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(38.dp).background(if (project.stance == "正方") Color(0xFFF8E5DF) else Color(0xFFE1EEF0), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Text(project.stance.take(1), color = if (project.stance == "正方") Pro else Con, fontWeight = FontWeight.Bold) }; Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) { Text(project.topic, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis); Spacer(Modifier.height(4.dp)); Text("我持${project.stance} · ${if (project.preparation.isBlank()) "尚未备赛" else "已生成备赛材料"} · ${project.turns.size} 条发言", style = MaterialTheme.typography.labelSmall, color = Color.Gray) }; IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "删除", tint = Color.Gray) } } }

@Composable
private fun CreateProjectDialog(onDismiss: () -> Unit, onConfirm: (String, String) -> Unit) {
    var topic by remember { mutableStateOf("") }
    var stance by remember { mutableStateOf("正方") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建辩题") },
        text = {
            Column {
                Text("输入辩题后，即可生成备赛简报或直接开始自由辩论。", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(value = topic, onValueChange = { topic = it }, label = { Text("辩题") }, modifier = Modifier.fillMaxWidth().padding(top = 14.dp), minLines = 2)
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("正方", "反方").forEach { value ->
                        val selected = stance == value
                        val color = if (value == "正方") Pro else Con
                        Button(onClick = { stance = value }, colors = ButtonDefaults.buttonColors(containerColor = if (selected) color else Color(0xFFE9E6DE), contentColor = if (selected) Color.White else Ink)) { Text("我持$value") }
                    }
                }
            }
        },
        confirmButton = { Button(onClick = { onConfirm(topic, stance) }, enabled = topic.trim().length >= 4) { Text("创建") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProjectScreen(project: DebateProject, loading: Boolean, onPrepare: () -> Unit, onDebate: (String) -> Unit, onBack: () -> Unit, modifier: Modifier) {
    var tab by rememberSaveable(project.id) { mutableStateOf("prepare") }
    Column(modifier.fillMaxSize()) {
        TopAppBar(
            title = { Column { Text("自由辩论", style = MaterialTheme.typography.labelSmall, color = Purple); Text(project.topic, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) } },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Outlined.ArrowBack, "返回") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper)
        )
        Row(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            TabButton("备赛工作台", tab == "prepare") { tab = "prepare" }
            TabButton("人机对辩", tab == "debate") { tab = "debate" }
            TabButton("本地记录", tab == "history") { tab = "history" }
        }
        when (tab) {
            "prepare" -> PreparationPane(project, loading, onPrepare)
            "debate" -> DebatePane(project, loading, onDebate)
            else -> HistoryPane(project)
        }
    }
}

@Composable private fun TabButton(label: String, selected: Boolean, onClick: () -> Unit) = TextButton(onClick = onClick, colors = ButtonDefaults.textButtonColors(contentColor = if (selected) Color.White else Color(0xFF77746C)), modifier = Modifier.background(if (selected) Ink else Color.Transparent, RoundedCornerShape(22.dp))) { Text(label, style = MaterialTheme.typography.labelMedium) }

@Composable private fun PreparationPane(project: DebateProject, loading: Boolean, onPrepare: () -> Unit) = LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
    item { Card(colors = CardDefaults.cardColors(containerColor = if (project.stance == "正方") Color(0xFFF8E9E4) else Color(0xFFE5F0F2)), shape = RoundedCornerShape(16.dp)) { Row(Modifier.padding(15.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(34.dp).background(if (project.stance == "正方") Pro else Con, RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) { Text(project.stance.take(1), color = Color.White, fontWeight = FontWeight.Bold) }; Spacer(Modifier.width(11.dp)); Column { Text("你持${project.stance}", fontWeight = FontWeight.Bold); Text("双边论证会一并生成，避免只准备单方材料。", style = MaterialTheme.typography.bodySmall, color = Color.DarkGray) } } } }
    if (project.preparation.isBlank()) item { Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(18.dp)) { Column(Modifier.padding(25.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(Icons.Outlined.AutoAwesome, null, tint = Purple, modifier = Modifier.size(29.dp)); Spacer(Modifier.height(10.dp)); Text("还没有备赛材料", fontWeight = FontWeight.Bold); Text("将调用你配置的模型生成双边论证、攻防问题树和自由辩论弹药。模型无法核验的材料会明确标注。", style = MaterialTheme.typography.bodySmall, color = Color.Gray, modifier = Modifier.padding(top = 5.dp)); Spacer(Modifier.height(16.dp)); Button(onClick = onPrepare, enabled = !loading) { if (loading) CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp, color = Color.White) else Icon(Icons.Outlined.AutoAwesome, null); Spacer(Modifier.width(7.dp)); Text(if (loading) "正在编排…" else "生成备赛简报") } } } }
    else item { Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(18.dp)) { Column(Modifier.padding(18.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Text("备赛简报", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); Spacer(Modifier.weight(1f)); TextButton(onClick = onPrepare, enabled = !loading) { Text(if (loading) "更新中…" else "重新生成") } }; HorizontalDivider(Modifier.padding(vertical = 10.dp)); Text(project.preparation, style = MaterialTheme.typography.bodyMedium, lineHeight = MaterialTheme.typography.bodyMedium.lineHeight) } } }
}

@Composable
private fun DebatePane(project: DebateProject, loading: Boolean, onDebate: (String) -> Unit) {
    var text by rememberSaveable(project.id) { mutableStateOf("") }
    val agentStance = if (project.stance == "正方") "反方" else "正方"
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("你持${project.stance}", if (project.stance == "正方") Pro else Con)
            Pill("Agent 持$agentStance", Ink)
            Text("仅自由辩论", style = MaterialTheme.typography.labelSmall, color = Color.Gray, modifier = Modifier.align(Alignment.CenterVertically))
        }
        if (project.turns.isEmpty()) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Outlined.MoreHoriz, null, tint = Color.Gray)
                    Text("从第一轮观点开始", fontWeight = FontWeight.Bold)
                    Text("Agent 会抓住关键争点回应，并自然抛出下一层质疑。", style = MaterialTheme.typography.bodySmall, color = Color.Gray, modifier = Modifier.padding(top = 5.dp))
                }
            }
        } else {
            LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 9.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(project.turns, key = { it.id }) { turn -> TurnCard(turn, project.stance) }
            }
        }
        Surface(shadowElevation = 8.dp, color = Color.White) {
            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Bottom) {
                OutlinedTextField(value = text, onValueChange = { text = it }, enabled = !loading, label = { Text(if (loading) "对方 Agent 正在思考…" else "以${project.stance}身份发言") }, modifier = Modifier.weight(1f), maxLines = 4)
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = { onDebate(text); text = "" }, enabled = text.isNotBlank() && !loading, modifier = Modifier.background(Ink, RoundedCornerShape(12.dp))) {
                    if (loading) CircularProgressIndicator(Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp) else Icon(Icons.Outlined.Send, "发送", tint = Color.White)
                }
            }
        }
    }
}

@Composable private fun Pill(text: String, color: Color) = Surface(color = color, shape = RoundedCornerShape(20.dp)) { Text(text, color = Color.White, style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp)) }

@Composable private fun TurnCard(turn: DebateTurn, userStance: String) { val mine = turn.role == "user"; Card(colors = CardDefaults.cardColors(containerColor = if (mine) Color(0xFFECE9E0) else Color.White), shape = RoundedCornerShape(15.dp), modifier = Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp)) { Text(if (mine) "你 · $userStance" else "对方 Agent · ${if (userStance == "正方") "反方" else "正方"}", color = if (mine) Color.DarkGray else Purple, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold); Spacer(Modifier.height(6.dp)); Text(turn.content, style = MaterialTheme.typography.bodyMedium) } } }

@Composable private fun HistoryPane(project: DebateProject) = LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) { item { Text("本地记录", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); Text("以下内容仅保存于这台设备；卸载应用会删除它们。", style = MaterialTheme.typography.bodySmall, color = Color.Gray, modifier = Modifier.padding(top = 5.dp)) }; item { RecordRow("创建时间", java.text.DateFormat.getDateTimeInstance().format(java.util.Date(project.createdAt))) }; item { RecordRow("备赛状态", if (project.preparation.isBlank()) "尚未生成" else "已保存于本机") }; item { RecordRow("对辩发言", "${project.turns.size} 条") } }

@Composable private fun RecordRow(label: String, value: String) = Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(13.dp)) { Row(Modifier.fillMaxWidth().padding(15.dp)) { Text(label, color = Color.Gray); Spacer(Modifier.weight(1f)); Text(value, fontWeight = FontWeight.Medium) } }

@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun SettingsScreen(config: ApiConfig, loading: Boolean, onSave: (ApiConfig) -> Unit, onTest: () -> Unit, onBack: () -> Unit, modifier: Modifier) { var key by rememberSaveable { mutableStateOf(config.apiKey) }; var base by rememberSaveable { mutableStateOf(config.baseUrl) }; var model by rememberSaveable { mutableStateOf(config.model) }; Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) { TopAppBar(title = { Text("模型连接", fontWeight = FontWeight.Bold) }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Outlined.ArrowBack, "返回") } }, colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper)); Spacer(Modifier.height(12.dp)); Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFE8F0EE)), shape = RoundedCornerShape(16.dp)) { Row(Modifier.padding(15.dp)) { Icon(Icons.Outlined.Key, null, tint = Con); Spacer(Modifier.width(10.dp)); Text("兼容 OpenAI Chat Completions 的服务均可使用。API Key 使用 Android Keystore 加密后仅保存在本机。", style = MaterialTheme.typography.bodySmall) } }; OutlinedTextField(value = key, onValueChange = { key = it }, label = { Text("API Key") }, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), modifier = Modifier.fillMaxWidth().padding(top = 18.dp)); OutlinedTextField(value = base, onValueChange = { base = it }, label = { Text("Base URL") }, placeholder = { Text("https://api.openai.com/v1") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)); OutlinedTextField(value = model, onValueChange = { model = it }, label = { Text("Model") }, placeholder = { Text("gpt-4o-mini") }, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)); Text("可填写基础地址（应用会自动补全 /chat/completions），也可直接填写完整接口地址。", style = MaterialTheme.typography.labelSmall, color = Color.Gray, modifier = Modifier.padding(top = 7.dp)); Row(Modifier.fillMaxWidth().padding(top = 22.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) { Button(onClick = { onSave(ApiConfig(key, base, model)) }, modifier = Modifier.weight(1f)) { Text("保存到本机") }; Button(onClick = { onSave(ApiConfig(key, base, model)); onTest() }, enabled = !loading, colors = ButtonDefaults.buttonColors(containerColor = Purple), modifier = Modifier.weight(1f)) { if (loading) CircularProgressIndicator(Modifier.size(17.dp), color = Color.White, strokeWidth = 2.dp) else Text("测试连接") } } } }
