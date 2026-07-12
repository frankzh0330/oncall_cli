from __future__ import annotations

from enum import StrEnum

from .models import CaseContext, Evidence, InvestigationReport, RouteDecision
from .registry import SkillRegistry
from .router import SkillRouter, normalize_context


class InvestigationState(StrEnum):
    INTAKE = "intake"
    NORMALIZE = "normalize"
    ROUTE = "route"
    CHECK_CONTEXT = "check_context"
    LOAD_SKILL = "load_skill"
    NEEDS_USER_INPUT = "needs_user_input"
    NO_MATCHING_SKILL = "no_matching_skill"
    BLOCKED_BY_INCOMPLETE_SKILL = "blocked_by_incomplete_skill"


class InvestigationEngine:
    def __init__(self, registry: SkillRegistry, router: SkillRouter | None = None):
        self.registry = registry
        self.router = router or SkillRouter()

    def investigate(self, context: CaseContext) -> InvestigationReport:
        normalize_context(context)
        decision = self.router.route(context, list(self.registry.skills.values()))
        if not decision.selected_skill_id:
            return self._report_without_skill(context, decision)
        skill = self.registry.get(decision.selected_skill_id)
        assert skill is not None

        route_evidence = Evidence(
            evidence_id="E-ROUTE-1",
            kind="route_decision",
            summary="；".join(decision.candidates[0].reasons),
            source=f"skill:{skill.id}@{skill.version}",
        )
        if decision.missing_context:
            return InvestigationReport(
                case_id=context.case_id,
                status=InvestigationState.NEEDS_USER_INPUT,
                summary=context.raw_input,
                conclusion="已完成 skill 路由，但缺少开始调查所需的上下文。",
                confidence="route_confirmed_investigation_not_started",
                route=decision,
                skill_id=skill.id,
                skill_version=skill.version,
                evidence=[route_evidence],
                missing_information=decision.missing_context,
                next_steps=[f"请补充：{name}" for name in decision.missing_context],
            )

        skill.skill_path.read_text(encoding="utf-8")
        if skill.status == "draft":
            return InvestigationReport(
                case_id=context.case_id,
                status=InvestigationState.BLOCKED_BY_INCOMPLETE_SKILL,
                summary=context.raw_input,
                conclusion="用户描述已路由到 CK 数据正确性排查 skill；尚未执行任何 CK 调查。",
                confidence="route_confirmed_root_cause_unknown",
                route=decision,
                skill_id=skill.id,
                skill_version=skill.version,
                evidence=[route_evidence],
                missing_information=["skill 调查流程尚未填写"],
                next_steps=["补充 SKILL.md 的只读调查流程、证据要求和停止条件。"],
            )
        return InvestigationReport(
            case_id=context.case_id,
            status=InvestigationState.BLOCKED_BY_INCOMPLETE_SKILL,
            summary=context.raw_input,
            conclusion="该骨架尚未启用 published skill 执行器，未执行任何外部调查。",
            confidence="route_confirmed_root_cause_unknown",
            route=decision,
            skill_id=skill.id,
            skill_version=skill.version,
            evidence=[route_evidence],
            missing_information=["published skill 执行器未启用"],
            next_steps=["在启用该 skill 前实现并测试只读执行器。"],
        )

    @staticmethod
    def _report_without_skill(context: CaseContext, decision: RouteDecision) -> InvestigationReport:
        return InvestigationReport(
            case_id=context.case_id,
            status=InvestigationState.NO_MATCHING_SKILL,
            summary=context.raw_input,
            conclusion="没有找到可靠匹配的 skill，因此未执行调查。",
            confidence="unknown",
            route=decision,
            skill_id=None,
            skill_version=None,
            evidence=[],
            missing_information=["需要更明确的系统和现象信息"],
            next_steps=["补充受影响系统、具体现象、环境和时间范围。"],
        )
