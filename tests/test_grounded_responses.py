import asyncio
import json

from backend.app import agents
from backend.app.evolution_memory import trajectory_experience


def test_shared_terms_do_not_force_a_new_topic_or_extra_request(monkeypatch):
    calls = []
    speech = "假设刚毕业的学生每月要付房租，转行期间谁支付生活费？我同意实习能增长能力，但可以先保留收入、利用周末试岗，等确认适合再辞职。这不是否认探索，而是避免一次失败迫使他欠债。"

    async def respond(prompt, **kwargs):
        calls.append(prompt)
        return {"speech": speech, "new_ground": "补上探索期间房租的支付方式", "spark": "一条没有出现在发言里的金句"}

    monkeypatch.setattr(agents.llm, "json", respond)
    topic = "年轻人是否应该优先追求稳定"
    transcript = [
        {"stance": "正方", "content": "每月要付房租，储蓄能覆盖房租就有缓冲。"},
        {"stance": "反方", "content": "每月要付房租并不妨碍年轻人尝试新工作。"},
        {"stance": "正方", "content": "每月要付房租是现实压力。"},
    ]
    result = asyncio.run(agents.generate_reply(topic, "正方", {}, transcript, transcript[1]["content"], "自由辩论", "赛事"))
    assert len(calls) == 1
    assert result["speech"] == speech
    assert result["spark"] == ""
    assert "不要求轮换视角或战术" in calls[0]
    assert "不能用一个故事证明所有人" in calls[0]


def test_spoken_reply_expands_evidence_ids_and_drops_command_templates(monkeypatch):
    calls = []

    async def respond(prompt, **kwargs):
        calls.append(prompt)
        return {
            "speech": "S1显示六成受访者遇到争议。请比较完成速度与长期能力，哪一个更重要？",
            "target": "把完成速度等同于学习收益",
            "tactic": "证据反驳",
            "issue": "评价维度缺失",
            "explanation": "补足来源并比较长期影响。",
            "evidence_ids": ["ev-1"],
            "spark": "",
            "lens": "时间尺度",
            "topic_link": "比较AI作业的长期利弊",
            "new_ground": "区分短期完成与长期能力",
            "used_example": "",
        }

    monkeypatch.setattr(agents.llm, "json", respond)
    topic = "大学生借助AI工具完成作业是否利大于弊"
    workspace = agents.demo_workspace(
        topic,
        "反方",
        [
            {
                "title": "大学生AI使用调查",
                "url": "https://example.edu/report",
                "domain": "某高校研究中心",
                "snippet": "调查显示部分学生面临学术争议。",
            }
        ],
    )
    workspace["evidence"][0]["date"] = "2025年"
    result = asyncio.run(
        agents.generate_reply(
            topic, "反方", workspace, [], "AI让作业完成得更快。", "自由辩论", "赛事"
        )
    )

    assert len(calls) == 1
    assert "S1" not in result["speech"]
    assert "请比较" not in result["speech"]
    assert "某高校研究中心" in result["speech"]
    assert "大学生AI使用调查" in result["speech"]
    assert "禁止使用“请回答”" in calls[0]
    assert "speech 中绝不能出现 S1" in calls[0]


def test_learning_keeps_opponents_challenge_and_own_response_together():
    row = {
        "candidate_stance": "反方", "outcome": "failure",
        "transcript": [
            {"stance": "正方", "content": "没存款时辞职，房租怎么办？"},
            {"stance": "反方", "content": "先在职试岗，验证以后再辞职。", "meta": {"new_ground": "区分探索与裸辞"}},
        ],
        "evaluation": {"highlights": [{"stance": "反方", "quote": "先在职试岗"}]},
    }
    experience = trajectory_experience(row)
    assert experience["outcome"] == "failure"
    assert experience["successful_patterns"]
    assert experience["exchanges"][0]["opponent"] == row["transcript"][0]["content"]
    assert experience["exchanges"][0]["new_ground"] == "区分探索与裸辞"


def test_revision_bounds_experience_input_without_extra_calls(monkeypatch):
    calls = []

    async def respond(prompt, **kwargs):
        calls.append(prompt)
        return {}

    monkeypatch.setattr(agents.llm, "json", respond)
    experiences = [{"outcome": "success" if i % 2 else "failure", "text": "案例" * 1800} for i in range(24)]
    asyncio.run(agents.propose_skill_revision({}, experiences, 1, "candidate-test"))
    assert len(calls) == 1
    payload = calls[0].split("复盘证据（有长度限制的节选，不是完整转录）：", 1)[1].split("\n\n要求：", 1)[0]
    assert len(payload) <= 20000
    records = json.loads(payload)
    assert {item["outcome"] for item in records} == {"success", "failure"}
