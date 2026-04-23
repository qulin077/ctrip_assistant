import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    KB_RETRIEVER_EVAL_SET_V2_PATH,
    KB_VECTOR_STORE_DIR,
)
from tools.retriever_vector import lookup_policy_structured


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_manifest() -> dict[str, Any]:
    manifest_path = KB_VECTOR_STORE_DIR / "manifest.json"
    if not manifest_path.exists():
        return {
            "embedding_provider": EMBEDDING_PROVIDER,
            "embedding_model": EMBEDDING_MODEL,
        }
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def summarize(text: str, limit: int = 96) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "..."


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"total": 0, "top1_accuracy": 0, "top3_accuracy": 0, "mrr": 0, "filtered_top1_accuracy": 0}
    return {
        "total": total,
        "top1_accuracy": round(sum(row["hit_top1"] for row in rows) / total, 4),
        "top3_accuracy": round(sum(row["hit_top3"] for row in rows) / total, 4),
        "mrr": round(sum(row["rr"] for row in rows) / total, 4),
        "filtered_top1_accuracy": round(sum(row["hit_filtered_top1"] for row in rows) / total, 4),
    }


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    return {name: metric_block(bucket) for name, bucket in sorted(buckets.items())}


def evaluate(eval_set_path: Path, top_k: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = read_jsonl(eval_set_path)
    rows: list[dict[str, Any]] = []

    for case in cases:
        result = lookup_policy_structured(case["query"], top_k=top_k)
        matches = result.get("matches", [])
        policy_ids = [match.get("policy_id") for match in matches]
        top_policy = policy_ids[0] if policy_ids else None
        expected = case["expected_policy_id"]
        rank = policy_ids.index(expected) + 1 if expected in policy_ids else 0
        filtered = lookup_policy_structured(
            case["query"],
            top_k=1,
            service=case.get("expected_service"),
            policy_type=case.get("expected_policy_type"),
        )
        filtered_top_policy = (filtered.get("matches") or [{}])[0].get("policy_id")
        top = matches[0] if matches else {}
        rows.append(
            {
                **case,
                "top_policy_id": top_policy,
                "top_section": top.get("section_title"),
                "top_similarity": top.get("similarity"),
                "top_snippet": summarize(top.get("chunk_text", "")),
                "policy_ids": policy_ids,
                "hit_top1": top_policy == expected,
                "hit_top3": expected in policy_ids,
                "rr": 1 / rank if rank else 0,
                "filtered_top_policy_id": filtered_top_policy,
                "hit_filtered_top1": filtered_top_policy == expected,
            }
        )

    metrics = {
        "overall": metric_block(rows),
        "by_query_type": grouped(rows, "query_type"),
        "by_difficulty": grouped(rows, "difficulty"),
        "by_service": grouped(rows, "expected_service"),
        "embedding": load_manifest(),
        "top_k": top_k,
    }
    return rows, metrics


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return lines


def metric_rows(metrics: dict[str, dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            name,
            value["total"],
            value["top1_accuracy"],
            value["top3_accuracy"],
            value["mrr"],
            value["filtered_top1_accuracy"],
        ]
        for name, value in metrics.items()
    ]


def write_report(rows: list[dict[str, Any]], metrics: dict[str, Any], output_path: Path) -> None:
    failed = [row for row in rows if not row["hit_top3"]]
    adjacent = [
        row
        for row in rows
        if row["top_policy_id"] != row["expected_policy_id"] and row["top_policy_id"] in row["policy_ids"]
    ]
    embedding = metrics["embedding"]
    provider = str(embedding.get("embedding_provider") or "")
    if provider.startswith("sentence_transformers"):
        embedding_note = (
            "`BAAI/bge-m3` 提升了语义召回，但多意图 query 仍需要 query router "
            "或意图拆分来减少相邻 policy 干扰。"
        )
    else:
        embedding_note = (
            "`local_hash` embedding 更依赖词面重叠，遇到口语化、英文缩写或隐含业务语义时 "
            "不如语义向量模型稳定。"
        )
    lines = [
        "# Retriever Evaluation V2",
        "",
        "## 1. Evaluation Setup",
        "",
        f"- Eval cases: {metrics['overall']['total']}",
        f"- Top K: {metrics['top_k']}",
        f"- Embedding provider: `{embedding.get('embedding_provider')}`",
        f"- Embedding model: `{embedding.get('embedding_model')}`",
        "",
        "## 2. Overall Metrics",
        "",
        *table(
            ["metric", "value"],
            [
                ["top1_accuracy", metrics["overall"]["top1_accuracy"]],
                ["top3_accuracy", metrics["overall"]["top3_accuracy"]],
                ["MRR", metrics["overall"]["mrr"]],
                ["filtered_top1_accuracy", metrics["overall"]["filtered_top1_accuracy"]],
            ],
        ),
        "",
        "## 3. Breakdown By Query Type",
        "",
        *table(["query_type", "total", "top1", "top3", "MRR", "filtered_top1"], metric_rows(metrics["by_query_type"])),
        "",
        "## 4. Breakdown By Difficulty",
        "",
        *table(["difficulty", "total", "top1", "top3", "MRR", "filtered_top1"], metric_rows(metrics["by_difficulty"])),
        "",
        "## 5. Breakdown By Service",
        "",
        *table(["service", "total", "top1", "top3", "MRR", "filtered_top1"], metric_rows(metrics["by_service"])),
        "",
        "## 6. Error Analysis",
        "",
        "- 多意图和高风险 query 最容易错，因为一个问题里同时出现退票、改签、酒店、租车等多个相邻业务意图。",
        "- 相邻 policy 的误命中主要发生在退款、票价规则、支付退款之间，以及酒店/租车/景点三个 `booking_policy` 类型之间。",
        f"- {embedding_note}",
        "",
        "## 7. Failed Or Weak Cases",
        "",
    ]
    if failed:
        lines.extend(
            table(
                ["query", "expected", "top_policy", "top_section", "snippet"],
                [
                    [
                        row["query"],
                        row["expected_policy_id"],
                        row["top_policy_id"],
                        row.get("top_section") or "",
                        row.get("top_snippet") or "",
                    ]
                    for row in failed[:30]
                ],
            )
        )
    else:
        lines.append("All cases hit expected policy within top 3.")

    lines.extend(["", "## 8. Top1 Misses For Review", ""])
    top1_misses = [row for row in rows if not row["hit_top1"]]
    if top1_misses:
        lines.extend(
            table(
                ["query", "expected", "top_policy", "query_type", "difficulty"],
                [
                    [
                        row["query"],
                        row["expected_policy_id"],
                        row["top_policy_id"],
                        row["query_type"],
                        row["difficulty"],
                    ]
                    for row in top1_misses[:40]
                ],
            )
        )
    else:
        lines.append("No top1 misses.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy retrieval on a larger enterprise-style set.")
    parser.add_argument("--eval-set", type=Path, default=KB_RETRIEVER_EVAL_SET_V2_PATH)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("analysis/retriever_eval_v2.md"))
    args = parser.parse_args()

    rows, metrics = evaluate(args.eval_set, args.top_k)
    write_report(rows, metrics, args.out)
    print(json.dumps(metrics["overall"], ensure_ascii=False))
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
