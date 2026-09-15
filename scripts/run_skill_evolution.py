#!/usr/bin/env python3
"""Run a versioned Debate Skill evolution benchmark from the command line."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.database import connect, init_db  # noqa: E402
from backend.app.main import evolution  # noqa: E402
from backend.app.schemas import EvolutionCreate  # noqa: E402
from backend.app.settings import settings  # noqa: E402


def ready_project_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    with connect() as db:
        row = db.execute(
            "SELECT id FROM projects WHERE status='ready' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        raise SystemExit(
            "没有已完成备赛的项目；请先在网页中完成一个项目，或用 --project-id 指定。"
        )
    return row["id"]


async def run(args: argparse.Namespace) -> None:
    init_db()
    if settings.demo_mode:
        raise SystemExit(
            "模型配置仍处于演示模式。请先设置有效的 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。"
        )
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    project_id = ready_project_id(args.project_id)
    with connect() as db:
        project = db.execute(
            "SELECT topic FROM projects WHERE id=?", (project_id,)
        ).fetchone()
    if not project:
        raise SystemExit(f"项目不存在：{project_id}")
    extra_topics = [topic for topic in suite["topics"] if topic != project["topic"]]
    result = await evolution(
        EvolutionCreate(
            project_id=project_id,
            games=args.games,
            iterations=args.iterations,
            topics=extra_topics,
            mode=args.mode,
            max_new_games=args.max_new_games,
            reuse_trajectories=not args.no_reuse,
            max_api_requests=args.max_api_requests,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result["skill_markdown"], encoding="utf-8")
    report_path = args.output.with_suffix(".json")
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "run_id": result["id"],
                "skill_id": result["candidate"],
                "promoted": result["promoted"],
                "games": result["aggregate_games"],
                "topics": result["unique_topics"],
                "win_rate": result["aggregate_win_rate"],
                "skill": str(args.output),
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="低成本增量学习；显式指定 promotion 才运行完整晋级评测"
    )
    parser.add_argument("--project-id")
    parser.add_argument(
        "--suite", type=Path, default=ROOT / "config" / "evolution_demo_topics.json"
    )
    parser.add_argument("--iterations", type=int, default=1, choices=range(1, 5))
    parser.add_argument(
        "--games", type=int, default=2, choices=range(2, 5), help="每个辩题的换边对局数"
    )
    parser.add_argument(
        "--mode", choices=("incremental", "promotion"), default="incremental"
    )
    parser.add_argument("--max-new-games", type=int, default=1, choices=range(0, 21))
    parser.add_argument(
        "--no-reuse", action="store_true", help="不把历史成功/失败轨迹输入本轮修订"
    )
    parser.add_argument(
        "--max-api-requests", type=int, help="包括重试在内的实际模型 HTTP 请求硬上限"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports" / "final_debate_skill.md"
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
