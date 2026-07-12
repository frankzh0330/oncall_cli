from __future__ import annotations

from .models import InvestigationReport


CONTEXT_LABELS = {"environment": "环境", "time_range": "时间范围"}


def format_report(report: InvestigationReport) -> str:
    lines = [f"Case: {report.case_id}"]
    if report.skill_id:
        lines.append(f"已路由: {report.skill_id} ({report.skill_version})")
    if report.route.candidates:
        selected = next(
            (candidate for candidate in report.route.candidates if candidate.skill_id == report.skill_id),
            report.route.candidates[0],
        )
        if selected.reasons:
            lines.append(f"原因: {'；'.join(selected.reasons)}")
    lines.extend(
        [
            f"调查状态: {report.status}",
            f"结论: {report.conclusion}",
            f"置信状态: {report.confidence}",
        ]
    )
    if report.evidence:
        lines.append("证据:")
        lines.extend(f"  - [{item.evidence_id}] {item.summary} ({item.source})" for item in report.evidence)
    if report.missing_information:
        lines.append("缺失信息/能力:")
        lines.extend(
            f"  - {CONTEXT_LABELS.get(item, item)}" for item in report.missing_information
        )
    if report.next_steps:
        lines.append("下一步:")
        lines.extend(f"  - {item}" for item in report.next_steps)
    return "\n".join(lines)

