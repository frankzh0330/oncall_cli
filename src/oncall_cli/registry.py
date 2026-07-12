from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import SkillManifest


REQUIRED_FIELDS = {
    "id",
    "version",
    "status",
    "description",
    "intents",
    "domains",
    "systems",
    "symptoms",
    "required_context",
    "optional_context",
    "risk",
}


@dataclass
class SkillRegistry:
    skills_root: Path
    skills: dict[str, SkillManifest] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def scan(self) -> "SkillRegistry":
        self.skills.clear()
        self.errors.clear()
        if not self.skills_root.exists():
            self.errors.append(f"Skills directory does not exist: {self.skills_root}")
            return self

        for manifest_path in sorted(self.skills_root.glob("*/skill.yaml")):
            try:
                manifest = self._load_manifest(manifest_path)
                self.skills[manifest.id] = manifest
            except (OSError, ValueError) as exc:
                self.errors.append(f"{manifest_path}: {exc}")
        return self

    def _load_manifest(self, path: Path) -> SkillManifest:
        data = parse_manifest(path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED_FIELDS - data.keys())
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        if data["id"] != path.parent.name:
            raise ValueError("manifest id must match its directory name")
        skill_path = path.parent / "SKILL.md"
        if not skill_path.is_file():
            raise ValueError("SKILL.md is missing")
        if data["id"] in self.skills:
            raise ValueError(f"duplicate skill id: {data['id']}")

        list_fields = (
            "intents",
            "domains",
            "systems",
            "symptoms",
            "required_context",
            "optional_context",
        )
        for name in list_fields:
            if not isinstance(data[name], list) or not all(isinstance(v, str) for v in data[name]):
                raise ValueError(f"{name} must be a list of strings")

        return SkillManifest(
            id=str(data["id"]),
            version=str(data["version"]),
            status=str(data["status"]),
            description=str(data["description"]),
            intents=tuple(data["intents"]),
            domains=tuple(data["domains"]),
            systems=tuple(data["systems"]),
            symptoms=tuple(data["symptoms"]),
            required_context=tuple(data["required_context"]),
            optional_context=tuple(data["optional_context"]),
            risk=str(data["risk"]),
            root=path.parent,
            skill_path=skill_path,
        )

    def get(self, skill_id: str) -> SkillManifest | None:
        return self.skills.get(skill_id)


def parse_manifest(content: str) -> dict[str, str | list[str]]:
    """Parse the flat scalar-and-list YAML subset used by skill manifests."""
    result: dict[str, str | list[str]] = {}
    current_list: list[str] | None = None
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"line {line_number}: list item has no parent field")
            value = stripped[2:].strip()
            if not value:
                raise ValueError(f"line {line_number}: empty list item")
            current_list.append(value)
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise ValueError(f"line {line_number}: unsupported manifest syntax")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key or key in result:
            raise ValueError(f"line {line_number}: invalid or duplicate field")
        value = raw_value.strip()
        if value == "[]":
            result[key] = []
            current_list = None
        elif value:
            result[key] = value
            current_list = None
        else:
            current_list = []
            result[key] = current_list
    return result
