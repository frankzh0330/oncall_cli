from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen


class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


@dataclass
class HashingEmbeddingProvider:
    """Zero-dependency fallback for offline use and deterministic tests."""

    dimensions: int = 384

    @property
    def name(self) -> str:
        return f"hashing-char-ngram-v1:{self.dimensions}"

    @property
    def dimension(self) -> int:
        return self.dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        compact = normalized.replace(" ", "")
        tokens = re.findall(r"[a-z0-9_./:-]+", normalized)
        tokens.extend(compact[i : i + size] for size in (2, 3) for i in range(len(compact) - size + 1))
        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        return _normalize(vector)


@dataclass
class OllamaEmbeddingProvider:
    model: str = "nomic-embed-text"
    base_url: str = "http://127.0.0.1:11434"
    timeout: float = 60.0
    _dimension: int = 0

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        request = Request(
            f"{self.base_url.rstrip('/')}/api/embed",
            data=json.dumps({"model": self.model, "input": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.load(response)
        embeddings = [[float(value) for value in vector] for vector in payload["embeddings"]]
        if len(embeddings) != len(texts):
            raise RuntimeError("Ollama returned an unexpected embedding count")
        if embeddings:
            self._dimension = len(embeddings[0])
        return [_normalize(vector) for vector in embeddings]


def build_embedding_provider(
    provider: str | None = None,
    model: str | None = None,
) -> EmbeddingProvider:
    provider_name = (provider or os.getenv("ONCALL_EMBEDDING_PROVIDER", "hashing")).lower()
    if provider_name == "hashing":
        return HashingEmbeddingProvider()
    if provider_name == "ollama":
        return OllamaEmbeddingProvider(
            model=model or os.getenv("ONCALL_EMBEDDING_MODEL", "nomic-embed-text"),
            base_url=os.getenv("ONCALL_OLLAMA_URL", "http://127.0.0.1:11434"),
        )
    raise ValueError(f"Unsupported embedding provider: {provider_name}")
