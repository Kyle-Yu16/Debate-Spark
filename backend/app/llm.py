import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import re
from typing import Any

import httpx

from .settings import settings


SYSTEM = """你是“观点火花”辩论系统的一名专业中文辩论 Agent。你的首要标准是相关、严谨、可证；新颖只是加分项。不得虚构事实、数据、论文或网址。资料不足时明确降低断言强度。输出必须符合调用方要求的 JSON 结构，不要使用 Markdown 代码围栏。"""


class ModelRequestBudgetExceeded(RuntimeError):
    pass


@dataclass
class RequestBudget:
    limit: int
    used: int = 0


_request_budget: ContextVar[RequestBudget | None] = ContextVar(
    "model_request_budget", default=None
)


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
    @contextmanager
    def request_budget(self, limit: int):
        tracker = RequestBudget(limit=max(1, limit))
        token = _request_budget.set(tracker)
        try:
            yield tracker
        finally:
            _request_budget.reset(token)

    @staticmethod
    def _consume_request_budget() -> None:
        tracker = _request_budget.get()
        if tracker is None:
            return
        if tracker.used >= tracker.limit:
            raise ModelRequestBudgetExceeded(
                f"模型 API 请求已达到本次硬上限：{tracker.limit}"
            )
        tracker.used += 1

    async def chat(
        self,
        prompt: str,
        *,
        system: str = SYSTEM,
        temperature: float = 0.65,
        transport: httpx.BaseTransport | None = None,
    ) -> str:
        if settings.demo_mode:
            raise RuntimeError("DEMO_MODE")
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }
        client_kwargs = {"timeout": settings.request_timeout}
        if transport is not None:
            client_kwargs["transport"] = transport
        last_error: Exception | None = None
        for attempt in range(settings.model_retries):
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    self._consume_request_budget()
                    response = await client.post(
                        f"{settings.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = (
                        data.get("choices", [{}])[0].get("message", {}).get("content")
                    )
                    if not content:
                        raise RuntimeError("EMPTY_MODEL_CONTENT")
                    return content
            except ModelRequestBudgetExceeded:
                raise
            except (
                httpx.TransportError,
                httpx.HTTPStatusError,
                RuntimeError,
                ValueError,
            ) as exc:
                last_error = exc
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    raise
                if attempt + 1 < settings.model_retries:
                    await asyncio.sleep(0.4 * (2**attempt))
        assert last_error is not None
        raise last_error

    async def json(
        self,
        prompt: str,
        *,
        system: str = SYSTEM,
        temperature: float = 0.55,
        transport: httpx.BaseTransport | None = None,
    ) -> Any:
        last_error: json.JSONDecodeError | None = None
        for attempt in range(2):
            retry_note = (
                "\n上一次响应无法解析。请只输出一个合法 JSON，不要添加解释或代码围栏。"
                if attempt
                else ""
            )
            text = await self.chat(
                prompt + retry_note,
                system=system,
                temperature=temperature,
                transport=transport,
            )
            try:
                return _extract_json(text)
            except json.JSONDecodeError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error


llm = OpenAICompatibleClient()
