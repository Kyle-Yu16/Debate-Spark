import asyncio
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main
from backend.app import agents
from backend.app.settings import settings


def make_client():
    temp = tempfile.TemporaryDirectory()
    settings.database_path = Path(temp.name) / "test.db"
    client = TestClient(main.app)
    client.__test_temp = temp
    return client


def test_health_and_project_flow(monkeypatch):
    client = make_client()
    fake_workspace = {
        "topic": "人工智能是否让教育更公平", "stance": "正方",
        "analysis": {"keywords": ["公平"], "definitions": [], "conflicts": ["效率与公平"], "criterion": "机会改善", "burdens": {"正方": "证明改善", "反方": "证明恶化"}},
        "arguments": [], "evidence": [], "matrix": [], "insights": [],
        "drafts": {"立论": "测试立论", "攻辩": [], "自由辩论": [], "总结": "测试总结"}, "warnings": [],
    }

    async def fake_prepare(topic, stance):
        return {**fake_workspace, "topic": topic, "stance": stance}

    monkeypatch.setattr(main, "prepare_workspace", fake_prepare)
    with client:
        health = client.get("/api/health")
        assert health.status_code == 200
        created = client.post("/api/projects", json={"topic": "人工智能是否让教育更公平", "stance": "正方"})
        assert created.status_code == 200
        project_id = created.json()["id"]
        prepared = client.post(f"/api/projects/{project_id}/prepare")
        assert prepared.status_code == 200
        assert prepared.json()["analysis"]["criterion"] == "机会改善"
        exported = client.get(f"/api/projects/{project_id}/export")
        assert "测试立论" in exported.text
        debate = client.post("/api/debates", json={"project_id": project_id, "mode": "human", "user_stance": "正方", "difficulty": "标准"})
        assert debate.status_code == 200


def test_project_validation():
    client = make_client()
    with client:
        response = client.post("/api/projects", json={"topic": "短", "stance": "正方"})
        assert response.status_code == 422


def test_nested_model_workspace_is_normalized_before_reaching_ui(monkeypatch):
    client = make_client()
    malformed = {
        "analysis": {
            "keywords": ["稳定"],
            "definitions": [{"term": "稳定", "definition": "可预期性"}],
            "conflicts": [{"issue": "机会成本", "description": "稳定可能降低探索"}],
            "criterion": "长期福祉",
            "burdens": {"正方": {"必须证明": ["稳定可获得", "收益更大"]}, "反方": {"必须证明": ["不确定性更优"]}},
        },
        "arguments": [{"id": "A1", "stance": "正方", "title": "底座", "claim": "稳定降低焦虑", "warrant": "可持续积累", "evidence_ids": [], "status": "待核验"}],
        "evidence": [], "matrix": [], "insights": [],
        "drafts": {"立论": "测试", "攻辩": [], "自由辩论": [], "总结": "测试"}, "warnings": [],
    }

    async def fake_prepare(topic, stance):
        return malformed

    monkeypatch.setattr(main, "prepare_workspace", fake_prepare)
    with client:
        created = client.post("/api/projects", json={"topic": "当代年轻人是否应该追求稳定", "stance": "正方"}).json()
        workspace = client.post(f"/api/projects/{created['id']}/prepare").json()
        assert workspace["analysis"]["definitions"] == ["稳定：可预期性"]
        assert workspace["analysis"]["conflicts"] == ["机会成本：稳定可能降低探索"]
        assert isinstance(workspace["analysis"]["burdens"]["正方"], str)
        reopened = client.get(f"/api/projects/{created['id']}").json()["workspace"]
        assert reopened == workspace


def test_project_history_keeps_workspace_snapshots_and_debate_sessions(monkeypatch):
    client = make_client()
    workspace = {
        "topic": "年轻人是否应该追求稳定", "stance": "正方",
        "analysis": {"keywords": ["稳定"], "definitions": [], "conflicts": ["风险与积累"], "criterion": "长期发展", "burdens": {"正方": "证明稳定有利", "反方": "证明不稳定更优"}},
        "arguments": [], "evidence": [], "matrix": [], "insights": [],
        "drafts": {"立论": "初稿", "攻辩": [], "自由辩论": [], "总结": "总结"}, "warnings": [],
    }

    async def fake_prepare(topic, stance):
        return {**workspace, "topic": topic, "stance": stance}

    monkeypatch.setattr(main, "prepare_workspace", fake_prepare)
    with client:
        project = client.post("/api/projects", json={"topic": "年轻人是否应该追求稳定", "stance": "正方"}).json()
        project_id = project["id"]
        prepared = client.post(f"/api/projects/{project_id}/prepare").json()
        prepared["drafts"]["立论"] = "修改后的初稿"
        saved = client.patch(f"/api/projects/{project_id}/workspace", json={"workspace": prepared})
        assert saved.status_code == 200
        debate = client.post("/api/debates", json={"project_id": project_id, "mode": "human", "user_stance": "正方", "difficulty": "标准"})
        assert debate.status_code == 200

        history = client.get(f"/api/projects/{project_id}/history").json()
        assert [item["label"] for item in history["workspace_versions"]] == ["手动保存", "备赛完成"]
        assert history["debates"][0]["id"] == debate.json()["id"]
        assert history["debates"][0]["turn_count"] == 0

        original_id = history["workspace_versions"][-1]["id"]
        restored = client.post(f"/api/projects/{project_id}/history/{original_id}/restore")
        assert restored.status_code == 200
        assert restored.json()["drafts"]["立论"] == "初稿"


def test_delete_debate_and_project_cascade(monkeypatch):
    client = make_client()
    workspace = {
        "topic": "人工智能是否让教育更公平", "stance": "正方",
        "analysis": {"keywords": ["公平"], "definitions": [], "conflicts": ["效率与公平"], "criterion": "机会改善", "burdens": {"正方": "证明改善", "反方": "证明恶化"}},
        "arguments": [], "evidence": [], "matrix": [], "insights": [],
        "drafts": {"立论": "初稿", "攻辩": [], "自由辩论": [], "总结": "总结"}, "warnings": [],
    }

    async def fake_prepare(topic, stance):
        return {**workspace, "topic": topic, "stance": stance}

    monkeypatch.setattr(main, "prepare_workspace", fake_prepare)
    with client:
        project = client.post("/api/projects", json={"topic": "人工智能是否让教育更公平", "stance": "正方"}).json()
        project_id = project["id"]
        client.post(f"/api/projects/{project_id}/prepare")
        debate = client.post("/api/debates", json={"project_id": project_id, "mode": "human", "user_stance": "正方", "difficulty": "标准"})
        debate_id = debate.json()["id"]

        # 删除单场对辩：debate 及其 turns 均消失
        deleted = client.delete(f"/api/debates/{debate_id}")
        assert deleted.status_code == 200
        assert client.get(f"/api/debates/{debate_id}").status_code == 404
        history = client.get(f"/api/projects/{project_id}/history").json()
        assert history["debates"] == []

        # 删除整个辩题：项目、备赛历史一并清空
        second = client.post("/api/debates", json={"project_id": project_id, "mode": "arena", "user_stance": "正方", "difficulty": "赛事"}).json()
        assert client.delete(f"/api/projects/{project_id}").status_code == 200
        assert client.get(f"/api/projects/{project_id}").status_code == 404
        assert client.get(f"/api/debates/{second['id']}").status_code == 404
        assert client.get(f"/api/projects/{project_id}/history").status_code == 404


def test_reply_rewrites_repeated_example_and_keeps_original_topic(monkeypatch):
    calls = []
    repeated = {
        "speech": "米开朗基罗每一次落凿都是选择，所以选择就是创造。",
        "target": "选择是不是创造", "tactic": "标准争夺", "issue": "定义争议",
        "explanation": "继续讨论选择。", "evidence_ids": [], "spark": "选择就是创造。",
        "lens": "因果机制", "topic_link": "", "new_ground": "", "used_example": "米开朗基罗",
    }
    rewritten = {
        "speech": "原题要比较的是人工智能普及前后，人类持续提出新颖且有价值成果的能力是否提高。与其纠缠单次选择的名称，不如比较两条机制：工具降低试错成本会增加探索次数，但自动化依赖也可能削弱能力内化。正方需要证明前者的增益在长期仍大于后者，而不是证明某一次操作也能被叫作创造。",
        "target": "AI发展对人类创造能力的净影响", "tactic": "反事实基线", "issue": "因变量偷换",
        "explanation": "把定义支线拉回群体能力变化。", "evidence_ids": [], "spark": "名称之争不能替代能力变化的证明。",
        "lens": "反事实基线", "topic_link": "比较AI普及前后人类创造能力的净变化", "new_ground": "引入长期能力内化与试错成本的机制比较", "used_example": "",
    }

    async def fake_json(prompt, temperature=0.7):
        calls.append(prompt)
        return repeated if len(calls) == 1 else rewritten

    monkeypatch.setattr(agents.llm, "json", fake_json)
    transcript = [
        {"stance": "正方", "content": "米开朗基罗面对大理石的每一凿都是选择。", "meta": {"target": "选择是否属于创造"}},
        {"stance": "反方", "content": "米开朗基罗是在创造可能，用户只是在选择。", "meta": {"target": "米开朗基罗类比"}},
    ]
    workspace = agents.demo_workspace("人工智能的发展是否让人类变得更有创造力", "正方", [])
    result = asyncio.run(agents.generate_reply(
        "人工智能的发展是否让人类变得更有创造力", "正方", workspace, transcript,
        "选择本身当然也是创造。", "自由辩论", "赛事",
    ))
    assert len(calls) == 2
    assert "米开朗基罗" not in result["speech"]
    assert "人工智能" in result["speech"]
    assert result["new_ground"]
    assert result["novelty"] > 0.5
