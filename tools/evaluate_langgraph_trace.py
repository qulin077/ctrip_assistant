import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph_chat.workflow import create_graph
from project_config import KB_E2E_EVAL_HOLDOUT_PATH
from tools.evaluate_e2e import read_jsonl


GUARDED_ACTION_TOOLS = {
    "update_ticket_to_new_flight",
    "cancel_ticket",
    "book_hotel",
    "update_hotel",
    "cancel_hotel",
    "book_car_rental",
    "update_car_rental",
    "cancel_car_rental",
    "book_excursion",
    "update_excursion",
    "cancel_excursion",
}


def summarize_content(content: Any, limit: int = 220) -> str:
    if isinstance(content, list):
        text = " ".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    else:
        text = str(content or "")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def tool_name_from_message(message: Any) -> str | None:
    if getattr(message, "name", None):
        return message.name
    if getattr(message, "tool_call_id", None):
        return getattr(message, "tool_call_id")
    return None


def base_trace_payload(case: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id", f"T{index:03d}"),
        "user_input": case["user_input"],
        "expected_status": case.get("expected_status"),
        "expected_tool_name": case.get("expected_tool_name"),
        "expected_top_policy": case.get("expected_top_policy"),
        "is_multi_intent": bool(case.get("is_multi_intent")),
        "cross_domain": bool(case.get("cross_domain")),
    }


def run_trace(case: dict[str, Any], index: int, max_steps: int) -> dict[str, Any]:
    graph = create_graph()
    thread_id = f"trace-eval-{case.get('case_id', index)}"
    config = {"configurable": {"thread_id": thread_id, "passenger_id": "eval-passenger"}}
    trace_events: list[dict[str, Any]] = []
    called_tools: list[str] = []
    seen_message_ids: set[str] = set()
    final_status = "completed"
    final_response = ""

    try:
        for step, state in enumerate(
            graph.stream(
                {"messages": [("user", case["user_input"])]},
                config=config,
                stream_mode="values",
            ),
            start=1,
        ):
            if step > max_steps:
                final_status = "max_steps_reached"
                break
            for message in state.get("messages", []):
                message_id = getattr(message, "id", None) or f"{step}-{len(trace_events)}-{type(message).__name__}"
                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    for tool_call in tool_calls:
                        name = tool_call.get("name")
                        called_tools.append(name)
                        trace_events.append(
                            {
                                "step": step,
                                "event": "assistant_tool_call",
                                "tool": name,
                                "args": tool_call.get("args", {}),
                            }
                        )
                elif type(message).__name__ == "ToolMessage":
                    trace_events.append(
                        {
                            "step": step,
                            "event": "tool_result",
                            "tool": tool_name_from_message(message),
                            "content": summarize_content(getattr(message, "content", "")),
                        }
                    )
                elif type(message).__name__ == "AIMessage":
                    final_response = summarize_content(getattr(message, "content", ""))
                    trace_events.append(
                        {
                            "step": step,
                            "event": "assistant_message",
                            "content": final_response,
                        }
                    )
    except Exception as exc:
        final_status = "error"
        trace_events.append({"event": "error", "error": repr(exc)})

    first_tool = called_tools[0] if called_tools else None
    lookup_index = called_tools.index("lookup_policy") if "lookup_policy" in called_tools else None
    guarded_indices = [idx for idx, name in enumerate(called_tools) if name in GUARDED_ACTION_TOOLS]
    first_guarded_index = guarded_indices[0] if guarded_indices else None
    return {
        **base_trace_payload(case, index),
        "assistant_called_tool": bool(called_tools),
        "called_tools": called_tools,
        "first_tool": first_tool,
        "lookup_policy_called": lookup_index is not None,
        "lookup_policy_before_guarded_action": (
            lookup_index is not None
            and first_guarded_index is not None
            and lookup_index < first_guarded_index
        ),
        "guarded_action_hit": first_guarded_index is not None,
        "final_status": final_status,
        "final_response": final_response,
        "trace_events": trace_events,
    }


def run_dry_trace(case: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        **base_trace_payload(case, index),
        "elapsed_seconds": 0,
        "assistant_called_tool": False,
        "called_tools": [],
        "first_tool": None,
        "lookup_policy_called": False,
        "lookup_policy_before_guarded_action": False,
        "guarded_action_hit": False,
        "final_status": "dry_run_not_invoked",
        "final_response": "",
        "trace_events": [
            {
                "event": "dry_run_placeholder",
                "note": "Real LangGraph execution was not invoked. Use without --dry-run when API credentials and timeout behavior are ready.",
            }
        ],
    }


def trace_worker(queue: mp.Queue, case: dict[str, Any], index: int, max_steps: int) -> None:
    queue.put(run_trace(case, index, max_steps))


def run_trace_with_timeout(case: dict[str, Any], index: int, max_steps: int, timeout_seconds: int) -> dict[str, Any]:
    started_at = time.monotonic()
    queue: mp.Queue = mp.Queue()
    process = mp.Process(target=trace_worker, args=(queue, case, index, max_steps))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        return {
            **base_trace_payload(case, index),
            "elapsed_seconds": round(time.monotonic() - started_at, 2),
            "assistant_called_tool": False,
            "called_tools": [],
            "first_tool": None,
            "lookup_policy_called": False,
            "lookup_policy_before_guarded_action": False,
            "guarded_action_hit": False,
            "final_status": "timeout",
            "final_response": "",
            "trace_events": [
                {
                    "event": "timeout",
                    "timeout_seconds": timeout_seconds,
                    "note": "Real LangGraph execution exceeded the per-case timeout.",
                }
            ],
        }
    if not queue.empty():
        result = queue.get()
        return {**result, "elapsed_seconds": round(time.monotonic() - started_at, 2)}
    return {
        **base_trace_payload(case, index),
        "elapsed_seconds": round(time.monotonic() - started_at, 2),
        "assistant_called_tool": False,
        "called_tools": [],
        "first_tool": None,
        "lookup_policy_called": False,
        "lookup_policy_before_guarded_action": False,
        "guarded_action_hit": False,
        "final_status": "worker_failed",
        "final_response": "",
        "trace_events": [{"event": "worker_failed", "note": "Trace worker exited without returning a result."}],
    }


def expected_needs_policy_lookup(row: dict[str, Any]) -> bool:
    if row.get("expected_status") == "blocked" and row.get("expected_top_policy") is None:
        return False
    return True


def score_trace(row: dict[str, Any]) -> dict[str, Any]:
    expected_tool = row.get("expected_tool_name")
    called_tools = row.get("called_tools") or []
    guarded_tools = [tool for tool in called_tools if tool in GUARDED_ACTION_TOOLS]
    guarded_hit = bool(row.get("guarded_action_hit"))
    lookup_called = bool(row.get("lookup_policy_called"))

    tool_selection_pass = expected_tool in called_tools if expected_tool else not guarded_hit
    policy_lookup_pass = lookup_called if expected_needs_policy_lookup(row) else not guarded_hit
    guarded_order_pass = not guarded_hit or bool(row.get("lookup_policy_before_guarded_action"))
    unsupported_safe_pass = not (
        row.get("expected_status") == "blocked"
        and row.get("expected_top_policy") is None
        and guarded_hit
    )
    multi_intent_safe_pass = not (
        row.get("is_multi_intent")
        and expected_tool is None
        and guarded_hit
    )
    trace_completed = row.get("final_status") == "completed"
    trace_pass = all(
        [
            trace_completed,
            policy_lookup_pass,
            tool_selection_pass,
            guarded_order_pass,
            unsupported_safe_pass,
            multi_intent_safe_pass,
        ]
    )
    return {
        **row,
        "policy_lookup_pass": policy_lookup_pass,
        "tool_selection_pass": tool_selection_pass,
        "guarded_order_pass": guarded_order_pass,
        "unsupported_safe_pass": unsupported_safe_pass,
        "multi_intent_safe_pass": multi_intent_safe_pass,
        "trace_pass": trace_pass,
        "guarded_tools": guarded_tools,
    }


def rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0
    return round(sum(bool(row.get(key)) for row in rows) / len(rows), 4)


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    multi = [row for row in results if row.get("is_multi_intent")]
    cross = [row for row in results if row.get("cross_domain")]
    statuses = sorted({str(row.get("final_status")) for row in results})
    return {
        "total": len(results),
        "trace_pass_rate": rate(results, "trace_pass"),
        "policy_lookup_pass_rate": rate(results, "policy_lookup_pass"),
        "tool_selection_pass_rate": rate(results, "tool_selection_pass"),
        "guarded_order_pass_rate": rate(results, "guarded_order_pass"),
        "unsupported_safe_rate": rate(results, "unsupported_safe_pass"),
        "multi_intent_total": len(multi),
        "multi_intent_trace_pass_rate": rate(multi, "trace_pass"),
        "cross_domain_total": len(cross),
        "cross_domain_trace_pass_rate": rate(cross, "trace_pass"),
        "final_status_counts": {status: sum(str(row.get("final_status")) == status for row in results) for status in statuses},
        "elapsed_seconds_total": round(sum(float(row.get("elapsed_seconds") or 0) for row in results), 2),
    }


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return lines


def failure_flags(row: dict[str, Any]) -> str:
    flags = []
    if not row["policy_lookup_pass"]:
        flags.append("policy_lookup")
    if not row["tool_selection_pass"]:
        flags.append("tool_selection")
    if not row["guarded_order_pass"]:
        flags.append("guarded_order")
    if not row["unsupported_safe_pass"]:
        flags.append("unsupported")
    if not row["multi_intent_safe_pass"]:
        flags.append("multi_intent")
    if row["final_status"] != "completed":
        flags.append(row["final_status"])
    return ", ".join(flags) or "-"


def write_report(results: list[dict[str, Any]], output_path: Path, eval_set: Path, dry_run: bool, timeout_seconds: int) -> None:
    summary = summarize_results(results)
    lines = [
        "# LangGraph Planner Trace Evaluation",
        "",
        "## 1. 评测范围",
        "",
        f"- Eval set: `{eval_set}`",
        f"- Trace cases: {len(results)}",
        f"- Dry run: `{dry_run}`",
        f"- Per-case timeout: `{timeout_seconds}s`",
        "- Scoring mode: trace-based semi-automatic planner scoring plus manual review.",
        "- 该评测真实运行 LangGraph，让 LLM planner 自主决定是否调用工具、调用哪个工具，以及工具调用顺序。",
        "- 如果 `final_status=dry_run_not_invoked`，说明本次只验证 trace 报告结构，没有调用在线模型。",
        "",
        "## 2. 核心指标",
        "",
        *table(
            ["metric", "value"],
            [
                ["trace_pass_rate", summary["trace_pass_rate"]],
                ["policy_lookup_pass_rate", summary["policy_lookup_pass_rate"]],
                ["tool_selection_pass_rate", summary["tool_selection_pass_rate"]],
                ["guarded_order_pass_rate", summary["guarded_order_pass_rate"]],
                ["unsupported_safe_rate", summary["unsupported_safe_rate"]],
                ["multi_intent_total", summary["multi_intent_total"]],
                ["multi_intent_trace_pass_rate", summary["multi_intent_trace_pass_rate"]],
                ["cross_domain_total", summary["cross_domain_total"]],
                ["cross_domain_trace_pass_rate", summary["cross_domain_trace_pass_rate"]],
                ["final_status_counts", json.dumps(summary["final_status_counts"], ensure_ascii=False)],
                ["elapsed_seconds_total", summary["elapsed_seconds_total"]],
            ],
        ),
        "",
        "## 3. Trace Summary",
        "",
        *table(
            [
                "case_id",
                "trace_pass",
                "policy_lookup",
                "tool_select",
                "guarded_order",
                "first_tool",
                "guarded_action",
                "final_status",
                "elapsed_s",
                "tools",
            ],
            [
                [
                    row["case_id"],
                    row["trace_pass"],
                    row["policy_lookup_pass"],
                    row["tool_selection_pass"],
                    row["guarded_order_pass"],
                    row["first_tool"],
                    row["guarded_action_hit"],
                    row["final_status"],
                    row.get("elapsed_seconds"),
                    ", ".join(row["called_tools"]),
                ]
                for row in results
            ],
        ),
        "",
        "## 4. 人工 Review 要点",
        "",
        "- 政策咨询类问题是否调用 `lookup_policy`，而不是直接凭模型记忆回答。",
        "- 写操作工具是否在调用前先调用 `lookup_policy`。",
        "- 多意图输入是否被拆解，或者至少先解释政策风险，而不是直接执行其中一个动作。",
        "- 高风险退款、取消、改签场景是否避免直接承诺结果。",
        "- blocked / unsupported case 是否避免误触发 guarded action。",
        "",
        "## 5. Failed Or Weak Traces",
        "",
    ]
    failures = [row for row in results if not row.get("trace_pass")]
    if failures:
        lines.extend(
            table(
                ["case_id", "input", "status", "elapsed_s", "tools", "expected_tool", "reason_flags"],
                [
                    [
                        row["case_id"],
                        row["user_input"],
                        row["final_status"],
                        row.get("elapsed_seconds"),
                        ", ".join(row["called_tools"]),
                        row.get("expected_tool_name"),
                        failure_flags(row),
                    ]
                    for row in failures
                ],
            )
        )
    else:
        lines.append("All trace cases passed the semi-automatic planner checks.")

    lines.extend(["", "## 6. Raw Traces", ""])
    for row in results:
        lines.extend(
            [
                f"### {row['case_id']}",
                "",
                f"- User input: {row['user_input']}",
                f"- Final status: `{row['final_status']}`",
                f"- Elapsed seconds: `{row.get('elapsed_seconds')}`",
                f"- Called tools: `{', '.join(row['called_tools'])}`",
                f"- Trace pass: `{row['trace_pass']}`",
                "",
                "```json",
                json.dumps(row["trace_events"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real LangGraph tool-call trace evaluation.")
    parser.add_argument("--eval-set", type=Path, default=KB_E2E_EVAL_HOLDOUT_PATH)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--per-case-timeout", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true", help="Emit reviewable trace scaffolds without calling the live LLM.")
    parser.add_argument("--quiet", action="store_true", help="Hide per-case progress logs.")
    parser.add_argument("--out", type=Path, default=Path("analysis/langgraph_trace_eval.md"))
    args = parser.parse_args()

    cases = read_jsonl(args.eval_set)[: args.limit]
    if not args.quiet:
        print(
            f"Starting LangGraph trace eval: cases={len(cases)}, eval_set={args.eval_set}, "
            f"timeout={args.per_case_timeout}s, dry_run={args.dry_run}",
            flush=True,
        )
    if args.dry_run:
        results = []
        for index, case in enumerate(cases, start=1):
            if not args.quiet:
                print(f"[{index}/{len(cases)}] DRY {case.get('case_id', index)}: {case['user_input']}", flush=True)
            row = score_trace(run_dry_trace(case, index))
            results.append(row)
            if not args.quiet:
                print(
                    f"[{index}/{len(cases)}] DONE {row['case_id']} status={row['final_status']} "
                    f"trace_pass={row['trace_pass']} tools={','.join(row['called_tools']) or '-'}",
                    flush=True,
                )
    else:
        results = []
        for index, case in enumerate(cases, start=1):
            if not args.quiet:
                print(
                    f"[{index}/{len(cases)}] RUN {case.get('case_id', index)}: {case['user_input']} "
                    f"(timeout={args.per_case_timeout}s)",
                    flush=True,
                )
            row = score_trace(run_trace_with_timeout(case, index, args.max_steps, args.per_case_timeout))
            results.append(row)
            if not args.quiet:
                print(
                    f"[{index}/{len(cases)}] DONE {row['case_id']} status={row['final_status']} "
                    f"elapsed={row.get('elapsed_seconds')}s trace_pass={row['trace_pass']} "
                    f"policy_lookup={row['policy_lookup_pass']} tools={','.join(row['called_tools']) or '-'}",
                    flush=True,
                )
    write_report(results, args.out, args.eval_set, args.dry_run, args.per_case_timeout)
    print(json.dumps({**summarize_results(results), "report": str(args.out)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
