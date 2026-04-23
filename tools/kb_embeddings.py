import hashlib
import math
import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    ascii_tokens = re.findall(r"[a-z0-9_]+", text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_bigrams = [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
    return ascii_tokens + cjk_chars + cjk_bigrams


@dataclass
class LocalHashEmbeddings:
    """Small deterministic embedding model for local/offline retrieval tests."""

    dimension: int = 1024

    @property
    def provider_name(self) -> str:
        return "local_hash"

    def embed_text(self, text: str) -> list[float]:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(float(np.dot(vector, vector)))
        if norm:
            vector /= norm
        return vector.astype(float).tolist()

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_text(text)


class OpenAICompatibleEmbeddings:
    """Optional OpenAI-compatible embedding provider.

    This class imports langchain_openai lazily so local tests can run without
    external dependencies.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for openai embedding provider")
        from langchain_openai import OpenAIEmbeddings

        self._client = OpenAIEmbeddings(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"openai:{self._model}"

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return self._client.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._client.embed_query(text)


class SentenceTransformersEmbeddings:
    """Optional local embedding provider for production-style Chinese retrieval."""

    def __init__(self, model: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for EMBEDDING_PROVIDER=sentence_transformers. "
                "Install requirements.txt or switch EMBEDDING_PROVIDER=local_hash for local tests."
            ) from exc

        self._model_name = model
        try:
            self._model = SentenceTransformer(model)
        except ValueError as exc:
            if "torch.load" not in str(exc) or "torch to at least v2.6" not in str(exc):
                raise
            # BAAI/bge-m3 currently ships PyTorch weights but no safetensors file.
            # Some older macOS x86 environments cannot install torch>=2.6, so we
            # keep this fallback local and narrow to unblock the demo index build.
            import transformers.modeling_utils as modeling_utils
            import transformers.utils.import_utils as import_utils

            import_utils.check_torch_load_is_safe = lambda: None
            modeling_utils.check_torch_load_is_safe = lambda: None
            self._model = SentenceTransformer(model)

    @property
    def provider_name(self) -> str:
        return f"sentence_transformers:{self._model_name}"

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.astype(float).tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return vector.astype(float).tolist()


def create_embedding_model(provider: str = "local_hash", **kwargs):
    if provider == "local_hash":
        return LocalHashEmbeddings(dimension=int(kwargs.get("dimension", 1024)))
    if provider == "openai":
        return OpenAICompatibleEmbeddings(
            api_key=kwargs.get("api_key", ""),
            base_url=kwargs.get("base_url", "https://api.openai.com/v1"),
            model=kwargs.get("model", "text-embedding-3-small"),
        )
    if provider == "sentence_transformers":
        return SentenceTransformersEmbeddings(model=kwargs.get("model", "BAAI/bge-m3"))
    raise ValueError(f"Unsupported embedding provider: {provider}")
