from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from src.config import APP_TIMEZONE

DEFAULT_TIMEZONE = APP_TIMEZONE


class NodePosition(BaseModel):
    x: float = 0
    y: float = 0


class Node(BaseModel):
    id: str
    type: Literal["credential", "extract", "transform", "load"]
    position: NodePosition = Field(default_factory=NodePosition)
    data: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None


class PipelineGraph(BaseModel):
    pipeline_name: str = "Untitled"
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    graph: PipelineGraph
    node_id: str


class LoginRequest(BaseModel):
    login_id: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=256)


class DBConnectionRequest(BaseModel):
    db_type: Literal["postgresql", "mysql", "redshift"] = "mysql"
    host: str = Field(..., min_length=1, max_length=255)
    port: Optional[str] = Field(default=None, max_length=12)
    database: str = Field(..., min_length=1, max_length=120)
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(default="", max_length=512)


class ConnectionProfileRequest(DBConnectionRequest):
    name: str = Field(..., min_length=1, max_length=160)
    allowed_schemas: list[str] = Field(default_factory=list)


class ConnectionProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    password: Optional[str] = Field(default=None, max_length=512)
    allowed_schemas: Optional[list[str]] = None


class SqlAssistantGenerateRequest(BaseModel):
    connection_id: int = Field(..., ge=1)
    requirement: str = Field(..., min_length=3, max_length=4000)


class SqlAssistantPreviewRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)


class ScheduleRuleRequest(BaseModel):
    name: str = Field(default="", max_length=200)
    trigger_type: Literal["cron", "date"] = "cron"
    day_of_week: str = Field(..., min_length=1, max_length=80)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    timezone: str = Field(default=DEFAULT_TIMEZONE, max_length=80)


class CreateSchedulesRequest(BaseModel):
    rules: list[ScheduleRuleRequest] = Field(..., min_length=1)
