import asyncio

from backend.app import agents
from backend.app.topic_playbooks import topic_playbook, topic_playbook_prompt


def test_all_exhibition_topics_have_playbooks():
    topics = [
        "大学生借助AI工具完成作业是否利大于弊",
        "当代年轻人是否应该优先追求稳定",
        "如果可以提前知道人生结局，我们是否应该选择知道？",
    ]
    for topic in topics:
        playbook = topic_playbook(topic)
        assert playbook is not None
        assert playbook["criterion"]
        assert len(playbook["traps"]) >= 3


def test_non_featured_topic_has_no_special_prompt():
    assert topic_playbook_prompt("电子书能否取代纸质书") == ""


def test_featured_prompt_and_short_response_contract_are_injected(monkeypatch):
    prompts = []

    async def fake_json(prompt, **kwargs):
        prompts.append(prompt)
        return {
            "speech": "效率提高不等于学习发生；如果学生无法独立解释作业中的关键步骤，AI只是把错误延后到考试或工作。请问对方，用什么可验证的评估区分辅助理解与替代思考？",
            "target": "AI提高完成效率",
            "tactic": "机制检验",
            "issue": "把效率当成学习成效",
            "explanation": "区分产出与能力内化。",
            "evidence_ids": [],
            "spark": "",
            "lens": "因果机制",
            "topic_link": "回答AI完成作业的长期利弊",
            "new_ground": "引入独立解释的验证条件",
            "used_example": "",
        }

    monkeypatch.setattr(agents.llm, "json", fake_json)
    topic = "大学生借助AI工具完成作业是否利大于弊"
    workspace = agents.demo_workspace(topic, "反方", [])
    result = asyncio.run(
        agents.generate_reply(
            topic,
            "反方",
            workspace,
            [],
            "AI可以让作业完成得更快。",
            "自由辩论",
            "赛事",
        )
    )
    assert result["speech"]
    assert "现场重点辩题护栏" in prompts[0]
    assert "一个质疑" in prompts[0]
    assert "90-150" in prompts[0]
    assert "不得超过170字" in prompts[0]
    assert "不得为压缩字数" in prompts[0]


def test_overlong_reply_is_rewritten_without_cutting_text(monkeypatch):
    calls = []
    base = {
        "target": "对方的关键质疑",
        "tactic": "直接回应",
        "issue": "因果跳跃",
        "explanation": "回答后追问。",
        "evidence_ids": [],
        "spark": "",
        "lens": "因果机制",
        "topic_link": "回到原题",
        "new_ground": "补充一项适用条件",
        "used_example": "",
    }

    async def fake_json(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return {**base, "speech": "这是完整句子。" * 30}
        return {
            **base,
            "speech": "我方直接回应核心质疑：局部可能性不能直接推出整体结论。必须说明该机制在主要场景中的强度与边界。请问对方，这一影响为何足以压过相反成本？",
        }

    monkeypatch.setattr(agents.llm, "json", fake_json)
    topic = "电子书能否取代纸质书"
    result = asyncio.run(
        agents.generate_reply(
            topic,
            "反方",
            agents.demo_workspace(topic, "反方", []),
            [],
            "电子书携带方便，所以必然取代纸质书。",
            "自由辩论",
            "赛事",
        )
    )
    assert len(calls) == 2
    assert "硬上限170字" in calls[1]
    assert len(result["speech"]) <= 170
    assert result["speech"].endswith("？")
