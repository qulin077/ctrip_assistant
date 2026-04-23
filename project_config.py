import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

TRAVEL_DB_PATH = PROJECT_ROOT / "travel_new.sqlite"
TRAVEL_DB_BACKUP_PATH = PROJECT_ROOT / "travel2.sqlite"
ORDER_FAQ_PATH = PROJECT_ROOT / "order_faq.md"
KB_POLICY_INDEX_PATH = PROJECT_ROOT / "kb" / "metadata" / "policy_index.jsonl"
KB_CHUNKS_PATH = PROJECT_ROOT / "kb" / "processed" / "chunks.jsonl"
KB_VECTOR_STORE_DIR = PROJECT_ROOT / "kb" / "processed" / "vector_store"
KB_RETRIEVER_EVAL_SET_PATH = PROJECT_ROOT / "kb" / "metadata" / "retriever_eval_set.jsonl"
KB_RETRIEVER_EVAL_SET_V2_PATH = PROJECT_ROOT / "kb" / "metadata" / "retriever_eval_set_v2.jsonl"
KB_GUARDRAIL_EVAL_SET_PATH = PROJECT_ROOT / "kb" / "metadata" / "guardrail_eval_set.jsonl"
KB_E2E_EVAL_SET_PATH = PROJECT_ROOT / "kb" / "metadata" / "e2e_eval_set.jsonl"

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_REASONING_SPLIT = os.getenv("MINIMAX_REASONING_SPLIT", "true").lower() == "true"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or MINIMAX_API_KEY
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or MINIMAX_BASE_URL
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or MINIMAX_MODEL
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "1.0"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local_hash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
