import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from project_config import PROJECT_ROOT
from tools.audit_store import create_service_ticket, insert_action_audit
from tools.car_tools import (
    book_car_rental as _book_car_rental_tool,
    cancel_car_rental as _cancel_car_rental_tool,
    update_car_rental as _update_car_rental_tool,
)
from tools.flights_tools import (
    cancel_ticket as _cancel_ticket_tool,
    update_ticket_to_new_flight as _update_ticket_to_new_flight_tool,
)
from tools.hotels_tools import (
    book_hotel as _book_hotel_tool,
    cancel_hotel as _cancel_hotel_tool,
    update_hotel as _update_hotel_tool,
)
from tools.retriever_vector import lookup_policy_structured
from tools.trip_tools import (
    book_excursion as _book_excursion_tool,
    cancel_excursion as _cancel_excursion_tool,
    update_excursion as _update_excursion_tool,
)


AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "action_audit.jsonl"

CONFIRM_WORDS = {
    "确认",
    "确定",
    "是",
    "是的",
    "好的",
    "好",
    "可以",
    "同意",
    "继续",
    "执行",
    "确认执行",
    "yes",
    "y",
    "ok",
    "okay",
}


def is_confirmed(text: Optional[str]) -> bool:
    if not text:
        return False
    normalized = text.strip().lower()
    return normalized in CONFIRM_WORDS or any(word in normalized for word in ["确认", "同意", "继续执行"])


def summarize_policy(result: dict[str, Any]) -> dict[str, Any]:
    matches = result.get("matches", [])
    policy_ids = [match.get("policy_id") for match in matches if match.get("policy_id")]
    requires_human_review = any(match.get("requires_human_review") for match in matches)
    requires_confirmation = any(match.get("requires_confirmation") for match in matches)
    risk_levels = [match.get("risk_level") for match in matches if match.get("risk_level")]
    allowed_actions = sorted(
        {
            action
            for match in matches
            for action in (match.get("allowed_action") or [])
        }
    )
    top_match = matches[0] if matches else {}
    return {
        "policy_id": top_match.get("policy_id"),
        "policy_ids": policy_ids,
        "section_title": top_match.get("section_title"),
        "requires_human_review": requires_human_review,
        "risk_level": "high" if "high" in risk_levels else ("medium" if "medium" in risk_levels else None),
        "requires_confirmation": requires_confirmation,
        "allowed_action": allowed_actions,
        "match_count": len(matches),
    }


def write_audit_event(event: dict[str, Any]) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **event,
    }
    insert_action_audit(payload)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def config_context(config: Optional[RunnableConfig]) -> dict[str, Optional[str]]:
    configurable = (config or {}).get("configurable", {})
    return {
        "session_id": configurable.get("thread_id"),
        "passenger_id": configurable.get("passenger_id"),
    }


def maybe_create_service_ticket(event: dict[str, Any], reason: str) -> Optional[int]:
    policy = event.get("policy") or {}
    risk_level = policy.get("risk_level")
    requires_human_review = bool(policy.get("requires_human_review"))
    if not requires_human_review and risk_level != "high" and reason != "no_policy_match":
        return None
    priority = "high" if risk_level == "high" or reason == "no_policy_match" else "medium"
    return create_service_ticket(
        issue_type="policy_review",
        priority=priority,
        reason=reason,
        tool_name=event.get("tool_name"),
        intent=event.get("intent"),
        policy_id=policy.get("policy_id"),
        session_id=event.get("session_id"),
        passenger_id=event.get("passenger_id"),
        metadata={"policy": policy, "blocked_reason": event.get("blocked_reason")},
    )


def policy_block(policy_summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "政策检查结果：",
            f"- policy_id: {policy_summary.get('policy_id')}",
            f"- section_title: {policy_summary.get('section_title')}",
            f"- requires_human_review: {'是' if policy_summary.get('requires_human_review') else '否'}",
            f"- requires_confirmation: {'是' if policy_summary.get('requires_confirmation') else '否'}",
            f"- risk_level: {policy_summary.get('risk_level') or 'normal'}",
            f"- allowed_action: {', '.join(policy_summary.get('allowed_action') or []) or '无'}",
        ]
    )


def format_guarded_result(result: dict[str, Any]) -> str:
    parts = []
    policy_summary = result.get("policy_summary") or {}
    if policy_summary:
        parts.append(policy_block(policy_summary))
    result_text = result.get("result_text")
    if result_text:
        parts.append(result_text)
    confirmation_prompt = result.get("confirmation_prompt")
    if confirmation_prompt and result.get("status") == "needs_confirmation":
        parts.append(confirmation_prompt)
        parts.append("如确认执行，请明确回复“确认”。")
    if result.get("requires_human_review") and result.get("status") == "executed":
        parts.append("注意：命中的政策包含待人工确认内容，退款、费用或最终服务结果仍应以人工复核为准。")
    return "\n\n".join(parts)


def guarded_action_structured(
    *,
    tool_name: str,
    intent: str,
    policy_query: str,
    service: str,
    policy_type: str,
    confirmation_prompt: str,
    user_confirmation: Optional[str],
    executor: Callable[[], str],
    config: Optional[RunnableConfig] = None,
) -> dict[str, Any]:
    policy_result = lookup_policy_structured(
        query=policy_query,
        top_k=3,
        service=service,
        policy_type=policy_type,
    )
    policy_summary = summarize_policy(policy_result)
    requires_confirmation = True
    confirmed = is_confirmed(user_confirmation)

    context = config_context(config)
    audit_event = {
        "intent": intent,
        "tool_name": tool_name,
        "service": service,
        "policy_type": policy_type,
        "policy": policy_summary,
        "requires_confirmation": requires_confirmation,
        "user_confirmation": user_confirmation,
        "confirmed": confirmed,
        "executed": False,
        **context,
    }

    if not policy_summary["match_count"]:
        event = {**audit_event, "blocked_reason": "no_policy_match"}
        write_audit_event(event)
        service_ticket_id = maybe_create_service_ticket(event, "no_policy_match")
        return {
            "status": "blocked",
            "tool_name": tool_name,
            "intent": intent,
            "policy_summary": policy_summary,
            "confirmation_prompt": None,
            "result_text": f"未检索到可用于本次写操作的政策依据，暂不执行操作。请补充政策或转人工处理。\n操作意图：{intent}",
            "service_ticket_created": service_ticket_id is not None,
            "service_ticket_id": service_ticket_id,
            "executed": False,
            "requires_confirmation": requires_confirmation,
            "requires_human_review": False,
            "policy_id": None,
            "blocked_reason": "no_policy_match",
        }

    if not confirmed:
        event = {**audit_event, "blocked_reason": "missing_confirmation"}
        write_audit_event(event)
        service_ticket_id = maybe_create_service_ticket(event, "missing_confirmation")
        return {
            "status": "needs_confirmation",
            "tool_name": tool_name,
            "intent": intent,
            "policy_summary": policy_summary,
            "confirmation_prompt": confirmation_prompt,
            "result_text": "为避免误操作，本次写操作尚未执行。",
            "service_ticket_created": service_ticket_id is not None,
            "service_ticket_id": service_ticket_id,
            "executed": False,
            "requires_confirmation": requires_confirmation,
            "requires_human_review": bool(policy_summary.get("requires_human_review")),
            "policy_id": policy_summary.get("policy_id"),
            "blocked_reason": "missing_confirmation",
        }

    result = executor()
    event = {**audit_event, "executed": True, "result": result}
    write_audit_event(event)
    service_ticket_id = maybe_create_service_ticket(event, "executed_with_review_required")
    return {
        "status": "executed",
        "tool_name": tool_name,
        "intent": intent,
        "policy_summary": policy_summary,
        "confirmation_prompt": confirmation_prompt,
        "result_text": f"写操作执行结果：{result}",
        "service_ticket_created": service_ticket_id is not None,
        "service_ticket_id": service_ticket_id,
        "executed": True,
        "requires_confirmation": requires_confirmation,
        "requires_human_review": bool(policy_summary.get("requires_human_review")),
        "policy_id": policy_summary.get("policy_id"),
        "blocked_reason": None,
    }


def guarded_action(**kwargs) -> str:
    return format_guarded_result(guarded_action_structured(**kwargs))


@tool
def update_ticket_to_new_flight(
    ticket_no: str,
    new_flight_id: int,
    user_confirmation: Optional[str] = None,
    *,
    config: RunnableConfig,
) -> str:
    """受保护写工具：改签机票。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="update_ticket_to_new_flight",
        intent=f"将票号 {ticket_no} 改签到航班 {new_flight_id}",
        policy_query="机票在线改签规则 起飞前多久可以改签 改签后服务是否保留",
        service="flight",
        policy_type="change",
        confirmation_prompt=f"我将为您把票号 {ticket_no} 改签到航班 {new_flight_id}，是否确认？",
        user_confirmation=user_confirmation,
        config=config,
        executor=lambda: _update_ticket_to_new_flight_tool.func(
            ticket_no=ticket_no,
            new_flight_id=new_flight_id,
            config=config,
        ),
    )


@tool
def cancel_ticket(
    ticket_no: str,
    user_confirmation: Optional[str] = None,
    *,
    config: RunnableConfig,
) -> str:
    """受保护写工具：取消机票。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="cancel_ticket",
        intent=f"取消票号 {ticket_no}",
        policy_query="机票取消与退款规则 取消机票是否退款",
        service="flight",
        policy_type="refund",
        confirmation_prompt=f"我将为您取消票号 {ticket_no} 的机票，是否确认？",
        user_confirmation=user_confirmation,
        config=config,
        executor=lambda: _cancel_ticket_tool.func(ticket_no=ticket_no, config=config),
    )


@tool
def book_hotel(hotel_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：预订酒店。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="book_hotel",
        intent=f"预订酒店 {hotel_id}",
        policy_query="酒店预订 取消 修改 入住规则",
        service="hotel",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您预订酒店 {hotel_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _book_hotel_tool.func(hotel_id=hotel_id),
    )


@tool
def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
    user_confirmation: Optional[str] = None,
) -> str:
    """受保护写工具：修改酒店日期。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="update_hotel",
        intent=f"修改酒店 {hotel_id} 的入住/退房日期",
        policy_query="酒店修改入住日期 退房日期 修改规则",
        service="hotel",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您修改酒店 {hotel_id} 的入住或退房日期，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _update_hotel_tool.func(
            hotel_id=hotel_id,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
        ),
    )


@tool
def cancel_hotel(hotel_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：取消酒店。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="cancel_hotel",
        intent=f"取消酒店 {hotel_id}",
        policy_query="酒店取消 入住后取消 退款 人工处理",
        service="hotel",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您取消酒店 {hotel_id} 的预订，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _cancel_hotel_tool.func(hotel_id=hotel_id),
    )


@tool
def book_car_rental(rental_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：预订租车。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="book_car_rental",
        intent=f"预订租车 {rental_id}",
        policy_query="租车预订 取消 修改 证件规则",
        service="car_rental",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您预订租车服务 {rental_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _book_car_rental_tool.func(rental_id=rental_id),
    )


@tool
def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
    user_confirmation: Optional[str] = None,
) -> str:
    """受保护写工具：修改租车。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="update_car_rental",
        intent=f"修改租车 {rental_id}",
        policy_query="租车开始后修改 起租后修改 保险责任",
        service="car_rental",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您修改租车服务 {rental_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _update_car_rental_tool.func(
            rental_id=rental_id,
            start_date=start_date,
            end_date=end_date,
        ),
    )


@tool
def cancel_car_rental(rental_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：取消租车。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="cancel_car_rental",
        intent=f"取消租车 {rental_id}",
        policy_query="租车开始前取消 起租后取消 取消费",
        service="car_rental",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您取消租车服务 {rental_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _cancel_car_rental_tool.func(rental_id=rental_id),
    )


@tool
def book_excursion(recommendation_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：预订景点/行程。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="book_excursion",
        intent=f"预订景点/行程 {recommendation_id}",
        policy_query="景点行程预订 取消 改期 退款规则",
        service="excursion",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您预订景点/行程 {recommendation_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _book_excursion_tool.func(recommendation_id=recommendation_id),
    )


@tool
def update_excursion(
    recommendation_id: int,
    details: str,
    user_confirmation: Optional[str] = None,
) -> str:
    """受保护写工具：修改景点/行程。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="update_excursion",
        intent=f"修改景点/行程 {recommendation_id}",
        policy_query="景点行程改期 修改 供应商确认",
        service="excursion",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您修改景点/行程 {recommendation_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _update_excursion_tool.func(
            recommendation_id=recommendation_id,
            details=details,
        ),
    )


@tool
def cancel_excursion(recommendation_id: int, user_confirmation: Optional[str] = None) -> str:
    """受保护写工具：取消景点/行程。未传 user_confirmation=确认 时只返回确认提示，不执行。"""
    return guarded_action(
        tool_name="cancel_excursion",
        intent=f"取消景点/行程 {recommendation_id}",
        policy_query="景点活动取消 活动开始后退款 人工处理",
        service="excursion",
        policy_type="booking_policy",
        confirmation_prompt=f"我将为您取消景点/行程 {recommendation_id}，是否确认？",
        user_confirmation=user_confirmation,
        executor=lambda: _cancel_excursion_tool.func(recommendation_id=recommendation_id),
    )


def execute_guarded_action_structured(
    tool_name: str,
    arguments: dict[str, Any],
    user_confirmation: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> dict[str, Any]:
    """Execute a guarded write action and return the stable structured result."""
    args = dict(arguments)
    if tool_name == "update_ticket_to_new_flight":
        ticket_no = args["ticket_no"]
        new_flight_id = int(args["new_flight_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"将票号 {ticket_no} 改签到航班 {new_flight_id}",
            policy_query="机票在线改签规则 起飞前多久可以改签 改签后服务是否保留",
            service="flight",
            policy_type="change",
            confirmation_prompt=f"我将为您把票号 {ticket_no} 改签到航班 {new_flight_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _update_ticket_to_new_flight_tool.func(
                ticket_no=ticket_no,
                new_flight_id=new_flight_id,
                config=config,
            ),
        )
    if tool_name == "cancel_ticket":
        ticket_no = args["ticket_no"]
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"取消票号 {ticket_no}",
            policy_query="机票取消与退款规则 取消机票是否退款",
            service="flight",
            policy_type="refund",
            confirmation_prompt=f"我将为您取消票号 {ticket_no} 的机票，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _cancel_ticket_tool.func(ticket_no=ticket_no, config=config),
        )
    if tool_name == "book_hotel":
        hotel_id = int(args["hotel_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"预订酒店 {hotel_id}",
            policy_query="酒店预订 取消 修改 入住规则",
            service="hotel",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您预订酒店 {hotel_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _book_hotel_tool.func(hotel_id=hotel_id),
        )
    if tool_name == "update_hotel":
        hotel_id = int(args["hotel_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"修改酒店 {hotel_id} 的入住/退房日期",
            policy_query="酒店修改入住日期 退房日期 修改规则",
            service="hotel",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您修改酒店 {hotel_id} 的入住或退房日期，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _update_hotel_tool.func(
                hotel_id=hotel_id,
                checkin_date=args.get("checkin_date"),
                checkout_date=args.get("checkout_date"),
            ),
        )
    if tool_name == "cancel_hotel":
        hotel_id = int(args["hotel_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"取消酒店 {hotel_id}",
            policy_query="酒店取消 入住后取消 退款 人工处理",
            service="hotel",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您取消酒店 {hotel_id} 的预订，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _cancel_hotel_tool.func(hotel_id=hotel_id),
        )
    if tool_name == "book_car_rental":
        rental_id = int(args["rental_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"预订租车 {rental_id}",
            policy_query="租车预订 取消 修改 证件规则",
            service="car_rental",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您预订租车服务 {rental_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _book_car_rental_tool.func(rental_id=rental_id),
        )
    if tool_name == "update_car_rental":
        rental_id = int(args["rental_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"修改租车 {rental_id}",
            policy_query="租车开始后修改 起租后修改 保险责任",
            service="car_rental",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您修改租车服务 {rental_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _update_car_rental_tool.func(
                rental_id=rental_id,
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
            ),
        )
    if tool_name == "cancel_car_rental":
        rental_id = int(args["rental_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"取消租车 {rental_id}",
            policy_query="租车开始前取消 起租后取消 取消费",
            service="car_rental",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您取消租车服务 {rental_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _cancel_car_rental_tool.func(rental_id=rental_id),
        )
    if tool_name == "book_excursion":
        recommendation_id = int(args["recommendation_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"预订景点/行程 {recommendation_id}",
            policy_query="景点行程预订 取消 改期 退款规则",
            service="excursion",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您预订景点/行程 {recommendation_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _book_excursion_tool.func(recommendation_id=recommendation_id),
        )
    if tool_name == "update_excursion":
        recommendation_id = int(args["recommendation_id"])
        details = args["details"]
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"修改景点/行程 {recommendation_id}",
            policy_query="景点行程改期 修改 供应商确认",
            service="excursion",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您修改景点/行程 {recommendation_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _update_excursion_tool.func(
                recommendation_id=recommendation_id,
                details=details,
            ),
        )
    if tool_name == "cancel_excursion":
        recommendation_id = int(args["recommendation_id"])
        return guarded_action_structured(
            tool_name=tool_name,
            intent=f"取消景点/行程 {recommendation_id}",
            policy_query="景点活动取消 活动开始后退款 人工处理",
            service="excursion",
            policy_type="booking_policy",
            confirmation_prompt=f"我将为您取消景点/行程 {recommendation_id}，是否确认？",
            user_confirmation=user_confirmation,
            config=config,
            executor=lambda: _cancel_excursion_tool.func(recommendation_id=recommendation_id),
        )
    raise ValueError(f"Unknown guarded action: {tool_name}")
