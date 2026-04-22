import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import KB_CHUNKS_PATH, KB_VECTOR_STORE_DIR
from tools.policy_vector_store import PolicyVectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a persistent policy KB vector index.")
    parser.add_argument("--chunks", type=Path, default=KB_CHUNKS_PATH)
    parser.add_argument("--out", type=Path, default=KB_VECTOR_STORE_DIR)
    parser.add_argument(
        "--provider",
        default=None,
        help="Embedding provider. Defaults to EMBEDDING_PROVIDER, usually local_hash.",
    )
    args = parser.parse_args()

    store = PolicyVectorStore.build_from_chunks(
        chunks_path=args.chunks,
        vector_store_dir=args.out,
        provider=args.provider,
    )
    print(f"Wrote vector store to {args.out}")
    print(f"Chunks indexed: {len(store.chunks)}")
    print(f"Vector dimension: {store.vectors.shape[1] if store.vectors.ndim == 2 else 0}")


if __name__ == "__main__":
    main()
