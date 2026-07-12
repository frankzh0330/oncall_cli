from __future__ import annotations

import json
from pathlib import Path

from .models import CaseContext, CaseRecord, InvestigationReport


class CaseStore:
    def __init__(self, root: Path):
        self.root = root

    def save(self, context: CaseContext, report: InvestigationReport) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / f"{context.case_id}.json"
        destination.write_text(
            json.dumps(CaseRecord(context, report).to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destination

