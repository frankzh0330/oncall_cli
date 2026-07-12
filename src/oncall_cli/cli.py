from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from .case_store import CaseStore
from .engine import InvestigationEngine, InvestigationState
from .models import CaseContext
from .registry import SkillRegistry
from .reporter import CONTEXT_LABELS, format_report


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_case(
    raw_input: str,
    engine: InvestigationEngine,
    store: CaseStore,
    ask: Callable[[str], str] = input,
) -> str:
    context = CaseContext(raw_input=raw_input)
    report = engine.investigate(context)
    if report.status == InvestigationState.NEEDS_USER_INPUT:
        for name in list(report.missing_information):
            answer = ask(f"需要补充{CONTEXT_LABELS.get(name, name)}: ").strip()
            if answer:
                setattr(context, name, answer)
                context.user_supplied[name] = answer
        report = engine.investigate(context)
    path = store.save(context, report)
    return f"{format_report(report)}\n记录已保存: {path}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local skill-routed oncall agent")
    parser.add_argument("issue", nargs="*", help="Oncall symptom; omit for interactive mode")
    parser.add_argument("--skills-root", type=Path, default=project_root() / "skills")
    parser.add_argument("--cases-root", type=Path, default=project_root() / "cases")
    return parser


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "knowledge":
        from .knowledge_cli import main as knowledge_main

        raise SystemExit(knowledge_main(sys.argv[2:], project_root()))
    args = build_parser().parse_args()
    registry = SkillRegistry(args.skills_root).scan()
    if registry.errors:
        for error in registry.errors:
            print(f"Skill 加载错误: {error}")
    engine = InvestigationEngine(registry)
    store = CaseStore(args.cases_root)

    if args.issue:
        print(run_case(" ".join(args.issue), engine, store))
        return

    while True:
        try:
            issue = input("oncall> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if issue.lower() in {"exit", "quit"}:
            return
        if issue:
            print(run_case(issue, engine, store))


if __name__ == "__main__":
    main()
