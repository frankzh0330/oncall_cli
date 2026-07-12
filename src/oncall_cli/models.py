from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CaseContext:
    raw_input: str
    case_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    normalized_symptom: str = ""
    environment: str | None = None
    time_range: str | None = None
    entities: dict[str, str] = field(default_factory=dict)
    user_supplied: dict[str, str] = field(default_factory=dict)

    def value_for(self, name: str) -> str | None:
        value = getattr(self, name, None)
        return value if value else self.entities.get(name)


@dataclass(frozen=True)
class SkillManifest:
    id: str
    version: str
    status: str
    description: str
    intents: tuple[str, ...]
    domains: tuple[str, ...]
    systems: tuple[str, ...]
    symptoms: tuple[str, ...]
    required_context: tuple[str, ...]
    optional_context: tuple[str, ...]
    risk: str
    root: Path
    skill_path: Path


@dataclass
class RouteCandidate:
    skill_id: str
    score: int
    reasons: list[str]


@dataclass
class RouteDecision:
    candidates: list[RouteCandidate]
    selected_skill_id: str | None
    missing_context: list[str] = field(default_factory=list)
    can_execute: bool = False
    message: str = ""


@dataclass
class Evidence:
    evidence_id: str
    kind: str
    summary: str
    source: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class InvestigationReport:
    case_id: str
    status: str
    summary: str
    conclusion: str
    confidence: str
    route: RouteDecision
    skill_id: str | None
    skill_version: str | None
    evidence: list[Evidence]
    missing_information: list[str]
    next_steps: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseRecord:
    context: CaseContext
    report: InvestigationReport

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

