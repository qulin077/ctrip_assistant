import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from project_config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    KB_CHUNKS_PATH,
    KB_VECTOR_STORE_DIR,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)
from tools.kb_embeddings import create_embedding_model
from tools.kb_embeddings import _tokenize


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_embedding_model(provider: Optional[str] = None):
    provider = provider or EMBEDDING_PROVIDER
    if provider == "openai":
        return create_embedding_model(
            provider="openai",
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            model=EMBEDDING_MODEL,
        )
    if provider == "sentence_transformers":
        return create_embedding_model(provider="sentence_transformers", model=EMBEDDING_MODEL)
    return create_embedding_model(provider="local_hash")


def chunk_embedding_text(chunk: dict[str, Any]) -> str:
    return "\n".join(
        str(part)
        for part in [
            chunk.get("title", ""),
            chunk.get("service", ""),
            chunk.get("policy_type", ""),
            chunk.get("section_title", ""),
            chunk.get("chunk_text", ""),
        ]
        if part
    )


def token_overlap_score(query: str, chunk: dict[str, Any]) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0
    doc_tokens = set(_tokenize(chunk_embedding_text(chunk)))
    return len(query_tokens & doc_tokens) / len(query_tokens)


class PolicyVectorStore:
    def __init__(
        self,
        vectors: np.ndarray,
        chunks: list[dict[str, Any]],
        embedding_model,
    ):
        self.vectors = vectors.astype(np.float32)
        self.chunks = chunks
        self.embedding_model = embedding_model

    @classmethod
    def build_from_chunks(
        cls,
        chunks_path: Path = KB_CHUNKS_PATH,
        vector_store_dir: Path = KB_VECTOR_STORE_DIR,
        provider: Optional[str] = None,
    ):
        chunks = read_jsonl(chunks_path)
        embedding_model = load_embedding_model(provider)
        texts = [chunk_embedding_text(chunk) for chunk in chunks]
        vectors = np.array(embedding_model.embed_documents(texts), dtype=np.float32)
        vector_store_dir.mkdir(parents=True, exist_ok=True)
        np.save(vector_store_dir / "vectors.npy", vectors)
        (vector_store_dir / "chunks.jsonl").write_text(
            "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n",
            encoding="utf-8",
        )
        write_json(
            vector_store_dir / "manifest.json",
            {
                "embedding_provider": embedding_model.provider_name,
                "embedding_model": EMBEDDING_MODEL,
                "chunk_count": len(chunks),
                "dimension": int(vectors.shape[1]) if len(vectors.shape) == 2 else 0,
                "chunks_path": str(chunks_path),
            },
        )
        return cls(vectors=vectors, chunks=chunks, embedding_model=embedding_model)

    @classmethod
    def load(
        cls,
        vector_store_dir: Path = KB_VECTOR_STORE_DIR,
        provider: Optional[str] = None,
    ):
        vectors_path = vector_store_dir / "vectors.npy"
        chunks_path = vector_store_dir / "chunks.jsonl"
        if not vectors_path.exists() or not chunks_path.exists():
            raise FileNotFoundError(
                f"Vector store not found in {vector_store_dir}. "
                "Run `python tools/build_vector_index.py` first."
            )
        vectors = np.load(vectors_path)
        chunks = read_jsonl(chunks_path)
        embedding_model = load_embedding_model(provider)
        return cls(vectors=vectors, chunks=chunks, embedding_model=embedding_model)

    def search(
        self,
        query: str,
        top_k: int = 3,
        service: Optional[str] = None,
        policy_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        candidates = [
            (idx, chunk)
            for idx, chunk in enumerate(self.chunks)
            if (service is None or chunk.get("service") == service)
            and (policy_type is None or chunk.get("policy_type") == policy_type)
        ]
        if not candidates:
            return []

        query_vector = np.array(self.embedding_model.embed_query(query), dtype=np.float32)
        candidate_indices = np.array([idx for idx, _ in candidates], dtype=np.int64)
        candidate_vectors = self.vectors[candidate_indices]
        vector_scores = candidate_vectors @ query_vector
        overlap_scores = np.array(
            [token_overlap_score(query, chunk) for _, chunk in candidates],
            dtype=np.float32,
        )
        scores = (0.85 * vector_scores) + (0.15 * overlap_scores)
        top_count = min(top_k, len(candidates))
        order = np.argsort(-scores)[:top_count]

        results = []
        for rank_pos in order:
            chunk_idx = int(candidate_indices[rank_pos])
            chunk = dict(self.chunks[chunk_idx])
            chunk["similarity"] = float(scores[rank_pos])
            results.append(chunk)
        return results
