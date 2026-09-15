from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SKILL: dict[str, Any] = {
    "schema_version": 1,
    "name": "稳健回应基础 Skill",
    "version": "1.0.0",
    "parent": None,
    "purpose": "在不偏离原辩题的前提下，选择最重要、最可证、最能推进比较的回应。",
    "invariants": [
        "任何定义、例子和类比都必须说明它如何改变原辩题的结论。",
        "不得编造事实、数据、论文或来源；证据不足时降低断言强度。",
        "新颖性只能加分，不能弥补相关性、逻辑或证据缺陷。",
        "优先回应对方最强且尚未回应的论点，不攻击无关措辞。",
    ],
    "decision_steps": [
        "提取对方的主张、依据、结论、问题和隐含前提。",
        "把对方发言映射回原辩题的判准和当前争点。",
        "识别最可能改变胜负且尚未充分回应的一个目标。",
        "生成直接反驳、追问、反例、让步反转、标准争夺等候选战术。",
        "按影响力、紧迫度、证据强度和理解成本选择战术。",
        "检查回扣原题、逻辑链、证据边界、重复度和阶段任务后再表达。",
    ],
    "tactics": [
        {"name": "比较基线", "when": "双方都在罗列利弊但没有共同尺度", "action": "明确现实反事实与净影响，再比较双方机制", "risk": "不能把有无个案当作总体净效应"},
        {"name": "举证责任追问", "when": "对方从可能性直接跳到结论", "action": "指出缺失的推理桥梁并要求可验证条件", "risk": "追问后必须说明该缺口为何影响胜负"},
        {"name": "让步反转", "when": "对方局部事实成立但不足以决定全局", "action": "承认局部事实，转而比较范围、强度和长期后果", "risk": "避免让步过宽"},
        {"name": "边界检验", "when": "对方使用绝对化规则", "action": "给出能暴露标准不一致的边界情形", "risk": "边界案例必须具有代表性或能证伪规则"},
    ],
    "lessons": [],
    "anti_patterns": [
        "连续依赖同一人物、故事、例子或类比。",
        "把‘某行为是否算作某概念’偷换成‘某因素是否提升该能力’。",
        "只改写措辞，没有新增机制、比较或证据。",
        "为了追求一句漂亮话牺牲准确性。",
    ],
    "highlight_principles": [
        "亮点句必须能映射到具体漏洞、论点或证据。",
        "先完成论证，再压缩表达；删除修辞后逻辑仍应成立。",
    ],
}


def _texts(value: Any, fallback: list[str], limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return deepcopy(fallback)
    result = [str(item).strip() for item in value if str(item).strip()]
    return result[:limit] or deepcopy(fallback)


def normalize_skill(raw: Any, *, skill_id: str = "baseline-v1", parent: str | None = None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    skill = deepcopy(DEFAULT_SKILL)
    skill.update({
        "id": skill_id,
        "name": str(data.get("name") or skill["name"]),
        "version": str(data.get("version") or skill["version"]),
        "parent": data.get("parent", parent),
        "purpose": str(data.get("purpose") or skill["purpose"]),
    })
    for key in ("invariants", "decision_steps", "anti_patterns", "highlight_principles"):
        skill[key] = _texts(data.get(key), skill[key])

    tactics = []
    for item in data.get("tactics", []):
        if isinstance(item, dict) and item.get("name"):
            tactics.append({key: str(item.get(key, "")).strip() for key in ("name", "when", "action", "risk")})
    if tactics:
        skill["tactics"] = tactics[:10]

    lessons = []
    seen_lessons = set()
    for item in data.get("lessons", []):
        if not isinstance(item, dict) or not item.get("trigger") or not item.get("action"):
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.6))))
        except (TypeError, ValueError):
            confidence = 0.6
        lesson_key = (str(item["trigger"]).strip(), str(item["action"]).strip())
        if lesson_key in seen_lessons:
            continue
        seen_lessons.add(lesson_key)
        lessons.append({
            "trigger": str(item["trigger"]).strip(),
            "action": str(item["action"]).strip(),
            "rationale": str(item.get("rationale", "")).strip(),
            "evidence": str(item.get("evidence", "")).strip(),
            "confidence": confidence,
        })
    skill["lessons"] = lessons[:12]
    return skill


def skill_prompt(skill: dict[str, Any]) -> str:
    skill = normalize_skill(skill, skill_id=str(skill.get("id", "strategy")))
    tactics = "\n".join(
        f"- {item['name']}｜触发：{item['when']}｜动作：{item['action']}｜风险：{item['risk']}"
        for item in skill["tactics"]
    )
    lessons = "\n".join(
        f"- 当{item['trigger']}时，{item['action']}。原因：{item['rationale']}（置信度{item['confidence']:.0%}）"
        for item in skill["lessons"]
    ) or "- 暂无经跨辩题验证的新增经验。"
    return f"""【当前辩论 Skill：{skill['name']} / {skill['version']}】
目标：{skill['purpose']}
不可变原则：
{chr(10).join(f'- {item}' for item in skill['invariants'])}
决策流程：
{chr(10).join(f'{index + 1}. {item}' for index, item in enumerate(skill['decision_steps']))}
可用战术：
{tactics}
经验证经验：
{lessons}
禁止模式：
{chr(10).join(f'- {item}' for item in skill['anti_patterns'])}
亮点原则：
{chr(10).join(f'- {item}' for item in skill['highlight_principles'])}"""


def render_skill_markdown(skill: dict[str, Any], metrics: dict[str, Any] | None = None) -> str:
    skill = normalize_skill(skill, skill_id=str(skill.get("id", "strategy")))
    metrics = metrics or {}
    lines = [
        "---", f"id: {skill['id']}", f"version: {skill['version']}",
        f"parent: {skill.get('parent') or 'null'}", f"status: {metrics.get('status', 'unknown')}", "---", "",
        f"# {skill['name']}", "", skill["purpose"], "", "## 不可变原则", "",
        *[f"- {item}" for item in skill["invariants"]], "", "## 决策流程", "",
        *[f"{index + 1}. {item}" for index, item in enumerate(skill["decision_steps"])], "", "## 战术手册", "",
    ]
    for tactic in skill["tactics"]:
        lines += [f"### {tactic['name']}", "", f"- 触发：{tactic['when']}", f"- 动作：{tactic['action']}", f"- 风险：{tactic['risk']}", ""]
    lines += ["## 经验证经验", ""]
    if skill["lessons"]:
        for index, lesson in enumerate(skill["lessons"], 1):
            lines += [f"### 经验 {index}", "", f"- 触发：{lesson['trigger']}", f"- 动作：{lesson['action']}", f"- 原因：{lesson['rationale']}", f"- 证据：{lesson['evidence']}", f"- 置信度：{lesson['confidence']:.0%}", ""]
    else:
        lines += ["尚无经跨辩题验证的新增经验。", ""]
    lines += ["## 失败模式", "", *[f"- {item}" for item in skill["anti_patterns"]], "", "## 亮点原则", "", *[f"- {item}" for item in skill["highlight_principles"]]]
    if metrics:
        lines += ["", "## 评测记录", "", f"- 对局：{metrics.get('games', 0)}", f"- 辩题数：{metrics.get('topics', 0)}", f"- 候选得分率：{metrics.get('win_rate', 0):.1%}"]
    return "\n".join(lines) + "\n"
