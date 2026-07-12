from __future__ import annotations

import argparse
import json
from pathlib import Path

from .embeddings import build_embedding_provider
from .knowledge import IndexOutcome, KnowledgeStore


def build_parser(project_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oncall_cli knowledge", description="Local embedding knowledge index")
    parser.add_argument("--database", type=Path, default=project_root / "knowledge" / "knowledge.db")
    parser.add_argument("--provider", choices=("hashing", "ollama"), default=None)
    parser.add_argument("--model", default=None, help="Embedding model name for the selected provider")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser("index", help="Index or update one case")
    index.add_argument("case", type=Path)
    index.add_argument("--include-incomplete", action="store_true")

    rebuild = subparsers.add_parser("rebuild", help="Rebuild the index from a cases directory")
    rebuild.add_argument("--cases-root", type=Path, default=project_root / "cases")
    rebuild.add_argument("--include-incomplete", action="store_true")

    search = subparsers.add_parser("search", help="Search indexed cases by embedding similarity")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--region")
    search.add_argument("--environment")
    search.add_argument("--system")

    delete = subparsers.add_parser("delete", help="Delete one case from the index")
    delete.add_argument("case_id")
    subparsers.add_parser("status", help="Show index statistics")
    return parser


def _print_outcome(outcome: IndexOutcome) -> None:
    detail = f" ({outcome.reason})" if outcome.reason else ""
    print(f"{outcome.action}: {outcome.case_id}, chunks={outcome.chunks}{detail}")


def main(argv: list[str], project_root: Path) -> int:
    args = build_parser(project_root).parse_args(argv)
    provider = build_embedding_provider(args.provider, args.model)
    store = KnowledgeStore(args.database, provider)
    if args.command == "index":
        _print_outcome(store.index_file(args.case, include_incomplete=args.include_incomplete))
    elif args.command == "rebuild":
        outcomes = store.rebuild(args.cases_root, include_incomplete=args.include_incomplete)
        for outcome in outcomes:
            _print_outcome(outcome)
    elif args.command == "search":
        results = store.search(
            args.query,
            limit=args.limit,
            region=args.region,
            environment=args.environment,
            system=args.system,
        )
        print(
            json.dumps(
                [
                    {
                        "case_id": result.case_id,
                        "score": round(result.score, 6),
                        "matched_chunk": result.chunk_type,
                        "content": result.content,
                        "skill_id": result.skill_id,
                        "skill_version": result.skill_version,
                        "status": result.status,
                        "source_path": result.source_path,
                    }
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "delete":
        print("deleted" if store.delete(args.case_id) else "not found")
    elif args.command == "status":
        print(json.dumps(store.status(), ensure_ascii=False, indent=2))
    return 0
