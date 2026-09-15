from typing import Any, Literal

from pydantic import BaseModel, Field


Stance = Literal["正方", "反方"]


class ProjectCreate(BaseModel):
    topic: str = Field(min_length=4, max_length=300)
    stance: Stance = "正方"
    config: dict[str, Any] = Field(default_factory=dict)


class DebateCreate(BaseModel):
    project_id: str
    mode: Literal["human", "arena"] = "human"
    user_stance: Stance = "正方"
    difficulty: Literal["陪练", "标准", "赛事"] = "标准"
    rounds: int = Field(default=6, ge=2, le=16)


class TurnCreate(BaseModel):
    content: str = Field(min_length=1, max_length=6000)
    stage: str = "自由辩论"


class WorkspacePatch(BaseModel):
    workspace: dict[str, Any]


class EvolutionCreate(BaseModel):
    project_id: str
    games: int = Field(default=2, ge=2, le=4, description="每个辩题的换边对局数")
    iterations: int = Field(default=1, ge=1, le=4)
    topics: list[str] = Field(default_factory=list, max_length=8)
    mode: Literal["incremental", "promotion"] = "incremental"
    max_new_games: int = Field(
        default=1,
        ge=0,
        le=20,
        description="本次最多新生成的对局总数；历史轨迹复用不计入",
    )
    reuse_trajectories: bool = True
    max_api_requests: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="包括重试在内的实际模型 HTTP 请求硬上限",
    )
