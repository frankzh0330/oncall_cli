from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_claude_project_instruction_routes_through_cli_registry():
    instructions = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert ".claude/skills/oncall-investigation/SKILL.md" in instructions
    assert 'PYTHONPATH=src python3 -m oncall_cli "<original incident description>"' in instructions
    assert "Do not choose a business skill" in instructions


def test_claude_skill_has_discovery_metadata_and_safe_stop_rules():
    skill = (
        PROJECT_ROOT / ".claude" / "skills" / "oncall-investigation" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert skill.startswith("---\nname: oncall-investigation\n")
    assert "description:" in skill
    assert "blocked_by_incomplete_skill" in skill
    assert "The Python registry is the only authority" in skill
