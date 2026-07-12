from pathlib import Path

from oncall_cli.registry import SkillRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_registry_discovers_example_skill():
    registry = SkillRegistry(PROJECT_ROOT / "skills").scan()

    assert registry.errors == []
    assert list(registry.skills) == ["diagnose-ck-not-correct"]
    assert registry.skills["diagnose-ck-not-correct"].status == "draft"


def test_registry_reports_directory_id_mismatch(tmp_path):
    skill_dir = tmp_path / "wrong-name"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# placeholder", encoding="utf-8")
    (skill_dir / "skill.yaml").write_text(
        """id: expected-name
version: 0.1.0
status: draft
description: test
intents: []
domains: []
systems: []
symptoms: []
required_context: []
optional_context: []
risk: read_only
""",
        encoding="utf-8",
    )

    registry = SkillRegistry(tmp_path).scan()

    assert registry.skills == {}
    assert "manifest id must match" in registry.errors[0]
