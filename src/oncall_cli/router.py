from __future__ import annotations

import re

from .models import CaseContext, RouteCandidate, RouteDecision, SkillManifest


SYSTEM_TERMS = {"clickhouse": ("clickhouse", "ck")}
SYMPTOM_TERMS = {
    "data_not_correct": ("数据不对", "对不上", "不正确", "incorrect", "wrong"),
    "data_missing": ("数据缺失", "没有数据", "少数据", "missing"),
    "data_inconsistent": ("不一致", "inconsistent", "mismatch"),
    "data_delayed": ("延迟", "没更新", "delayed", "stale"),
}
ENVIRONMENT_TERMS = {
    "production": ("线上", "生产", "prod", "production"),
    "staging": ("预发", "staging"),
    "test": ("测试环境", "test"),
}


def contains_term(text: str, term: str) -> bool:
    if term == "ck":
        return bool(re.search(r"(?<![a-z0-9])ck(?![a-z0-9])", text))
    return term in text


class SkillRouter:
    minimum_score = 5

    def route(self, context: CaseContext, skills: list[SkillManifest]) -> RouteDecision:
        text = context.raw_input.lower().strip()
        candidates: list[RouteCandidate] = []

        for skill in skills:
            score = 0
            reasons: list[str] = []
            for system in skill.systems:
                terms = SYSTEM_TERMS.get(system, (system,))
                matched = next((term for term in terms if contains_term(text, term)), None)
                if matched:
                    score += 3
                    reasons.append(f"命中系统 {matched}")
            for symptom in skill.symptoms:
                terms = SYMPTOM_TERMS.get(symptom, (symptom.replace("_", " "),))
                matched = next((term for term in terms if contains_term(text, term)), None)
                if matched:
                    score += 2
                    reasons.append(f"命中现象 {matched}")
            if score:
                candidates.append(RouteCandidate(skill.id, score, reasons))

        candidates.sort(key=lambda item: (-item.score, item.skill_id))
        qualified = [item for item in candidates if item.score >= self.minimum_score]
        if not qualified:
            return RouteDecision(candidates, None, message="没有找到可靠匹配的 skill；不会猜测执行路径。")
        if len(qualified) > 1 and qualified[0].score == qualified[1].score:
            return RouteDecision(candidates, None, message="多个 skill 的匹配度相同，需要更多现象信息。")

        selected = next(skill for skill in skills if skill.id == qualified[0].skill_id)
        missing = [name for name in selected.required_context if not context.value_for(name)]
        return RouteDecision(
            candidates=candidates,
            selected_skill_id=selected.id,
            missing_context=missing,
            can_execute=not missing,
            message="已完成确定性 skill 路由。",
        )


def normalize_context(context: CaseContext) -> CaseContext:
    text = context.raw_input.lower()
    context.normalized_symptom = "ck_data_not_correct" if any(
        term in text for terms in SYMPTOM_TERMS.values() for term in terms
    ) else text.strip()
    for environment, terms in ENVIRONMENT_TERMS.items():
        if any(contains_term(text, term) for term in terms):
            context.environment = environment
            break
    if any(term in text for term in ("最近一小时", "过去一小时", "last hour")):
        context.time_range = "最近一小时"
    return context

