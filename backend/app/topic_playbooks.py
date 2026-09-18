from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = ROOT / "config" / "live_debate_topics.json"


def _topic_key(topic: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", topic).lower()


@lru_cache(maxsize=1)
def _playbooks() -> list[dict[str, Any]]:
    try:
        payload = json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in payload.get("topics", []) if isinstance(item, dict)]


def topic_playbook(topic: str) -> dict[str, Any] | None:
    """Return a curated guardrail for a featured topic, never a canned answer."""
    key = _topic_key(topic)
    for item in _playbooks():
        aliases = [item.get("topic", ""), *item.get("aliases", [])]
        alias_keys = [_topic_key(str(alias)) for alias in aliases]
        if key in alias_keys:
            return item
    return None


def topic_playbook_prompt(topic: str) -> str:
    playbook = topic_playbook(topic)
    if not playbook:
        return ""
    conflicts = "\n".join(f"- {item}" for item in playbook.get("conflicts", []))
    traps = "\n".join(f"- {item}" for item in playbook.get("traps", []))
    questions = "\n".join(
        f"- {item}" for item in playbook.get("pressure_questions", [])
    )
    return f"""【现场重点辩题护栏】
这不是预制立场或背诵稿，只用于稳定讨论范围并暴露薄弱推理。
最低设定：{playbook.get('contract', '')}
建议判准：{playbook.get('criterion', '')}
核心冲突：
{conflicts or '- 以原题判准为准'}
常见跑偏：
{traps or '- 不得把局部定义争议替代原题证明'}
可用于检验双方论证的问题：
{questions or '- 对方的机制在什么条件下成立，如何改变原题结论？'}"""
