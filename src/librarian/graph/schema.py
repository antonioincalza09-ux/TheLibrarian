from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    confidence: float = 1.0
    reason: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


FindingSeverity = Literal["error", "warning", "info"]


class ValidationFinding(BaseModel):
    severity: FindingSeverity
    code: str
    message: str
    path: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    workspace_root: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ok: bool = True
    counts: dict[str, int] = Field(default_factory=dict)
    findings: list[ValidationFinding] = Field(default_factory=list)

    def finalize(self) -> "ValidationReport":
        self.ok = not any(finding.severity == "error" for finding in self.findings)
        self.counts = {
            "errors": len([finding for finding in self.findings if finding.severity == "error"]),
            "warnings": len([finding for finding in self.findings if finding.severity == "warning"]),
            "info": len([finding for finding in self.findings if finding.severity == "info"]),
        }
        return self
