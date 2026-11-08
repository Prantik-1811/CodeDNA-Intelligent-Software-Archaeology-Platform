"""Pydantic schemas for the CodeDNA API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------
class RepositoryBase(BaseModel):
    repo_url: Optional[str] = None
    local_path: str = ""
    status: str = "registered"


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryOut(RepositoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Analysis job
# ---------------------------------------------------------------------------
class AnalysisJobBase(BaseModel):
    repo_id: int
    status: str = "pending"


class AnalysisJobCreate(AnalysisJobBase):
    pass


class AnalysisJobOut(AnalysisJobBase):
    id: int
    result_json: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Module risk
# ---------------------------------------------------------------------------
class ModuleRiskOut(BaseModel):
    id: int
    repo_id: int
    path: str
    risk_score: float
    risk_level: str
    features_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Impact report
# ---------------------------------------------------------------------------
class ImpactReportOut(BaseModel):
    id: int
    repo_id: int
    target: str
    risk_score: float
    risk_level: str
    report_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
class GraphNodeOut(BaseModel):
    id: str
    type: str
    label: str
    file_path: str
    line: int
    language: Optional[str] = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    type: str
    line: int = 0


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    cycles: list[list[str]] = []
    metrics: dict[str, Any] = {}
