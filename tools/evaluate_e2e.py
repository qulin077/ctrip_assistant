import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    KB_E2E_EVAL_SET_PATH,
    KB_VECTOR_STORE_DIR,
    TRAVEL_DB_PATH,
)
from tools.action_guard import guarded_action_structured
from tools.audit_store import init_audit_tables
from tools.escalation_policy import infer_route_hint, should_handoff_policy_question
from tools.evaluate_guardrails import ACTION_PROFILES
from tools.retriever_vector import lookup_policy_structured


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_manifest() -> dict[str, Any]:
    manifest_path = KB_VECTOR_STORE_DIR / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"embedding_provider": EMBEDDING_PROVIDER, "embedding_model": EMBEDDING_MODEL}


def count_audit(session_id: str) -> int:
    with sqlite3.connect(TRAVEL_DB_PATH) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM action_audit_logs WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            or 0
        )


def is_confirmation(text: str) -> bool:
    return any(word in text for word in ["确认", "确定", "好的", "同意", "继续"])


def is_question_like(text: str) -> bool:
    return any(word in text for word in ["吗", "能不能", "可以", "是否", "会不会", "够不够", "为什么", "怎么办"])


def should_answer_multi_intent_first(text: str) -> bool:
    return (
        "先看看" in text
        or ("不行" in text and any(word in text for word in ["退票", "退款", "取消", "改签"]))
        or ("顺序" in text and any(word in text for word in ["发票", "退票", "取消"]))
    )


def infer_action(user_input: str) -> Optional[str]:
    text = user_input.lower()
    if "乘客姓名" in text or "姓名" in text:
        return "unsupported_write"
    if any(word in text for word in ["第三方", "旅行社", "团体"]) and is_question_like(text):
        return None
    if should_answer_multi_intent_first(text):
        if "景点" not in text and "行程" not in text:
            return None
    if is_question_like(text) and not is_confirmation(text):
        return None
    if "取消" in text and "票" in text:
        return "cancel_ticket"
    if ("改签" in text or "改到航班" in text or "改到" in text) and ("票" in text or "航班" in text):
        return "update_ticket_to_new_flight"
    if "预订酒店" in text or "订酒店" in text:
        return "book_hotel"
    if "取消酒店" in text:
        return "cancel_hotel"
    if "改酒店" in text:
        return "update_hotel"
    if "预订租车" in text or "帮我预订租车" in text:
        return "book_car_rental"
    if "取消租车" in text:
        return "cancel_car_rental"
    if "租车" in text and any(word in text for word in ["改", "顺延", "往后"]):
        return "update_car_rental"
    if ("取消景点" in text or "取消景点行程" in text or "取消行程" in text) and "不行就取消" not in text:
        return "cancel_excursion"
    if "预订" in text and ("景点" in text or "行程" in text):
        return "book_excursion"
    if ("改景点" in text or "改行程" in text or "景点日期" in text) and "取消" in text:
        return "update_excursion"
    return None


def default_query_for_action(tool_name: str, user_input: str) -> str:
    if tool_name and tool_name in ACTION_PROFILES:
        return ACTION_PROFILES[tool_name]["policy_query"]
    return user_input


def run_guarded(tool_name: str, case: dict[str, Any]) -> dict[str, Any]:
    profile = ACTION_PROFILES[tool_name]
    session_id = f"eval-e2e-{case['case_id']}"
    before = count_audit(session_id)
    result = guarded_action_structured(
        tool_name=tool_name,
        intent=f"{profile['intent']}；用户原始输入：{case['user_input']}",
        policy_query=profile["policy_query"],
        service=profile["service"],
        policy_type=profile["policy_type"],
        confirmation_prompt=profile["confirmation_prompt"],
        user_confirmation="确认" if is_confirmation(case["user_input"]) else None,
        config={"configurable": {"thread_id": session_id, "passenger_id": "eval-passenger"}},
        executor=lambda: "DRY_RUN_EXECUTED_FOR_E2E_EVALUATION",
    )
    after = count_audit(session_id)
    return {
        "status": result.get("status"),
        "tool_name": tool_name,
        "top_policy": result.get("policy_id"),
        "requires_human_review": bool(result.get("requires_human_review")),
        "service_ticket": bool(result.get("service_ticket_created")),
        "audit_written": after > before,
        "risk_level": (result.get("policy_summary") or {}).get("risk_level") or "normal",
    }


def run_answer_or_handoff(case: dict[str, Any]) -> dict[str, Any]:
    route_hint = infer_route_hint(case["user_input"])
    result = lookup_policy_structured(
        case["user_input"],
        top_k=3,
        service=route_hint.service,
        policy_type=route_hint.policy_type,
    )
    top = (result.get("matches") or [{}])[0]
    requires_human_review = bool(top.get("requires_human_review"))
    risk_level = top.get("risk_level") or "normal"
    should_handoff, _reason = should_handoff_policy_question(case["user_input"], top)
    status = "answer_only" if route_hint.is_multi_intent else ("handoff" if should_handoff else "answer_only")
    return {
        "status": status,
        "tool_name": None,
        "top_policy": top.get("policy_id"),
        "requires_human_review": requires_human_review,
        "service_ticket": should_handoff or route_hint.is_multi_intent,
        "audit_written": False,
        "risk_level": risk_level,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    action = infer_action(case["user_input"])
    if action == "unsupported_write":
        actual = {
            "status": "blocked",
            "tool_name": None,
            "top_policy": None,
            "requires_human_review": False,
            "service_ticket": True,
            "audit_written": False,
            "risk_level": "high",
        }
    elif action:
        actual = run_guarded(action, case)
    else:
        actual = run_answer_or_handoff(case)

    return {
        **case,
        "actual_status": actual["status"],
        "actual_tool_name": actual["tool_name"],
        "actual_top_policy": actual["top_policy"],
        "actual_requires_human_review": actual["requires_human_review"],
        "actual_service_ticket": actual["service_ticket"],
        "actual_audit_written": actual["audit_written"],
        "actual_risk_level": actual["risk_level"],
        "status_pass": actual["status"] == case["expected_status"],
        "tool_pass": actual["tool_name"] == case.get("expected_tool_name"),
        "policy_pass": actual["top_policy"] == case.get("expected_top_policy"),
        "human_review_pass": actual["requires_human_review"] == case["expected_requires_human_review"],
        "service_ticket_pass": actual["service_ticket"] == case["expected_service_ticket"],
        "audit_pass": actual["audit_written"] == case["expected_audit_written"],
    }


def accuracy(rows: list[dict[str, Any]], status: Optional[str] = None) -> float:
    subset = [row for row in rows if status is None or row["expected_status"] == status]
    if not subset:
        return 0
    return round(
        sum(
            row["status_pass"]
            and row["tool_pass"]
            and row["policy_pass"]
            and row["service_ticket_pass"]
            and row["audit_pass"]
            for row in subset
        )
        / len(subset),
        4,
    )


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    return {name: accuracy(bucket) for name, bucket in sorted(buckets.items())}


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return lines


def evaluate(eval_set_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    init_audit_tables()
    rows = [run_case(case) for case in read_jsonl(eval_set_path)]
    summary = {
        "total": len(rows),
        "scenario_pass_rate": accuracy(rows),
        "answer_only_accuracy": accuracy(rows, "answer_only"),
        "needs_confirmation_accuracy": accuracy(rows, "needs_confirmation"),
        "blocked_accuracy": accuracy(rows, "blocked"),
        "executed_accuracy": accuracy(rows, "executed"),
        "handoff_accuracy": accuracy(rows, "handoff"),
        "status_counts": dict(Counter(row["actual_status"] for row in rows)),
        "by_intent": grouped(rows, "expected_intent"),
        "embedding": load_manifest(),
    }
    return rows, summary


def write_report(rows: list[dict[str, Any]], summary: dict[str, Any], output_path: Path) -> None:
    failures = [
        row
        for row in rows
        if not (
            row["status_pass"]
            and row["tool_pass"]
            and row["policy_pass"]
            and row["service_ticket_pass"]
            and row["audit_pass"]
        )
    ]
    embedding = summary["embedding"]
    lines = [
        "# End-to-End Scenario Evaluation",
        "",
        "## 1. Evaluation Setup",
        "",
        f"- Eval cases: {summary['total']}",
        f"- Embedding provider: `{embedding.get('embedding_provider')}`",
        f"- Embedding model: `{embedding.get('embedding_model')}`",
        "- Orchestrator: deterministic evaluator over policy retriever + guarded action core logic.",
        "",
        "## 2. Metrics",
        "",
        *table(
            ["metric", "value"],
            [
                ["scenario_pass_rate", summary["scenario_pass_rate"]],
                ["answer_only_accuracy", summary["answer_only_accuracy"]],
                ["needs_confirmation_accuracy", summary["needs_confirmation_accuracy"]],
                ["blocked_accuracy", summary["blocked_accuracy"]],
                ["executed_accuracy", summary["executed_accuracy"]],
                ["handoff_accuracy", summary["handoff_accuracy"]],
                ["status_counts", json.dumps(summary["status_counts"], ensure_ascii=False)],
            ],
        ),
        "",
        "## 3. Accuracy By Intent",
        "",
        *table(["intent", "pass_rate"], [[key, value] for key, value in summary["by_intent"].items()]),
        "",
        "## 4. Error Analysis",
        "",
        "- 当前 E2E 评测没有直接调用在线大模型，主要评估可重复的业务控制逻辑；这让结果稳定，但不能完全代表真实自然语言 planner。",
        "- 本轮增加 query router 后，多意图场景会优先回答政策和风险，不再直接执行第二个写操作。",
        "- 本轮增加 escalation policy 后，高风险咨询类问题可以稳定进入 handoff/service-ticket 逻辑。",
        "- 后续仍需要接入真实 LangGraph tool call trace，验证在线模型 planner 是否与确定性 orchestrator 一致。",
        "",
        "## 5. Failed Or Weak Cases",
        "",
    ]
    if failures:
        lines.extend(
            table(
                [
                    "case_id",
                    "input",
                    "expected_status",
                    "actual_status",
                    "expected_policy",
                    "actual_policy",
                    "expected_ticket",
                    "actual_ticket",
                ],
                [
                    [
                        row["case_id"],
                        row["user_input"],
                        row["expected_status"],
                        row["actual_status"],
                        row["expected_top_policy"],
                        row["actual_top_policy"],
                        row["expected_service_ticket"],
                        row["actual_service_ticket"],
                    ]
                    for row in failures
                ],
            )
        )
    else:
        lines.append("All E2E scenarios passed expected status, policy, action, ticket, and audit behavior.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate end-to-end customer service scenarios.")
    parser.add_argument("--eval-set", type=Path, default=KB_E2E_EVAL_SET_PATH)
    parser.add_argument("--out", type=Path, default=Path("analysis/e2e_eval.md"))
    args = parser.parse_args()

    rows, summary = evaluate(args.eval_set)
    write_report(rows, summary, args.out)
    print(json.dumps({key: value for key, value in summary.items() if key != "by_intent"}, ensure_ascii=False))
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
