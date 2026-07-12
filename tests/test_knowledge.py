import json
from pathlib import Path

from oncall_cli.embeddings import HashingEmbeddingProvider
from oncall_cli.knowledge import KnowledgeStore
from oncall_cli.knowledge_cli import main as knowledge_main


def write_case(
    root: Path,
    case_id: str,
    description: str,
    conclusion: str,
    *,
    region: str = "sg",
    system: str = "clickhouse",
    status: str = "resolved",
) -> Path:
    path = root / f"{case_id}.json"
    path.write_text(
        json.dumps(
            {
                "context": {
                    "case_id": case_id,
                    "created_at": "2026-07-12T00:00:00+00:00",
                    "raw_input": description,
                    "normalized_symptom": description,
                    "environment": "production",
                    "time_range": "最近一小时",
                    "entities": {"region": region, "system": system},
                    "user_supplied": {},
                },
                "report": {
                    "case_id": case_id,
                    "status": status,
                    "conclusion": conclusion,
                    "confidence": "confirmed",
                    "route": {"candidates": [], "selected_skill_id": "diagnose-ck-not-correct"},
                    "skill_id": "diagnose-ck-not-correct",
                    "skill_version": "1.0.0",
                    "evidence": [{"summary": conclusion, "source": "test"}],
                    "missing_information": [],
                    "next_steps": ["验证数据恢复"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def build_store(tmp_path: Path) -> KnowledgeStore:
    return KnowledgeStore(tmp_path / "knowledge.db", HashingEmbeddingProvider())


def test_index_is_incremental_and_search_returns_related_case(tmp_path):
    cases = tmp_path / "cases"
    cases.mkdir()
    event_case = write_case(
        cases,
        "event-delay",
        "SG ClickHouse event 表事件缺失，消费者延迟",
        "消费任务积压导致 event 数据延迟落入",
    )
    write_case(
        cases,
        "ab-wrong",
        "EU ClickHouse AB 实验配置不一致",
        "AB 配置同步失败",
        region="eu",
    )
    store = build_store(tmp_path)

    first = store.index_file(event_case)
    second = store.index_file(event_case)
    store.index_file(cases / "ab-wrong.json")
    results = store.search("SG event 数据消费延迟和事件缺失", limit=2)

    assert first.action == "indexed"
    assert second.action == "unchanged"
    assert results[0].case_id == "event-delay"
    assert results[0].source_path == str(event_case.resolve())


def test_filters_status_and_delete(tmp_path):
    cases = tmp_path / "cases"
    cases.mkdir()
    sg = write_case(cases, "sg-case", "SG CK event 数据缺失", "SG 消费延迟")
    eu = write_case(cases, "eu-case", "EU CK event 数据缺失", "EU 消费延迟", region="eu")
    blocked = write_case(
        cases,
        "blocked-case",
        "SG CK event 数据缺失",
        "尚未执行调查",
        status="blocked_by_incomplete_skill",
    )
    store = build_store(tmp_path)

    assert store.index_file(blocked).action == "skipped"
    store.index_file(sg)
    store.index_file(eu)
    results = store.search("event 数据缺失", region="eu")

    assert [result.case_id for result in results] == ["eu-case"]
    assert store.status()["cases"] == 2
    assert store.delete("eu-case") is True
    assert store.delete("eu-case") is False
    assert store.status()["cases"] == 1


def test_rebuild_and_cli_output(tmp_path, capsys):
    cases = tmp_path / "cases"
    cases.mkdir()
    write_case(cases, "one", "SG CK event 延迟", "消费积压")
    database = tmp_path / "cli.db"

    exit_code = knowledge_main(
        ["--database", str(database), "rebuild", "--cases-root", str(cases)],
        tmp_path,
    )
    knowledge_main(["--database", str(database), "search", "event 消费延迟"], tmp_path)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "indexed: one" in output
    assert '"case_id": "one"' in output
