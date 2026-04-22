import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import KB_RETRIEVER_EVAL_SET_PATH
from tools.retriever_vector import lookup_policy_structured


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summarize(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else f"{text[:limit]}..."


def evaluate(eval_set_path: Path, top_k: int) -> tuple[list[dict], dict]:
    cases = read_jsonl(eval_set_path)
    rows = []
    top1_hits = 0
    topk_hits = 0

    for case in cases:
        result = lookup_policy_structured(query=case["query"], top_k=top_k)
        matches = result["matches"]
        policy_ids = [match["policy_id"] for match in matches]
        top_policy = policy_ids[0] if policy_ids else None
        hit_top1 = top_policy == case["expected_policy_id"]
        hit_topk = case["expected_policy_id"] in policy_ids
        top1_hits += int(hit_top1)
        topk_hits += int(hit_topk)
        top = matches[0] if matches else {}
        rows.append(
            {
                "query": case["query"],
                "expected_policy_id": case["expected_policy_id"],
                "top_policy_id": top_policy,
                "top_section": top.get("section_title"),
                "top_similarity": top.get("similarity"),
                "top_requires_human_review": top.get("requires_human_review"),
                "top_chunk": summarize(top.get("chunk_text", "")),
                "hit_top1": hit_top1,
                "hit_topk": hit_topk,
            }
        )

    total = len(cases)
    metrics = {
        "total": total,
        "top1_accuracy": round(top1_hits / total, 4) if total else 0,
        "topk_accuracy": round(topk_hits / total, 4) if total else 0,
        "top_k": top_k,
    }
    return rows, metrics


def write_report(rows: list[dict], metrics: dict, output_path: Path) -> None:
    lines = [
        "# Policy Retriever Evaluation",
        "",
        f"- total: {metrics['total']}",
        f"- top_k: {metrics['top_k']}",
        f"- top1_accuracy: {metrics['top1_accuracy']}",
        f"- topk_accuracy: {metrics['topk_accuracy']}",
        "",
        "| Query | Expected | Top Policy | Section | Top1 | TopK | Snippet |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {query} | `{expected}` | `{top}` | {section} | {top1} | {topk} | {snippet} |".format(
                query=row["query"],
                expected=row["expected_policy_id"],
                top=row["top_policy_id"],
                section=row.get("top_section") or "",
                top1="PASS" if row["hit_top1"] else "CHECK",
                topk="PASS" if row["hit_topk"] else "CHECK",
                snippet=(row.get("top_chunk") or "").replace("|", "\\|"),
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy retriever against a small golden set.")
    parser.add_argument("--eval-set", type=Path, default=KB_RETRIEVER_EVAL_SET_PATH)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("analysis/policy_retriever_eval.md"))
    args = parser.parse_args()

    rows, metrics = evaluate(args.eval_set, args.top_k)
    write_report(rows, metrics, args.out)

    print(f"Evaluated {metrics['total']} cases")
    print(f"Top-1 accuracy: {metrics['top1_accuracy']}")
    print(f"Top-{metrics['top_k']} accuracy: {metrics['topk_accuracy']}")
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
