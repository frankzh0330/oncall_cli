# Implementation record

## Minimal oncall agent skeleton

Status: complete

### Decision

Build a local Python CLI around one explicit state machine. Discover skills from manifests, route deterministically, ask for required context, and stop safely when a draft skill has no investigation workflow.

### Implemented

- Standard `src` Python package and CLI entry point.
- `diagnose-ck-not-correct` draft skill with manifest and progressive-loading folders.
- Skill registry, explainable router, case context, evidence report, and local JSON persistence.
- Tests for discovery, validation, routing, clarification, safe stopping, and case persistence.
- Design and coding-principles documents.

No model, ClickHouse connection, MySQL connection, TCC connection, or code-repository tool is implemented in this phase.

