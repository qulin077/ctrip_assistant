import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func=None, *args, **kwargs):
        if func is None:
            return lambda wrapped: wrapped
        return func

from project_config import KB_VECTOR_STORE_DIR
from tools.escalation_policy import infer_route_hint
from tools.policy_vector_store import PolicyVectorStore


@lru_cache(maxsize=1)
def get_policy_vector_store() -> PolicyVectorStore:
    return PolicyVectorStore.load(vector_store_dir=KB_VECTOR_STORE_DIR)


def lookup_policy_structured(
    query: str,
    top_k: int = 3,
    service: Optional[str] = None,
    policy_type: Optional[str] = None,
    auto_route: bool = True,
) -> dict[str, Any]:
    """Return structured policy matches from the processed KB vector store."""
    store = get_policy_vector_store()
    route_hint = infer_route_hint(query) if auto_route and not service and not policy_type else None
    effective_service = service or (route_hint.service if route_hint else None)
    effective_policy_type = policy_type or (route_hint.policy_type if route_hint else None)
    if route_hint:
        filtered_matches = store.search(
            query=query,
            top_k=1,
            service=effective_service,
            policy_type=effective_policy_type,
        )
        broad_matches = store.search(query=query, top_k=max(top_k * 3, top_k))
        matches = []
        seen_chunk_ids = set()
        for match in [*filtered_matches, *broad_matches]:
            chunk_id = match.get("chunk_id")
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            matches.append(match)
            if len(matches) >= top_k:
                break
    else:
        matches = store.search(
            query=query,
            top_k=top_k,
            service=effective_service,
            policy_type=effective_policy_type,
        )
    return {
        "query": query,
        "top_k": top_k,
        "filters": {
            "service": effective_service,
            "policy_type": effective_policy_type,
            "auto_route": bool(route_hint),
            "is_multi_intent": bool(route_hint.is_multi_intent) if route_hint else False,
        },
        "matches": [
            {
                "chunk_id": match.get("chunk_id"),
                "policy_id": match.get("policy_id"),
                "title": match.get("title"),
                "service": match.get("service"),
                "policy_type": match.get("policy_type"),
                "section_title": match.get("section_title"),
                "requires_human_review": match.get("requires_human_review", False),
                "review_status": match.get("review_status"),
                "file_path": match.get("file_path"),
                "similarity": round(float(match.get("similarity", 0.0)), 4),
                "chunk_text": match.get("chunk_text", ""),
                "risk_level": match.get("risk_level"),
                "requires_confirmation": match.get("requires_confirmation"),
                "allowed_action": match.get("allowed_action"),
            }
            for match in matches
        ],
    }


def format_policy_matches(result: dict[str, Any]) -> str:
    matches = result.get("matches", [])
    if not matches:
        filters = result.get("filters", {})
        filter_text = ", ".join(f"{key}={value}" for key, value in filters.items() if value)
        suffix = f"（过滤条件：{filter_text}）" if filter_text else ""
        return f"未检索到匹配的政策内容{suffix}。"

    blocks = []
    for idx, match in enumerate(matches, start=1):
        review_note = "是" if match.get("requires_human_review") else "否"
        blocks.append(
            "\n".join(
                [
                    f"【政策命中 {idx}】",
                    f"- policy_id: {match.get('policy_id')}",
                    f"- title: {match.get('title')}",
                    f"- service: {match.get('service')}",
                    f"- policy_type: {match.get('policy_type')}",
                    f"- section_title: {match.get('section_title')}",
                    f"- requires_human_review: {review_note}",
                    f"- requires_confirmation: {'是' if match.get('requires_confirmation') else '否'}",
                    f"- risk_level: {match.get('risk_level') or 'normal'}",
                    f"- allowed_action: {', '.join(match.get('allowed_action') or []) or '无'}",
                    f"- similarity: {match.get('similarity')}",
                    "",
                    str(match.get("chunk_text", "")).strip(),
                ]
            )
        )
    return "\n\n".join(blocks)


@tool
def lookup_policy(
    query: str,
    service: Optional[str] = None,
    policy_type: Optional[str] = None,
) -> str:
    """查询旅行客服政策知识库。可传 service 和 policy_type 过滤政策范围。"""
    result = lookup_policy_structured(
        query=query,
        top_k=3,
        service=service,
        policy_type=policy_type,
    )
    return format_policy_matches(result)


if __name__ == "__main__":
    print(lookup_policy("我可以在起飞前多久在线改签？"))
