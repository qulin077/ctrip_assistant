from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RouteHint:
    service: Optional[str] = None
    policy_type: Optional[str] = None
    primary_policy_id: Optional[str] = None
    is_multi_intent: bool = False


def infer_route_hint(query: str) -> RouteHint:
    text = query.lower()
    has_hotel = any(word in text for word in ["酒店", "入住", "退房", "房费", "房型", "no-show"])
    has_car = any(word in text for word in ["租车", "起租", "取车", "还车", "驾驶证", "驾照", "车辆"])
    has_excursion = any(word in text for word in ["景点", "行程推荐", "活动", "供应商", "迟到", "集合"])
    has_payment = any(word in text for word in ["支付", "信用卡", "3ds", "3-d", "secure", "安全码", "发票支付", "银行卡"])
    has_invoice = any(word in text for word in ["发票", "报销", "收据", "确认单", "电子票", "电子机票", "原件", "税"])
    has_refund = any(word in text for word in ["退票", "退款", "退钱", "全额退", "免费取消", "取消费", "退到"])
    has_change = any(word in text for word in ["改签", "改票", "换日期", "往后挪", "改到", "改航班"])
    has_platform = any(word in text for word in ["第三方", "旅行社", "团体", "app", "桌面", "个人资料", "找不到", "显示"])
    has_fare = any(word in text for word in ["舱位", "票价", "特价票", "普通票", "行李", "升级", "轻便"])

    intent_count = sum(
        bool(flag)
        for flag in [has_hotel, has_car, has_excursion, has_payment, has_invoice, has_refund, has_change, has_platform, has_fare]
    )
    is_multi_intent = intent_count >= 2 and any(word in text for word in ["再", "然后", "不行", "顺序", "两个", "先"])

    # More specific business domains take precedence over generic flight words.
    if has_hotel:
        return RouteHint("hotel", "booking_policy", "hotel_policy", is_multi_intent)
    if has_car:
        return RouteHint("car_rental", "booking_policy", "car_rental_policy", is_multi_intent)
    if has_excursion:
        return RouteHint("excursion", "booking_policy", "excursion_policy", is_multi_intent)
    if has_invoice:
        return RouteHint("flight", "invoice", "invoice_policy", is_multi_intent)
    if has_payment:
        return RouteHint("payment", "payment", "payment_policy", is_multi_intent)
    if has_platform:
        return RouteHint("booking", "platform", "booking_platform_policy", is_multi_intent)
    if has_refund:
        return RouteHint("flight", "refund", "refund_policy", is_multi_intent)
    if has_change:
        return RouteHint("flight", "change", "ticket_change_policy", is_multi_intent)
    if has_fare:
        return RouteHint("flight", "fare_rules", "fare_rules", is_multi_intent)
    return RouteHint(is_multi_intent=is_multi_intent)


def should_create_service_ticket(
    *,
    policy_summary: dict[str, Any],
    reason: str,
    intent: Optional[str] = None,
    query: Optional[str] = None,
) -> tuple[bool, str]:
    policy_id = policy_summary.get("policy_id")
    risk_level = policy_summary.get("risk_level")
    requires_human_review = bool(policy_summary.get("requires_human_review"))
    text = f"{intent or ''} {query or ''}".lower()

    if reason == "no_policy_match":
        return True, "no_policy_match"
    if policy_id in {"refund_policy", "invoice_policy"} and requires_human_review:
        return True, "policy_requires_human_review"
    if any(word in text for word in ["第三方", "旅行社", "团体"]):
        return True, "third_party_or_group_booking"
    if any(word in text for word in ["入住后", "已入住", "no-show", "起租后", "活动开始", "迟到", "全额退", "具体退款金额", "不行就取消"]):
        return True, "high_risk_customer_claim"
    if risk_level == "high" and any(word in text for word in ["取消", "退款", "改", "修改", "退"]):
        return True, "high_risk_policy"
    return False, "no_escalation_required"


def should_handoff_policy_question(query: str, top_match: dict[str, Any]) -> tuple[bool, str]:
    policy_summary = {
        "policy_id": top_match.get("policy_id"),
        "risk_level": top_match.get("risk_level"),
        "requires_human_review": top_match.get("requires_human_review"),
    }
    if bool(top_match.get("requires_human_review")):
        return True, "policy_requires_human_review"
    should_ticket, reason = should_create_service_ticket(
        policy_summary=policy_summary,
        reason="policy_question",
        query=query,
    )
    return should_ticket, reason
