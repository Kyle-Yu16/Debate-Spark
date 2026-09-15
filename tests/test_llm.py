import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from backend.app import agents
from backend.app.agents import prepare_workspace
from backend.app.llm import OpenAICompatibleClient, _extract_json
from backend.app.settings import settings

ROOT = Path(__file__).resolve().parents[1]


def configure_real_settings(monkeypatch, *, api_key="sk-test-real", base_url="https://llm.test/v1", model="test-model"):
    """把模块级 settings 置为可正常调用（非 demo 模式）的值。"""
    monkeypatch.setattr(settings, "api_key", api_key)
    monkeypatch.setattr(settings, "base_url", base_url)
    monkeypatch.setattr(settings, "model", model)


def make_transport(handler):
    return httpx.MockTransport(handler)


# ---------- JSON 解析 ----------

def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced_and_embedded():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('先说明一段话 {"a": 1} 然后继续') == {"a": 1}


def test_extract_json_array():
    assert _extract_json('[1, 2, 3]') == [1, 2, 3]


# ---------- OpenAI-compatible HTTP 调用 ----------

def test_chat_posts_to_chat_completions_with_expected_payload(monkeypatch):
    configure_real_settings(monkeypatch)
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好，这是模型回复。"}}]})

    transport = make_transport(handler)
    result = asyncio.run(OpenAICompatibleClient().chat("请回应", transport=transport))

    assert captured["url"] == "https://llm.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test-real"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "请回应"}
    assert result == "你好，这是模型回复。"


def test_json_parses_fenced_content_from_chat(monkeypatch):
    configure_real_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"winner": "正方"}\n```'}}]})

    result = asyncio.run(OpenAICompatibleClient().json("评审", transport=make_transport(handler)))
    assert result == {"winner": "正方"}


def test_empty_model_content_is_rejected_not_passed_through(monkeypatch):
    configure_real_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": None}}]})

    with pytest.raises(RuntimeError, match="EMPTY_MODEL_CONTENT"):
        asyncio.run(OpenAICompatibleClient().chat("回应", transport=make_transport(handler)))


def test_http_error_raises(monkeypatch):
    configure_real_settings(monkeypatch)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "upstream"})

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(OpenAICompatibleClient().chat("回应", transport=make_transport(handler)))


# ---------- demo 模式 ----------

def test_demo_mode_raises_when_placeholders(monkeypatch):
    configure_real_settings(monkeypatch, api_key="your_api_key", base_url="", model="your_model_name")
    assert settings.demo_mode is True
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        asyncio.run(OpenAICompatibleClient().chat("回应"))


def test_demo_mode_detects_example_endpoint(monkeypatch):
    configure_real_settings(monkeypatch, base_url="https://api.example.com/v1")
    assert settings.demo_mode is True


# ---------- Agent 完整流程（真实 HTTP 路径，mock 传输层） ----------

async def no_search_results(topic):
    return []


def test_prepare_workspace_end_to_end_with_configured_model(monkeypatch):
    configure_real_settings(monkeypatch)
    monkeypatch.setattr(agents, "search_web", no_search_results)
    model_output = {
        "analysis": {"keywords": ["公平"], "definitions": ["教育：知识能力培养", "公平：机会可及"], "conflicts": ["效率与公平"],
                      "criterion": "机会改善", "burdens": {"正方": "证明改善", "反方": "证明不改善"}},
        "arguments": [{"id": "a1", "stance": "正方", "title": "机会论", "claim": "教育提升竞争力", "warrant": "能力可迁移",
                       "evidence_ids": [], "locked": False, "status": "待核验"}],
        "evidence": [], "matrix": [{"our": "机会", "attack": "成本", "response": "比较净收益"}],
        "insights": [{"lens": "反事实", "idea": "比较基线决定结论", "score": 0.8, "support": "待验证"}],
        "drafts": {"立论": "模型初稿", "攻辩": ["追问标准"], "自由辩论": [], "总结": "收束"},
        "warnings": [],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(model_output, ensure_ascii=False)}}]})

    real_json = agents.llm.json

    async def fake_json(prompt, *, system=None, temperature=0.55):
        return await real_json(prompt, system=system, temperature=temperature, transport=make_transport(handler))

    monkeypatch.setattr(agents.llm, "json", fake_json)
    workspace = asyncio.run(prepare_workspace("人工智能是否让教育更公平", "正方"))

    assert workspace["analysis"]["criterion"] == "机会改善"
    assert workspace["arguments"][0]["title"] == "机会论"
    assert workspace["drafts"]["立论"] == "模型初稿"
    assert workspace["warnings"] == []
    assert not any("演示稿" in str(w) for w in workspace["warnings"])


def test_prepare_workspace_falls_back_to_demo_on_model_failure(monkeypatch):
    configure_real_settings(monkeypatch, api_key="your_api_key", base_url="", model="your_model_name")
    monkeypatch.setattr(agents, "search_web", no_search_results)
    workspace = asyncio.run(prepare_workspace("人工智能是否让教育更公平", "正方"))
    assert any("演示稿" in w for w in workspace["warnings"])
    assert workspace["topic"] == "人工智能是否让教育更公平"


# ---------- 配置一致性 ----------

def test_env_example_and_env_define_identical_variable_names():
    def parse(path):
        text = path.read_text(encoding="utf-8")
        return set(re.findall(r"^([A-Z][A-Z0-9_]+)=", text, flags=re.M))

    example = parse(ROOT / ".env.example")
    env = parse(ROOT / ".env")
    assert {"LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "REQUEST_TIMEOUT", "DATABASE_PATH"} <= example
    assert env == example
