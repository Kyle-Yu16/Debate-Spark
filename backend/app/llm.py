import json
import re
from typing import Any

import httpx

from .settings import settings


SYSTEM = """你是“观点火花”辩论系统的一名专业中文辩论 Agent。你的首要标准是相关、严谨、可证；新颖只是加分项。不得虚构事实、数据、论文或网址。资料不足时明确降低断言强度。输出必须符合调用方要求的 JSON 结构，不要使用 Markdown 代码围栏。"""


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_candidates = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(text.rfind("}"), text.rfind("]"))
        return json.loads(text[start : end + 1])


class OpenAICompatibleClient:
    async def chat(self, prompt: str, *, system: str = SYSTEM, temperature: float = 0.65, transport: httpx.BaseTransport | None = None) -> str:
        if settings.demo_mode:
            raise RuntimeError("DEMO_MODE")
        headers = {"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False,
        }
        client_kwargs = {"timeout": settings.request_timeout}
        if transport is not None:
            client_kwargs["transport"] = transport
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(f"{settings.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise RuntimeError("EMPTY_MODEL_CONTENT")
            return content

    async def json(self, prompt: str, *, system: str = SYSTEM, temperature: float = 0.55, transport: httpx.BaseTransport | None = None) -> Any:
        return _extract_json(await self.chat(prompt, system=system, temperature=temperature, transport=transport))


llm = OpenAICompatibleClient()
