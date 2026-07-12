from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingProvider


INDEXABLE_STATUSES = {"completed", "resolved", "success"}


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_type: str
    content: str


@dataclass(frozen=True)
class SearchResult:
    case_id: str
    score: float
    chunk_type: str
    content: str
    skill_id: str | None
    skill_version: str | None
    status: str
    source_path: str


@dataclass(frozen=True)
class IndexOutcome:
    case_id: str
    action: str
    chunks: int = 0
    reason: str = ""


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack(blob: bytes, dimension: int) -> tuple[float, ...]:
    return struct.unpack(f"<{dimension}f", blob)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def case_to_chunks(record: dict[str, Any]) -> list[KnowledgeChunk]:
    context = record.get("context", {})
    report = record.get("report", {})
    entities = context.get("entities", {})
    evidence = report.get("evidence", [])
    summary = "\n".join(
        part
        for part in (
            f"故障描述: {_text(context.get('raw_input'))}",
            f"规范化现象: {_text(context.get('normalized_symptom'))}",
            f"环境: {_text(context.get('environment'))}",
            f"时间范围: {_text(context.get('time_range'))}",
            f"实体: {_text(entities)}",
            f"使用技能: {_text(report.get('skill_id'))} {_text(report.get('skill_version'))}",
        )
        if not part.endswith(": ")
    )
    diagnosis = "\n".join(
        (
            f"结论: {_text(report.get('conclusion'))}",
            f"置信度: {_text(report.get('confidence'))}",
            f"证据: {_text(evidence)}",
        )
    )
    resolution = "\n".join(
        (
            f"后续步骤: {_text(report.get('next_steps', []))}",
            f"用户补充: {_text(context.get('user_supplied', {}))}",
        )
    )
    return [
        KnowledgeChunk("summary", summary),
        KnowledgeChunk("diagnosis", diagnosis),
        KnowledgeChunk("resolution", resolution),
    ]


class KnowledgeStore:
    def __init__(self, database: Path, provider: EmbeddingProvider):
        self.database = database
        self.provider = provider

    def _connect(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                region TEXT,
                environment TEXT,
                system TEXT,
                skill_id TEXT,
                skill_version TEXT,
                status TEXT NOT NULL,
                conclusion TEXT,
                source_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding_provider TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS case_chunks (
                chunk_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
                chunk_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                embedding_provider TEXT NOT NULL,
                content_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cases_filters
                ON cases(region, environment, system, status);
            CREATE INDEX IF NOT EXISTS idx_chunks_case ON case_chunks(case_id);
            """
        )
        return connection

    def index_file(self, path: Path, include_incomplete: bool = False) -> IndexOutcome:
        record = json.loads(path.read_text(encoding="utf-8"))
        context = record.get("context", {})
        report = record.get("report", {})
        case_id = _text(context.get("case_id") or report.get("case_id") or path.stem)
        status = _text(report.get("status"))
        if status not in INDEXABLE_STATUSES and not include_incomplete:
            return IndexOutcome(case_id, "skipped", reason=f"status {status!r} is not resolved")
        chunks = case_to_chunks(record)
        canonical = json.dumps(record, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT content_hash, embedding_provider FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if existing and existing["content_hash"] == content_hash and existing["embedding_provider"] == self.provider.name:
                return IndexOutcome(case_id, "unchanged", chunks=len(chunks))
        embeddings = self.provider.embed([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise RuntimeError("Embedding provider returned an unexpected result count")
        dimension = len(embeddings[0]) if embeddings else 0
        entities = context.get("entities", {})
        with self._connect() as connection:
            connection.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
            connection.execute(
                """INSERT INTO cases (
                    case_id, created_at, region, environment, system, skill_id,
                    skill_version, status, conclusion, source_path, content_hash,
                    embedding_provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    case_id,
                    _text(context.get("created_at")),
                    entities.get("region") or context.get("region"),
                    context.get("environment"),
                    entities.get("system"),
                    report.get("skill_id"),
                    report.get("skill_version"),
                    status,
                    report.get("conclusion"),
                    str(path.resolve()),
                    content_hash,
                    self.provider.name,
                ),
            )
            for position, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                chunk_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                connection.execute(
                    """INSERT INTO case_chunks (
                        chunk_id, case_id, chunk_type, content, embedding, dimension,
                        embedding_provider, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"{case_id}:{position}:{chunk.chunk_type}",
                        case_id,
                        chunk.chunk_type,
                        chunk.content,
                        _pack(embedding),
                        dimension,
                        self.provider.name,
                        chunk_hash,
                    ),
                )
        return IndexOutcome(case_id, "indexed", chunks=len(chunks))

    def rebuild(self, cases_root: Path, include_incomplete: bool = False) -> list[IndexOutcome]:
        with self._connect() as connection:
            connection.execute("DELETE FROM case_chunks")
            connection.execute("DELETE FROM cases")
        return [
            self.index_file(path, include_incomplete=include_incomplete)
            for path in sorted(cases_root.glob("*.json"))
        ]

    def search(
        self,
        query: str,
        limit: int = 5,
        region: str | None = None,
        environment: str | None = None,
        system: str | None = None,
    ) -> list[SearchResult]:
        query_vector = self.provider.embed([query])[0]
        clauses = ["c.embedding_provider = ?", "cc.embedding_provider = ?"]
        parameters: list[Any] = [self.provider.name, self.provider.name]
        for column, value in (("region", region), ("environment", environment), ("system", system)):
            if value:
                clauses.append(f"c.{column} = ?")
                parameters.append(value)
        sql = f"""SELECT c.*, cc.chunk_type, cc.content, cc.embedding, cc.dimension
                  FROM case_chunks cc JOIN cases c ON c.case_id = cc.case_id
                  WHERE {' AND '.join(clauses)}"""
        best: dict[str, SearchResult] = {}
        with self._connect() as connection:
            for row in connection.execute(sql, parameters):
                vector = _unpack(row["embedding"], row["dimension"])
                if len(vector) != len(query_vector):
                    continue
                score = sum(left * right for left, right in zip(query_vector, vector, strict=True))
                candidate = SearchResult(
                    case_id=row["case_id"],
                    score=score,
                    chunk_type=row["chunk_type"],
                    content=row["content"],
                    skill_id=row["skill_id"],
                    skill_version=row["skill_version"],
                    status=row["status"],
                    source_path=row["source_path"],
                )
                if row["case_id"] not in best or score > best[row["case_id"]].score:
                    best[row["case_id"]] = candidate
        return sorted(best.values(), key=lambda result: result.score, reverse=True)[:limit]

    def delete(self, case_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))
        return cursor.rowcount > 0

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            cases = connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            chunks = connection.execute("SELECT COUNT(*) FROM case_chunks").fetchone()[0]
            providers = [row[0] for row in connection.execute("SELECT DISTINCT embedding_provider FROM cases")]
        return {"database": str(self.database), "cases": cases, "chunks": chunks, "providers": providers}
