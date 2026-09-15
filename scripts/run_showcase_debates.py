#!/usr/bin/env python3
"""Run a small, checkpointed showcase suite for presentation material."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.agents import (
    arena_speech,
    evaluate_debate,
    normalize_workspace,
)  # noqa: E402
from backend.app.database import connect, decode, init_db  # noqa: E402
from backend.app.llm import llm  # noqa: E402
from backend.app.settings import settings  # noqa: E402
from backend.app.strategy_skill import normalize_skill  # noqa: E402


def load_strategy() -> tuple[dict, str]:
    with connect() as db:
        row = db.execute(
            "SELECT id,status,config FROM strategies WHERE status IN ('candidate','active') ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row:
        return (
            normalize_skill(decode(row["config"], {}), skill_id=row["id"]),
            row["status"],
        )
    report = json.loads(
        (ROOT / "reports" / "final_debate_skill.json").read_text(encoding="utf-8")
    )
    return (
        normalize_skill(report["skill"], skill_id=report["candidate"]),
        "bundled-candidate",
    )


def workspace_for(case: dict) -> dict:
    topic = case["topic"]
    evidence_ids = [item["id"] for item in case["evidence"]]
    return normalize_workspace(
        {
            "topic": topic,
            "stance": "正方",
            "analysis": {
                "keywords": [],
                "definitions": [],
                "conflicts": case["conflicts"],
                "criterion": case["criterion"],
                "burdens": {
                    "正方": "证明命题在主要现实场景中的净收益为正",
                    "反方": "证明命题的因果链不成立、成本更高或存在更优替代",
                },
            },
            "arguments": [
                {
                    "id": "pro",
                    "stance": "正方",
                    "title": "正方核心机制",
                    "claim": topic,
                    "warrant": case["criterion"],
                    "evidence_ids": evidence_ids,
                    "status": "已核验",
                },
                {
                    "id": "con",
                    "stance": "反方",
                    "title": "反方替代解释",
                    "claim": f"反对：{topic}",
                    "warrant": "必须比较现实替代方案与边界条件",
                    "evidence_ids": evidence_ids,
                    "status": "已核验",
                },
            ],
            "evidence": case["evidence"],
            "matrix": [],
            "insights": [],
            "drafts": {"立论": "", "攻辩": [], "自由辩论": [], "总结": ""},
            "warnings": [],
        },
        topic,
        "正方",
    )


def render_markdown(result: dict) -> str:
    lines = [
        "# 观点火花：决赛展示对辩实测",
        "",
        f"- 测试 Skill：`{result['strategy']['id']}` / {result['strategy']['version']}（{result['strategy']['status']}）",
        f"- 实际模型请求：{result['api_requests_used']} / {result['api_request_budget']}",
        f"- 完成辩题：{len(result['debates'])}",
        "",
        "> 注：菲尔兹奖事件是对 AI 数学竞赛激励的联合警告，并非对 AI 的全面抵制。",
        "",
    ]
    for index, debate in enumerate(result["debates"], 1):
        lines += [
            f"## {index}. {debate['topic']}",
            "",
            f"**裁判结论：** {debate.get('evaluation', {}).get('summary', '未完成')}",
            "",
            "### PPT 候选亮点",
            "",
        ]
        highlights = debate.get("evaluation", {}).get("highlights", [])
        if highlights:
            for item in highlights[:4]:
                lines += [
                    f"> {item.get('quote', '')}",
                    "",
                    f"- {item.get('stance', '')}｜{item.get('reason', '')}",
                    "",
                ]
        else:
            for turn in debate.get("turns", [])[:2]:
                spark = turn.get("meta", {}).get("spark")
                if spark:
                    lines += [
                        f"> {spark}",
                        "",
                        f"- {turn['stance']}｜来自{turn['stage']}环节",
                        "",
                    ]
        lines += ["### 完整交锋", ""]
        for turn in debate.get("turns", []):
            lines += [f"**{turn['stance']}·{turn['stage']}**", "", turn["content"], ""]
        lines += ["### 证据来源", ""]
        for evidence in debate["evidence"]:
            lines.append(
                f"- [{evidence['title']}]({evidence['url']})：{evidence['scope']}"
            )
        lines.append("")
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> None:
    init_db()
    if settings.demo_mode:
        raise SystemExit("模型未配置，无法进行真实展示测试。")
    suite = json.loads(args.suite.read_text(encoding="utf-8"))["debates"]
    strategy, strategy_status = load_strategy()
    result = {
        "run_id": f"showcase_{uuid4().hex[:12]}",
        "strategy": {
            "id": strategy["id"],
            "version": strategy["version"],
            "status": strategy_status,
        },
        "api_request_budget": args.max_api_requests,
        "api_requests_used": 0,
        "debates": [],
    }

    def checkpoint() -> None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix(".json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        args.output.write_text(render_markdown(result), encoding="utf-8")

    with llm.request_budget(args.max_api_requests) as budget:
        for case in suite:
            workspace = workspace_for(case)
            debate = {
                "topic": case["topic"],
                "criterion": case["criterion"],
                "evidence": case["evidence"],
                "turns": [],
            }
            result["debates"].append(debate)
            for turn_index in range(4):
                stance = "正方" if turn_index % 2 == 0 else "反方"
                stage = "立论" if turn_index < 2 else "自由辩论"
                generated = await arena_speech(
                    case["topic"], stance, workspace, debate["turns"], stage, strategy
                )
                if generated.get("degraded"):
                    result["api_requests_used"] = budget.used
                    debate["error"] = "模型调用降级；已保留此前回合"
                    checkpoint()
                    raise SystemExit(debate["error"])
                debate["turns"].append(
                    {
                        "stance": stance,
                        "stage": stage,
                        "content": generated["speech"],
                        "meta": generated,
                    }
                )
                result["api_requests_used"] = budget.used
                checkpoint()
            evaluation = await evaluate_debate(case["topic"], debate["turns"])
            if evaluation.get("degraded"):
                result["api_requests_used"] = budget.used
                debate["error"] = "裁判调用降级；完整发言已保留"
                checkpoint()
                raise SystemExit(debate["error"])
            debate["evaluation"] = evaluation
            result["api_requests_used"] = budget.used
            checkpoint()
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "debates": len(result["debates"]),
                "api_requests": result["api_requests_used"],
                "markdown": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成决赛PPT所需的少量真实对辩亮点")
    parser.add_argument(
        "--suite", type=Path, default=ROOT / "config" / "showcase_debates.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports" / "showcase_debates.md"
    )
    parser.add_argument(
        "--max-api-requests", type=int, default=20, choices=range(1, 51)
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
