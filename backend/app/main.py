import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from .agents import arena_speech, demo_workspace, evaluate_debate, normalize_workspace, other, prepare_workspace, propose_skill_revision, short_pause
from .database import connect, decode, encode, init_db, new_id, now_iso, row_dict
from .schemas import DebateCreate, EvolutionCreate, ProjectCreate, TurnCreate, WorkspacePatch
from .settings import settings
from .strategy_skill import normalize_skill, render_skill_markdown


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="观点火花 Debate Spark API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def get_project(project_id: str) -> dict:
    with connect() as db:
        row = row_dict(db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    if not row:
        raise HTTPException(404, "项目不存在")
    row["config"] = decode(row["config"], {})
    raw_workspace = decode(row["workspace"], None)
    if raw_workspace is not None:
        normalized = normalize_workspace(raw_workspace, row["topic"], row["stance"])
        row["workspace"] = normalized
        if normalized != raw_workspace:
            with connect() as db:
                db.execute("UPDATE projects SET workspace=?, updated_at=? WHERE id=?", (encode(normalized), now_iso(), project_id))
    else:
        row["workspace"] = None
    return row


def get_debate(debate_id: str) -> dict:
    with connect() as db:
        row = row_dict(db.execute("SELECT * FROM debates WHERE id=?", (debate_id,)).fetchone())
    if not row:
        raise HTTPException(404, "辩论会话不存在")
    row["state"] = decode(row["state"], {})
    row["evaluation"] = decode(row["evaluation"], None)
    return row


def get_turns(debate_id: str) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT * FROM turns WHERE debate_id=? ORDER BY created_at", (debate_id,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["meta"] = decode(item["meta"], {})
        result.append(item)
    return result


def add_turn(debate_id: str, speaker: str, stance: str, stage: str, content: str, meta: dict | None = None) -> dict:
    item = {"id": new_id("turn"), "debate_id": debate_id, "speaker": speaker, "stance": stance, "stage": stage, "content": content, "meta": meta or {}, "created_at": now_iso()}
    with connect() as db:
        db.execute("INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)", (item["id"], debate_id, speaker, stance, stage, content, encode(item["meta"]), item["created_at"]))
    return item


def snapshot_workspace(project_id: str, workspace: dict, label: str) -> dict:
    item = {"id": new_id("wsver"), "project_id": project_id, "label": label, "workspace": workspace, "created_at": now_iso()}
    with connect() as db:
        db.execute("INSERT INTO workspace_versions VALUES (?,?,?,?,?)", (item["id"], project_id, label, encode(workspace), item["created_at"]))
    return item


def get_strategy(strategy_id: str) -> dict:
    with connect() as db:
        row = row_dict(db.execute("SELECT * FROM strategies WHERE id=?", (strategy_id,)).fetchone())
    if not row:
        raise HTTPException(404, "辩论 Skill 不存在")
    row["skill"] = normalize_skill(decode(row.pop("config"), {}), skill_id=row["id"])
    row["metrics"] = decode(row["metrics"], {})
    row["markdown"] = render_skill_markdown(row["skill"], {**row["metrics"], "status": row["status"]})
    return row


def get_active_strategy() -> dict:
    with connect() as db:
        row = db.execute("SELECT id FROM strategies WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    return get_strategy(row["id"] if row else "baseline-v1")


@app.get("/api/health")
def health():
    return {"ok": True, "model": settings.model, "base_url": settings.base_url, "configured": not settings.demo_mode}


@app.get("/api/projects")
def list_projects():
    with connect() as db:
        rows = db.execute("SELECT id,topic,stance,status,created_at,updated_at FROM projects ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/projects")
def create_project(body: ProjectCreate):
    item = {"id": new_id("proj"), "topic": body.topic.strip(), "stance": body.stance, "config": body.config, "status": "created", "created_at": now_iso(), "updated_at": now_iso()}
    with connect() as db:
        db.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)", (item["id"], item["topic"], item["stance"], encode(item["config"]), item["status"], None, item["created_at"], item["updated_at"]))
    return item


@app.get("/api/projects/{project_id}")
def project_detail(project_id: str):
    return get_project(project_id)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    get_project(project_id)
    with connect() as db:
        db.execute("DELETE FROM workspace_versions WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM turns WHERE debate_id IN (SELECT id FROM debates WHERE project_id=?)", (project_id,))
        db.execute("DELETE FROM debates WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"ok": True}


@app.post("/api/projects/{project_id}/prepare")
async def prepare(project_id: str):
    project = get_project(project_id)
    with connect() as db:
        db.execute("UPDATE projects SET status='preparing', updated_at=? WHERE id=?", (now_iso(), project_id))
    workspace = normalize_workspace(await prepare_workspace(project["topic"], project["stance"]), project["topic"], project["stance"])
    with connect() as db:
        db.execute("UPDATE projects SET status='ready', workspace=?, updated_at=? WHERE id=?", (encode(workspace), now_iso(), project_id))
    snapshot_workspace(project_id, workspace, "备赛完成")
    return workspace


@app.get("/api/projects/{project_id}/workspace")
def workspace(project_id: str):
    project = get_project(project_id)
    if not project["workspace"]:
        raise HTTPException(409, "请先完成备赛")
    return project["workspace"]


@app.patch("/api/projects/{project_id}/workspace")
def patch_workspace(project_id: str, body: WorkspacePatch):
    project = get_project(project_id)
    normalized = normalize_workspace(body.workspace, project["topic"], project["stance"])
    with connect() as db:
        db.execute("UPDATE projects SET workspace=?, updated_at=? WHERE id=?", (encode(normalized), now_iso(), project_id))
    snapshot_workspace(project_id, normalized, "手动保存")
    return normalized


@app.get("/api/projects/{project_id}/history")
def project_history(project_id: str):
    get_project(project_id)
    with connect() as db:
        versions = db.execute(
            "SELECT id,label,created_at FROM workspace_versions WHERE project_id=? ORDER BY created_at DESC LIMIT 30", (project_id,)
        ).fetchall()
        debates = db.execute(
            """SELECT d.id,d.mode,d.user_stance,d.difficulty,d.status,d.state,d.evaluation,d.created_at,d.updated_at,
               COUNT(t.id) AS turn_count FROM debates d LEFT JOIN turns t ON t.debate_id=d.id
               WHERE d.project_id=? GROUP BY d.id ORDER BY d.updated_at DESC LIMIT 50""", (project_id,)
        ).fetchall()
    debate_history = []
    for row in debates:
        item = dict(row)
        item["state"] = decode(item["state"], {})
        item["evaluation"] = decode(item["evaluation"], None)
        debate_history.append(item)
    return {"workspace_versions": [dict(row) for row in versions], "debates": debate_history}


@app.get("/api/projects/{project_id}/history/{version_id}")
def workspace_version(project_id: str, version_id: str):
    get_project(project_id)
    with connect() as db:
        row = row_dict(db.execute("SELECT * FROM workspace_versions WHERE id=? AND project_id=?", (version_id, project_id)).fetchone())
    if not row:
        raise HTTPException(404, "备赛历史不存在")
    return {"id": row["id"], "label": row["label"], "created_at": row["created_at"], "workspace": decode(row["workspace"], {})}


@app.post("/api/projects/{project_id}/history/{version_id}/restore")
def restore_workspace_version(project_id: str, version_id: str):
    project = get_project(project_id)
    with connect() as db:
        row = row_dict(db.execute("SELECT * FROM workspace_versions WHERE id=? AND project_id=?", (version_id, project_id)).fetchone())
    if not row:
        raise HTTPException(404, "备赛历史不存在")
    workspace = normalize_workspace(decode(row["workspace"], {}), project["topic"], project["stance"])
    with connect() as db:
        db.execute("UPDATE projects SET workspace=?, updated_at=? WHERE id=?", (encode(workspace), now_iso(), project_id))
    snapshot_workspace(project_id, workspace, f"恢复：{row['label']}")
    return workspace


def render_markdown(project: dict) -> str:
    w = project["workspace"] or {}
    lines = [f"# {project['topic']}", "", f"- 持方：{project['stance']}", f"- 判断标准：{w.get('analysis', {}).get('criterion', '')}", "", "## 论证地图", ""]
    for arg in w.get("arguments", []):
        lines += [f"### {arg.get('stance')} · {arg.get('title')}", arg.get("claim", ""), "", f"推理桥梁：{arg.get('warrant', '')}", ""]
    lines += ["## 证据卡", ""]
    for ev in w.get("evidence", []):
        lines += [f"### {ev.get('title')}", ev.get("claim", ""), f"来源：{ev.get('url') or '待补充'}", f"适用边界：{ev.get('scope', '')}", ""]
    lines += ["## 发言初稿", ""]
    for name, draft in w.get("drafts", {}).items():
        value = "\n".join(f"- {x}" for x in draft) if isinstance(draft, list) else draft
        lines += [f"### {name}", value, ""]
    return "\n".join(lines)


@app.get("/api/projects/{project_id}/export", response_class=PlainTextResponse)
def export_project(project_id: str):
    project = get_project(project_id)
    if not project["workspace"]:
        raise HTTPException(409, "请先完成备赛")
    return PlainTextResponse(render_markdown(project), headers={"Content-Disposition": f'attachment; filename="debate-{project_id}.md"'})


@app.post("/api/debates")
def create_debate(body: DebateCreate):
    project = get_project(body.project_id)
    if not project["workspace"]:
        raise HTTPException(409, "请先完成备赛")
    debate_id = new_id("deb")
    state = {"round": 0, "rounds": body.rounds, "stage": "立论", "pending": [], "focus": project["workspace"].get("analysis", {}).get("conflicts", [])[:3]}
    created = now_iso()
    with connect() as db:
        db.execute("INSERT INTO debates VALUES (?,?,?,?,?,?,?,?,?,?)", (debate_id, body.project_id, body.mode, body.user_stance, body.difficulty, "ready", encode(state), None, created, created))
    return {"id": debate_id, "project_id": body.project_id, "mode": body.mode, "user_stance": body.user_stance, "difficulty": body.difficulty, "status": "ready", "state": state}


@app.get("/api/debates/{debate_id}")
def debate_detail(debate_id: str):
    item = get_debate(debate_id)
    item["turns"] = get_turns(debate_id)
    return item


@app.delete("/api/debates/{debate_id}")
def delete_debate(debate_id: str):
    get_debate(debate_id)
    with connect() as db:
        db.execute("DELETE FROM turns WHERE debate_id=?", (debate_id,))
        db.execute("DELETE FROM debates WHERE id=?", (debate_id,))
    return {"ok": True}


@app.post("/api/debates/{debate_id}/turns")
async def submit_turn(debate_id: str, body: TurnCreate):
    debate = get_debate(debate_id)
    if debate["mode"] != "human":
        raise HTTPException(409, "机器竞技场使用流式接口")
    project = get_project(debate["project_id"])
    human = add_turn(debate_id, "用户", debate["user_stance"], body.stage, body.content)
    history = get_turns(debate_id)
    from .agents import generate_reply
    strategy = get_active_strategy()["skill"]
    result = await generate_reply(project["topic"], other(debate["user_stance"]), project["workspace"], history, body.content, body.stage, debate["difficulty"], strategy)
    ai = add_turn(debate_id, "AI 辩手", other(debate["user_stance"]), body.stage, result["speech"], result)
    state = debate["state"]
    state.update({"round": state.get("round", 0) + 1, "stage": body.stage, "pending": [result.get("target", "")], "last_issue": result.get("issue", ""), "last_lens": result.get("lens", ""), "novelty": result.get("novelty", 0)})
    with connect() as db:
        db.execute("UPDATE debates SET status='running', state=?, updated_at=? WHERE id=?", (encode(state), now_iso(), debate_id))
    return {"user_turn": human, "ai_turn": ai, "state": state}


@app.post("/api/debates/{debate_id}/pause")
def pause(debate_id: str):
    get_debate(debate_id)
    with connect() as db:
        db.execute("UPDATE debates SET status='paused', updated_at=? WHERE id=?", (now_iso(), debate_id))
    return {"status": "paused"}


@app.post("/api/debates/{debate_id}/resume")
def resume(debate_id: str):
    get_debate(debate_id)
    with connect() as db:
        db.execute("UPDATE debates SET status='running', updated_at=? WHERE id=?", (now_iso(), debate_id))
    return {"status": "running"}


@app.get("/api/debates/{debate_id}/stream")
async def arena_stream(debate_id: str):
    debate = get_debate(debate_id)
    if debate["mode"] != "arena":
        raise HTTPException(409, "该会话不是机器竞技场")

    async def events():
        with connect() as db:
            db.execute("UPDATE debates SET status='running' WHERE id=?", (debate_id,))
        project = get_project(debate["project_id"])
        strategy = get_active_strategy()["skill"]
        rounds = debate["state"].get("rounds", 6)
        existing = len(get_turns(debate_id))
        for index in range(existing, rounds):
            while get_debate(debate_id)["status"] == "paused":
                yield "event: status\ndata: {\"status\":\"paused\"}\n\n"
                await asyncio.sleep(0.7)
            stance = "正方" if index % 2 == 0 else "反方"
            stage = "立论" if index < 2 else ("总结" if index >= rounds - 2 else "自由辩论")
            transcript = get_turns(debate_id)
            result = await arena_speech(project["topic"], stance, project["workspace"], transcript, stage, strategy)
            turn = add_turn(debate_id, f"{stance} Agent", stance, stage, result["speech"], result)
            state = get_debate(debate_id)["state"]
            state.update({"round": index + 1, "stage": stage, "last_issue": result.get("issue", ""), "last_lens": result.get("lens", ""), "novelty": result.get("novelty", 0), "pending": [result.get("target", "")]})
            with connect() as db:
                db.execute("UPDATE debates SET state=?, updated_at=? WHERE id=?", (encode(state), now_iso(), debate_id))
            yield f"event: turn\ndata: {json.dumps({'turn': turn, 'state': state}, ensure_ascii=False)}\n\n"
            await short_pause()
        evaluation = await evaluate_debate(project["topic"], get_turns(debate_id))
        with connect() as db:
            db.execute("UPDATE debates SET status='finished', evaluation=?, updated_at=? WHERE id=?", (encode(evaluation), now_iso(), debate_id))
        yield f"event: finished\ndata: {json.dumps({'evaluation': evaluation}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/debates/{debate_id}/finish")
async def finish(debate_id: str):
    debate = get_debate(debate_id)
    project = get_project(debate["project_id"])
    evaluation = await evaluate_debate(project["topic"], get_turns(debate_id))
    with connect() as db:
        db.execute("UPDATE debates SET status='finished', evaluation=?, updated_at=? WHERE id=?", (encode(evaluation), now_iso(), debate_id))
    return evaluation


@app.get("/api/strategies")
def list_strategies():
    with connect() as db:
        rows = db.execute("SELECT id,status,metrics,created_at FROM strategies ORDER BY created_at DESC").fetchall()
    return [{**dict(row), "metrics": decode(row["metrics"], {})} for row in rows]


@app.get("/api/strategies/active")
def active_strategy():
    return get_active_strategy()


@app.get("/api/strategies/{strategy_id}")
def strategy_detail(strategy_id: str):
    return get_strategy(strategy_id)


@app.post("/api/evolution/runs")
async def evolution(body: EvolutionCreate):
    project = get_project(body.project_id)
    if not project["workspace"]:
        raise HTTPException(409, "请先完成备赛")
    if settings.demo_mode:
        raise HTTPException(409, "自我进化需要有效的 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL；演示降级输出不能作为晋级证据")
    run_id = new_id("evo")
    champion_record = get_active_strategy()
    champion = champion_record["skill"]
    candidate_id = new_id("skill")
    topics = list(dict.fromkeys([project["topic"], *(topic.strip() for topic in body.topics if topic.strip())]))[:8]
    workspaces = {topic: project["workspace"] if topic == project["topic"] else demo_workspace(topic, "正方", []) for topic in topics}
    experiences = [{
        "source": "产品退化测试",
        "observations": ["重复依赖同一例子会降低新意和回应性", "子概念定义之争可能偷换原命题"],
        "lesson_requirement": "将局部争议重新连接到总体因果、比较基线与举证责任",
    }]
    game_results = []
    iteration_reports = []
    candidate_points = 0.0
    total_games = 0
    candidate = champion
    fact_errors = []
    rule_violations = []
    quality = {"candidate_logic": [], "candidate_evidence": [], "champion_logic": [], "champion_evidence": []}
    topic_points = {topic: 0.0 for topic in topics}
    topic_games = {topic: 0 for topic in topics}

    for iteration in range(1, body.iterations + 1):
        try:
            candidate = await propose_skill_revision(candidate, experiences, iteration, candidate_id)
        except Exception as exc:
            raise HTTPException(503, f"候选 Skill 生成失败，已中止本轮评测：{type(exc).__name__}") from exc
        iteration_points = 0.0
        iteration_games = 0
        iteration_diagnoses = []
        iteration_highlights = []
        for topic in topics:
            for game in range(body.games):
                candidate_stance = "正方" if game % 2 == 0 else "反方"
                transcript = []
                for index in range(4):
                    stance = "正方" if index % 2 == 0 else "反方"
                    chosen_skill = candidate if stance == candidate_stance else champion
                    generated = await arena_speech(topic, stance, workspaces[topic], transcript, "立论" if index < 2 else "自由辩论", chosen_skill)
                    if generated.get("degraded"):
                        raise HTTPException(503, "模型调用失败并进入降级模式；本轮结果不会作为 Skill 晋级证据")
                    transcript.append({"stance": stance, "content": generated["speech"], "meta": generated})
                judged = await evaluate_debate(topic, transcript)
                if judged.get("degraded"):
                    raise HTTPException(503, "裁判模型调用失败；本轮结果不会作为 Skill 晋级证据")
                winner = judged.get("winner", "平局")
                points = 1 if winner == candidate_stance else (0.5 if winner == "平局" else 0)
                iteration_points += points
                candidate_points += points
                topic_points[topic] += points
                topic_games[topic] += 1
                iteration_games += 1
                total_games += 1
                misses = [str(item) for item in judged.get("missed_responses", [])]
                highlights = judged.get("highlights", [])
                fact_errors.extend(str(item) for item in judged.get("fact_errors", []))
                rule_violations.extend(str(item) for item in judged.get("rule_violations", []))
                scores = judged.get("scores", {})
                candidate_scores = scores.get(candidate_stance, {})
                champion_scores = scores.get(other(candidate_stance), {})
                for dimension in ("logic", "evidence"):
                    if isinstance(candidate_scores.get(dimension), (int, float)):
                        quality[f"candidate_{dimension}"].append(float(candidate_scores[dimension]))
                    if isinstance(champion_scores.get(dimension), (int, float)):
                        quality[f"champion_{dimension}"].append(float(champion_scores[dimension]))
                iteration_diagnoses.extend(misses)
                iteration_highlights.extend(highlights)
                game_results.append({
                    "iteration": iteration, "topic": topic, "game": game + 1,
                    "candidate_stance": candidate_stance, "winner": winner,
                    "scores": scores, "missed_responses": misses,
                })
        iteration_rate = iteration_points / max(1, iteration_games)
        report = {
            "iteration": iteration, "skill_version": candidate["version"], "games": iteration_games,
            "win_rate": iteration_rate, "diagnosis": list(dict.fromkeys(iteration_diagnoses))[:8],
            "highlights": iteration_highlights[:8], "lesson_count": len(candidate.get("lessons", [])),
        }
        iteration_reports.append(report)
        experiences.append({
            "source": f"第{iteration}轮跨辩题换边评测", "topics": topics,
            "win_rate": iteration_rate, "missed_responses": report["diagnosis"],
            "validated_highlights": report["highlights"],
        })

    aggregate_rate = candidate_points / max(1, total_games)
    enough_evidence = len(topics) >= 5 and total_games >= 20
    averages = {key: (sum(values) / len(values) if values else None) for key, values in quality.items()}
    no_quality_regression = all(
        averages[f"candidate_{dimension}"] is None
        or averages[f"champion_{dimension}"] is None
        or averages[f"candidate_{dimension}"] >= averages[f"champion_{dimension}"] - 2
        for dimension in ("logic", "evidence")
    )
    no_topic_collapse = all(topic_points[topic] / max(1, topic_games[topic]) >= 0.25 for topic in topics)
    safety_passed = not fact_errors and not rule_violations
    promoted = enough_evidence and aggregate_rate >= 0.55 and no_quality_regression and no_topic_collapse and safety_passed
    status = "active" if promoted else ("rejected" if enough_evidence else "candidate")
    metrics = {
        "status": status, "games": total_games, "topics": len(topics), "win_rate": aggregate_rate,
        "iterations": body.iterations, "parent": champion["id"], "iteration_reports": iteration_reports,
        "quality_averages": averages, "no_quality_regression": no_quality_regression,
        "no_topic_collapse": no_topic_collapse, "safety_passed": safety_passed,
    }
    result = {
        "games": total_games, "candidate": candidate_id, "champion": champion["id"], "promoted": promoted,
        "project_id": body.project_id, "topics": topics, "candidate_points": candidate_points,
        "aggregate_win_rate": aggregate_rate, "aggregate_games": total_games, "unique_topics": len(topics),
        "threshold": 0.55, "game_results": game_results, "iteration_reports": iteration_reports,
        "skill": candidate, "skill_markdown": render_skill_markdown(candidate, metrics),
        "fact_errors": list(dict.fromkeys(fact_errors)), "rule_violations": list(dict.fromkeys(rule_violations)),
        "diagnosis": list(dict.fromkeys(item for report in iteration_reports for item in report["diagnosis"]))[:10],
        "message": "候选 Skill 已完成跨辩题换边评测；样本未达到晋级门槛，已保留供审阅。" if not enough_evidence else ("候选 Skill 未达到55%得分率，保留评测记录但不晋级。" if not promoted else "候选 Skill 已通过跨辩题门槛，晋级为正式版本；旧版本可回滚。"),
    }
    with connect() as db:
        db.execute("INSERT INTO evolution_runs VALUES (?,?,?,?)", (run_id, "evaluated", encode(result), now_iso()))
        db.execute("INSERT OR REPLACE INTO strategies VALUES (?,?,?,?,?)", (candidate_id, status, encode(candidate), encode(metrics), now_iso()))
        if promoted:
            db.execute("UPDATE strategies SET status='archived' WHERE status='active' AND id!=?", (candidate_id,))
    return {"id": run_id, **result}
