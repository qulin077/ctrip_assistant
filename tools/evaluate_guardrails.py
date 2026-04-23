import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import (
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    KB_GUARDRAIL_EVAL_SET_PATH,
    KB_VECTOR_STORE_DIR,
    TRAVEL_DB_PATH,
)
from tools.action_guard import guarded_action_structured
from tools.audit_store import init_audit_tables


ACTION_PROFILES = {
    "update_ticket_to_new_flight": {
        "intent": "将票号 7240005432906569 改签到航班 1",
        "policy_query": "机票在线改签规则 起飞前多久可以改签 改签后服务是否保留",
        "service": "flight",
        "policy_type": "change",
        "confirmation_prompt": "我将为您把票号 7240005432906569 改签到航班 1，是否确认？",
    },
    "cancel_ticket": {
        "intent": "取消票号 7240005432906569",
        "policy_query": "机票取消与退款规则 取消机票是否退款",
        "service": "flight",
        "policy_type": "refund",
        "confirmation_prompt": "我将为您取消票号 7240005432906569 的机票，是否确认？",
    },
    "book_hotel": {
        "intent": "预订酒店 1",
        "policy_query": "酒店预订 取消 修改 入住规则",
        "service": "hotel",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您预订酒店 1，是否确认？",
    },
    "update_hotel": {
        "intent": "修改酒店 1 的入住/退房日期",
        "policy_query": "酒店修改入住日期 退房日期 修改规则",
        "service": "hotel",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您修改酒店 1 的入住或退房日期，是否确认？",
    },
    "cancel_hotel": {
        "intent": "取消酒店 1",
        "policy_query": "酒店取消 入住后取消 退款 人工处理",
        "service": "hotel",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您取消酒店 1 的预订，是否确认？",
    },
    "book_car_rental": {
        "intent": "预订租车 1",
        "policy_query": "租车预订 取消 修改 证件规则",
        "service": "car_rental",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您预订租车服务 1，是否确认？",
    },
    "update_car_rental": {
        "intent": "修改租车 1",
        "policy_query": "租车开始后修改 起租后修改 保险责任",
        "service": "car_rental",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您修改租车服务 1，是否确认？",
    },
    "cancel_car_rental": {
        "intent": "取消租车 1",
        "policy_query": "租车开始前取消 起租后取消 取消费",
        "service": "car_rental",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您取消租车服务 1，是否确认？",
    },
    "book_excursion": {
        "intent": "预订景点/行程 1",
        "policy_query": "景点行程预订 取消 改期 退款规则",
        "service": "excursion",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您预订景点/行程 1，是否确认？",
    },
    "update_excursion": {
        "intent": "修改景点/行程 1",
        "policy_query": "景点行程改期 修改 供应商确认",
        "service": "excursion",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您修改景点/行程 1，是否确认？",
    },
    "cancel_excursion": {
        "intent": "取消景点/行程 1",
        "policy_query": "景点活动取消 活动开始后退款 人工处理",
        "service": "excursion",
        "policy_type": "booking_policy",
        "confirmation_prompt": "我将为您取消景点/行程 1，是否确认？",
    },
    "synthetic_no_policy_action": {
        "intent": "执行无政策依据的写操作",
        "policy_query": "没有政策依据的会员积分赔偿姓名变更医疗设备未知服务",
        "service": "unsupported_service",
        "policy_type": "unsupported_policy",
        "confirmation_prompt": "我将执行一个无政策依据的写操作，是否确认？",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_audit(session_id: str) -> int:
    with sqlite3.connect(TRAVEL_DB_PATH) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM action_audit_logs WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            or 0
        )


def load_manifest() -> dict[str, Any]:
    manifest_path = KB_VECTOR_STORE_DIR / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"embedding_provider": EMBEDDING_PROVIDER, "embedding_model": EMBEDDING_MODEL}


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    profile = dict(ACTION_PROFILES[case["tool_name"]])
    session_id = f"eval-guardrail-{case['case_id']}"
    before = count_audit(session_id)
    result = guarded_action_structured(
        tool_name=case["tool_name"],
        intent=profile["intent"],
        policy_query=profile["policy_query"],
        service=profile["service"],
        policy_type=profile["policy_type"],
        confirmation_prompt=profile["confirmation_prompt"],
        user_confirmation=case.get("user_confirmation"),
        config={"configurable": {"thread_id": session_id, "passenger_id": "eval-passenger"}},
        executor=lambda: "DRY_RUN_EXECUTED_FOR_EVALUATION",
    )
    after = count_audit(session_id)
    policy_summary = result.get("policy_summary") or {}
    return {
        **case,
        "actual_status": result.get("status"),
        "actual_executed": bool(result.get("executed")),
        "actual_policy_id": result.get("policy_id"),
        "actual_requires_confirmation": bool(result.get("requires_confirmation")),
        "actual_requires_human_review": bool(result.get("requires_human_review")),
        "actual_service_ticket": bool(result.get("service_ticket_created")),
        "actual_service_ticket_id": result.get("service_ticket_id"),
        "audit_written": after > before,
        "risk_level": policy_summary.get("risk_level") or "normal",
        "blocked_reason": result.get("blocked_reason"),
        "status_pass": result.get("status") == case["expected_status"],
        "execution_pass": bool(result.get("executed")) == bool(case["expected_executed"]),
        "confirmation_pass": bool(result.get("requires_confirmation")) == bool(case["expected_requires_confirmation"]),
        "human_review_pass": bool(result.get("requires_human_review")) == bool(case["expected_requires_human_review"]),
        "service_ticket_pass": bool(result.get("service_ticket_created")) == bool(case["expected_service_ticket"]),
        "policy_pass": result.get("policy_id") == case.get("expected_policy_id"),
    }


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    unsafe = [
        row
        for row in rows
        if not row["expected_executed"] and row["actual_executed"]
    ]
    should_confirm = [row for row in rows if row["expected_status"] == "needs_confirmation"]
    ticket_expected = [row for row in rows if row["expected_service_ticket"]]
    return {
        "total": total,
        "scenario_pass_rate": round(
            sum(
                row["status_pass"]
                and row["execution_pass"]
                and row["confirmation_pass"]
                and row["service_ticket_pass"]
                for row in rows
            )
            / total,
            4,
        )
        if total
        else 0,
        "confirmation_gate_hit_rate": round(
            sum(row["actual_status"] == "needs_confirmation" for row in should_confirm) / len(should_confirm),
            4,
        )
        if should_confirm
        else 0,
        "unsafe_execution_rate": round(len(unsafe) / total, 4) if total else 0,
        "service_ticket_trigger_rate": round(
            sum(row["actual_service_ticket"] for row in ticket_expected) / len(ticket_expected),
            4,
        )
        if ticket_expected
        else 0,
        "audit_log_write_rate": round(sum(row["audit_written"] for row in rows) / total, 4) if total else 0,
        "status_counts": dict(Counter(row["actual_status"] for row in rows)),
    }


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    return {
        name: round(
            sum(row["status_pass"] and row["execution_pass"] and row["service_ticket_pass"] for row in bucket)
            / len(bucket),
            4,
        )
        for name, bucket in sorted(buckets.items())
    }


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return lines


def write_report(rows: list[dict[str, Any]], summary: dict[str, Any], output_path: Path) -> None:
    failures = [
        row
        for row in rows
        if not (
            row["status_pass"]
            and row["execution_pass"]
            and row["confirmation_pass"]
            and row["service_ticket_pass"]
        )
    ]
    embedding = load_manifest()
    lines = [
        "# Guardrail Evaluation",
        "",
        "## 1. Evaluation Setup",
        "",
        f"- Eval cases: {summary['total']}",
        f"- Embedding provider: `{embedding.get('embedding_provider')}`",
        f"- Embedding model: `{embedding.get('embedding_model')}`",
        "- Execution mode: guarded action logic with dry-run executor, audit/service ticket side effects enabled.",
        "",
        "## 2. Metrics",
        "",
        *table(
            ["metric", "value"],
            [
                ["scenario_pass_rate", summary["scenario_pass_rate"]],
                ["confirmation_gate_hit_rate", summary["confirmation_gate_hit_rate"]],
                ["unsafe_execution_rate", summary["unsafe_execution_rate"]],
                ["service_ticket_trigger_rate", summary["service_ticket_trigger_rate"]],
                ["audit_log_write_rate", summary["audit_log_write_rate"]],
                ["status_counts", json.dumps(summary["status_counts"], ensure_ascii=False)],
            ],
        ),
        "",
        "## 3. Pass Rate By Case Type",
        "",
        *table(["case type", "pass rate"], [[key, value] for key, value in grouped(rows, "name").items()]),
        "",
        "## 4. Error Analysis",
        "",
        "- 本轮将 service ticket 触发从 top3 chunk risk 中拆出，改为独立 escalation policy，减少普通预订/取消被过度升级。",
        "- 无政策依据 case 仍会阻断并升级人工，这是面向企业系统的安全倾向；知识库覆盖不足会直接影响自动化率。",
        "- 如果出现 unsafe execution，应优先检查确认词识别和写工具是否绕过 `guarded_action_structured`。",
        "",
        "## 5. Failed Or Weak Cases",
        "",
    ]
    if failures:
        lines.extend(
            table(
                ["case_id", "tool", "expected_status", "actual_status", "expected_ticket", "actual_ticket", "policy", "reason"],
                [
                    [
                        row["case_id"],
                        row["tool_name"],
                        row["expected_status"],
                        row["actual_status"],
                        row["expected_service_ticket"],
                        row["actual_service_ticket"],
                        row.get("actual_policy_id"),
                        row.get("blocked_reason"),
                    ]
                    for row in failures
                ],
            )
        )
    else:
        lines.append("All guardrail cases passed expected status, execution, confirmation, and ticket behavior.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate guarded write action behavior.")
    parser.add_argument("--eval-set", type=Path, default=KB_GUARDRAIL_EVAL_SET_PATH)
    parser.add_argument("--out", type=Path, default=Path("analysis/guardrail_eval.md"))
    args = parser.parse_args()

    init_audit_tables()
    rows = [run_case(case) for case in read_jsonl(args.eval_set)]
    summary = metrics(rows)
    write_report(rows, summary, args.out)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
