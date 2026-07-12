import json
from pathlib import Path

from oncall_cli.case_store import CaseStore
from oncall_cli.cli import run_case
from oncall_cli.engine import InvestigationEngine
from oncall_cli.registry import SkillRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_engine():
    return InvestigationEngine(SkillRegistry(PROJECT_ROOT / "skills").scan())


def test_complete_context_stops_at_draft_skill_and_saves_case(tmp_path):
    output = run_case(
        "线上 CK 数据不对，排查最近一小时",
        build_engine(),
        CaseStore(tmp_path),
    )

    assert "已路由: diagnose-ck-not-correct" in output
    assert "blocked_by_incomplete_skill" in output
    assert "尚未执行任何 CK 调查" in output
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    record = json.loads(saved[0].read_text(encoding="utf-8"))
    assert record["report"]["skill_version"] == "0.1.0"
    assert record["report"]["evidence"][0]["evidence_id"] == "E-ROUTE-1"


def test_missing_context_is_requested_and_preserved(tmp_path):
    answers = iter(["production", "最近一小时"])

    output = run_case(
        "CK 数据不一致",
        build_engine(),
        CaseStore(tmp_path),
        ask=lambda _prompt: next(answers),
    )

    record = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert record["context"]["environment"] == "production"
    assert record["context"]["time_range"] == "最近一小时"
    assert record["context"]["user_supplied"] == {
        "environment": "production",
        "time_range": "最近一小时",
    }
    assert "blocked_by_incomplete_skill" in output


def test_unrelated_issue_saves_no_match_report(tmp_path):
    output = run_case("Java 服务无法启动", build_engine(), CaseStore(tmp_path))

    assert "no_matching_skill" in output
    assert "未执行调查" in output
