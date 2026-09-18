#!/usr/bin/env python3
"""Run the three exhibition topics through a checkpointed, real-model stress test."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agents import (  # noqa: E402
    STAGE_SPEECH_HARD_LIMITS,
    arena_speech,
    evaluate_debate,
    normalize_workspace,
)
from backend.app.database import connect, decode, init_db  # noqa: E402
from backend.app.llm import llm  # noqa: E402
from backend.app.settings import settings  # noqa: E402
from backend.app.strategy_skill import DEFAULT_SKILL, normalize_skill  # noqa: E402


def load_strategy() -> tuple[dict, str]:
    with connect() as db:
        row = db.execute(
            "SELECT id,status,config FROM strategies WHERE status='active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return normalize_skill(DEFAULT_SKILL, skill_id="baseline-v1"), "built-in"
    return normalize_skill(decode(row["config"], {}), skill_id=row["id"]), row["status"]


def workspace_for(case: dict) -> dict:
    return normalize_workspace(
        {
            "topic": case["topic"],
            "stance": "正方",
            "analysis": {
                "keywords": [],
                "definitions": [case["contract"]],
                "conflicts": case["conflicts"],
                "criterion": case["criterion"],
                "burdens": {
                    "正方": "证明命题在主要现实场景中的长期净收益为正",
                    "反方": "证明其机制不成立、代价更高或存在更优替代",
                },
            },
            "arguments": [],
            "evidence": [],
            "matrix": [],
            "insights": [],
            "drafts": {"立论": "", "攻辩": [], "自由辩论": [], "总结": ""},
            "warnings": ["本次压力测试不提供外部事实证据，只检查逻辑、回应与话题守恒。"],
        },
        case["topic"],
        "正方",
    )


def render_markdown(result: dict) -> str:
    lines = [
        "# 现场三辩题真实 API 压力测试",
        "",
        f"- 测试编号：`{result['run_id']}`",
        f"- 策略：`{result['strategy']['id']}` / {result['strategy']['version']}",
        f"- 请求数：{result['api_requests_used']} / {result['api_request_budget']}",
        f"- 总回合：{result['summary']['turns']}；平均发言：{result['summary']['average_chars']:.1f} 字",
        "",
    ]
    for index, debate in enumerate(result["debates"], 1):
        lines += [
            f"## {index}. {debate['topic']}",
            "",
            f"- 平均长度：{debate['metrics']['average_chars']:.1f} 字",
            f"- 超长回合：{debate['metrics']['over_limit_turns']}",
            f"- 裁判：{debate.get('evaluation', {}).get('winner', '未完成')}；{debate.get('evaluation', {}).get('summary', '')}",
            "",
        ]
        for turn in debate["turns"]:
            lines += [
                f"**{turn['stance']} · {turn['stage']} · {turn['chars']} 字**",
                "",
                turn["content"],
                "",
                f"> 回应对象：{turn['meta'].get('target', '')}｜回扣原题：{turn['meta'].get('topic_link', '')}",
                "",
            ]
    return "\n".join(lines)


def update_metrics(result: dict) -> None:
    all_turns = []
    for debate in result["debates"]:
        all_turns.extend(debate["turns"])
        over_limit = 0
        for turn in debate["turns"]:
            maximum = STAGE_SPEECH_HARD_LIMITS.get(turn["stage"], 170)
            if turn["chars"] > maximum:
                over_limit += 1
        debate["metrics"] = {
            "turns": len(debate["turns"]),
            "average_chars": (
                sum(turn["chars"] for turn in debate["turns"])
                / len(debate["turns"])
                if debate["turns"]
                else 0
            ),
            "over_limit_turns": over_limit,
        }
    result["summary"] = {
        "topics": len(result["debates"]),
        "turns": len(all_turns),
        "average_chars": (
            sum(turn["chars"] for turn in all_turns) / len(all_turns)
            if all_turns
            else 0
        ),
        "over_limit_turns": sum(
            debate["metrics"]["over_limit_turns"] for debate in result["debates"]
        ),
    }


async def run(args: argparse.Namespace) -> None:
    init_db()
    if settings.demo_mode:
        raise SystemExit("模型未配置，无法进行真实 API 压力测试。")
    cases = json.loads(args.suite.read_text(encoding="utf-8"))["topics"]
    strategy, status = load_strategy()
    result = {
        "run_id": f"live_{uuid4().hex[:12]}",
        "strategy": {
            "id": strategy["id"],
            "version": strategy["version"],
            "status": status,
        },
        "api_request_budget": args.max_api_requests,
        "api_requests_used": 0,
        "debates": [],
        "summary": {},
    }

    def checkpoint() -> None:
        update_metrics(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix(".json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        args.output.write_text(render_markdown(result), encoding="utf-8")

    with llm.request_budget(args.max_api_requests) as budget:
        for case in cases:
            debate = {"topic": case["topic"], "turns": [], "metrics": {}}
            result["debates"].append(debate)
            workspace = workspace_for(case)
            for turn_index in range(args.turns):
                stance = "正方" if turn_index % 2 == 0 else "反方"
                stage = "立论" if turn_index < 2 else "自由辩论"
                generated = await arena_speech(
                    case["topic"], stance, workspace, debate["turns"], stage, strategy
                )
                if generated.get("degraded"):
                    debate["error"] = "模型调用降级"
                    result["api_requests_used"] = budget.used
                    checkpoint()
                    raise SystemExit(debate["error"])
                speech = generated["speech"]
                debate["turns"].append(
                    {
                        "stance": stance,
                        "stage": stage,
                        "content": speech,
                        "chars": len(speech),
                        "meta": generated,
                    }
                )
                result["api_requests_used"] = budget.used
                checkpoint()
            debate["evaluation"] = await evaluate_debate(
                case["topic"], debate["turns"]
            )
            result["api_requests_used"] = budget.used
            checkpoint()

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="压力测试现场三个固定辩题")
    parser.add_argument(
        "--suite", type=Path, default=ROOT / "config" / "live_debate_topics.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports" / "live_debate_test.md"
    )
    parser.add_argument("--turns", type=int, default=6, choices=range(2, 11))
    parser.add_argument(
        "--max-api-requests", type=int, default=30, choices=range(1, 101)
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
