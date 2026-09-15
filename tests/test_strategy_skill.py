import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.settings import settings
from backend.app.strategy_skill import DEFAULT_SKILL, normalize_skill, render_skill_markdown, skill_prompt


def make_client():
    temp = tempfile.TemporaryDirectory()
    settings.database_path = Path(temp.name) / "test.db"
    client = TestClient(main.app)
    client.__test_temp = temp
    return client


def test_skill_is_human_readable_and_preserves_invariants():
    skill = normalize_skill({
        "name": "测试 Skill",
        "lessons": [{"trigger": "出现单一例子", "action": "回到总体比较", "confidence": 0.8}],
    }, skill_id="skill-test", parent="baseline-v1")
    assert skill["invariants"] == DEFAULT_SKILL["invariants"]
    assert "出现单一例子" in skill_prompt(skill)
    markdown = render_skill_markdown(skill, {"status": "candidate", "games": 8, "topics": 2, "win_rate": 0.625})
    assert "# 测试 Skill" in markdown
    assert "置信度：80%" in markdown
    assert "候选得分率：62.5%" in markdown


def test_evolution_updates_skill_across_topics_and_iterations(monkeypatch):
    client = make_client()
    monkeypatch.setattr(settings, "api_key", "sk-test")
    monkeypatch.setattr(settings, "base_url", "https://llm.test/v1")
    monkeypatch.setattr(settings, "model", "test-model")
    workspace = {
        "topic": "人工智能是否提升创造力", "stance": "正方",
        "analysis": {"keywords": ["创造力"], "definitions": [], "conflicts": ["工具增益与能力依赖"], "criterion": "长期净影响", "burdens": {"正方": "证明提升", "反方": "证明未提升"}},
        "arguments": [], "evidence": [], "matrix": [], "insights": [],
        "drafts": {"立论": "初稿", "攻辩": [], "自由辩论": [], "总结": "总结"}, "warnings": [],
    }

    async def fake_prepare(topic, stance):
        return {**workspace, "topic": topic, "stance": stance}

    async def fake_revision(champion, experiences, iteration, skill_id):
        return normalize_skill({
            **champion,
            "name": "经验驱动 Skill",
            "version": f"1.{iteration}.0",
            "parent": "baseline-v1",
            "lessons": [{
                "trigger": f"第{iteration}轮发现对方偏离比较基线",
                "action": "要求连接原命题的净影响",
                "rationale": "子问题不能独立完成举证",
                "evidence": f"{len(experiences)}组跨辩题复盘",
                "confidence": 0.75,
            }],
        }, skill_id=skill_id, parent="baseline-v1")

    async def fake_speech(topic, stance, workspace, transcript, stage, strategy):
        return {"speech": f"{stance}回应{topic}", "target": "比较基线", "strategy_id": strategy["id"]}

    async def fake_judge(topic, transcript):
        candidate_turn = next(turn for turn in transcript if turn["meta"].get("strategy_id", "").startswith("skill_"))
        return {"winner": candidate_turn["stance"], "scores": {}, "missed_responses": ["需要更快回扣原题"], "highlights": []}

    monkeypatch.setattr(main, "prepare_workspace", fake_prepare)
    monkeypatch.setattr(main, "propose_skill_revision", fake_revision)
    monkeypatch.setattr(main, "arena_speech", fake_speech)
    monkeypatch.setattr(main, "evaluate_debate", fake_judge)

    with client:
        project = client.post("/api/projects", json={"topic": workspace["topic"], "stance": "正方"}).json()
        client.post(f"/api/projects/{project['id']}/prepare")
        response = client.post("/api/evolution/runs", json={
            "project_id": project["id"], "games": 2, "iterations": 2,
            "topics": ["年轻人是否应该追求稳定"],
        })
        assert response.status_code == 200
        result = response.json()
        assert result["aggregate_games"] == 8
        assert result["unique_topics"] == 2
        assert len(result["iteration_reports"]) == 2
        assert result["skill"]["version"] == "1.2.0"
        assert "第2轮" in result["skill_markdown"]
        assert result["promoted"] is False
        saved = client.get(f"/api/strategies/{result['candidate']}")
        assert saved.status_code == 200
        assert saved.json()["status"] == "candidate"
