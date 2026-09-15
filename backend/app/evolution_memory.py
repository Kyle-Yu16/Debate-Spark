from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .database import connect, decode, encode, new_id, now_iso


def outcome_for(winner: str, candidate_stance: str) -> str:
    if winner == "平局":
        return "draw"
    return "success" if winner == candidate_stance else "failure"


def trajectory_experience(row: dict[str, Any]) -> dict[str, Any]:
    evaluation = row.get("evaluation", {})
    candidate_stance = row.get("candidate_stance", "正方")
    highlights = [
        item
        for item in evaluation.get("highlights", [])
        if isinstance(item, dict) and item.get("stance") == candidate_stance
    ]
    return {
        "source": "已保存的真实辩论轨迹",
        "trajectory_id": row.get("id"),
        "topic": row.get("topic"),
        "outcome": row.get("outcome"),
        "candidate_stance": candidate_stance,
        "scores": evaluation.get("scores", {}).get(candidate_stance, {}),
        "successful_patterns": highlights[:4],
        "missed_responses": evaluation.get("missed_responses", [])[:6],
        "fact_errors": evaluation.get("fact_errors", [])[:4],
        "rule_violations": evaluation.get("rule_violations", [])[:4],
        "learning_instruction": (
            "保留可跨辩题复用的成功决策，同时修补遗漏回应；不得记忆具体立场结论。"
            if row.get("outcome") == "success"
            else "把失败归因转成可执行的触发条件与动作；不得只记录输了或照抄具体发言。"
        ),
    }


def save_trajectory(
    *,
    run_id: str,
    iteration: int,
    topic: str,
    candidate_id: str,
    champion_id: str,
    candidate_stance: str,
    transcript: list[dict],
    evaluation: dict,
) -> dict[str, Any]:
    winner = str(evaluation.get("winner", "平局"))
    item = {
        "id": new_id("traj"),
        "run_id": run_id,
        "iteration": iteration,
        "topic": topic,
        "candidate_id": candidate_id,
        "champion_id": champion_id,
        "candidate_stance": candidate_stance,
        "outcome": outcome_for(winner, candidate_stance),
        "transcript": transcript,
        "evaluation": evaluation,
        "created_at": now_iso(),
    }
    with connect() as db:
        db.execute(
            "INSERT INTO debate_trajectories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                item["id"],
                run_id,
                iteration,
                topic,
                candidate_id,
                champion_id,
                candidate_stance,
                item["outcome"],
                encode(transcript),
                encode(evaluation),
                item["created_at"],
            ),
        )
    return item


def load_trajectory_experiences(limit: int = 24) -> list[dict[str, Any]]:
    """Return a balanced sample so wins and losses can both change the Skill."""
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM debate_trajectories ORDER BY created_at DESC LIMIT ?",
            (max(limit * 4, 40),),
        ).fetchall()
    groups: dict[str, list[dict[str, Any]]] = {"success": [], "failure": [], "draw": []}
    for raw in rows:
        row = dict(raw)
        row["evaluation"] = decode(row["evaluation"], {})
        groups.get(row["outcome"], groups["draw"]).append(trajectory_experience(row))
    result: list[dict[str, Any]] = []
    while len(result) < limit and any(groups.values()):
        for key in ("failure", "success", "draw"):
            if groups[key] and len(result) < limit:
                result.append(groups[key].pop(0))
    return result


def load_legacy_evolution_experiences(limit: int = 12) -> list[dict[str, Any]]:
    """Recover useful summaries from runs created before full trajectories were persisted."""
    with connect() as db:
        rows = db.execute(
            "SELECT id,result FROM evolution_runs ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    saved_results = [(row["id"], decode(row["result"], {})) for row in rows]
    report_path = (
        Path(__file__).resolve().parents[2] / "reports" / "final_debate_skill.json"
    )
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_id = str(report.get("id", "bundled-evolution-report"))
            if all(run_id != report_id for run_id, _ in saved_results):
                saved_results.append((report_id, report))
        except (OSError, json.JSONDecodeError):
            pass
    experiences: list[dict[str, Any]] = []
    for run_id, result in saved_results:
        for report in reversed(result.get("iteration_reports", [])):
            rate = report.get("win_rate", 0.5)
            experiences.append(
                {
                    "source": "历史自博弈评测摘要",
                    "run_id": run_id,
                    "topics": result.get("topics", []),
                    "outcome": (
                        "success"
                        if rate > 0.5
                        else ("failure" if rate < 0.5 else "draw")
                    ),
                    "win_rate": rate,
                    "missed_responses": report.get("diagnosis", [])[:6],
                    "successful_patterns": report.get("highlights", [])[:4],
                    "learning_instruction": "同时复用亮点与失败诊断，只提炼跨辩题规则。",
                }
            )
            if len(experiences) >= limit:
                return experiences
    showcase_path = (
        Path(__file__).resolve().parents[2] / "reports" / "showcase_debates.json"
    )
    if showcase_path.exists():
        try:
            showcase = json.loads(showcase_path.read_text(encoding="utf-8"))
            for debate in showcase.get("debates", []):
                evaluation = debate.get("evaluation", {})
                if not evaluation:
                    continue
                experiences.append(
                    {
                        "source": "决赛展示真实对辩轨迹",
                        "run_id": showcase.get("run_id"),
                        "topic": debate.get("topic"),
                        "outcome": "mixed",
                        "scores": evaluation.get("scores", {}),
                        "missed_responses": evaluation.get("missed_responses", [])[:6],
                        "successful_patterns": evaluation.get("highlights", [])[:4],
                        "learning_instruction": "双方使用同一Skill，不学习立场胜负；只提炼共同暴露的成功战术、遗漏回应和证据边界。",
                    }
                )
                if len(experiences) >= limit:
                    return experiences
        except (OSError, json.JSONDecodeError):
            pass
    return experiences


def trajectory_stats() -> dict[str, Any]:
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM debate_trajectories").fetchone()[0]
        outcomes = db.execute(
            "SELECT outcome,COUNT(*) count FROM debate_trajectories GROUP BY outcome"
        ).fetchall()
        topics = db.execute(
            "SELECT COUNT(DISTINCT topic) FROM debate_trajectories"
        ).fetchone()[0]
    return {
        "total": total,
        "topics": topics,
        "outcomes": {row["outcome"]: row["count"] for row in outcomes},
    }
