from pathlib import Path

from oncall_cli.models import CaseContext
from oncall_cli.registry import SkillRegistry
from oncall_cli.router import SkillRouter, normalize_context


SKILLS = list(SkillRegistry(Path(__file__).resolve().parents[1] / "skills").scan().skills.values())


def test_routes_chinese_ck_incorrect_data_with_reasons():
    context = normalize_context(CaseContext("线上 CK 的订单数据和源数据对不上，帮我排查最近一小时"))

    decision = SkillRouter().route(context, SKILLS)

    assert decision.selected_skill_id == "diagnose-ck-not-correct"
    assert decision.can_execute
    assert any("命中系统 ck" in reason for reason in decision.candidates[0].reasons)
    assert any("命中现象 对不上" in reason for reason in decision.candidates[0].reasons)


def test_routes_clickhouse_missing_data_but_requires_context():
    decision = SkillRouter().route(CaseContext("ClickHouse 数据缺失"), SKILLS)

    assert decision.selected_skill_id == "diagnose-ck-not-correct"
    assert decision.missing_context == ["environment", "time_range"]
    assert not decision.can_execute


def test_does_not_route_unrelated_problem():
    decision = SkillRouter().route(CaseContext("Spring 服务启动失败"), SKILLS)

    assert decision.selected_skill_id is None
    assert not decision.can_execute


def test_generic_data_problem_does_not_imply_clickhouse():
    decision = SkillRouter().route(CaseContext("线上数据不对"), SKILLS)

    assert decision.selected_skill_id is None
